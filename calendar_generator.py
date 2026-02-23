import uuid
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event, Alarm
from icalendar import vText, vDatetime


def generate_ics(subtasks, start_date, daily_slots, task_title) -> bytes:
    cal = Calendar()
    cal.add("PRODID", "-//TaskSync//TaskSync//EN")
    cal.add("VERSION", "2.0")
    cal.add("METHOD", "PUBLISH")
    cal.add("X-WR-CALNAME", task_title)
    cal.add("X-WR-TIMEZONE", "UTC")

    # Parse daily_slots: list of "HH:MM" strings
    slot_times = []
    for slot in daily_slots:
        h, m = map(int, slot.split(":"))
        slot_times.append((h, m))

    if not slot_times:
        slot_times = [(9, 0)]

    slot_index = 0

    for subtask in subtasks:
        day_offset = int(subtask.get("suggested_day_offset", 0))
        duration_minutes = int(subtask.get("duration_minutes", 30))

        event_date = start_date + timedelta(days=day_offset)
        h, m = slot_times[slot_index % len(slot_times)]
        slot_index += 1

        dtstart = datetime(
            event_date.year, event_date.month, event_date.day, h, m, 0,
            tzinfo=timezone.utc
        )
        dtend = dtstart + timedelta(minutes=duration_minutes)
        dtstamp = datetime.now(tz=timezone.utc)

        event = Event()
        event.add("SUMMARY", subtask.get("title", "Task"))
        event.add("DESCRIPTION", subtask.get("description", ""))
        event.add("DTSTART", dtstart)
        event.add("DTEND", dtend)
        event.add("DTSTAMP", dtstamp)
        event["UID"] = f"{uuid.uuid4()}@tasksync"

        alarm = Alarm()
        alarm.add("ACTION", "DISPLAY")
        alarm.add("DESCRIPTION", "Reminder")
        alarm.add("TRIGGER", timedelta(minutes=-10))
        event.add_component(alarm)

        cal.add_component(event)

    return cal.to_ical()
