from datetime import UTC, datetime
from uuid import uuid4

from chastease.domains.roleplay import build_roleplay_context, build_setup_preview_roleplay_context, to_story_turn_context
from chastease.models import ChastitySession, Turn


def _register_and_complete_setup(client, username="roleplay-user", email=None):
    auth_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "display_name": username,
            "password": "demo-pass-123",
        },
    )
    assert auth_response.status_code == 200
    user_id = auth_response.json()["user_id"]
    auth_token = auth_response.json()["auth_token"]
    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth_token, "language": "en"},
    )
    assert setup_response.status_code == 200
    setup_id = setup_response.json()["setup_session_id"]

    client.post(
        f"/api/v1/setup/sessions/{setup_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 5},
                {"question_id": "q5_novelty_challenge", "value": 7},
                {"question_id": "q6_intensity_1_5", "value": 4},
                {"question_id": "q8_instruction_style", "value": "mixed"},
                {"question_id": "q9_open_context", "value": "Ready."},
            ]
        },
    )
    complete_response = client.post(f"/api/v1/setup/sessions/{setup_id}/complete")
    assert complete_response.status_code == 200
    session_id = complete_response.json()["chastity_session"]["session_id"]
    return user_id, session_id


def test_build_setup_preview_roleplay_context_includes_tools_and_scene_state(client):
    context = build_setup_preview_roleplay_context(
        client.app,
        action="Preview the scenario.",
        language="en",
        psychogram={"summary": "calm and curious"},
        policy={
            "hard_stop_enabled": True,
            "roleplay": {
                "character_card": {
                    "card_id": "preview-card",
                    "display_name": "Preview Keyholder",
                    "persona": {
                        "name": "Preview Keyholder",
                        "archetype": "keyholder",
                        "description": "Preview persona",
                        "goals": ["hold continuity"],
                        "speech_style": {"tone": "balanced", "dominance_style": "moderate"},
                    },
                },
                "scenario": {
                    "scenario_id": "preview-scenario",
                    "title": "Preview Scenario",
                    "summary": "Scenario preview",
                },
                "prompt_profile": {"name": "preview", "version": "v2", "mode": "preview"},
            },
        },
    )

    assert context.session_id == "setup-preview"
    assert context.scene_state is not None
    assert context.scene_state.phase == "preview"
    assert context.tools_summary is not None
    assert "execute=" in context.tools_summary
    assert context.character_card is not None
    assert context.character_card.display_name == "Preview Keyholder"
    assert context.scenario is not None
    assert context.scenario.scenario_id == "preview-scenario"
    assert context.prompt_profile.name == "preview"
    story_context = to_story_turn_context(context)
    assert story_context.session_id == "setup-preview"
    assert story_context.tools_summary == context.tools_summary


def test_build_roleplay_context_preserves_history_and_live_snapshot(client):
    _, session_id = _register_and_complete_setup(client, username="roleplay-history-user")
    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        db.add(
            Turn(
                id=str(uuid4()),
                session_id=session_id,
                turn_no=1,
                player_action="I kneel and wait.",
                ai_narration="Remain still and attentive.",
                language="en",
                created_at=datetime.now(UTC),
            )
        )
        db.commit()

        context = build_roleplay_context(
            db,
            client.app,
            session,
            "I report back.",
            "en",
            history_turn_limit=3,
            include_tools_summary=True,
            live_snapshot_builder=lambda current_session: {"session_id": current_session.id, "status": current_session.status},
        )
    finally:
        db.close()

    assert context.session_id == session_id
    assert context.turns_history
    assert context.turns_history[0].player_action == "I kneel and wait."
    assert context.live_snapshot == {"session_id": session_id, "status": "active"}
    assert "hard_stop=" in context.psychogram_summary
    assert context.character_card is not None
    assert context.character_card.display_name
    assert context.scenario is not None
    assert context.prompt_profile.name == "roleplay-session"

    story_context = to_story_turn_context(context)
    assert len(story_context.turns_history) == 1
    assert story_context.turns_history[0].ai_narration == "Remain still and attentive."
    assert story_context.live_snapshot == context.live_snapshot