import json
from typing import Any

from chastease.services.ai.base import StoryTurnContext


def build_attachment_summary(attachments: list[dict[str, Any]] | None) -> tuple[str, list[dict[str, Any]]]:
    attachment_lines: list[str] = []
    attachment_content: list[dict[str, Any]] = []
    for item in attachments or []:
        name = str(item.get("name", "file"))
        mime_type = str(item.get("type", item.get("mime_type", "application/octet-stream")))
        attachment_lines.append(f"- {name} ({mime_type})")
        data_url = item.get("data_url")
        if isinstance(data_url, str) and data_url.startswith("data:image/"):
            attachment_content.append({"type": "image_url", "image_url": {"url": data_url}})
    attachment_summary = "\n".join(attachment_lines) if attachment_lines else "- none"
    return attachment_summary, attachment_content


def build_action_block(context: StoryTurnContext, attachments: list[dict[str, Any]] | None) -> str:
    history_parts: list[str] = []
    history_chars = 280
    for entry in context.turns_history:
        compact_player = " ".join(str(entry.player_action or "").split())
        compact_ai = " ".join(str(entry.ai_narration or "").split())
        if len(compact_player) > history_chars:
            compact_player = compact_player[: max(1, history_chars - 3)].rstrip() + "..."
        if len(compact_ai) > history_chars:
            compact_ai = compact_ai[: max(1, history_chars - 3)].rstrip() + "..."
        history_parts.append(f"Wearer: {compact_player}")
        history_parts.append(f"Keyholder: {compact_ai}")
    history_block = "\n".join(history_parts).strip()

    attachment_names = [str(item.get("name", "file")) for item in (attachments or [])]
    attachment_hint = f"\nCurrent attachments: {', '.join(attachment_names)}" if attachment_names else ""
    if history_block:
        action_block = f"Recent dialogue:\n{history_block}\n\nCurrent wearer input: {context.action}{attachment_hint}"
    else:
        action_block = f"Current wearer input: {context.action}{attachment_hint}"

    if context.live_snapshot:
        action_block = (
            f"{action_block}\n\n"
            f"LIVE_SESSION_SNAPSHOT_JSON:\n{json.dumps(context.live_snapshot, ensure_ascii=False)}"
        )

    if context.tools_summary:
        action_block = f"{action_block}\n\nAvailable tools: {context.tools_summary}"

    return action_block


def build_roleplay_user_prompt(context: StoryTurnContext, attachments: list[dict[str, Any]] | None) -> tuple[str, list[dict[str, Any]]]:
    attachment_summary, attachment_content = build_attachment_summary(attachments)
    action_block = build_action_block(context, attachments)
    roleplay_payload = context.policy.get("roleplay") if isinstance(context.policy, dict) and isinstance(context.policy.get("roleplay"), dict) else {}
    summary_payload = roleplay_payload.get("session_summary") if isinstance(roleplay_payload.get("session_summary"), dict) else {}
    summary_text = str(summary_payload.get("summary_text") or "").strip()
    memory_payload = roleplay_payload.get("memory_entries") if isinstance(roleplay_payload.get("memory_entries"), list) else []
    memory_lines = [
        f"- {str(item.get('kind') or 'memory')}: {str(item.get('content') or '').strip()}"
        for item in memory_payload
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]
    continuity_block = ""
    if summary_text:
        continuity_block = f"Session summary:\n{summary_text}\n"
    if memory_lines:
        continuity_block = f"{continuity_block}Continuity memory:\n" + "\n".join(memory_lines[:4]) + "\n"
    attachment_note = ""
    if attachment_content:
        attachment_note = (
            "\n\nNote: The user has provided images for your review and context. "
            "These are NOT verification requests. Only request image_verification if you need a specific proof/check."
        )
    user_prompt = (
        f"Session: {context.session_id}\n"
        f"Psychogram summary: {context.psychogram_summary}\n"
        f"{continuity_block}"
        f"Wearer action: {action_block}\n"
        f"Attachments:\n{attachment_summary}{attachment_note}\n"
        f"Language: {context.language}\n"
        "Respond as the keyholder with concise narrative and next guidance. "
        "Do not echo raw machine-readable key/value profile fields."
    )
    return user_prompt, attachment_content
