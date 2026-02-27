import json
import re
from datetime import datetime, timezone

from openai import OpenAI


def build_skill_tree(api_key: str, base_url: str, model: str, entries: list) -> dict:
    client = OpenAI(api_key=api_key, base_url=base_url or None)

    compact = "\n".join(
        f"{e['id']} | {e.get('type','')} | {e.get('title','')} | {','.join(e.get('tags',[]))}"
        for e in entries
    )

    prompt = f"""You are a skill analysis assistant. Analyze the following knowledge entries and extract a skill tree.

Entries (format: id | type | title | tags):
{compact}

Return a JSON object with exactly this structure:
{{
  "skills": [
    {{
      "id": "skill_xxx",
      "name": "skill name",
      "category": "language",
      "status": "has",
      "level": "intermediate",
      "evidence_entry_ids": ["ke_xxx"],
      "parent_skill_id": null,
      "recommendation_reason": null
    }}
  ]
}}

Rules:
- category must be one of: language, framework, tool, concept, domain
- status must be one of: has, missing
- level must be one of: beginner, intermediate, advanced, or null (for missing skills)
- For "has" skills: extract from the entries, set evidence_entry_ids to relevant entry IDs, set level based on depth of content
- For "missing" skills: recommend 5-10 skills that would complement the existing set, set evidence_entry_ids to [], set recommendation_reason explaining why this skill is recommended
- parent_skill_id links a skill to a broader parent skill id (e.g. "skill_react" parent is "skill_javascript")
- Use the same language as the entries for skill names
- Return ONLY the JSON object, no markdown, no explanation"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"AI 返回了无效的 JSON：{e}") from e

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skills": data.get("skills", []),
    }
