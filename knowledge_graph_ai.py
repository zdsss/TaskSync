import json
import re
from datetime import datetime, timezone

from openai import OpenAI


def build_knowledge_graph(api_key: str, base_url: str, model: str, entries: list) -> dict:
    client = OpenAI(api_key=api_key, base_url=base_url or None)

    compact = "\n".join(
        f"{e['id']} | {e.get('type','')} | {e.get('title','')} | {','.join(e.get('tags',[]))} | {e.get('summary','')}"
        for e in entries
    )

    prompt = f"""You are a knowledge organization assistant. Analyze the following knowledge entries and identify thematic clusters and relationships between them.

Entries (format: id | type | title | tags | summary):
{compact}

Return a JSON object with exactly this structure:
{{
  "clusters": [
    {{
      "id": "cluster_001",
      "label": "short cluster name in the same language as the entries",
      "theme": "one sentence describing the theme",
      "entry_ids": ["ke_xxx", "ke_yyy"]
    }}
  ],
  "relationships": [
    {{
      "from_id": "ke_xxx",
      "to_id": "ke_yyy",
      "relation": "extends"
    }}
  ]
}}

Rules:
- relation must be one of: extends, related, prerequisite, contradicts
- Each entry should belong to at least one cluster
- Only include relationships that are clearly meaningful
- Return ONLY the JSON object, no markdown, no explanation"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw.strip())

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clusters": data.get("clusters", []),
        "relationships": data.get("relationships", []),
    }
