import io
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _ppm_bytes(width: int, height: int, rgb: tuple[int, int, int] = (128, 128, 128)) -> bytes:
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    pixel = bytes([rgb[0], rgb[1], rgb[2]])
    return header + (pixel * (width * height))


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Game Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_list_game_modules_contains_posture_training():
    with TestClient(app) as client:
        resp = client.get("/api/games/modules")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(item["key"] == "posture_training" for item in items)


def test_start_game_run_and_fetch_state():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "easy",
                "duration_minutes": 10,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 120,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["module_key"] == "posture_training"
        assert body["difficulty"] == "easy"
        assert body["status"] == "active"
        assert body["transition_seconds"] == 8
        assert body["current_step"] is not None

        run_id = body["id"]
        run_resp = client.get(f"/api/games/runs/{run_id}")
        assert run_resp.status_code == 200
        run = run_resp.json()
        assert run["id"] == run_id
        assert run["status"] == "active"
        assert len(run["steps"]) >= 1

def test_verify_step_with_photo_advances_or_retries():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)
        start = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 10,
                "max_misses_before_penalty": 1,
                "session_penalty_seconds": 60,
            },
        )
        assert start.status_code == 200
        run = start.json()
        run_id = run["id"]
        step_id = run["current_step"]["id"]

        verify = client.post(
            f"/api/games/runs/{run_id}/steps/{step_id}/verify",
            files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
            data={"observed_posture": run["current_step"]["posture_name"]},
        )
        assert verify.status_code == 200
        payload = verify.json()
        assert payload["run"]["id"] == run_id
        assert payload["step"]["status"] in {"passed", "failed"}


def test_game_verification_capture_is_saved_under_session_and_run_timestamp_folder():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)
        start = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 10,
                "max_misses_before_penalty": 1,
                "session_penalty_seconds": 60,
            },
        )
        assert start.status_code == 200
        run = start.json()
        run_id = run["id"]
        step_id = run["current_step"]["id"]

        verify = client.post(
            f"/api/games/runs/{run_id}/steps/{step_id}/verify",
            files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
            data={"observed_posture": run["current_step"]["posture_name"]},
        )
        assert verify.status_code == 200
        payload = verify.json()
        capture_path = (payload.get("step") or {}).get("capture_path") or ""
        assert capture_path.startswith(f"verifications/games/{session_id}/")
        run_segment = capture_path.split("/")[3]
        assert run_segment.startswith(f"{run_id}-")

        full_path = Path(settings.media_dir) / capture_path
        assert full_path.is_file()


def test_start_game_run_accepts_custom_transition_seconds():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 10,
                "transition_seconds": 12,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 120,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["transition_seconds"] == 12


def test_posture_management_crud_and_run_uses_managed_postures():
    with TestClient(app) as client:
        created = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "title": "Wandhaltung",
                "image_url": "/static/img/postures/wall.jpg",
                "instruction": "Ruecken an die Wand und stabil bleiben.",
                "target_seconds": 75,
                "sort_order": 1,
                "is_active": True,
            },
        )
        assert created.status_code == 200
        posture = created.json()
        posture_id = posture["id"]
        assert posture["title"] == "Wandhaltung"

        listed = client.get("/api/games/modules/posture_training/postures")
        assert listed.status_code == 200
        assert any(item["id"] == posture_id for item in listed.json()["items"])

        updated = client.put(
            f"/api/games/modules/posture_training/postures/{posture_id}",
            json={
                "title": "Wandhaltung Plus",
                "target_seconds": 80,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Wandhaltung Plus"
        assert updated.json()["target_seconds"] == 80

        session_id = _create_and_sign(client)
        started = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "easy",
                "duration_minutes": 10,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 120,
            },
        )
        assert started.status_code == 200
        run_id = started.json()["id"]
        run_detail = client.get(f"/api/games/runs/{run_id}")
        assert run_detail.status_code == 200
        names = [step["posture_name"] for step in run_detail.json()["steps"]]
        assert "Wandhaltung Plus" in names

        deleted = client.delete(f"/api/games/modules/posture_training/postures/{posture_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] == posture_id


def test_upload_posture_image_returns_content_url():
    with TestClient(app) as client:
        img = _ppm_bytes(768, 1024)
        uploaded = client.post(
            "/api/games/modules/posture_training/postures/upload-image",
            files={"file": ("pose.jpg", img, "image/jpeg")},
        )
        assert uploaded.status_code == 200
        payload = uploaded.json()
        assert payload["media_kind"] == "game_posture"
        assert payload["content_url"].startswith("/api/media/")


def test_upload_posture_image_rejects_too_small_resolution():
    with TestClient(app) as client:
        small = _ppm_bytes(320, 480)
        uploaded = client.post(
            "/api/games/modules/posture_training/postures/upload-image",
            files={"file": ("small.jpg", small, "image/jpeg")},
        )
        assert uploaded.status_code == 422
        assert "resolution too small" in (uploaded.json().get("detail") or "").lower()


def test_uploaded_posture_image_url_can_be_persisted_on_posture():
    with TestClient(app) as client:
        created = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "title": "Upload Test",
                "image_url": "/static/img/postures/upload-test.jpg",
                "instruction": "Bild testen",
                "target_seconds": 60,
                "sort_order": 55,
                "is_active": True,
            },
        )
        assert created.status_code == 200
        posture_id = created.json()["id"]

        img = _ppm_bytes(768, 1024, rgb=(64, 90, 120))
        uploaded = client.post(
            "/api/games/modules/posture_training/postures/upload-image",
            files={"file": ("pose.png", img, "image/png")},
        )
        assert uploaded.status_code == 200
        image_url = uploaded.json()["content_url"]

        updated = client.put(
            f"/api/games/modules/posture_training/postures/{posture_id}",
            json={"image_url": image_url},
        )
        assert updated.status_code == 200
        assert updated.json()["image_url"] == image_url


def test_posture_zip_export_and_import_roundtrip_with_images():
    with TestClient(app) as client:
        existing = client.get("/api/games/modules/posture_training/postures")
        assert existing.status_code == 200
        for row in existing.json().get("items") or []:
            removed = client.delete(f"/api/games/modules/posture_training/postures/{row['id']}")
            assert removed.status_code == 200

        img_a = _ppm_bytes(768, 1024, rgb=(20, 60, 120))
        up_a = client.post(
            "/api/games/modules/posture_training/postures/upload-image",
            files={"file": ("pose-a.png", img_a, "image/png")},
        )
        assert up_a.status_code == 200
        image_a = up_a.json()["content_url"]

        img_b = _ppm_bytes(800, 1100, rgb=(90, 140, 30))
        up_b = client.post(
            "/api/games/modules/posture_training/postures/upload-image",
            files={"file": ("pose-b.jpg", img_b, "image/jpeg")},
        )
        assert up_b.status_code == 200
        image_b = up_b.json()["content_url"]

        create_a = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "title": "ZIP Export A",
                "image_url": image_a,
                "instruction": "A halten",
                "target_seconds": 90,
                "sort_order": 1,
                "is_active": True,
            },
        )
        create_b = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "title": "ZIP Export B",
                "image_url": image_b,
                "instruction": "B halten",
                "target_seconds": 120,
                "sort_order": 2,
                "is_active": False,
            },
        )
        assert create_a.status_code == 200
        assert create_b.status_code == 200

        exported = client.get("/api/games/modules/posture_training/postures/export")
        assert exported.status_code == 200
        assert exported.headers.get("content-type", "").startswith("application/zip")

        archive = zipfile.ZipFile(io.BytesIO(exported.content), mode="r")
        names = archive.namelist()
        assert "manifest.json" in names
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest.get("format") == "chastease-postures-v1"
        assert len(manifest.get("postures") or []) == 2
        assert any(name.startswith("images/") for name in names)

        listed_before = client.get("/api/games/modules/posture_training/postures")
        assert listed_before.status_code == 200
        for item in listed_before.json().get("items") or []:
            deleted = client.delete(f"/api/games/modules/posture_training/postures/{item['id']}")
            assert deleted.status_code == 200

        listed_empty = client.get("/api/games/modules/posture_training/postures")
        assert listed_empty.status_code == 200
        assert listed_empty.json().get("items") == []

        imported = client.post(
            "/api/games/modules/posture_training/postures/import-zip",
            files={"file": ("postures.zip", exported.content, "application/zip")},
        )
        assert imported.status_code == 200
        assert imported.json()["imported"] == 2

        listed_after = client.get("/api/games/modules/posture_training/postures")
        assert listed_after.status_code == 200
        items = listed_after.json().get("items") or []
        assert len(items) == 2
        titles = {item["title"] for item in items}
        assert "ZIP Export A" in titles
        assert "ZIP Export B" in titles
        assert all((item.get("image_url") or "").startswith("/api/media/") for item in items)


def test_posture_zip_import_rejects_missing_local_image_file_reference():
    with TestClient(app) as client:
        manifest = {
            "format": "chastease-postures-v1",
            "module_key": "posture_training",
            "postures": [
                {
                    "posture_key": "broken_local_ref",
                    "title": "Broken Local Ref",
                    "instruction": "test",
                    "target_seconds": 90,
                    "sort_order": 1,
                    "is_active": True,
                    "image_url": "/api/media/999999/content",
                }
            ],
        }
        archive_io = io.BytesIO()
        with zipfile.ZipFile(archive_io, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True))

        imported = client.post(
            "/api/games/modules/posture_training/postures/import-zip",
            files={"file": ("broken.zip", archive_io.getvalue(), "application/zip")},
        )
        assert imported.status_code == 422
        detail = imported.json().get("detail") or ""
        assert "lokale bild-url" in detail.lower()


def test_difficulty_uses_medium_baseline_target_with_multipliers():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        medium_run = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 8,
                "easy_target_multiplier": 0.5,
                "hard_target_multiplier": 1.5,
                "target_randomization_percent": 0,
            },
        )
        assert medium_run.status_code == 200
        base_target = medium_run.json()["current_step"]["target_seconds"]

        easy_run = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "easy",
                "duration_minutes": 8,
                "easy_target_multiplier": 0.5,
                "hard_target_multiplier": 1.5,
                "target_randomization_percent": 0,
            },
        )
        assert easy_run.status_code == 200
        easy_target = easy_run.json()["current_step"]["target_seconds"]

        hard_run = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "hard",
                "duration_minutes": 8,
                "easy_target_multiplier": 0.5,
                "hard_target_multiplier": 1.5,
                "target_randomization_percent": 0,
            },
        )
        assert hard_run.status_code == 200
        hard_target = hard_run.json()["current_step"]["target_seconds"]

        assert easy_target == max(1, int(round(base_target * 0.5)))
        assert hard_target == max(1, int(round(base_target * 1.5)))


def test_target_randomization_applies_within_expected_bounds():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        baseline_run = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 8,
                "target_randomization_percent": 0,
            },
        )
        assert baseline_run.status_code == 200
        baseline_target = baseline_run.json()["current_step"]["target_seconds"]

        randomized_run = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 8,
                "target_randomization_percent": 20,
            },
        )
        assert randomized_run.status_code == 200
        randomized_target = randomized_run.json()["current_step"]["target_seconds"]

        lower = max(1, int(round(baseline_target * 0.8)))
        upper = max(lower, int(round(baseline_target * 1.2)))
        assert lower <= randomized_target <= upper


def test_sort_order_zero_is_allowed_and_used_for_run_steps():
    with TestClient(app) as client:
        created_a = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "title": "Random A",
                "image_url": "/static/img/postures/random-a.jpg",
                "instruction": "A",
                "target_seconds": 30,
                "sort_order": 0,
                "is_active": True,
            },
        )
        created_b = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "title": "Random B",
                "image_url": "/static/img/postures/random-b.jpg",
                "instruction": "B",
                "target_seconds": 30,
                "sort_order": 0,
                "is_active": True,
            },
        )
        assert created_a.status_code == 200
        assert created_b.status_code == 200
        assert created_a.json()["sort_order"] == 0
        assert created_b.json()["sort_order"] == 0

        session_id = _create_and_sign(client)
        started = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 6,
            },
        )
        assert started.status_code == 200
        run = client.get(f"/api/games/runs/{started.json()['id']}")
        assert run.status_code == 200
        steps = run.json()["steps"]
        assert len(steps) >= 2


def test_module_settings_can_be_saved_and_used_for_run_start_defaults():
    with TestClient(app) as client:
        saved = client.put(
            "/api/games/modules/posture_training/settings",
            json={
                "easy_target_multiplier": 0.6,
                "hard_target_multiplier": 1.4,
                "target_randomization_percent": 0,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["easy_target_multiplier"] == 0.6
        assert saved.json()["hard_target_multiplier"] == 1.4
        assert saved.json()["target_randomization_percent"] == 0

        read_back = client.get("/api/games/modules/posture_training/settings")
        assert read_back.status_code == 200
        assert read_back.json()["easy_target_multiplier"] == 0.6

        session_id = _create_and_sign(client)
        medium = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 6,
            },
        )
        assert medium.status_code == 200
        base = medium.json()["current_step"]["target_seconds"]

        easy = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "easy",
                "duration_minutes": 6,
            },
        )
        assert easy.status_code == 200
        easy_target = easy.json()["current_step"]["target_seconds"]
        assert easy_target == max(1, int(round(base * 0.6)))
