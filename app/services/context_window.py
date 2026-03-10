from app.models.message import Message


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
            ],
            None,
        )

    older = rows[: len(rows) - max_messages]
    newer = rows[len(rows) - max_messages :]
    summary = (
        f"{len(older)} aeltere Nachrichten zusammengefasst: "
        "Fortlaufende Session mit Regeln, Statusupdates und Compliance-Checks."
    )
    return (
        [
            {
                "role": row.role,
                "content": row.content,
                "message_type": row.message_type,
            }
            for row in newer
        ],
        summary,
    )
