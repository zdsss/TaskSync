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
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                weeks INTEGER DEFAULT 1,
                start_date TEXT,
                daily_slots TEXT NOT NULL DEFAULT '["09:00"]',
                status TEXT NOT NULL DEFAULT 'in_progress',
                created_at TEXT NOT NULL,
                completed_at TEXT,
                reflection TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS subtasks (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                duration_minutes INTEGER DEFAULT 30,
                suggested_day_offset INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                completed_at TEXT,
                scheduled_at TEXT,
                sort_order INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_subtasks_task_id ON subtasks(task_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, created_at);
        """)
    conn.close()


def _row_to_subtask(row) -> dict:
    return dict(row)


def _row_to_task(row, subtask_rows) -> dict:
    task = dict(row)
    task["daily_slots"] = json.loads(task["daily_slots"])
    task["subtasks"] = [_row_to_subtask(st) for st in subtask_rows]
    return task


def list_tasks() -> list:
    conn = _get_conn()
    try:
        tasks = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for t in tasks:
            subtasks = conn.execute(
                "SELECT * FROM subtasks WHERE task_id=? ORDER BY sort_order",
                (t["id"],)
            ).fetchall()
            result.append(_row_to_task(t, subtasks))
        return result
    finally:
        conn.close()


def get_task(task_id: str) -> dict | None:
    conn = _get_conn()
    try:
        t = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if t is None:
            return None
        subtasks = conn.execute(
            "SELECT * FROM subtasks WHERE task_id=? ORDER BY sort_order",
            (task_id,)
        ).fetchall()
        return _row_to_task(t, subtasks)
    finally:
        conn.close()


def create_task(task_data: dict) -> dict:
    task_id = f"tk_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    task_data["id"] = task_id
    task_data.setdefault("created_at", now)
    task_data.setdefault("status", "in_progress")
    task_data.setdefault("completed_at", None)
    task_data.setdefault("reflection", "")

    daily_slots = task_data.get("daily_slots", ["09:00"])
    daily_slots_json = json.dumps(daily_slots) if isinstance(daily_slots, list) else daily_slots

    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                """INSERT INTO tasks
                   (id, title, weeks, start_date, daily_slots, status, created_at, completed_at, reflection)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_data["id"],
                    task_data.get("title", ""),
                    task_data.get("weeks", 1),
                    task_data.get("start_date"),
                    daily_slots_json,
                    task_data["status"],
                    task_data["created_at"],
                    task_data.get("completed_at"),
                    task_data.get("reflection", ""),
                )
            )
            subtasks = task_data.get("subtasks", [])
            for idx, st in enumerate(subtasks):
                if not st.get("id"):
                    st["id"] = f"st_{uuid.uuid4().hex[:8]}"
                st.setdefault("status", "pending")
                st.setdefault("completed_at", None)
                st.setdefault("scheduled_at", None)
                conn.execute(
                    """INSERT INTO subtasks
                       (id, task_id, title, description, duration_minutes,
                        suggested_day_offset, status, completed_at, scheduled_at, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        st["id"],
                        task_id,
                        st.get("title", ""),
                        st.get("description", ""),
                        st.get("duration_minutes", 30),
                        st.get("suggested_day_offset", 0),
                        st["status"],
                        st.get("completed_at"),
                        st.get("scheduled_at"),
                        idx,
                    )
                )
    finally:
        conn.close()

    task_data["daily_slots"] = json.loads(daily_slots_json)
    return task_data


def update_task(task_id: str, updates: dict) -> dict | None:
    updates.pop("id", None)
    updates.pop("created_at", None)

    conn = _get_conn()
    try:
        t = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if t is None:
            return None

        allowed = {"title", "weeks", "start_date", "daily_slots", "status", "completed_at", "reflection"}
        set_parts = []
        values = []
        for k, v in updates.items():
            if k in allowed:
                if k == "daily_slots" and isinstance(v, list):
                    v = json.dumps(v)
                set_parts.append(f"{k}=?")
                values.append(v)

        if set_parts:
            values.append(task_id)
            with conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(set_parts)} WHERE id=?",
                    values
                )

        subtasks = conn.execute(
            "SELECT * FROM subtasks WHERE task_id=? ORDER BY sort_order",
            (task_id,)
        ).fetchall()
        updated_t = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return _row_to_task(updated_t, subtasks)
    finally:
        conn.close()


def delete_task(task_id: str) -> bool:
    conn = _get_conn()
    try:
        with conn:
            cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        return cur.rowcount > 0
    finally:
        conn.close()


def create_subtask(task_id: str, data: dict) -> dict | None:
    conn = _get_conn()
    try:
        if conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone() is None:
            return None
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM subtasks WHERE task_id=?",
            (task_id,)
        ).fetchone()[0]
        st_id = f"st_{uuid.uuid4().hex[:8]}"
        with conn:
            conn.execute(
                """INSERT INTO subtasks
                   (id, task_id, title, description, duration_minutes,
                    suggested_day_offset, status, completed_at, scheduled_at, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?)""",
                (
                    st_id, task_id,
                    data.get("title", ""),
                    data.get("description", ""),
                    data.get("duration_minutes", 30),
                    data.get("suggested_day_offset", 0),
                    data.get("scheduled_at"),
                    max_order + 1,
                )
            )
        return _row_to_subtask(conn.execute(
            "SELECT * FROM subtasks WHERE id=?", (st_id,)
        ).fetchone())
    finally:
        conn.close()


def update_subtask(task_id: str, subtask_id: str, updates: dict) -> dict | None:
    updates.pop("id", None)
    updates.pop("task_id", None)

    conn = _get_conn()
    try:
        st = conn.execute(
            "SELECT * FROM subtasks WHERE id=? AND task_id=?",
            (subtask_id, task_id)
        ).fetchone()
        if st is None:
            return None

        allowed = {
            "title", "description", "duration_minutes", "suggested_day_offset",
            "status", "completed_at", "scheduled_at", "sort_order"
        }
        set_parts = []
        values = []
        for k, v in updates.items():
            if k in allowed:
                set_parts.append(f"{k}=?")
                values.append(v)

        if set_parts:
            values.extend([subtask_id, task_id])
            with conn:
                conn.execute(
                    f"UPDATE subtasks SET {', '.join(set_parts)} WHERE id=? AND task_id=?",
                    values
                )

        updated_st = conn.execute(
            "SELECT * FROM subtasks WHERE id=? AND task_id=?",
            (subtask_id, task_id)
        ).fetchone()
        return _row_to_subtask(updated_st)
    finally:
        conn.close()


def get_stats() -> dict:
    import knowledge_store as ks
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc)
        month_start_iso = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

        completed_this_month = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='done' AND completed_at >= ?",
            (month_start_iso,)
        ).fetchone()[0]

        total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        total_subtasks = conn.execute("SELECT COUNT(*) FROM subtasks").fetchone()[0]
        done_subtasks = conn.execute(
            "SELECT COUNT(*) FROM subtasks WHERE status='done'"
        ).fetchone()[0]
        subtask_rate = round(done_subtasks / total_subtasks * 100) if total_subtasks > 0 else 0

        entries = ks.list_entries()
        new_entries_this_month = sum(
            1 for e in entries if (e.get("created_at") or "") >= month_start_iso
        )

        return {
            "completed_tasks_this_month": completed_this_month,
            "subtask_completion_rate": subtask_rate,
            "new_knowledge_entries_this_month": new_entries_this_month,
            "total_tasks": total_tasks,
            "total_subtasks": total_subtasks,
            "done_subtasks": done_subtasks,
        }
    finally:
        conn.close()
