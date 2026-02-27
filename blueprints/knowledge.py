import json

from flask import Blueprint, jsonify, request, Response

import stores.knowledge_store as ks
from ai.knowledge_ai import analyze_entry

bp = Blueprint("knowledge", __name__)


@bp.route("/knowledge")
def knowledge_page():
    from flask import render_template
    return render_template("knowledge.html")


@bp.route("/api/knowledge/tags", methods=["GET"])
def api_knowledge_tags():
    return jsonify(ks.get_all_tags())


@bp.route("/api/knowledge", methods=["GET"])
def api_knowledge_list():
    type_filter = request.args.get("type", "").strip() or None
    tags = request.args.getlist("tag") or None
    q = request.args.get("q", "").strip() or None
    return jsonify(ks.list_entries(type_filter, tags, q))


@bp.route("/api/knowledge", methods=["POST"])
def api_knowledge_create():
    data = request.get_json(force=True)
    if not data.get("title", "").strip():
        return jsonify({"error": "title is required"}), 400
    if not data.get("type", "").strip():
        return jsonify({"error": "type is required"}), 400
    entry = ks.create_entry(data)
    return jsonify(entry), 201


@bp.route("/api/knowledge/<entry_id>", methods=["PUT"])
def api_knowledge_update(entry_id):
    data = request.get_json(force=True)
    entry = ks.update_entry(entry_id, data)
    if entry is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(entry)


@bp.route("/api/knowledge/<entry_id>", methods=["DELETE"])
def api_knowledge_delete(entry_id):
    if not ks.delete_entry(entry_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@bp.route("/api/knowledge/bulk-delete", methods=["POST"])
def api_knowledge_bulk_delete():
    ids = request.json.get("ids", [])
    deleted = ks.bulk_delete(ids)
    return jsonify({"deleted": deleted})


@bp.route("/api/knowledge/bulk-export", methods=["POST"])
def api_knowledge_bulk_export():
    ids = set(request.json.get("ids", []))
    data = ks._load()
    subset = [e for e in data["entries"] if e["id"] in ids]
    payload = {"entries": subset}
    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(json_bytes, mimetype="application/json",
                    headers={"Content-Disposition": 'attachment; filename="knowledge_export.json"'})


@bp.route("/api/knowledge/export", methods=["GET"])
def api_knowledge_export():
    data = ks._load()
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": 'attachment; filename="knowledge_backup.json"'},
    )


@bp.route("/api/knowledge/import", methods=["POST"])
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


@bp.route("/api/knowledge/analyze", methods=["POST"])
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
