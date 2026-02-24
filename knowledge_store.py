import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
KNOWLEDGE_FILE = DATA_DIR / "knowledge.json"


def _load() -> dict:
    if not KNOWLEDGE_FILE.exists():
        return {"version": 1, "entries": []}
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = KNOWLEDGE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(KNOWLEDGE_FILE)


def list_entries(type_filter=None, tags=None, q=None) -> list:
    data = _load()
    entries = data["entries"]

    if type_filter:
        entries = [e for e in entries if e.get("type") == type_filter]

    if tags:
        tag_set = set(t.lower() for t in tags)
        entries = [e for e in entries if tag_set.intersection(t.lower() for t in e.get("tags", []))]

    if q:
        q_lower = q.lower()
        entries = [
            e for e in entries
            if q_lower in e.get("title", "").lower()
            or q_lower in e.get("content", "").lower()
            or q_lower in e.get("summary", "").lower()
            or any(q_lower in t.lower() for t in e.get("tags", []))
        ]

    return sorted(entries, key=lambda e: e.get("created_at", ""), reverse=True)


def get_entry(entry_id: str) -> dict | None:
    data = _load()
    for e in data["entries"]:
        if e["id"] == entry_id:
            return e
    return None


def create_entry(entry: dict) -> dict:
    data = _load()
    entry_id = f"ke_{int(time.time() * 1000)}"
    now = datetime.now(timezone.utc).isoformat()
    entry["id"] = entry_id
    entry.setdefault("created_at", now)
    entry.setdefault("updated_at", now)
    entry.setdefault("tags", [])
    entry.setdefault("summary", "")
    entry.setdefault("source_url", "")
    data["entries"].append(entry)
    _save(data)
    return entry


def update_entry(entry_id: str, updates: dict) -> dict | None:
    data = _load()
    for e in data["entries"]:
        if e["id"] == entry_id:
            updates.pop("id", None)
            updates.pop("created_at", None)
            e.update(updates)
            e["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save(data)
            return e
    return None


def delete_entry(entry_id: str) -> bool:
    data = _load()
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    if len(data["entries"]) < before:
        _save(data)
        return True
    return False


def import_entries(entries: list, mode: str = "merge") -> dict:
    data = _load()
    existing_ids = {e["id"] for e in data["entries"]}
    added = 0
    skipped = 0
    for entry in entries:
        eid = entry.get("id")
        if mode == "replace" and eid and eid in existing_ids:
            data["entries"] = [entry if e["id"] == eid else e for e in data["entries"]]
            added += 1
        elif eid and eid in existing_ids:
            skipped += 1
        else:
            data["entries"].append(entry)
            existing_ids.add(eid)
            added += 1
    _save(data)
    return {"added": added, "skipped": skipped}


def get_all_tags() -> list:
    data = _load()
    freq: dict[str, int] = {}
    for e in data["entries"]:
        for t in e.get("tags", []):
            freq[t] = freq.get(t, 0) + 1
    return sorted([{"tag": t, "count": c} for t, c in freq.items()], key=lambda x: -x["count"])


# ── Knowledge Graph ────────────────────────────────────────────────────────────

GRAPH_FILE = DATA_DIR / "knowledge_graph.json"


def load_graph() -> dict:
    if not GRAPH_FILE.exists():
        return {"version": 1, "clusters": [], "relationships": []}
    with open(GRAPH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_graph(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = GRAPH_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(GRAPH_FILE)


# ── Skill Tree ─────────────────────────────────────────────────────────────────

SKILL_TREE_FILE = DATA_DIR / "skill_tree.json"


def load_skill_tree() -> dict:
    if not SKILL_TREE_FILE.exists():
        return {"version": 1, "skills": []}
    with open(SKILL_TREE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_skill_tree(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SKILL_TREE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(SKILL_TREE_FILE)


# ── Validation ─────────────────────────────────────────────────────────────────

VALIDATION_FILE = DATA_DIR / "validation_results.json"


def load_validation() -> dict:
    if not VALIDATION_FILE.exists():
        return {"version": 1, "results": []}
    with open(VALIDATION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_validation(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = VALIDATION_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(VALIDATION_FILE)


def apply_correction(entry_id: str, new_content: str) -> dict | None:
    return update_entry(entry_id, {"content": new_content})
