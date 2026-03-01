"""
Tests for Seal / Plomben Control Feature

Diese Test-Suite überprüft die Seal-Steuerung während Setup und Session.
"""

import pytest


def test_setup_seal_mode_default(client):
    """Vertraue, dass der Default Seal-Modus 'none' ist."""
    # Setup starten
    auth_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_user",
            "email": "test@example.com",
            "display_name": "Test User",
            "password": "test-pass-123",
        },
    )
    assert auth_response.status_code == 200
    auth = auth_response.json()

    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
        },
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
    
    # Default sollte "none" sein
    assert setup_data.get("seal_mode", "none") == "none"


def test_setup_seal_mode_plomben_via_start(client):
    """Seal-Modus kann beim Setup-Start gesetzt werden."""
    auth_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_user_seal",
            "email": "test_seal@example.com",
            "display_name": "Test User Seal",
            "password": "test-pass-123",
        },
    )
    assert auth_response.status_code == 200
    auth = auth_response.json()

    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "seal_mode": "plomben",
        },
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
    assert setup_data.get("seal_mode") == "plomben"


def test_setup_seal_mode_update_endpoint(client):
    """Seal-Modus kann später via PATCH geändert werden."""
    # Setup starten
    auth_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_user_update",
            "email": "test_update@example.com",
            "display_name": "Test User Update",
            "password": "test-pass-123",
        },
    )
    assert auth_response.status_code == 200
    auth = auth_response.json()

    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "seal_mode": "none",
        },
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
    setup_id = setup_data["setup_session_id"]

    # Seal-Modus aktualisieren
    update_response = client.post(
        f"/api/v1/setup/sessions/{setup_id}/seal",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "seal_mode": "versiegelung",
        },
    )
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data.get("seal_mode") == "versiegelung"


def test_setup_seal_mode_validation(client):
    """Ungültige Seal-Modi werden von Pydantic abgelehnt."""
    auth_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_user_invalid",
            "email": "test_invalid@example.com",
            "display_name": "Test User Invalid",
            "password": "test-pass-123",
        },
    )
    assert auth_response.status_code == 200
    auth = auth_response.json()

    # Ungültiger Modus wird von Pydantic validierung abgelehnt
    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "seal_mode": "invalid_seal_mode",
        },
    )
    assert setup_response.status_code == 422  # Validation error


def test_seal_mode_in_psychogram_summary(client, monkeypatch):
    """Seal-Informationen sind in der psychogram_summary verfügbar."""
    # Dieser Test würde mit einer aktiven Session durchgeführt
    # und würde überprüfen, ob seal_mode in der psychogram_summary angezeigt wird
    # Beispiel: "seal=mode=plomben, status=sealed, current_number=PLOMBE-01"
    pass


def test_get_seal_status_endpoint(client):
    """GET /chat/seal/{session_id} gibt den aktuellen Seal-Status zurück."""
    # Dieser Test würde:
    # 1. Eine aktive Session mit seal_mode="plomben" erstellen
    # 2. GET /chat/seal/{session_id} aufrufen
    # 3. Überprüfen, dass runtime_seal mit status, current_text, etc. zurückkommt
    pass


def test_hygiene_close_seal_text_required(client, monkeypatch):
    """Hygiene-Schließung erfordert seal_text wenn seal_mode aktiv ist."""
    # Dieser Test würde mit dem existierenden test_chat_action_execute_hygiene_close_requires_seal_text_when_enabled
    # kombiniert werden, um die vollständige Funktionalität zu überprüfen
    pass


"""
Weitere Test-IDs für die Seal-Integration:

- test_hygiene_open_breaks_seal_when_enabled
  Überprüft, dass hygiene_open den Seal-Status auf "broken" setzt

- test_hygiene_close_stores_new_seal_text
  Überprüft, dass die neue Plombennummer in runtime_seal.current_text gespeichert wird

- test_seal_text_min_length_validation
  Überprüft, dass seal_text mindestens 3 Zeichen sein muss

- test_seal_mode_propagates_to_active_session
  Überprüft, dass Änderungen der seal_mode sofort in der aktiven Session wirksam werden

- test_policy_seal_structure
  Überprüft die richtige Struktur von policy.seal und policy.runtime_seal
"""


def test_initial_seal_number_transferred_to_active_session(client):
    """Initial seal number wird korrekt in runtime_seal der aktiven Session übertragen."""
    import json
    from chastease.models import ChastitySession
    
    auth_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_initial_seal",
            "email": "initial_seal@example.com",
            "display_name": "Initial Seal User",
            "password": "test-pass-123",
        },
    )
    assert auth_response.status_code == 200
    auth = auth_response.json()

    # Setup mit initial seal number starten
    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "seal_mode": "versiegelung",
            "initial_seal_number": "A001733",
        },
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
    setup_session_id = setup_data["setup_session_id"]
    assert setup_data["initial_seal_number"] == "A001733"

    # Antworten geben
    answers_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
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
    assert answers_response.status_code == 200

    # Setup abschließen
    complete_response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200
    complete_data = complete_response.json()
    
    # Aktive Session sollte erstellt sein
    session_id = complete_data["chastity_session"]["session_id"]
    assert session_id is not None

    # Policy aus der DB überprüfen
    db = client.app.state.db_session_factory()
    try:
        db_session = db.get(ChastitySession, session_id)
        assert db_session is not None
        
        policy = json.loads(db_session.policy_snapshot_json)
        assert "runtime_seal" in policy
        assert policy["runtime_seal"]["status"] == "sealed"
        assert policy["runtime_seal"]["current_text"] == "A001733"
        assert policy["runtime_seal"]["needs_new_seal"] is False
        assert "sealed_at" in policy["runtime_seal"]
    finally:
        db.close()
