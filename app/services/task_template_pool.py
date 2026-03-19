import hashlib
import json
import re

from app.models.persona_task_template import PersonaTaskTemplate


_TASK_REQUEST_PATTERN = re.compile(r"\b(aufgabe|task|challenge|uebung|übung|verification|verifikation|foto)\b", re.IGNORECASE)


def user_requested_task(text: str | None) -> bool:
    return bool(_TASK_REQUEST_PATTERN.search(str(text or "")))


def _template_tags(row: PersonaTaskTemplate) -> list[str]:
    try:
        value = json.loads(row.tags_json or "[]")
    except Exception:
        value = []
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def _template_score(row: PersonaTaskTemplate, text_lower: str) -> int:
    haystack_parts = [row.title or "", row.description or "", row.category or "", " ".join(_template_tags(row))]
    haystack = " ".join(haystack_parts).lower()
    score = 0
    for token in re.findall(r"[a-z0-9äöüß_-]+", text_lower):
        if len(token) >= 3 and token in haystack:
            score += 2
    if any(word in text_lower for word in ("foto", "bild", "verifikation", "verification")) and row.requires_verification:
        score += 4
    if any(word in text_lower for word in ("einfach", "leicht", "kurz", "simple")) and (row.deadline_minutes or 0) <= 20:
        score += 1
    if row.deadline_minutes:
        score += 1
    return score


def select_task_template(rows: list[PersonaTaskTemplate], user_text: str | None) -> PersonaTaskTemplate | None:
    if not rows:
        return None
    text_lower = str(user_text or "").lower()
    scored = [(_template_score(row, text_lower), row.id, row) for row in rows]
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score = scored[0][0]
    top_rows = [row for score, _, row in scored if score == best_score]
    if len(top_rows) == 1:
        return top_rows[0]
    selector = hashlib.sha256(str(user_text or "task").encode("utf-8")).hexdigest()
    index = int(selector[:8], 16) % len(top_rows)
    return top_rows[index]


def build_template_task_action(row: PersonaTaskTemplate) -> dict:
    action = {
        "type": "create_task",
        "title": row.title,
        "description": row.description or "",
    }
    if row.deadline_minutes:
        action["deadline_minutes"] = int(row.deadline_minutes)
    if row.requires_verification:
        action["requires_verification"] = True
    if row.verification_criteria:
        action["verification_criteria"] = row.verification_criteria
    return action
