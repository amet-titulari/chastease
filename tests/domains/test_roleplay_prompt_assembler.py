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
    )
    attachments = [{"name": "proof.png", "type": "image/png", "data_url": "data:image/png;base64,abc"}]

    user_prompt, attachment_content = build_roleplay_user_prompt(context, attachments)

    assert "Session: session-2" in user_prompt
    assert "Psychogram summary: summary=test" in user_prompt
    assert "These are NOT verification requests." in user_prompt
    assert attachment_content == [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]


def test_build_attachment_summary_without_attachments_returns_none_marker() -> None:
    summary, content = build_attachment_summary(None)

    assert summary == "- none"
    assert content == []