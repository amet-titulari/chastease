from app.schemas.ai_actions import normalize_action_payloads


def test_normalize_action_payloads_drops_invalid_and_coerces_valid_items():
    actions = normalize_action_payloads(
        [
            {"type": "unknown_action", "foo": "bar"},
            {"type": "create_task", "title": "", "deadline_minutes": "abc"},
            {"type": "create_task", "title": "Task A", "deadline_minutes": "15"},
            {"type": "update_task", "task_id": "42", "deadline_minutes": "30", "title": "New title"},
            {"type": "fail_task", "task_id": "7"},
            {"type": "update_roleplay_state", "scene": {"title": "Inspection"}, "relationship": {"obedience": 73}},
        ]
    )

    assert actions == [
        {"type": "create_task", "title": "Task A", "description": "", "deadline_minutes": 15},
        {"type": "update_task", "task_id": 42, "title": "New title", "deadline_minutes": 30},
        {"type": "fail_task", "task_id": 7},
        {"type": "update_roleplay_state", "scene": {"title": "Inspection"}, "relationship": {"obedience": 73}},
    ]
