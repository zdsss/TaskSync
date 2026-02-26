import json
import logging
import os
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, Response

from calendar_generator import generate_ics
from task_decomposer import decompose_task
import knowledge_store as ks
import task_store as ts
from knowledge_ai import analyze_entry
from knowledge_graph_ai import build_knowledge_graph
from skill_tree_ai import build_skill_tree
from validation_ai import validate_entries

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


@app.route("/api/generate-ics", methods=["POST"])
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
    filename = f"{safe_title}.ics"

    return Response(
        ics_bytes,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/calendar; charset=utf-8",
        },
    )


@app.route("/knowledge")
def knowledge_page():
    return render_template("knowledge.html")


@app.route("/api/knowledge/tags", methods=["GET"])
def api_knowledge_tags():
    return jsonify(ks.get_all_tags())


@app.route("/api/knowledge", methods=["GET"])
def api_knowledge_list():
    type_filter = request.args.get("type", "").strip() or None
    tag = request.args.get("tag", "").strip()
    tags = [tag] if tag else None
    q = request.args.get("q", "").strip() or None
    return jsonify(ks.list_entries(type_filter, tags, q))


@app.route("/api/knowledge", methods=["POST"])
def api_knowledge_create():
    data = request.get_json(force=True)
    if not data.get("title", "").strip():
        return jsonify({"error": "title is required"}), 400
    if not data.get("type", "").strip():
        return jsonify({"error": "type is required"}), 400
    entry = ks.create_entry(data)
    return jsonify(entry), 201


@app.route("/api/knowledge/<entry_id>", methods=["PUT"])
def api_knowledge_update(entry_id):
    data = request.get_json(force=True)
    entry = ks.update_entry(entry_id, data)
    if entry is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(entry)


@app.route("/api/knowledge/<entry_id>", methods=["DELETE"])
def api_knowledge_delete(entry_id):
    if not ks.delete_entry(entry_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/knowledge/export", methods=["GET"])
def api_knowledge_export():
    data = ks._load()
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": 'attachment; filename="knowledge_backup.json"'},
    )


@app.route("/api/knowledge/import", methods=["POST"])
def api_knowledge_import():
    mode = request.args.get("mode", "merge")
    if mode not in ("merge", "replace"):
        return jsonify({"error": "mode must be merge or replace"}), 400
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "file is required"}), 400
    try:
        raw = json.loads(f.read().decode("utf-8"))
    except Exception:
        return jsonify({"error": "Invalid JSON file"}), 400
    entries = raw.get("entries", raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return jsonify({"error": "Invalid format: expected entries list"}), 400
    result = ks.import_entries(entries, mode)
    return jsonify(result)


@app.route("/api/knowledge/analyze", methods=["POST"])
def api_knowledge_analyze():
    data = request.get_json(force=True)
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()

    if not api_key:
        return jsonify({"error": "api_key is required"}), 400
    if not title and not content:
        return jsonify({"error": "title or content is required"}), 400

    try:
        result = analyze_entry(api_key, base_url, model, title, content)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


# ── Knowledge Graph ────────────────────────────────────────────────────────────

@app.route("/knowledge/graph")
def knowledge_graph_page():
    return render_template("knowledge_graph.html")


@app.route("/api/knowledge/graph/build", methods=["POST"])
def api_graph_build():
    data = request.get_json(force=True)
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"
    if not api_key:
        return jsonify({"error": "api_key is required"}), 400
    entries = ks.list_entries()
    if not entries:
        return jsonify({"error": "知识库为空，请先添加条目"}), 400
    try:
        graph = build_knowledge_graph(api_key, base_url, model, entries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    ks.save_graph(graph)
    return jsonify(graph)


@app.route("/api/knowledge/graph", methods=["GET"])
def api_graph_get():
    return jsonify(ks.load_graph())


# ── Skill Tree ─────────────────────────────────────────────────────────────────

@app.route("/knowledge/skills")
def knowledge_skills_page():
    return render_template("skill_tree.html")


@app.route("/api/knowledge/skill-tree/build", methods=["POST"])
def api_skill_tree_build():
    data = request.get_json(force=True)
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"
    if not api_key:
        return jsonify({"error": "api_key is required"}), 400
    entries = ks.list_entries()
    if not entries:
        return jsonify({"error": "知识库为空，请先添加条目"}), 400
    try:
        tree = build_skill_tree(api_key, base_url, model, entries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    ks.save_skill_tree(tree)
    return jsonify(tree)


@app.route("/api/knowledge/skill-tree", methods=["GET"])
def api_skill_tree_get():
    return jsonify(ks.load_skill_tree())


# ── Validation ─────────────────────────────────────────────────────────────────

@app.route("/knowledge/validate")
def knowledge_validate_page():
    return render_template("validation.html")


@app.route("/api/knowledge/validate/run", methods=["POST"])
def api_validate_run():
    data = request.get_json(force=True)
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"
    entry_ids = data.get("entry_ids", [])
    if not api_key:
        return jsonify({"error": "api_key is required"}), 400
    if not entry_ids:
        return jsonify({"error": "entry_ids is required"}), 400
    entries = [ks.get_entry(eid) for eid in entry_ids]
    entries = [e for e in entries if e]
    if not entries:
        return jsonify({"error": "No valid entries found"}), 400
    try:
        new_results = validate_entries(api_key, base_url, model, entries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    # Merge into existing validation results
    store = ks.load_validation()
    existing_ids = {r["entry_id"] for r in store["results"]}
    for r in new_results:
        if r["entry_id"] in existing_ids:
            store["results"] = [r if x["entry_id"] == r["entry_id"] else x for x in store["results"]]
        else:
            store["results"].append(r)
    store["last_run_at"] = datetime.now(timezone.utc).isoformat()
    ks.save_validation(store)
    return jsonify({"results": new_results})


@app.route("/api/knowledge/validate/results", methods=["GET"])
def api_validate_results():
    return jsonify(ks.load_validation())


@app.route("/api/knowledge/validate/decide", methods=["POST"])
def api_validate_decide():
    data = request.get_json(force=True)
    result_id = data.get("result_id", "").strip()
    decision = data.get("decision", "").strip()
    if decision not in ("approve", "reject", "undo"):
        return jsonify({"error": "decision must be approve, reject, or undo"}), 400
    store = ks.load_validation()
    target = next((r for r in store["results"] if r["id"] == result_id), None)
    if not target:
        return jsonify({"error": "result not found"}), 404
    if decision == "approve":
        correction = target.get("suggested_correction")
        if correction:
            current = ks.get_entry(target["entry_id"])
            if current:
                target["original_content"] = current.get("content", "")
            ks.apply_correction(target["entry_id"], correction)
        target["status"] = "applied"
    elif decision == "undo":
        original = target.get("original_content")
        if original is not None:
            ks.apply_correction(target["entry_id"], original)
        target["status"] = "pending_review"
        target.pop("original_content", None)
    else:
        target["status"] = "rejected"
    ks.save_validation(store)
    return jsonify(target)




# ── Tasks ──────────────────────────────────────────────────────────────────────

@app.route("/tasks/<task_id>")
def task_detail_page(task_id):
    return render_template("task_detail.html")


@app.route("/insights")
def insights_page():
    return render_template("insights.html")


@app.route("/api/tasks", methods=["GET"])
def api_tasks_list():
    return jsonify(ts.list_tasks())


@app.route("/api/tasks", methods=["POST"])
def api_tasks_create():
    data = request.get_json(force=True)
    if not data.get("title", "").strip():
        return jsonify({"error": "title is required"}), 400
    task = ts.create_task(data)
    return jsonify(task), 201


@app.route("/api/tasks/<task_id>", methods=["GET"])
def api_tasks_get(task_id):
    task = ts.get_task(task_id)
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@app.route("/api/tasks/<task_id>", methods=["PUT"])
def api_tasks_update(task_id):
    data = request.get_json(force=True)
    task = ts.update_task(task_id, data)
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_tasks_delete(task_id):
    if not ts.delete_task(task_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/tasks/<task_id>/subtasks/<subtask_id>", methods=["PATCH"])
def api_subtask_update(task_id, subtask_id):
    data = request.get_json(force=True)
    st = ts.update_subtask(task_id, subtask_id, data)
    if st is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(st)


@app.route("/api/tasks/<task_id>/complete", methods=["POST"])
def api_task_complete(task_id):
    now = datetime.now(timezone.utc).isoformat()
    task = ts.update_task(task_id, {"status": "done", "completed_at": now})
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@app.route("/api/tasks/<task_id>/knowledge", methods=["GET"])
def api_task_knowledge(task_id):
    return jsonify(ks.list_entries(source_task_id=task_id))


@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(ts.get_stats())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)