from fastapi.testclient import TestClient
from uuid import uuid4

from app.config import settings
from app.main import app


def _register_admin(client: TestClient) -> None:
    unique = uuid4().hex[:8]
    email = f"persona-admin-{unique}@example.com"
    existing = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([item for item in [existing, email] if item])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"persona-admin-{unique}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_persona_presets_include_core_personas():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/api/personas/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        keys = {item["key"] for item in data["items"]}
        assert "ametara_titulari" in keys
        assert "iron_coach_mara" in keys
        assert "calm_guardian_lina" in keys
        ametara = next(item for item in data["items"] if item["key"] == "ametara_titulari")
        assert ametara["strictness_level"] >= 1


def test_scenario_presets_and_card_schema_exist():
    with TestClient(app) as client:
        _register_admin(client)
        scenarios = client.get("/api/personas/scenario-presets")
        assert scenarios.status_code == 200
        scenario_items = scenarios.json()["items"]
        assert any(item["key"] == "devotion_protocol" for item in scenario_items)

        schema = client.get("/api/personas/card-schema")
        assert schema.status_code == 200
        payload = schema.json()
        assert payload["schema_version"] == "0.1.2"
        assert "character_fields" in payload
        assert "scenario_fields" in payload


def test_map_external_card_payload():
    sample_card = {
        "schema_version": 1,
        "characters": [
            {
                "display_name": "Ametara Titulari",
                "persona": {
                    "name": "Ametara Titulari",
                    "description": "Warm und praezise fuehrende Persona.",
                    "goals": [
                        "Vertiefe Hingabe und Verbindung.",
                        "Halte taegliche Rituale aufrecht.",
                    ],
                    "speech_style": {
                        "tone": "warm",
                        "dominance_style": "gentle-dominant",
                        "ritual_phrases": ["Mein Lieber."],
                    },
                },
                "tags": ["keyholder", "ritual"],
            }
        ],
        "scenarios": [
            {
                "title": "Ametara Titulari Devotion Protocol",
                "summary": "Langfristige Chastity-Rahmung mit Ritualen.",
                "tags": ["devotion", "ritual"],
                "lorebook": [{"key": "session-rules", "content": "Regeln"}],
                "phases": [{"phase_id": "active", "title": "Initiierung"}],
            }
        ],
    }

    with TestClient(app) as client:
        _register_admin(client)
        resp = client.post("/api/personas/map-card", json={"card": sample_card})
        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "0.1.2"
        assert data["persona_preset"]["name"] == "Ametara Titulari"
        assert data["persona_preset"]["strictness_level"] == 3
        assert data["setup_defaults"]["role_style"] == "supportive"
        assert data["scenario_preset"]["title"] == "Ametara Titulari Devotion Protocol"


def test_map_card_requires_character_entry():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.post("/api/personas/map-card", json={"card": {"characters": []}})
        assert resp.status_code == 400


def test_persona_task_template_crud_flow():
    with TestClient(app) as client:
        _register_admin(client)
        create_persona = client.post(
            "/api/personas",
            json={
                "name": "Template Persona",
                "description": "Persona fuer Task-Bibliothek",
                "strictness_level": 3,
            },
        )
        assert create_persona.status_code == 200
        persona_id = create_persona.json()["id"]

        create_template = client.post(
            f"/api/personas/{persona_id}/task-templates",
            json={
                "title": "Morgen-Checkin",
                "description": "Skala + kurzer Statusbericht",
                "deadline_minutes": 120,
                "requires_verification": False,
                "category": "daily",
                "tags": ["morning", "checkin"],
            },
        )
        assert create_template.status_code == 200
        template_payload = create_template.json()
        assert template_payload["title"] == "Morgen-Checkin"
        assert template_payload["deadline_minutes"] == 120
        template_id = template_payload["id"]

        list_templates = client.get(f"/api/personas/{persona_id}/task-templates")
        assert list_templates.status_code == 200
        assert any(item["id"] == template_id for item in list_templates.json()["items"])

        update_template = client.put(
            f"/api/personas/{persona_id}/task-templates/{template_id}",
            json={
                "title": "Morgen-Checkin v2",
                "clear_deadline": True,
                "is_active": True,
            },
        )
        assert update_template.status_code == 200
        assert update_template.json()["title"] == "Morgen-Checkin v2"
        assert update_template.json()["deadline_minutes"] is None

        delete_template = client.delete(f"/api/personas/{persona_id}/task-templates/{template_id}")
        assert delete_template.status_code == 200
        assert delete_template.json()["deleted"] == template_id


def test_persona_task_library_export_and_cross_import():
    with TestClient(app) as client:
        _register_admin(client)
        source_persona = client.post(
            "/api/personas",
            json={
                "name": "Source Persona",
                "description": "Quelle",
                "strictness_level": 3,
            },
        )
        assert source_persona.status_code == 200
        source_id = source_persona.json()["id"]

        target_persona = client.post(
            "/api/personas",
            json={
                "name": "Target Persona",
                "description": "Ziel",
                "strictness_level": 3,
            },
        )
        assert target_persona.status_code == 200
        target_id = target_persona.json()["id"]

        create_template = client.post(
            f"/api/personas/{source_id}/task-templates",
            json={
                "title": "Abend-Report",
                "description": "Kurzer Tagesreport",
                "deadline_minutes": 180,
                "requires_verification": True,
                "verification_criteria": "Plombe und Uhrzeit sichtbar",
                "category": "daily",
                "tags": ["evening", "report"],
                "is_active": True,
            },
        )
        assert create_template.status_code == 200

        export_resp = client.get(f"/api/personas/{source_id}/task-templates/export")
        assert export_resp.status_code == 200
        library = export_resp.json()
        assert library["kind"] == "persona_task_library"
        assert len(library["templates"]) == 1
        assert library["templates"][0]["title"] == "Abend-Report"

        import_resp = client.post(
            f"/api/personas/{target_id}/task-templates/import",
            json={"library": library, "replace_existing": True},
        )
        assert import_resp.status_code == 200
        assert import_resp.json()["imported"] == 1

        target_templates = client.get(f"/api/personas/{target_id}/task-templates")
        assert target_templates.status_code == 200
        items = target_templates.json()["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Abend-Report"
        assert items[0]["requires_verification"] is True
