import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "tasksync.db"


def _get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                source_task_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entry_tags (
                entry_id TEXT NOT NULL REFERENCES knowledge_entries(id) ON DELETE CASCADE,
                tag TEXT NOT NULL,
                PRIMARY KEY (entry_id, tag)
            );

            CREATE TABLE IF NOT EXISTS blobs (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ke_type ON knowledge_entries(type, created_at);
            CREATE INDEX IF NOT EXISTS idx_ke_source_task ON knowledge_entries(source_task_id);
            CREATE INDEX IF NOT EXISTS idx_entry_tags_tag ON entry_tags(tag);
        """)
    conn.close()


def _get_tags(conn, entry_id: str) -> list:
    rows = conn.execute(
        "SELECT tag FROM entry_tags WHERE entry_id=? ORDER BY tag",
        (entry_id,)
    ).fetchall()
    return [r["tag"] for r in rows]


def _row_to_entry(row, tags) -> dict:
    entry = dict(row)
    entry["tags"] = tags
    return entry


def list_entries(type_filter=None, tags=None, q=None, source_task_id=None) -> list:
    conn = _get_conn()
    try:
        where = []
        params = []

        if type_filter:
            where.append("ke.type=?")
            params.append(type_filter)

        if source_task_id:
            where.append("ke.source_task_id=?")
            params.append(source_task_id)

        if q:
            where.append("(ke.title LIKE ? OR ke.content LIKE ? OR ke.summary LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like, like])

        if tags:
            placeholders = ",".join("?" * len(tags))
            where.append(
                f"EXISTS (SELECT 1 FROM entry_tags et WHERE et.entry_id=ke.id AND et.tag IN ({placeholders}))"
            )
            params.extend(tags)

        sql = "SELECT ke.* FROM knowledge_entries ke"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ke.created_at DESC"

        rows = conn.execute(sql, params).fetchall()

        if tags and len(tags) > 1:
            tag_set = set(t.lower() for t in tags)
            result = []
            for row in rows:
                entry_tags = set(t.lower() for t in _get_tags(conn, row["id"]))
                if tag_set.issubset(entry_tags):
                    result.append(_row_to_entry(row, _get_tags(conn, row["id"])))
            return result

        return [_row_to_entry(row, _get_tags(conn, row["id"])) for row in rows]
    finally:
        conn.close()


def get_entry(entry_id: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_entries WHERE id=?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_entry(row, _get_tags(conn, entry_id))
    finally:
        conn.close()


def create_entry(entry: dict) -> dict:
    entry_id = f"ke_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    entry["id"] = entry_id
    entry.setdefault("created_at", now)
    entry.setdefault("updated_at", now)
    entry.setdefault("tags", [])
    entry.setdefault("summary", "")
    entry.setdefault("source_url", "")

    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                """INSERT INTO knowledge_entries
                   (id, type, title, content, summary, source_url, source_task_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry["id"],
                    entry.get("type", ""),
                    entry.get("title", ""),
                    entry.get("content", ""),
                    entry.get("summary", ""),
                    entry.get("source_url", ""),
                    entry.get("source_task_id"),
                    entry["created_at"],
                    entry["updated_at"],
                )
            )
            for tag in entry.get("tags", []):
                conn.execute(
                    "INSERT OR IGNORE INTO entry_tags (entry_id, tag) VALUES (?, ?)",
                    (entry_id, tag)
                )
    finally:
        conn.close()

    return entry


def update_entry(entry_id: str, updates: dict) -> dict | None:
    updates.pop("id", None)
    updates.pop("created_at", None)

    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_entries WHERE id=?", (entry_id,)
        ).fetchone()
        if row is None:
            return None

        allowed = {"type", "title", "content", "summary", "source_url", "source_task_id"}
        set_parts = ["updated_at=?"]
        values = [datetime.now(timezone.utc).isoformat()]

        for k, v in updates.items():
            if k in allowed:
                set_parts.append(f"{k}=?")
                values.append(v)

        values.append(entry_id)
        with conn:
            conn.execute(
                f"UPDATE knowledge_entries SET {', '.join(set_parts)} WHERE id=?",
                values
            )
            if "tags" in updates:
                conn.execute("DELETE FROM entry_tags WHERE entry_id=?", (entry_id,))
                for tag in updates["tags"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO entry_tags (entry_id, tag) VALUES (?, ?)",
                        (entry_id, tag)
                    )

        updated = conn.execute(
            "SELECT * FROM knowledge_entries WHERE id=?", (entry_id,)
        ).fetchone()
        return _row_to_entry(updated, _get_tags(conn, entry_id))
    finally:
        conn.close()


def delete_entry(entry_id: str) -> bool:
    conn = _get_conn()
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM knowledge_entries WHERE id=?", (entry_id,)
            )
        return cur.rowcount > 0
    finally:
        conn.close()


def bulk_delete(ids: list) -> int:
    if not ids:
        return 0
    conn = _get_conn()
    try:
        placeholders = ",".join("?" * len(ids))
        with conn:
            cur = conn.execute(
                f"DELETE FROM knowledge_entries WHERE id IN ({placeholders})", ids
            )
        return cur.rowcount
    finally:
        conn.close()


def _insert_entry(conn, entry: dict):
    now = datetime.now(timezone.utc).isoformat()
    entry_id = entry.get("id") or f"ke_{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT OR REPLACE INTO knowledge_entries
           (id, type, title, content, summary, source_url, source_task_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry_id,
            entry.get("type", ""),
            entry.get("title", ""),
            entry.get("content", ""),
            entry.get("summary", ""),
            entry.get("source_url", ""),
            entry.get("source_task_id"),
            entry.get("created_at", now),
            entry.get("updated_at", now),
        )
    )
    conn.execute("DELETE FROM entry_tags WHERE entry_id=?", (entry_id,))
    for tag in entry.get("tags", []):
        conn.execute(
            "INSERT OR IGNORE INTO entry_tags (entry_id, tag) VALUES (?, ?)",
            (entry_id, tag)
        )


def import_entries(entries: list, mode: str = "merge") -> dict:
    conn = _get_conn()
    try:
        existing_ids = {
            r["id"] for r in conn.execute("SELECT id FROM knowledge_entries").fetchall()
        }
        added = 0
        skipped = 0
        for entry in entries:
            eid = entry.get("id")
            if mode == "replace" and eid and eid in existing_ids:
                with conn:
                    _insert_entry(conn, entry)
                added += 1
            elif eid and eid in existing_ids:
                skipped += 1
            else:
                with conn:
                    _insert_entry(conn, entry)
                if eid:
                    existing_ids.add(eid)
                added += 1
        return {"added": added, "skipped": skipped}
    finally:
        conn.close()


def get_all_tags() -> list:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT tag, COUNT(*) as count FROM entry_tags GROUP BY tag ORDER BY count DESC"
        ).fetchall()
        return [{"tag": r["tag"], "count": r["count"]} for r in rows]
    finally:
        conn.close()


def _load() -> dict:
    """Compatibility shim used by app.py bulk export routes."""
    return {"version": 1, "entries": list_entries()}


# ── Knowledge Graph ────────────────────────────────────────────────────────────

def load_graph() -> dict:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT data FROM blobs WHERE key='graph'").fetchone()
        if row is None:
            return {"version": 1, "clusters": [], "relationships": []}
        return json.loads(row["data"])
    finally:
        conn.close()


def save_graph(data: dict):
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO blobs (key, data, updated_at) VALUES ('graph', ?, ?)",
                (json.dumps(data, ensure_ascii=False), now)
            )
    finally:
        conn.close()


# ── Skill Tree ─────────────────────────────────────────────────────────────────

def load_skill_tree() -> dict:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT data FROM blobs WHERE key='skill_tree'").fetchone()
        if row is None:
            return {"version": 1, "skills": []}
        return json.loads(row["data"])
    finally:
        conn.close()


def save_skill_tree(data: dict):
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO blobs (key, data, updated_at) VALUES ('skill_tree', ?, ?)",
                (json.dumps(data, ensure_ascii=False), now)
            )
    finally:
        conn.close()


# ── Validation ─────────────────────────────────────────────────────────────────

def load_validation() -> dict:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT data FROM blobs WHERE key='validation'").fetchone()
        if row is None:
            return {"version": 1, "results": []}
        return json.loads(row["data"])
    finally:
        conn.close()


def save_validation(data: dict):
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO blobs (key, data, updated_at) VALUES ('validation', ?, ?)",
                (json.dumps(data, ensure_ascii=False), now)
            )
    finally:
        conn.close()


def apply_correction(entry_id: str, new_content: str) -> dict | None:
    return update_entry(entry_id, {"content": new_content})
