from flask import Blueprint, jsonify, request

import stores.knowledge_store as ks
from ai.knowledge_graph_ai import build_knowledge_graph

bp = Blueprint("graph", __name__)


@bp.route("/knowledge/graph")
def knowledge_graph_page():
    from flask import render_template
    return render_template("knowledge_graph.html")


@bp.route("/api/knowledge/graph/build", methods=["POST"])
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


@bp.route("/api/knowledge/graph", methods=["GET"])
def api_graph_get():
    return jsonify(ks.load_graph())
