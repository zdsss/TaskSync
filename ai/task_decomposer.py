import json
import re
from openai import OpenAI


def decompose_task(api_key, base_url, model, task, weeks, start_date, daily_slots) -> list:
    client = OpenAI(api_key=api_key, base_url=base_url)

    total_days = weeks * 7
    slots_per_day = len(daily_slots) if daily_slots else 1

    prompt = f"""You are a productivity assistant. Break down the following task into concrete, actionable subtasks that can be scheduled over {weeks} week(s) ({total_days} days), with up to {slots_per_day} task(s) per day.

Main task: {task}
Start date: {start_date.strftime('%Y-%m-%d')}

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{{
  "subtasks": [
    {{
      "title": "Short action title",
      "description": "What to do in this session",
      "duration_minutes": 30,
      "suggested_day_offset": 0
    }}
  ]
}}

Rules:
- suggested_day_offset must be between 0 and {total_days - 1}
- duration_minutes should be 15, 30, 45, or 60
- Create enough subtasks to meaningfully progress on the main task
- Order subtasks logically (earlier steps first)"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    data = json.loads(raw)
    return data.get("subtasks", [])
