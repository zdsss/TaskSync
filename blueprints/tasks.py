import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, Response

from calendar_generator import generate_ics
from ai.task_decomposer import decompose_task
import stores.task_store as ts
import stores.knowledge_store as ks

bp = Blueprint("tasks", __name__)


@bp.route("/")
def index():
    from flask import render_template
    return render_template("index.html")


@bp.route("/tasks/<task_id>")
def task_detail_page(task_id):
    from flask import render_template
    return render_template("task_detail.html")


@bp.route("/insights")
def insights_page():
    from flask import render_template
    return render_template("insights.html")


@bp.route("/api/tasks", methods=["GET"])
def api_tasks_list():
    return jsonify(ts.list_tasks())


@bp.route("/api/tasks", methods=["POST"])
def api_tasks_create():
    data = request.get_json(force=True)
    if not data.get("title", "").strip():
        return jsonify({"error": "title is required"}), 400
    task = ts.create_task(data)
    return jsonify(task), 201


@bp.route("/api/tasks/<task_id>", methods=["GET"])
def api_tasks_get(task_id):
    task = ts.get_task(task_id)
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@bp.route("/api/tasks/<task_id>", methods=["PUT"])
def api_tasks_update(task_id):
    data = request.get_json(force=True)
    task = ts.update_task(task_id, data)
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@bp.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_tasks_delete(task_id):
    if not ts.delete_task(task_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@bp.route("/api/tasks/<task_id>/subtasks", methods=["POST"])
def api_subtask_create(task_id):
    data = request.get_json(force=True)
    if not data.get("title", "").strip():
        return jsonify({"error": "title is required"}), 400
    st = ts.create_subtask(task_id, data)
    if st is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(st), 201


@bp.route("/api/tasks/<task_id>/subtasks/<subtask_id>", methods=["PATCH"])
def api_subtask_update(task_id, subtask_id):
    data = request.get_json(force=True)
    st = ts.update_subtask(task_id, subtask_id, data)
    if st is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(st)


@bp.route("/api/tasks/<task_id>/complete", methods=["POST"])
def api_task_complete(task_id):
    now = datetime.now(timezone.utc).isoformat()
    task = ts.update_task(task_id, {"status": "done", "completed_at": now})
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@bp.route("/api/tasks/<task_id>/knowledge", methods=["GET"])
def api_task_knowledge(task_id):
    return jsonify(ks.list_entries(source_task_id=task_id))


@bp.route("/api/stats", methods=["GET"])
def api_stats():
    stats = ts.get_task_stats()
    month_start_iso = stats.pop("_month_start_iso")
    stats["new_knowledge_entries_this_month"] = ks.get_knowledge_stats(month_start_iso)
    return jsonify(stats)


@bp.route("/api/decompose", methods=["POST"])
def api_decompose():
    data = request.get_json(force=True)
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"
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
        subtasks = decompose_task(api_key, base_url, model, task, weeks, start_date, daily_slots)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"subtasks": subtasks})


@bp.route("/api/generate-ics", methods=["POST"])
def api_generate_ics():
    data = request.get_json(force=True)
    subtasks = data.get("subtasks", [])
    start_date_str = data.get("start_date", "")
    daily_slots = data.get("daily_slots", ["09:00"])
    task_title = data.get("task_title", "My Tasks")

    if not subtasks:
        return jsonify({"error": "subtasks are required"}), 400

    _SLOT_RE = re.compile(r"^\d{2}:\d{2}$")
    for slot in daily_slots:
        if not _SLOT_RE.match(str(slot)):
            return jsonify({"error": f"Invalid time slot format: {slot}"}), 400
        h, m = int(slot[:2]), int(slot[3:])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return jsonify({"error": f"Time slot out of range: {slot}"}), 400

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid start_date format, expected YYYY-MM-DD"}), 400

    try:
        ics_bytes = generate_ics(subtasks, start_date, daily_slots, task_title)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_title)
    return Response(
        ics_bytes,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_title}.ics"',
            "Content-Type": "text/calendar; charset=utf-8",
        },
    )
