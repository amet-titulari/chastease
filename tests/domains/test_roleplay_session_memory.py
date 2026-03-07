from chastease.domains.roleplay.session_memory import (
    build_memory_entries,
    build_scene_state,
    build_session_summary,
    select_memory_entries_for_prompt,
    select_scene_beats_for_prompt,
)
from chastease.domains.roleplay.models import MemoryEntry, RoleplayTurn, SceneState


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
    assert entries[0].kind == "rituals"
    assert entries[0].tags == ["recent", "wearer", "continuity"]
    assert entries[1].kind == "rituals"
    assert entries[-1].content == "Remain focused."


def test_build_memory_entries_classifies_vows_and_threads() -> None:
    turns = [
        RoleplayTurn(turn_no=1, player_action="I will obey the ritual from now on.", ai_narration="We will revisit this later."),
    ]

    entries = build_memory_entries(turns, max_entries=2)

    assert entries[0].kind == "vows"
    assert entries[0].weight == 1.3
    assert entries[1].kind == "unresolved_threads"
    assert "pending" in entries[1].tags


def test_build_scene_state_derives_phase_and_beats() -> None:
    turns = [
        RoleplayTurn(turn_no=1, player_action="I kneel and wait.", ai_narration="Hold still and breathe evenly."),
        RoleplayTurn(turn_no=2, player_action="I report my breathing.", ai_narration="Keep the ritual cadence."),
    ]

    scene_state = build_scene_state(turns)

    assert scene_state.name == "active-session"
    assert scene_state.phase == "control"
    assert scene_state.status == "active"
    assert any("wearer:I report my breathing." == beat for beat in scene_state.beats)
    assert any("keyholder:Keep the ritual cadence." == beat for beat in scene_state.beats)


def test_build_scene_state_prefers_runtime_pause_and_seal_state() -> None:
    turns = [
        RoleplayTurn(turn_no=1, player_action="I wait.", ai_narration="Remain still."),
    ]

    scene_state = build_scene_state(
        turns,
        policy={
            "runtime_timer": {"state": "paused"},
            "runtime_seal": {"status": "sealed", "current_text": "A-42"},
        },
    )

    assert scene_state.phase == "suspension"
    assert scene_state.status == "paused"
    assert "timer:paused" in scene_state.beats
    assert "seal:sealed:A-42" in scene_state.beats


def test_build_scene_state_tracks_hygiene_openings_and_recent_actions() -> None:
    turns = [
        RoleplayTurn(turn_no=1, player_action="I wait.", ai_narration="Prepare for the hygiene routine."),
    ]

    scene_state = build_scene_state(
        turns,
        policy={
            "runtime_hygiene": {"is_open": True, "window_end_at": "2026-03-07T12:00:00+00:00"},
            "runtime_opening_limits": {"open_events": ["2026-03-07T10:00:00+00:00", "2026-03-07T11:00:00+00:00"]},
            "limits": {"opening_limit_period": "day", "max_openings_in_period": 2},
        },
        recent_action_types=["hygiene_open"],
    )

    assert scene_state.phase == "maintenance"
    assert scene_state.status == "hygiene-open"
    assert "hygiene:open" in scene_state.beats
    assert any(beat.startswith("openings:2/2:day") for beat in scene_state.beats)
    assert "action:hygiene_open" in scene_state.beats


def test_build_scene_state_applies_recent_event_overlay() -> None:
    turns = [RoleplayTurn(turn_no=1, player_action="Status.", ai_narration="Awaiting next step.")]

    scene_state = build_scene_state(
        turns,
        recent_event_phase="emergency",
        recent_event_status="abort-blocked",
        recent_event_beats=["abort:confirmed", "failed:ttlock_open", "abort:failed-open"],
    )

    assert scene_state.phase == "emergency"
    assert scene_state.status == "abort-blocked"
    assert "abort:confirmed" in scene_state.beats
    assert "failed:ttlock_open" in scene_state.beats


def test_select_memory_entries_for_prompt_prioritizes_overlap_and_commitment() -> None:
    entries = [
        MemoryEntry(kind="facts", content="The room is quiet.", source="turn:1", tags=["recent"], weight=1.0),
        MemoryEntry(kind="rituals", content="Report your breathing cadence before each reply.", source="turn:2", tags=["recent", "continuity"], weight=1.15),
        MemoryEntry(kind="unresolved_threads", content="The seal number still needs confirmation.", source="turn:3", tags=["recent", "pending"], weight=1.1),
        MemoryEntry(kind="vows", content="I will obey the current seal protocol.", source="turn:4", tags=["recent", "commitment"], weight=1.3),
        MemoryEntry(kind="guidance", content="Keep your posture steady.", source="turn:5", tags=["recent"], weight=0.95),
    ]

    selected = select_memory_entries_for_prompt(
        entries,
        action_text="I will obey and report the seal status now.",
        scene_state=SceneState(name="active-session", phase="control", status="sealed", beats=["seal:sealed:A-42"]),
        limit=3,
    )

    assert len(selected) == 3
    assert any(entry.kind == "vows" for entry in selected)
    assert any(entry.kind == "unresolved_threads" for entry in selected)
    assert any(entry.kind == "rituals" for entry in selected)
    assert all(entry.content != "The room is quiet." for entry in selected)


def test_select_scene_beats_for_prompt_prioritizes_critical_runtime_signals() -> None:
    beats = [
        "wearer:I wait quietly.",
        "hygiene:open",
        "seal:broken",
        "timer:expired",
        "openings:limit-reached",
        "abort:confirmed",
        "failed:ttlock_open",
        "action:hygiene_open",
    ]

    selected = select_scene_beats_for_prompt(
        beats,
        action_text="Please open immediately, timer expired.",
        scene_state=SceneState(name="active-session", phase="emergency", status="abort-blocked", beats=beats),
        limit=4,
    )

    assert len(selected) == 4
    assert "abort:confirmed" in selected
    assert "failed:ttlock_open" in selected
    assert "timer:expired" in selected
    assert "wearer:I wait quietly." not in selected