from chastease.domains.roleplay.session_memory import build_memory_entries, build_session_summary
from chastease.domains.roleplay.models import RoleplayTurn


def test_build_session_summary_uses_recent_turns() -> None:
    turns = [
        RoleplayTurn(turn_no=1, player_action="I wait quietly.", ai_narration="Hold still."),
        RoleplayTurn(turn_no=2, player_action="I report my pulse.", ai_narration="Keep breathing evenly."),
    ]

    summary = build_session_summary(turns)

    assert summary is not None
    assert summary.source_turn_no == 2
    assert "Wearer reported: I wait quietly." in summary.summary_text
    assert "Keyholder replied: Keep breathing evenly." in summary.summary_text


def test_build_memory_entries_returns_recent_player_and_ai_items() -> None:
    turns = [
        RoleplayTurn(turn_no=1, player_action="I kneel.", ai_narration="Count your breaths."),
        RoleplayTurn(turn_no=2, player_action="I confirm the count.", ai_narration="Remain focused."),
    ]

    entries = build_memory_entries(turns, max_entries=4)

    assert len(entries) == 4
    assert entries[0].kind == "wearer_state"
    assert entries[1].kind == "keyholder_guidance"
    assert entries[-1].content == "Remain focused."