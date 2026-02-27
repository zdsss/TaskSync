from datetime import date, timedelta, datetime as dt

from flask import Blueprint, jsonify, request

import stores.task_store as ts

bp = Blueprint("calendar", __name__)


@bp.route("/calendar")
def calendar_page():
    from flask import render_template
    return render_template("calendar.html")


@bp.route("/api/calendar/week", methods=["GET"])
def api_calendar_week():
    start_str = request.args.get("start", "")
    try:
        week_start = dt.strptime(start_str, "%Y-%m-%d").date()
    except ValueError:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    events = []
    for task in ts.list_tasks():
        task_start = task.get("start_date")
        daily_slots = task.get("daily_slots") or ["09:00"]
        slot_times = [tuple(map(int, s.split(":"))) for s in daily_slots]
        subtasks = task.get("subtasks", [])

        for idx, st in enumerate(subtasks):
            if st.get("scheduled_at"):
                sched = dt.fromisoformat(st["scheduled_at"])
                event_date = sched.date()
                is_computed = False
            elif task_start:
                base = dt.strptime(task_start, "%Y-%m-%d").date()
                event_date = base + timedelta(days=st.get("suggested_day_offset", 0))
                h, m = slot_times[idx % len(slot_times)]
                sched = dt(event_date.year, event_date.month, event_date.day, h, m)
                is_computed = True
            else:
                continue

            if week_start <= event_date <= week_end:
                events.append({
                    "task_id": task["id"],
                    "task_title": task["title"],
                    "subtask_id": st["id"],
                    "title": st["title"],
                    "description": st.get("description", ""),
                    "status": st.get("status", "pending"),
                    "duration_minutes": st.get("duration_minutes", 30),
                    "scheduled_at": sched.isoformat(),
                    "is_computed": is_computed,
                })

    return jsonify({"week_start": week_start.isoformat(), "events": events})
