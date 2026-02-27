import json
import re
from openai import OpenAI


def analyze_entry(api_key: str, base_url: str, model: str, title: str, content: str) -> dict:
    client = OpenAI(api_key=api_key, base_url=base_url or None)

    prompt = f"""Analyze the following knowledge entry and return a JSON object with:
- "summary": a concise summary in no more than 80 characters
- "tags": an array of up to 5 relevant lowercase tags
- "suggested_type": one of "bug", "experience", "skill", "note", "command", "link"

Title: {title}
Content: {content}

Return ONLY a JSON object, no markdown, no explanation."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    data = json.loads(raw)
    return {
        "summary": str(data.get("summary", ""))[:80],
        "tags": [str(t) for t in data.get("tags", [])][:5],
        "suggested_type": data.get("suggested_type", "note"),
    }
