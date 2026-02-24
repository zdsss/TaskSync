import json
import re
import uuid
from datetime import datetime, timezone

from openai import OpenAI


def validate_entries(api_key: str, base_url: str, model: str, entries: list) -> list:
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    results = []

    for entry in entries:
        result = _validate_one(client, model, entry)
        results.append(result)

    return results


def _validate_one(client, model: str, entry: dict) -> dict:
    entry_id = entry.get("id", "")
    title = entry.get("title", "")
    content = entry.get("content", "")
    now = datetime.now(timezone.utc).isoformat()
    val_id = f"val_{uuid.uuid4().hex[:12]}"

    # Phase 1: triage
    triage_prompt = f"""Does the following knowledge entry contain verifiable factual claims (e.g. version numbers, API names, commands, technical specifications, dates)?

Title: {title}
Content: {content[:500]}

Reply with only "yes" or "no"."""

    triage_resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": triage_prompt}],
        temperature=0,
    )
    triage = triage_resp.choices[0].message.content.strip().lower()

    if "yes" not in triage:
        return {
            "id": val_id,
            "entry_id": entry_id,
            "entry_title": title,
            "verdict": "unverifiable",
            "issue": None,
            "suggested_correction": None,
            "sources": [],
            "status": "pending_review",
            "created_at": now,
        }

    # Phase 2: full fact-check
    check_prompt = f"""You are a technical fact-checker. Review the following knowledge entry for factual accuracy based on your training knowledge.

Title: {title}
Content: {content}

Return a JSON object:
{{
  "verdict": "correct",
  "issue": null,
  "suggested_correction": null,
  "sources": []
}}

verdict must be one of: correct, outdated, incorrect, unverifiable
- correct: all facts appear accurate
- outdated: facts were once correct but are now outdated
- incorrect: contains factual errors
- unverifiable: cannot be verified from training knowledge

If verdict is outdated or incorrect:
- issue: describe the specific problem
- suggested_correction: provide the corrected content (full replacement for the content field)
- sources: list up to 3 sources as [{{"title": "...", "url": "..."}}] (use your training knowledge; note these are AI-generated citations)

Return ONLY the JSON object, no markdown, no explanation."""

    check_resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": check_prompt}],
        temperature=0.1,
    )

    raw = check_resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw.strip())

    return {
        "id": val_id,
        "entry_id": entry_id,
        "entry_title": title,
        "verdict": data.get("verdict", "unverifiable"),
        "issue": data.get("issue"),
        "suggested_correction": data.get("suggested_correction"),
        "sources": data.get("sources", []),
        "status": "pending_review",
        "created_at": now,
    }
