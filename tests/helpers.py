import json
from datetime import UTC, datetime
from uuid import uuid4

from chastease.models import ChastitySession


def register_user(client, username="reg-user", password="demo-pass-123") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert response.status_code == 200
    return response.json()


def create_active_session(client, auth: dict, **start_overrides) -> str:
    payload = {"user_id": auth["user_id"], "auth_token": auth["auth_token"], "language": "en"}
    payload.update(start_overrides)
    start = client.post("/api/v1/setup/sessions", json=payload)
    assert start.status_code == 200
    sid = start.json()["setup_session_id"]
    answers = client.post(
        f"/api/v1/setup/sessions/{sid}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 5},
                {"question_id": "q5_novelty_challenge", "value": 7},
                {"question_id": "q6_intensity_1_5", "value": 4},
            ]
        },
    )
    assert answers.status_code == 200
    answers_data = answers.json()

    session_id = str(uuid4())
    db = client.app.state.db_session_factory()
    try:
        db.add(
            ChastitySession(
                id=session_id,
                user_id=auth["user_id"],
                character_id=None,
                status="active",
                language=str(payload.get("language") or "en"),
                policy_snapshot_json=json.dumps(answers_data["policy_preview"]),
                psychogram_snapshot_json=json.dumps(answers_data["psychogram_preview"]),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()
    return session_id


def update_session_snapshots(client, session_id: str, *, policy=None, psychogram=None) -> None:
    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        if policy is not None:
            session.policy_snapshot_json = json.dumps(policy)
        if psychogram is not None:
            session.psychogram_snapshot_json = json.dumps(psychogram)
        session.updated_at = datetime.now(UTC)
        db.add(session)
        db.commit()
    finally:
        db.close()
