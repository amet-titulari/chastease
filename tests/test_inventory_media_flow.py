from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient):
    unique = uuid4().hex[:8]
    return client.post(
        "/auth/register",
        data={
            "username": f"inv-{unique}",
            "email": f"inv-{unique}@example.com",
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )


def test_inventory_catalog_scenario_and_session_flow():
    unique = uuid4().hex[:8]
    item_key = f"test_item_{unique}"
    scenario_key = f"test_scenario_{unique}"

    with TestClient(app) as client:
        register_resp = _register(client)
        assert register_resp.status_code == 303

        create_item = client.post(
            "/api/inventory/items",
            json={
                "key": item_key,
                "name": "Test Cage",
                "category": "device",
                "tags": ["test", "cage"],
            },
        )
        assert create_item.status_code == 200
        item_id = create_item.json()["id"]

        create_scenario = client.post(
            "/api/scenarios",
            json={
                "title": f"Scenario {unique}",
                "key": scenario_key,
                "summary": "Scenario with inventory",
                "lorebook": [],
                "phases": [],
                "tags": ["test"],
            },
        )
        assert create_scenario.status_code == 200
        scenario_id = create_scenario.json()["id"]

        replace_scenario_inventory = client.put(
            f"/api/inventory/scenarios/{scenario_id}/items",
            json={
                "entries": [
                    {
                        "item_id": item_id,
                        "is_required": True,
                        "default_quantity": 1,
                        "notes": "Baseline gear",
                    }
                ]
            },
        )
        assert replace_scenario_inventory.status_code == 200
        assert len(replace_scenario_inventory.json()["items"]) == 1

        create_session = client.post(
            "/api/sessions",
            json={
                "persona_name": f"Persona {unique}",
                "player_nickname": f"Player {unique}",
                "min_duration_seconds": 600,
            },
        )
        assert create_session.status_code == 200
        session_id = create_session.json()["session_id"]

        add_session_item = client.post(
            f"/api/inventory/sessions/{session_id}/items",
            json={
                "item_id": item_id,
                "quantity": 1,
                "status": "available",
                "is_equipped": False,
            },
        )
        assert add_session_item.status_code == 200
        payload = add_session_item.json()
        assert payload["session_id"] == session_id
        assert payload["item"]["id"] == item_id


def test_avatar_upload_and_assignment_to_persona_and_player():
    unique = uuid4().hex[:8]

    with TestClient(app) as client:
        register_resp = _register(client)
        assert register_resp.status_code == 303

        upload = client.post(
            "/api/media/avatar",
            files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\n", "image/png")},
            data={"visibility": "private"},
        )
        assert upload.status_code == 200
        media = upload.json()
        media_id = media["id"]

        create_persona = client.post(
            "/api/personas",
            json={
                "name": f"Avatar Persona {unique}",
                "strictness_level": 3,
                "avatar_media_id": media_id,
            },
        )
        assert create_persona.status_code == 200
        persona_payload = create_persona.json()
        assert persona_payload["avatar_media_id"] == media_id
        assert persona_payload["avatar_url"] == f"/api/media/{media_id}/content"

        create_session = client.post(
            "/api/sessions",
            json={
                "persona_name": persona_payload["name"],
                "player_nickname": f"Avatar Player {unique}",
                "min_duration_seconds": 600,
            },
        )
        assert create_session.status_code == 200
        session_id = create_session.json()["session_id"]

        update_player = client.put(
            f"/api/sessions/{session_id}/player-profile",
            json={"avatar_media_id": media_id},
        )
        assert update_player.status_code == 200
        player_payload = update_player.json()["player_profile"]
        assert player_payload["avatar_media_id"] == media_id

        media_content = client.get(f"/api/media/{media_id}/content")
        assert media_content.status_code == 200
        assert media_content.headers["content-type"].startswith("image/png")


def test_inventory_item_export_and_import_flow():
    unique = uuid4().hex[:8]

    with TestClient(app) as client:
        register_resp = _register(client)
        assert register_resp.status_code == 303

        create_item = client.post(
            "/api/inventory/items",
            json={
                "key": f"export_item_{unique}",
                "name": f"Export Item {unique}",
                "category": "device",
                "description": "Export test item",
                "tags": ["export", "test"],
                "is_active": True,
            },
        )
        assert create_item.status_code == 200
        item_id = create_item.json()["id"]

        export_one = client.get(f"/api/inventory/items/{item_id}/export")
        assert export_one.status_code == 200
        card = export_one.json()
        assert card["kind"] == "item_card"
        assert card["name"].startswith("Export Item")

        export_all = client.get("/api/inventory/items/export")
        assert export_all.status_code == 200
        collection = export_all.json()
        assert collection["kind"] == "item_collection"
        assert any(row.get("key") == card["key"] for row in collection.get("items", []))

        imported = client.post("/api/inventory/items/import", json={"card": card})
        assert imported.status_code == 200
        imported_payload = imported.json()
        assert imported_payload["name"] == card["name"]
        assert imported_payload["key"] != card["key"]
