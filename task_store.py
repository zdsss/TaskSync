import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
TASKS_FILE = DATA_DIR / "tasks.json"


def _load() -> dict:
    if not TASKS_FILE.exists():
        return {"version": 1, "tasks": []}
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TASKS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(TASKS_FILE)


def list_tasks() -> list:
    data = _load()
    return sorted(data["tasks"], key=lambda t: t.get("created_at", ""), reverse=True)


def get_task(task_id: str) -> dict | None:
    data = _load()
    for t in data["tasks"]:
        if t["id"] == task_id:
            return t
    return None


def create_task(task_data: dict) -> dict:
    data = _load()
    task_id = f"tk_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    task_data["id"] = task_id
    task_data.setdefault("created_at", now)
    task_data.setdefault("status", "in_progress")
    task_data.setdefault("completed_at", None)
    task_data.setdefault("reflection", "")
    for st in task_data.get("subtasks", []):
        if not st.get("id"):
            st["id"] = f"st_{uuid.uuid4().hex[:8]}"
        st.setdefault("status", "pending")
        st.setdefault("completed_at", None)
        st.setdefault("scheduled_at", None)
    data["tasks"].append(task_data)
    _save(data)
    return task_data


def update_task(task_id: str, updates: dict) -> dict | None:
    data = _load()
    for t in data["tasks"]:
        if t["id"] == task_id:
            updates.pop("id", None)
            updates.pop("created_at", None)
            t.update(updates)
            _save(data)
            return t
    return None


def delete_task(task_id: str) -> bool:
    data = _load()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    if len(data["tasks"]) < before:
        _save(data)
        return True
    return False


def update_subtask(task_id: str, subtask_id: str, updates: dict) -> dict | None:
    data = _load()
    for t in data["tasks"]:
        if t["id"] == task_id:
            for st in t.get("subtasks", []):
                if st["id"] == subtask_id:
                    updates.pop("id", None)
                    st.update(updates)
                    _save(data)
                    return st
    return None


def get_stats() -> dict:
    import knowledge_store as ks
    data = _load()
    tasks = data["tasks"]
    now = datetime.now(timezone.utc)
    month_start_iso = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    completed_this_month = sum(
        1 for t in tasks
        if t.get("status") == "done" and (t.get("completed_at") or "") >= month_start_iso
    )
    total_subtasks = sum(len(t.get("subtasks", [])) for t in tasks)
    done_subtasks = sum(
        sum(1 for st in t.get("subtasks", []) if st.get("status") == "done")
        for t in tasks
    )
    subtask_rate = round(done_subtasks / total_subtasks * 100) if total_subtasks > 0 else 0
    entries = ks.list_entries()
    new_entries_this_month = sum(
        1 for e in entries if (e.get("created_at") or "") >= month_start_iso
    )
    return {
        "completed_tasks_this_month": completed_this_month,
        "subtask_completion_rate": subtask_rate,
        "new_knowledge_entries_this_month": new_entries_this_month,
        "total_tasks": len(tasks),
        "total_subtasks": total_subtasks,
        "done_subtasks": done_subtasks,
    }
