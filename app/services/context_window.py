from app.models.message import Message

# Per-step game events are suppressed from the AI context window.
# The AI receives only the end-of-game summary (game_report) instead.
_GAME_STEP_INTERNAL_TYPES: frozenset[str] = frozenset(
    {
        "game_started",
        "game_step_fail",
        "game_step_sample_pass",
        "game_step_sample_fail",
        "game_penalty",
    }
)


def _is_ai_visible(row: Message) -> bool:
    return str(row.message_type or "") not in _GAME_STEP_INTERNAL_TYPES


def _shorten(value: str | None, limit: int = 180) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if not text:
        return ""
    return text if len(text) <= limit else (text[: limit - 3].rstrip() + "...")


def _build_memory_summary(rows: list[Message]) -> str | None:
    if not rows:
        return None

    last_user = next((row for row in reversed(rows) if row.role == "user" and str(row.content or "").strip()), None)
    last_assistant = next((row for row in reversed(rows) if row.role == "assistant" and str(row.content or "").strip()), None)
    system_notes = [
        _shorten(row.content, 120)
        for row in rows
        if str(row.message_type or "") in {"task_assigned", "task_updated", "task_failed", "session_state_updated", "system_warning"}
        and str(row.content or "").strip()
    ]
    system_notes = system_notes[-3:]

    fragments: list[str] = []
    if last_user is not None:
        fragments.append(f"Letztes Nutzeranliegen: {_shorten(last_user.content)}")
    if last_assistant is not None:
        fragments.append(f"Letzte fuehrende Antwort: {_shorten(last_assistant.content)}")
    if system_notes:
        fragments.append("Wichtige Systemereignisse: " + " | ".join(system_notes))
    if not fragments:
        return None
    return "Session-Memory: " + " || ".join(fragments)


def build_context_window(
    rows: list[Message],
    max_messages: int = 12,
) -> tuple[list[dict], str | None]:
    if len(rows) <= max_messages:
        return (
            [
                {
                    "role": row.role,
                    "content": row.content,
                    "message_type": row.message_type,
                }
                for row in rows
                if _is_ai_visible(row)
            ],
            _build_memory_summary(rows),
        )

    older = rows[: len(rows) - max_messages]
    newer = rows[len(rows) - max_messages :]
    coarse_summary = (
        f"{len(older)} aeltere Nachrichten zusammengefasst: "
        "Fortlaufende Session mit Regeln, Statusupdates und Compliance-Checks."
    )
    memory_summary = _build_memory_summary(older)
    summary = " ".join(part for part in [coarse_summary, memory_summary] if part)
    return (
        [
            {
                "role": row.role,
                "content": row.content,
                "message_type": row.message_type,
            }
            for row in newer
            if _is_ai_visible(row)
        ],
        summary,
    )
