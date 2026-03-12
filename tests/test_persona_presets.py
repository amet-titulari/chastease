from fastapi.testclient import TestClient

from app.main import app


def test_persona_presets_include_core_personas():
    with TestClient(app) as client:
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
        resp = client.post("/api/personas/map-card", json={"card": {"characters": []}})
        assert resp.status_code == 400
