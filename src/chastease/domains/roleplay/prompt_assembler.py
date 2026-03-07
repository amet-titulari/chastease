import json
from typing import Any

from chastease.services.ai.base import StoryTurnContext

from .models import MemoryEntry, SceneState
from .session_memory import select_memory_entries_for_prompt, select_scene_beats_for_prompt


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
    prompt_profile = roleplay_payload.get("prompt_profile") if isinstance(roleplay_payload.get("prompt_profile"), dict) else {}
    prompt_profile_name = str(prompt_profile.get("name") or "roleplay-session").strip()
    prompt_profile_mode = str(prompt_profile.get("mode") or "session").strip()
    prompt_profile_version = str(prompt_profile.get("version") or "v1").strip()
    summary_payload = roleplay_payload.get("session_summary") if isinstance(roleplay_payload.get("session_summary"), dict) else {}
    summary_text = str(summary_payload.get("summary_text") or "").strip()
    memory_payload = roleplay_payload.get("memory_entries") if isinstance(roleplay_payload.get("memory_entries"), list) else []
    scene_payload = roleplay_payload.get("scene_state") if isinstance(roleplay_payload.get("scene_state"), dict) else {}
    scene_beats = [
        str(item).strip()
        for item in (scene_payload.get("beats") or [])
        if str(item).strip()
    ]
    scene_state = SceneState(
        name=str(scene_payload.get("name") or "active-session").strip() or "active-session",
        phase=str(scene_payload.get("phase") or "active").strip() or "active",
        status=str(scene_payload.get("status") or "active").strip() or "active",
        beats=scene_beats,
    ) if scene_payload else None
    selected_scene_beats = select_scene_beats_for_prompt(
        scene_beats,
        action_text=context.action,
        scene_state=scene_state,
        limit=4,
    )
    selected_memory_entries = select_memory_entries_for_prompt(
        [
            MemoryEntry(
                kind=str(item.get("kind") or "memory"),
                content=str(item.get("content") or "").strip(),
                source=str(item.get("source") or "session"),
                tags=[str(tag) for tag in (item.get("tags") or []) if str(tag).strip()],
                weight=float(item.get("weight") or 1.0),
            )
            for item in memory_payload
            if isinstance(item, dict) and str(item.get("content") or "").strip()
        ],
        action_text=context.action,
        scene_state=scene_state,
        limit=4,
    )
    memory_lines = [f"- {entry.kind}: {entry.content}" for entry in selected_memory_entries]
    continuity_block = ""
    if scene_payload:
        continuity_block = (
            f"Scene state:\n"
            f"- name: {str(scene_payload.get('name') or 'active-session').strip()}\n"
            f"- phase: {str(scene_payload.get('phase') or 'active').strip()}\n"
            f"- status: {str(scene_payload.get('status') or 'active').strip()}\n"
        )
        if selected_scene_beats:
            continuity_block = f"{continuity_block}Scene beats:\n" + "\n".join(f"- {item}" for item in selected_scene_beats) + "\n"
    if summary_text:
        continuity_block = f"Session summary:\n{summary_text}\n"
        if scene_payload:
            continuity_block = (
                f"Scene state:\n"
                f"- name: {str(scene_payload.get('name') or 'active-session').strip()}\n"
                f"- phase: {str(scene_payload.get('phase') or 'active').strip()}\n"
                f"- status: {str(scene_payload.get('status') or 'active').strip()}\n"
                + ("Scene beats:\n" + "\n".join(f"- {item}" for item in selected_scene_beats) + "\n" if selected_scene_beats else "")
                + continuity_block
            )
    if memory_lines:
        continuity_block = f"{continuity_block}Continuity memory:\n" + "\n".join(memory_lines[:4]) + "\n"
    prompt_profile_block = (
        f"Prompt profile: name={prompt_profile_name}, mode={prompt_profile_mode}, version={prompt_profile_version}\n"
    )
    mode_instruction = ""
    if prompt_profile_mode == "immersive":
        mode_instruction = "Favor immersive in-character narration with sensory continuity and minimal meta explanation. "
    elif prompt_profile_mode == "strict":
        mode_instruction = "Favor concise, authoritative guidance with direct behavioral framing and minimal softness. "
    elif prompt_profile_mode == "supportive":
        mode_instruction = "Favor calm, reassuring authority while preserving structure and control. "
    attachment_note = ""
    if attachment_content:
        attachment_note = (
            "\n\nNote: The user has provided images for your review and context. "
            "These are NOT verification requests. Only request image_verification if you need a specific proof/check."
        )
    user_prompt = (
        f"Session: {context.session_id}\n"
        f"Psychogram summary: {context.psychogram_summary}\n"
        f"{prompt_profile_block}"
        f"{continuity_block}"
        f"Wearer action: {action_block}\n"
        f"Attachments:\n{attachment_summary}{attachment_note}\n"
        f"Language: {context.language}\n"
        f"{mode_instruction}"
        "Respond as the keyholder with concise narrative and next guidance. "
        "Do not echo raw machine-readable key/value profile fields."
    )
    return user_prompt, attachment_content
