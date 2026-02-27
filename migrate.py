"""
One-time migration from JSON files to SQLite.
Usage: python migrate.py
JSON files are kept as backup after migration.
"""
import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

import task_store as ts
import knowledge_store as ks


def migrate_tasks():
    tasks_file = DATA_DIR / "tasks.json"
    if not tasks_file.exists():
        print("No tasks.json found, skipping.")
        return 0

    with open(tasks_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    count = 0
    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        import sqlite3
        conn = ts._get_conn()
        existing = conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
        conn.close()
        if existing:
            print(f"  Task {task_id} already exists, skipping.")
            continue

        daily_slots = task.get("daily_slots", ["09:00"])
        daily_slots_json = json.dumps(daily_slots) if isinstance(daily_slots, list) else daily_slots

        conn = ts._get_conn()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO tasks
                       (id, title, weeks, start_date, daily_slots, status, created_at, completed_at, reflection)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id,
                        task.get("title", ""),
                        task.get("weeks", 1),
                        task.get("start_date"),
                        daily_slots_json,
                        task.get("status", "in_progress"),
                        task.get("created_at", ""),
                        task.get("completed_at"),
                        task.get("reflection", ""),
                    )
                )
                for idx, st in enumerate(task.get("subtasks", [])):
                    st_id = st.get("id")
                    if not st_id:
                        continue
                    conn.execute(
                        """INSERT OR IGNORE INTO subtasks
                           (id, task_id, title, description, duration_minutes,
                            suggested_day_offset, status, completed_at, scheduled_at, sort_order)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            st_id,
                            task_id,
                            st.get("title", ""),
                            st.get("description", ""),
                            st.get("duration_minutes", 30),
                            st.get("suggested_day_offset", 0),
                            st.get("status", "pending"),
                            st.get("completed_at"),
                            st.get("scheduled_at"),
                            idx,
                        )
                    )
        finally:
            conn.close()
        count += 1

    print(f"Migrated {count} tasks.")
    return count


def migrate_knowledge():
    knowledge_file = DATA_DIR / "knowledge.json"
    if not knowledge_file.exists():
        print("No knowledge.json found, skipping.")
        return 0

    with open(knowledge_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    result = ks.import_entries(entries, mode="merge")
    print(f"Migrated knowledge entries: {result}")
    return result["added"]


def migrate_blobs():
    blob_map = {
        "graph": DATA_DIR / "knowledge_graph.json",
        "skill_tree": DATA_DIR / "skill_tree.json",
        "validation": DATA_DIR / "validation_results.json",
    }
    for key, path in blob_map.items():
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            blob_data = json.load(f)
        if key == "graph":
            ks.save_graph(blob_data)
        elif key == "skill_tree":
            ks.save_skill_tree(blob_data)
        elif key == "validation":
            ks.save_validation(blob_data)
        print(f"Migrated blob: {key}")


if __name__ == "__main__":
    print("Initializing database...")
    ts.init_db()
    ks.init_db()

    print("\nMigrating tasks...")
    migrate_tasks()

    print("\nMigrating knowledge entries...")
    migrate_knowledge()

    print("\nMigrating blobs (graph, skill tree, validation)...")
    migrate_blobs()

    print("\nMigration complete. JSON files kept as backup.")
