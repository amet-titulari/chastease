from chastease.domains.roleplay import build_action_block, build_attachment_summary, build_roleplay_user_prompt
from chastease.services.ai.base import StoryTurnContext, TurnHistoryEntry


def test_build_action_block_includes_history_snapshot_and_tools() -> None:
    context = StoryTurnContext(
        session_id="session-1",
        action="I report back.",
        language="en",
        psychogram_summary="summary=test",
        turns_history=[
            TurnHistoryEntry(turn_no=1, player_action="I wait.", ai_narration="Stay still."),
        ],
        live_snapshot={"status": "active"},
        tools_summary="execute=add_time;suggest=-",
    )

    action_block = build_action_block(context, [{"name": "proof.jpg"}])

    assert "Recent dialogue:" in action_block
    assert "Current wearer input: I report back." in action_block
    assert "LIVE_SESSION_SNAPSHOT_JSON:" in action_block
    assert "Available tools: execute=add_time;suggest=-" in action_block
    assert "proof.jpg" in action_block


def test_build_roleplay_user_prompt_mentions_image_review_note() -> None:
    context = StoryTurnContext(
        session_id="session-2",
        action="Please review this.",
        language="en",
        psychogram_summary="summary=test",
        policy={
            "roleplay": {
                "prompt_profile": {"name": "immersive-keyholder", "mode": "immersive", "version": "v2"},
                "scene_state": {
                    "name": "vault-floor",
                    "phase": "control",
                    "status": "active",
                    "beats": ["wearer:steady breathing", "keyholder:maintain the ritual cadence"],
                },
                "session_summary": {"summary_text": "- Wearer reported: steady breathing."},
                "memory_entries": [
                    {"kind": "facts", "content": "steady breathing"},
                    {"kind": "rituals", "content": "maintain the ritual cadence"},
                ],
            }
        },
    )
    attachments = [{"name": "proof.png", "type": "image/png", "data_url": "data:image/png;base64,abc"}]

    user_prompt, attachment_content = build_roleplay_user_prompt(context, attachments)

    assert "Session: session-2" in user_prompt
    assert "Psychogram summary: summary=test" in user_prompt
    assert "Prompt profile: name=immersive-keyholder, mode=immersive, version=v2" in user_prompt
    assert "Scene state:" in user_prompt
    assert "- phase: control" in user_prompt
    assert "Scene beats:" in user_prompt
    assert "Session summary:" in user_prompt
    assert "Continuity memory:" in user_prompt
    assert "- facts: steady breathing" in user_prompt
    assert "- rituals: maintain the ritual cadence" in user_prompt
    assert "Favor immersive in-character narration" in user_prompt
    assert "These are NOT verification requests." in user_prompt
    assert attachment_content == [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]


def test_build_attachment_summary_without_attachments_returns_none_marker() -> None:
    summary, content = build_attachment_summary(None)

    assert summary == "- none"
    assert content == []


def test_build_roleplay_user_prompt_selects_most_relevant_memory_entries() -> None:
    context = StoryTurnContext(
        session_id="session-3",
        action="I will obey and report the seal status.",
        language="en",
        psychogram_summary="summary=test",
        policy={
            "roleplay": {
                "scene_state": {
                    "name": "vault-floor",
                    "phase": "control",
                    "status": "sealed",
                    "beats": ["seal:sealed:A-42"],
                },
                "memory_entries": [
                    {"kind": "facts", "content": "The room is quiet.", "source": "turn:1", "weight": 1.0},
                    {"kind": "rituals", "content": "Report your breathing cadence before each reply.", "source": "turn:2", "tags": ["continuity"], "weight": 1.15},
                    {"kind": "unresolved_threads", "content": "The seal number still needs confirmation.", "source": "turn:3", "tags": ["pending"], "weight": 1.1},
                    {"kind": "vows", "content": "I will obey the current seal protocol.", "source": "turn:4", "tags": ["commitment"], "weight": 1.3},
                    {"kind": "guidance", "content": "Keep your posture steady.", "source": "turn:5", "weight": 0.95},
                    {"kind": "guidance", "content": "Report the seal code clearly before anything else.", "source": "turn:6", "tags": ["continuity"], "weight": 1.05},
                ],
            }
        },
    )

    user_prompt, _attachment_content = build_roleplay_user_prompt(context, None)

    assert "- vows: I will obey the current seal protocol." in user_prompt
    assert "- unresolved_threads: The seal number still needs confirmation." in user_prompt
    assert "- rituals: Report your breathing cadence before each reply." in user_prompt
    assert "- guidance: Report the seal code clearly before anything else." in user_prompt
    assert "- facts: The room is quiet." not in user_prompt


def test_build_roleplay_user_prompt_selects_most_relevant_scene_beats() -> None:
    context = StoryTurnContext(
        session_id="session-4",
        action="The timer expired and the abort path is blocked.",
        language="en",
        psychogram_summary="summary=test",
        policy={
            "roleplay": {
                "scene_state": {
                    "name": "vault-floor",
                    "phase": "emergency",
                    "status": "abort-blocked",
                    "beats": [
                        "wearer:I wait quietly.",
                        "hygiene:open",
                        "seal:broken",
                        "timer:expired",
                        "openings:limit-reached",
                        "abort:confirmed",
                        "failed:ttlock_open",
                        "action:hygiene_open",
                    ],
                },
            }
        },
    )

    user_prompt, _attachment_content = build_roleplay_user_prompt(context, None)

    assert "- abort:confirmed" in user_prompt
    assert "- failed:ttlock_open" in user_prompt
    assert "- timer:expired" in user_prompt
    assert "- action:hygiene_open" in user_prompt
    assert "- wearer:I wait quietly." not in user_prompt