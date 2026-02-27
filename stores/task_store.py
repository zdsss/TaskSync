import json
import uuid
from datetime import datetime, timedelta, timezone

from stores.db import get_conn


def init_db():
    conn = get_conn()
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
            CREATE INDEX IF NOT EXISTS idx_subtasks_status ON subtasks(status);
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


def list_tasks(include_subtasks: bool = True) -> list:
    conn = get_conn()
    try:
        tasks = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
        if not tasks:
            return []
        if include_subtasks:
            result = []
            for t in tasks:
                subtasks = conn.execute(
                    "SELECT * FROM subtasks WHERE task_id=? ORDER BY sort_order",
                    (t["id"],)
                ).fetchall()
                result.append(_row_to_task(t, subtasks))
            return result
        # Slim path: fetch all subtask counts in one query
        ids = [t["id"] for t in tasks]
        placeholders = ",".join("?" * len(ids))
        count_rows = conn.execute(
            f"SELECT task_id,"
            f" COUNT(*) as total,"
            f" SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done"
            f" FROM subtasks WHERE task_id IN ({placeholders}) GROUP BY task_id",
            ids
        ).fetchall()
        counts = {r["task_id"]: r for r in count_rows}
        result = []
        for t in tasks:
            task_dict = _row_to_task(t, [])
            c = counts.get(t["id"])
            task_dict["subtask_total"] = c["total"] if c else 0
            task_dict["subtask_done"] = c["done"] if c else 0
            result.append(task_dict)
        return result
    finally:
        conn.close()


def get_task(task_id: str) -> dict | None:
    conn = get_conn()
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

    conn = get_conn()
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
                        st["id"], task_id,
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

    conn = get_conn()
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
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        return cur.rowcount > 0
    finally:
        conn.close()


def create_subtask(task_id: str, data: dict) -> dict | None:
    conn = get_conn()
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

    conn = get_conn()
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


def get_task_stats() -> dict:
    """Returns task/subtask counts. Knowledge stats handled separately in the route."""
    conn = get_conn()
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

        # Weekly subtask completion trend: last 8 weeks (Mon–Sun buckets)
        today = now.date()
        week_monday = today - timedelta(days=today.weekday())
        range_start = week_monday - timedelta(weeks=7)
        range_end = week_monday + timedelta(days=7)

        # Single query for all 8 weeks; bucket in Python
        done_rows = conn.execute(
            "SELECT completed_at FROM subtasks WHERE status='done'"
            " AND completed_at >= ? AND completed_at < ?",
            (range_start.isoformat(), range_end.isoformat())
        ).fetchall()

        # Build week buckets
        week_counts: dict = {}
        for i in range(7, -1, -1):
            w = (week_monday - timedelta(weeks=i)).isoformat()
            week_counts[w] = 0
        for row in done_rows:
            try:
                d = datetime.fromisoformat(row["completed_at"]).date()
                w = (d - timedelta(days=d.weekday())).isoformat()
                if w in week_counts:
                    week_counts[w] += 1
            except (ValueError, TypeError):
                pass
        weekly_trend = [{"week": w, "done": c} for w, c in week_counts.items()]

        return {
            "completed_tasks_this_month": completed_this_month,
            "subtask_completion_rate": subtask_rate,
            "total_tasks": total_tasks,
            "total_subtasks": total_subtasks,
            "done_subtasks": done_subtasks,
            "weekly_subtask_trend": weekly_trend,
            "_month_start_iso": month_start_iso,
        }
    finally:
        conn.close()
