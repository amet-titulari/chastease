from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_session_starts_only_after_contract_signature():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Test Persona",
                "player_nickname": "Tester",
                "min_duration_seconds": 300,
                "max_duration_seconds": 600,
                "hard_limits": ["public play"],
                "contract_keyholder_title": "Mistress",
                "contract_wearer_title": "pet",
                "contract_goal": "Klare Fuehrung und kontrollierte Enthaltsamkeit.",
                "contract_method": "psychologische Keuschhaltung",
                "contract_touch_rules": "Keine Stimulation ohne Erlaubnis.",
            },
        )
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert data["status"] == "draft"
        assert data["contract_required"] is True
        assert "KEUSCHHEITS-VERTRAG" in data["contract_preview"]
        assert "Test Persona" in data["contract_preview"]
        assert "Mistress" in data["contract_preview"]
        assert "Keine Stimulation ohne Erlaubnis." in data["contract_preview"]
        assert "Hard Limits: public play" in data["contract_preview"]

        sign_resp = client.post(f"/api/sessions/{data['session_id']}/sign-contract")
        assert sign_resp.status_code == 200
        signed = sign_resp.json()
        assert signed["status"] == "active"


def test_session_sign_uses_duration_within_min_max(monkeypatch):
    monkeypatch.setattr("app.services.session_service.random.randint", lambda low, high: 451)

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Test Persona",
                "player_nickname": "Tester",
                "min_duration_seconds": 300,
                "max_duration_seconds": 600,
            },
        )
        session_id = create_resp.json()["session_id"]

        sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert sign_resp.status_code == 200
        signed = sign_resp.json()
        lock_end = datetime.fromisoformat(signed["lock_end"])

        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        lock_start = datetime.fromisoformat(detail["lock_start"])

        assert int((lock_end - lock_start).total_seconds()) == 451


def test_contract_addendum_consent_flow():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "Reduce minimum duration",
                "proposed_changes": {"min_duration_seconds": 240},
            },
        )
        assert propose_resp.status_code == 200
        addendum_id = propose_resp.json()["addendum_id"]

        consent_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda/{addendum_id}/consent",
            json={"decision": "approved"},
        )
        assert consent_resp.status_code == 200
        assert consent_resp.json()["decision"] == "approved"
        assert consent_resp.json()["consent_tier"] == "standard"


def test_active_contract_addendum_clamps_duration_only_when_outside_new_range(monkeypatch):
    monkeypatch.setattr("app.services.session_service.random.randint", lambda low, high: 540)

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert sign_resp.status_code == 200

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "Tighten max duration but keep current run valid",
                "proposed_changes": {"max_duration_seconds": 600},
            },
        )
        addendum_id = propose_resp.json()["addendum_id"]
        consent_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda/{addendum_id}/consent",
            json={"decision": "approved"},
        )
        assert consent_resp.status_code == 200

        detail = client.get(f"/api/sessions/{session_id}").json()
        lock_start = datetime.fromisoformat(detail["lock_start"])
        lock_end = datetime.fromisoformat(detail["lock_end"])
        assert int((lock_end - lock_start).total_seconds()) == 540


def test_contract_view_and_export_endpoints():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "Reduce minimum duration",
                "proposed_changes": {"min_duration_seconds": 240},
            },
        )
        addendum_id = propose_resp.json()["addendum_id"]
        client.post(
            f"/api/sessions/{session_id}/contract/addenda/{addendum_id}/consent",
            json={"decision": "approved"},
        )

        view_resp = client.get(f"/api/sessions/{session_id}/contract")
        assert view_resp.status_code == 200
        payload = view_resp.json()
        assert payload["session_id"] == session_id
        assert "KEUSCHHEITS-VERTRAG" in payload["contract"]["content_text"]
        assert "Vertragsbeginn:" in payload["contract"]["content_text"]
        assert "Mindestbindung bis:" in payload["contract"]["content_text"]
        assert len(payload["addenda"]) >= 1

        export_text = client.get(f"/api/sessions/{session_id}/contract/export?format=text")
        assert export_text.status_code == 200
        assert "ADDENDA" in export_text.text

        export_json = client.get(f"/api/sessions/{session_id}/contract/export?format=json")
        assert export_json.status_code == 200
        export_payload = export_json.json()
        assert export_payload["session_id"] == session_id
        assert export_payload["addenda"][0]["effect_summary"]
        assert export_payload["addenda"][0]["validated_changes"]["min_duration_seconds"] == 240


def test_contract_addendum_rejects_direct_time_manipulation_requests():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "Bitte direkt 10 Tage drauf",
                "proposed_changes": {"extend_lock_by_seconds": 864000},
            },
        )
        assert propose_resp.status_code == 400
        assert "Unsupported addendum fields" in propose_resp.json()["detail"]


def test_contract_addendum_can_update_hygiene_and_penalty_policy():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "Adjust hygiene and penalties",
                "proposed_changes": {
                    "hygiene_limit_daily": 2,
                    "hygiene_opening_max_duration_seconds": 1800,
                    "penalty_multiplier": 1.6,
                    "default_penalty_seconds": 1800,
                    "max_penalty_seconds": 7200,
                },
            },
        )
        assert propose_resp.status_code == 200
        addendum_id = propose_resp.json()["addendum_id"]

        consent_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda/{addendum_id}/consent",
            json={"decision": "approved"},
        )
        assert consent_resp.status_code == 200
        assert consent_resp.json()["decision"] == "approved"

        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        session_data = detail_resp.json()
        assert session_data["hygiene_limit_daily"] == 2
        assert session_data["hygiene_opening_max_duration_seconds"] == 1800

        reaction = session_data["player_profile"]["reaction_patterns"]
        assert reaction["penalty_multiplier"] == 1.6
        assert reaction["default_penalty_seconds"] == 1800
        assert reaction["max_penalty_seconds"] == 7200


def test_contract_addendum_can_update_protocol_rules_and_orders():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "New protocol expectations",
                "proposed_changes": {
                    "active_rules_add": ["Rueckfragen kurz und ehrlich beantworten"],
                    "active_rules_remove": ["Status klar und wahrheitsgemass melden"],
                    "open_orders_add": ["Heute Abend um 21:00 Uhr Status melden"],
                },
            },
        )
        assert propose_resp.status_code == 200
        assert propose_resp.json()["effect_summary"] == "Roleplay-Protokoll"
        addendum_id = propose_resp.json()["addendum_id"]

        consent_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda/{addendum_id}/consent",
            json={"decision": "approved"},
        )
        assert consent_resp.status_code == 200

        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        protocol = detail_resp.json()["roleplay_state"]["protocol"]
        assert "Rueckfragen kurz und ehrlich beantworten" in protocol["active_rules"]
        assert "Status klar und wahrheitsgemass melden" not in protocol["active_rules"]
        assert "Heute Abend um 21:00 Uhr Status melden" in protocol["open_orders"]


def test_contract_addendum_flags_high_impact_tightening():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 200000,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "Tighten the outer frame",
                "proposed_changes": {"max_duration_seconds": 100000},
            },
        )
        assert propose_resp.status_code == 200
        assert propose_resp.json()["consent_tier"] == "high_impact"
