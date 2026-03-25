from app.services.roleplay_progression import roleplay_patch_for_event
from app.services.roleplay_state import build_roleplay_state


def _state() -> dict:
    return build_roleplay_state(None, None, None, scenario_title="Test Scenario")


def test_task_completed_patch_increases_trust_and_obedience():
    patch = roleplay_patch_for_event(_state(), event_type="task_completed", task_title="Status sauber melden")
    assert patch is not None
    assert patch["relationship"]["trust"] == 57
    assert patch["relationship"]["obedience"] == 52
    assert patch["scene"]["pressure"] == "niedrig"


def test_task_failed_patch_raises_strictness_and_frustration():
    patch = roleplay_patch_for_event(_state(), event_type="task_failed", task_title="Abendritual")
    assert patch is not None
    assert patch["relationship"]["strictness"] == 70
    assert patch["relationship"]["frustration"] == 20
    assert "Kontrolle" in patch["scene"]["last_consequence"]


def test_game_report_patch_rewards_clean_success():
    patch = roleplay_patch_for_event(
        _state(),
        event_type="game_report",
        passed_steps=8,
        failed_steps=0,
        miss_count=0,
        scheduled_steps=8,
    )
    assert patch is not None
    assert patch["relationship"]["trust"] == 58
    assert patch["relationship"]["obedience"] == 53
    assert patch["scene"]["pressure"] == "niedrig"


def test_game_report_patch_penalizes_poor_run():
    patch = roleplay_patch_for_event(
        _state(),
        event_type="game_report",
        passed_steps=1,
        failed_steps=4,
        miss_count=3,
        scheduled_steps=6,
    )
    assert patch is not None
    assert patch["relationship"]["strictness"] == 70
    assert patch["relationship"]["frustration"] == 21
    assert patch["scene"]["pressure"] == "hoch"


def test_roleplay_defaults_can_be_overridden_by_behavior_profile():
    state = build_roleplay_state(
        None,
        None,
        None,
        scenario_title="Test Scenario",
        behavior_profile={
            "roleplay_defaults": {
                "relationship": {"strictness": 80, "control_level": "ritual"},
                "protocol": {"active_rules": ["Nur knapp reporten"]},
                "scene": {"next_beat": "Sofort kurze Rueckmeldung einfordern"},
            }
        },
    )
    assert state["relationship"]["strictness"] == 80
    assert state["relationship"]["control_level"] == "ritual"
    assert state["protocol"]["active_rules"] == ["Nur knapp reporten"]
    assert state["scene"]["next_beat"] == "Sofort kurze Rueckmeldung einfordern"


def test_progression_profile_can_override_task_failure_deltas_and_scene_copy():
    patch = roleplay_patch_for_event(
        _state(),
        event_type="task_failed",
        task_title="Abendritual",
        behavior_profile={
            "progression": {
                "events": {
                    "task_failed": {
                        "relationship_deltas": {"trust": -5, "strictness": 4},
                        "scene": {
                            "pressure": "hoch",
                            "last_consequence": "Sofortiges Nachfassen.",
                            "next_beat": "Kurzen Re-Check verlangen.",
                        },
                    }
                }
            }
        },
    )
    assert patch is not None
    assert patch["relationship"]["trust"] == 50
    assert patch["relationship"]["strictness"] == 72
    assert patch["scene"]["pressure"] == "hoch"
    assert patch["scene"]["last_consequence"] == "Sofortiges Nachfassen."
