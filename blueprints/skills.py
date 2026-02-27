from flask import Blueprint, jsonify, request

import stores.knowledge_store as ks
from ai.skill_tree_ai import build_skill_tree

bp = Blueprint("skills", __name__)


@bp.route("/knowledge/skills")
def knowledge_skills_page():
    from flask import render_template
    return render_template("skill_tree.html")


@bp.route("/api/knowledge/skill-tree/build", methods=["POST"])
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


@bp.route("/api/knowledge/skill-tree", methods=["GET"])
def api_skill_tree_get():
    return jsonify(ks.load_skill_tree())
