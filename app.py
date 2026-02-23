import logging
import os
from datetime import datetime

from flask import Flask, jsonify, render_template, request, Response

from calendar_generator import generate_ics
from task_decomposer import decompose_task

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# Suppress werkzeug request body logging
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/decompose", methods=["POST"])
def api_decompose():
    data = request.get_json(force=True)

    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    task = data.get("task", "").strip()
    weeks = int(data.get("weeks", 1))
    start_date_str = data.get("start_date", "")
    daily_slots = data.get("daily_slots", ["09:00"])

    if not api_key or not task:
        return jsonify({"error": "api_key and task are required"}), 400

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid start_date format, expected YYYY-MM-DD"}), 400

    try:
        subtasks = decompose_task(api_key, base_url, task, weeks, start_date, daily_slots)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"subtasks": subtasks})


@app.route("/api/generate-ics", methods=["POST"])
def api_generate_ics():
    data = request.get_json(force=True)

    subtasks = data.get("subtasks", [])
    start_date_str = data.get("start_date", "")
    daily_slots = data.get("daily_slots", ["09:00"])
    task_title = data.get("task_title", "My Tasks")

    if not subtasks:
        return jsonify({"error": "subtasks are required"}), 400

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid start_date format, expected YYYY-MM-DD"}), 400

    try:
        ics_bytes = generate_ics(subtasks, start_date, daily_slots, task_title)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_title)
    filename = f"{safe_title}.ics"

    return Response(
        ics_bytes,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/calendar; charset=utf-8",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
