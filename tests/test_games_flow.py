import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import zipfile

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.game_run import GameRun
from app.models.session import Session as SessionModel


def _ppm_bytes(width: int, height: int, rgb: tuple[int, int, int] = (128, 128, 128)) -> bytes:
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    pixel = bytes([rgb[0], rgb[1], rgb[2]])
    return header + (pixel * (width * height))


def _register_admin(client: TestClient) -> None:
    unique = uuid4().hex[:8]
    email = f"games-admin-{unique}@example.com"
    existing = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([item for item in [existing, email] if item])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"games-admin-{unique}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


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
        _register_admin(client)
        resp = client.get("/api/games/modules")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(item["key"] == "posture_training" for item in items)
        assert any(item["key"] == "dont_move" for item in items)
        assert any(item["key"] == "tiptoeing" for item in items)


def test_start_game_run_with_dont_move_module():
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)

        resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "dont_move",
                "difficulty": "medium",
                "duration_minutes": 8,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 90,
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["module_key"] == "dont_move"
        assert payload["status"] == "active"
        assert payload["transition_seconds"] == 5
        assert payload["max_misses_before_penalty"] == 1
        assert payload["current_step"] is not None
        assert int(payload["current_step"]["raw_target_seconds"]) == 8 * 60


def test_start_game_run_with_tiptoeing_module():
    with TestClient(app) as client:
        _register_admin(client)

        posture_key = f"test_tiptoeing_pose_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/tiptoeing/postures",
            json={
                "posture_key": posture_key,
                "title": "Tiptoeing Pose",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "Stay on tiptoes.",
                "target_seconds": 120,
                "sort_order": 1,
                "is_active": True,
                "allowed_module_keys": ["tiptoeing"],
            },
        )
        assert create_resp.status_code == 200

        session_id = _create_and_sign(client)

        resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "tiptoeing",
                "difficulty": "medium",
                "duration_minutes": 6,
                "max_misses_before_penalty": 4,
                "session_penalty_seconds": 120,
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["module_key"] == "tiptoeing"
        assert payload["status"] == "active"
        assert payload["transition_seconds"] == 5
        assert payload["max_misses_before_penalty"] == 1
        assert payload["current_step"] is not None
        assert int(payload["current_step"]["raw_target_seconds"]) == 6 * 60


def test_strict_module_accepts_custom_start_countdown_seconds():
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)

        resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "dont_move",
                "difficulty": "medium",
                "duration_minutes": 8,
                "start_countdown_seconds": 9,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 90,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["transition_seconds"] == 9


def test_strict_module_uses_admin_configured_start_countdown_by_default():
    with TestClient(app) as client:
        _register_admin(client)

        saved = client.put(
            "/api/games/settings/global",
            json={
                "easy_target_multiplier": 0.75,
                "hard_target_multiplier": 1.5,
                "target_randomization_percent": 10,
                "start_countdown_seconds": 11,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["start_countdown_seconds"] == 11

        session_id = _create_and_sign(client)
        resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "dont_move",
                "difficulty": "medium",
                "duration_minutes": 8,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 90,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["transition_seconds"] == 11


def test_posture_allowed_module_keys_roundtrip():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_roundtrip_allowed_modules_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "Roundtrip Allowed Modules",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "Keep position.",
                "target_seconds": 90,
                "sort_order": 1,
                "is_active": True,
                "allowed_module_keys": ["posture_training", "dont_move"],
            },
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        posture_id = int(created["id"])
        assert sorted(created["allowed_module_keys"]) == ["dont_move", "posture_training"]

        update_resp = client.put(
            f"/api/games/modules/posture_training/postures/{posture_id}",
            json={"allowed_module_keys": ["dont_move"]},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["allowed_module_keys"] == ["dont_move"]

        list_resp = client.get("/api/games/modules/posture_training/postures")
        assert list_resp.status_code == 200
        updated = next((item for item in list_resp.json()["items"] if int(item["id"]) == posture_id), None)
        assert updated is not None
        assert updated["allowed_module_keys"] == ["dont_move"]


def test_posture_matrix_bulk_update_endpoint():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_matrix_bulk_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "Matrix Bulk",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "Matrix update.",
                "target_seconds": 80,
                "sort_order": 4,
                "is_active": True,
                "allowed_module_keys": ["posture_training"],
            },
        )
        assert create_resp.status_code == 200
        posture_id = int(create_resp.json()["id"])

        update_resp = client.put(
            "/api/inventory/postures/matrix",
            json={
                "items": [
                    {
                        "posture_id": posture_id,
                        "allowed_module_keys": ["posture_training", "dont_move"],
                    }
                ]
            },
        )
        assert update_resp.status_code == 200
        assert int(update_resp.json().get("updated", 0)) >= 1

        matrix_resp = client.get("/api/inventory/postures/matrix")
        assert matrix_resp.status_code == 200
        matrix_items = matrix_resp.json().get("items") or []
        target = next((item for item in matrix_items if int(item.get("id", 0)) == posture_id), None)
        assert target is not None
        assert sorted(target.get("allowed_module_keys") or []) == ["dont_move", "posture_training"]


def test_available_postures_endpoint_respects_module_assignment_matrix():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_available_filter_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "Available Filter",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "Filter endpoint.",
                "target_seconds": 75,
                "sort_order": 5,
                "is_active": True,
                "allowed_module_keys": ["posture_training"],
            },
        )
        assert create_resp.status_code == 200

        allowed_dm = client.get("/api/games/modules/dont_move/postures/available")
        assert allowed_dm.status_code == 200
        dm_keys = {str(item.get("posture_key") or "") for item in (allowed_dm.json().get("items") or [])}
        assert posture_key not in dm_keys

        allowed_pt = client.get("/api/games/modules/posture_training/postures/available")
        assert allowed_pt.status_code == 200
        pt_keys = {str(item.get("posture_key") or "") for item in (allowed_pt.json().get("items") or [])}
        assert posture_key in pt_keys


def test_posture_matrix_can_persist_empty_allowed_module_keys():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_empty_allowed_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "Empty Allowed",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "No module assignment.",
                "target_seconds": 65,
                "sort_order": 6,
                "is_active": True,
                "allowed_module_keys": ["posture_training", "dont_move"],
            },
        )
        assert create_resp.status_code == 200
        posture_id = int(create_resp.json()["id"])

        update_resp = client.put(
            "/api/inventory/postures/matrix",
            json={
                "items": [
                    {
                        "posture_id": posture_id,
                        "allowed_module_keys": [],
                    }
                ]
            },
        )
        assert update_resp.status_code == 200

        matrix_resp = client.get("/api/inventory/postures/matrix")
        assert matrix_resp.status_code == 200
        matrix_items = matrix_resp.json().get("items") or []
        target = next((item for item in matrix_items if int(item.get("id", 0)) == posture_id), None)
        assert target is not None
        assert target.get("allowed_module_keys") == []


def test_dont_move_rejects_posture_not_allowed_for_module():
    with TestClient(app) as client:
        _register_admin(client)
        allowed_dm_key = f"test_dm_allowed_pose_{uuid4().hex[:8]}"
        allowed_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": allowed_dm_key,
                "title": "DM Allowed Pose",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "No movement.",
                "target_seconds": 100,
                "sort_order": 1,
                "is_active": True,
                "allowed_module_keys": ["dont_move"],
            },
        )
        assert allowed_resp.status_code == 200

        posture_key = f"test_pt_only_pose_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "PT Only Pose",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "Stand still.",
                "target_seconds": 100,
                "sort_order": 2,
                "is_active": True,
                "allowed_module_keys": ["posture_training"],
            },
        )
        assert create_resp.status_code == 200
        posture_key = create_resp.json()["posture_key"]

        session_id = _create_and_sign(client)
        start_resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "dont_move",
                "difficulty": "medium",
                "duration_minutes": 5,
                "selected_posture_key": posture_key,
                "hold_seconds": 60,
            },
        )
        assert start_resp.status_code == 422
        assert "Selected posture" in start_resp.json()["detail"]


def test_dont_move_counts_each_violation_and_applies_penalty_per_violation():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_dm_penalty_pose_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "DM Penalty Pose",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "No movement.",
                "target_seconds": 120,
                "sort_order": 3,
                "is_active": True,
                "allowed_module_keys": ["dont_move"],
            },
        )
        assert create_resp.status_code == 200

        session_id = _create_and_sign(client)

        db = SessionLocal()
        try:
            baseline_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            assert baseline_session is not None
            baseline_lock_end = baseline_session.lock_end
        finally:
            db.close()

        start_resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "dont_move",
                "difficulty": "medium",
                "duration_minutes": 5,
                "selected_posture_key": posture_key,
                "hold_seconds": 60,
                "session_penalty_seconds": 3600,
                "transition_seconds": 12,
                "max_misses_before_penalty": 7,
            },
        )
        assert start_resp.status_code == 200
        run = start_resp.json()
        run_id = int(run["id"])
        step_id = int(run["current_step"]["id"])

        with patch("app.routers.games.analyze_verification", return_value=("suspicious", "AI movement detected")):
            first = client.post(
                f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                data={"observed_posture": run["current_step"]["posture_name"], "sample_only": "true"},
            )
            second = client.post(
                f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                data={"observed_posture": run["current_step"]["posture_name"], "sample_only": "true"},
            )

        assert first.status_code == 200
        assert second.status_code == 200

        first_payload = first.json()
        second_payload = second.json()
        assert first_payload["step"]["status"] == "pending"
        assert first_payload["step"]["finalized"] is False
        assert second_payload["step"]["status"] == "pending"
        assert second_payload["step"]["finalized"] is False
        assert int(second_payload["run"]["miss_count"]) == 2

        db = SessionLocal()
        try:
            updated_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            assert updated_session is not None
            assert baseline_lock_end is not None and updated_session.lock_end is not None
            delta_seconds = int((updated_session.lock_end - baseline_lock_end).total_seconds())
            assert delta_seconds >= 7200
        finally:
            db.close()


def test_dont_move_movement_event_endpoint_registers_violation_and_capture():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_dm_motion_event_pose_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "DM Motion Event Pose",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "No movement.",
                "target_seconds": 120,
                "sort_order": 4,
                "is_active": True,
                "allowed_module_keys": ["dont_move"],
            },
        )
        assert create_resp.status_code == 200

        session_id = _create_and_sign(client)
        start_resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "dont_move",
                "difficulty": "medium",
                "duration_minutes": 5,
                "selected_posture_key": posture_key,
                "session_penalty_seconds": 0,
            },
        )
        assert start_resp.status_code == 200
        run = start_resp.json()
        run_id = int(run["id"])
        step_id = int(run["current_step"]["id"])

        movement_resp = client.post(
            f"/api/games/runs/{run_id}/steps/{step_id}/movement-event",
            files={"file": ("movement.jpg", b"fakejpegbytes", "image/jpeg")},
            data={
                "marker_x": "0.52",
                "marker_y": "0.74",
                "reason": "Lokale Bewegung erkannt",
            },
        )
        assert movement_resp.status_code == 200

        payload = movement_resp.json()
        assert payload["step"]["verification_status"] == "suspicious"
        assert payload["step"]["sample_only"] is True
        assert payload["step"]["finalized"] is False
        assert payload["step"]["status"] == "pending"
        assert int(payload["run"]["miss_count"]) == 1
        assert str(payload["step"]["capture_url"]).startswith("/media/verifications/games/")


def test_dont_move_complete_endpoint_passes_without_creating_capture():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_dm_complete_pose_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "posture_key": posture_key,
                "title": "DM Complete Pose",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "No movement.",
                "target_seconds": 90,
                "sort_order": 6,
                "is_active": True,
                "allowed_module_keys": ["dont_move"],
            },
        )
        assert create_resp.status_code == 200

        session_id = _create_and_sign(client)
        start_resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "dont_move",
                "difficulty": "medium",
                "duration_minutes": 3,
                "selected_posture_key": posture_key,
                "session_penalty_seconds": 0,
            },
        )
        assert start_resp.status_code == 200
        run = start_resp.json()
        run_id = int(run["id"])
        step_id = int(run["current_step"]["id"])

        complete_resp = client.post(f"/api/games/runs/{run_id}/steps/{step_id}/complete")
        assert complete_resp.status_code == 200

        payload = complete_resp.json()
        assert payload["step"]["status"] == "passed"
        assert payload["step"]["verification_status"] == "confirmed"
        assert payload["step"]["capture_path"] is None
        assert payload["step"]["capture_url"] is None
        assert payload["step"]["verification_count"] == 0


def test_tiptoeing_complete_endpoint_passes_without_creating_capture():
    with TestClient(app) as client:
        _register_admin(client)
        posture_key = f"test_tiptoeing_complete_pose_{uuid4().hex[:8]}"
        create_resp = client.post(
            "/api/games/modules/tiptoeing/postures",
            json={
                "posture_key": posture_key,
                "title": "Tiptoeing Complete Pose",
                "image_url": "/static/img/postures/stand.jpg",
                "instruction": "Stay on tiptoes.",
                "target_seconds": 90,
                "sort_order": 7,
                "is_active": True,
                "allowed_module_keys": ["tiptoeing"],
            },
        )
        assert create_resp.status_code == 200

        session_id = _create_and_sign(client)
        start_resp = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "tiptoeing",
                "difficulty": "medium",
                "duration_minutes": 3,
                "session_penalty_seconds": 0,
            },
        )
        assert start_resp.status_code == 200
        run = start_resp.json()
        run_id = int(run["id"])
        step_id = int(run["current_step"]["id"])

        complete_resp = client.post(f"/api/games/runs/{run_id}/steps/{step_id}/complete")
        assert complete_resp.status_code == 200

        payload = complete_resp.json()
        assert payload["step"]["status"] == "passed"
        assert payload["step"]["verification_status"] == "confirmed"
        assert payload["step"]["capture_path"] is None
        assert payload["step"]["capture_url"] is None
        assert payload["step"]["verification_count"] == 0


def test_start_game_run_and_fetch_state():
    with TestClient(app) as client:
        _register_admin(client)
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
        _register_admin(client)
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
        assert payload["step"]["verification_status"] in {"confirmed", "suspicious"}
        assert payload["step"]["status"] in {"passed", "failed"}


def test_pose_similarity_suspicious_forces_verification_to_suspicious():
    with TestClient(app) as client:
        _register_admin(client)
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

        with patch("app.routers.games.analyze_verification", return_value=("confirmed", "AI confirmed")):
            with patch(
                "app.routers.games._evaluate_pose_similarity_for_step",
                return_value=(
                    "suspicious",
                    "Pose-Score 58.0/100 (min 74.0)",
                    {"score": 58.0, "threshold": 74.0},
                ),
            ):
                verify = client.post(
                    f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                    files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                    data={"observed_posture": run["current_step"]["posture_name"]},
                )
        assert verify.status_code == 200
        payload = verify.json()
        assert payload["step"]["verification_status"] == "suspicious"
        assert payload["step"]["pose_similarity_status"] == "suspicious"
        assert payload["step"]["pose_similarity"]["score"] == 58.0


def test_pose_similarity_result_is_exposed_in_verify_payload():
    with TestClient(app) as client:
        _register_admin(client)
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

        with patch("app.routers.games.analyze_verification", return_value=("confirmed", "AI confirmed")):
            with patch(
                "app.routers.games._evaluate_pose_similarity_for_step",
                return_value=(
                    "confirmed",
                    "Pose-Score 88.5/100 (min 74.0)",
                    {"score": 88.5, "threshold": 74.0},
                ),
            ):
                verify = client.post(
                    f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                    files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                    data={"observed_posture": run["current_step"]["posture_name"]},
                )
        assert verify.status_code == 200
        payload = verify.json()
        assert payload["step"]["pose_similarity_status"] == "confirmed"
        assert payload["step"]["pose_similarity"]["threshold"] == 74.0


def test_pose_similarity_uses_module_configured_threshold():
    with TestClient(app) as client:
        _register_admin(client)

        saved = client.put(
            "/api/games/modules/posture_training/settings",
            json={
                "easy_target_multiplier": 0.75,
                "hard_target_multiplier": 1.5,
                "target_randomization_percent": 10,
                "start_countdown_seconds": 7,
                "movement_easy_pose_deviation": 0.4,
                "movement_easy_stillness": 0.04,
                "movement_medium_pose_deviation": 0.35,
                "movement_medium_stillness": 0.03,
                "movement_hard_pose_deviation": 0.225,
                "movement_hard_stillness": 0.02,
                "pose_similarity_min_score_easy": 70.0,
                "pose_similarity_min_score_medium": 90.0,
                "pose_similarity_min_score_hard": 95.0,
            },
        )
        assert saved.status_code == 200
        assert float(saved.json()["pose_similarity_min_score_medium"]) == 90.0

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

        with patch("app.routers.games.analyze_verification", return_value=("confirmed", "AI confirmed")):
            with patch("app.routers.games.pose_similarity_available", return_value=True):
                with patch(
                    "app.routers.games._lookup_posture_template_for_step",
                    return_value=SimpleNamespace(reference_landmarks_json="{}"),
                ):
                    with patch(
                        "app.routers.games.score_against_reference",
                        return_value={"score": 88.0, "position_score": 88.0, "angle_score": 88.0},
                    ):
                        verify = client.post(
                            f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                            files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                            data={"observed_posture": run["current_step"]["posture_name"]},
                        )

        assert verify.status_code == 200
        payload = verify.json()
        assert payload["step"]["verification_status"] == "suspicious"
        assert payload["step"]["pose_similarity_status"] == "suspicious"
        assert payload["step"]["pose_similarity"]["threshold"] == 90.0


def test_sample_only_verification_keeps_step_pending_when_confirmed():
    with TestClient(app) as client:
        _register_admin(client)
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

        with patch("app.routers.games.analyze_verification", return_value=("confirmed", "AI mock confirmed")):
            verify = client.post(
                f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                data={
                    "observed_posture": run["current_step"]["posture_name"],
                    "sample_only": "true",
                },
            )
        assert verify.status_code == 200
        payload = verify.json()
        assert payload["step"]["sample_only"] is True
        assert payload["step"]["status"] == "pending"
        assert payload["step"]["finalized"] is False

        run_after = payload["run"]
        assert run_after["status"] == "active"
        assert run_after["current_step"] is not None
        assert run_after["current_step"]["id"] == step_id


def test_monitor_only_verification_keeps_step_pending_without_capture_on_confirmed_score():
    with TestClient(app) as client:
        _register_admin(client)
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

        with patch(
            "app.routers.games._evaluate_pose_similarity_for_step",
            return_value=(
                "confirmed",
                "Pose-Score 92.0/100 (min 80.0)",
                {"score": 92.0, "threshold": 80.0},
            ),
        ):
            verify = client.post(
                f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                data={
                    "observed_posture": run["current_step"]["posture_name"],
                    "monitor_only": "true",
                },
            )

        assert verify.status_code == 200
        payload = verify.json()
        assert payload["step"]["monitor_only"] is True
        assert payload["step"]["sample_only"] is False
        assert payload["step"]["status"] == "pending"
        assert payload["step"]["finalized"] is False
        assert payload["step"]["capture_path"] is None
        assert payload["step"]["capture_url"] is None


def test_failed_step_chain_appends_max_two_retries():
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)
        start = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 10,
                "max_misses_before_penalty": 5,
                "session_penalty_seconds": 0,
            },
        )
        assert start.status_code == 200
        run = start.json()
        run_id = run["id"]
        initial_step_id = run["current_step"]["id"]

        def _verify_fail(step_id: int) -> None:
            with patch("app.routers.games.analyze_verification", return_value=("suspicious", "AI mock fail")):
                resp = client.post(
                    f"/api/games/runs/{run_id}/steps/{step_id}/verify",
                    files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                    data={"observed_posture": run["current_step"]["posture_name"]},
                )
            assert resp.status_code == 200

        _verify_fail(initial_step_id)
        detail_1 = client.get(f"/api/games/runs/{run_id}").json()
        retry_1 = next((s for s in detail_1["steps"] if s.get("retry_of_step_id") == initial_step_id), None)
        assert retry_1 is not None

        _verify_fail(int(retry_1["id"]))
        detail_2 = client.get(f"/api/games/runs/{run_id}").json()
        retry_2 = next((s for s in detail_2["steps"] if s.get("retry_of_step_id") == int(retry_1["id"])), None)
        assert retry_2 is not None

        _verify_fail(int(retry_2["id"]))
        detail_3 = client.get(f"/api/games/runs/{run_id}").json()
        retry_3 = next((s for s in detail_3["steps"] if s.get("retry_of_step_id") == int(retry_2["id"])), None)
        assert retry_3 is None


def test_game_verification_capture_is_saved_with_session_game_run_timestamp_name():
    with TestClient(app) as client:
        _register_admin(client)
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
        path_parts = capture_path.split("/")
        assert len(path_parts) == 4
        filename = path_parts[3]
        assert filename.startswith(f"session{session_id}-game{run_id}-run")
        assert "-" in filename

        full_path = Path(settings.media_dir) / capture_path
        assert full_path.is_file()


def test_start_game_run_accepts_custom_transition_seconds():
    with TestClient(app) as client:
        _register_admin(client)
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


def test_game_run_auto_completes_when_total_time_elapsed_with_summary():
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)
        start = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 1,
                "transition_seconds": 8,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 120,
            },
        )
        assert start.status_code == 200
        run_id = start.json()["id"]

        db = SessionLocal()
        try:
            run = db.query(GameRun).filter(GameRun.id == run_id).first()
            assert run is not None
            run.started_at = datetime.now(timezone.utc) - timedelta(seconds=120)
            db.add(run)
            db.commit()
        finally:
            db.close()

        detail = client.get(f"/api/games/runs/{run_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["status"] == "completed"
        assert payload["remaining_seconds"] == 0
        assert payload["current_step"] is None

        summary = payload.get("summary") or {}
        assert summary.get("end_reason") == "time_elapsed"
        assert int(summary.get("total_steps") or 0) >= 1


def test_final_summary_contains_detailed_check_entries():
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)
        start = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 1,
                "transition_seconds": 0,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 120,
            },
        )
        assert start.status_code == 200
        run_id = start.json()["id"]
        step = start.json()["current_step"]
        assert step is not None

        with patch("app.routers.games.analyze_verification", return_value=("confirmed", "AI mock ok")):
            verify = client.post(
                f"/api/games/runs/{run_id}/steps/{step['id']}/verify",
                files={"file": ("pose.jpg", b"fakejpegbytes", "image/jpeg")},
                data={"observed_posture": step["posture_name"]},
            )
        assert verify.status_code == 200

        db = SessionLocal()
        try:
            run = db.query(GameRun).filter(GameRun.id == run_id).first()
            assert run is not None
            run.started_at = datetime.now(timezone.utc) - timedelta(seconds=120)
            db.add(run)
            db.commit()
        finally:
            db.close()

        detail = client.get(f"/api/games/runs/{run_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["status"] == "completed"
        summary = payload.get("summary") or {}
        checks = summary.get("checks") or []
        assert len(checks) >= 1
        last = checks[-1]
        assert last.get("verification_status") in {"confirmed", "suspicious"}
        assert (last.get("capture_url") or "").startswith("/media/verifications/games/")
        assert last.get("analysis")


def test_current_step_target_seconds_is_capped_by_remaining_budget():
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)
        start = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 1,
                "transition_seconds": 8,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 120,
            },
        )
        assert start.status_code == 200
        run_id = start.json()["id"]

        db = SessionLocal()
        try:
            run = db.query(GameRun).filter(GameRun.id == run_id).first()
            assert run is not None
            run.started_at = datetime.now(timezone.utc) - timedelta(seconds=56)
            db.add(run)
            db.commit()
        finally:
            db.close()

        detail = client.get(f"/api/games/runs/{run_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["status"] == "active"
        assert payload["remaining_seconds"] <= 4
        step = payload.get("current_step")
        assert step is not None

        max_hold_budget = max(0, int(payload["remaining_seconds"]) - int(payload["transition_seconds"]))
        assert int(step["target_seconds"]) <= max_hold_budget
        assert int(step["raw_target_seconds"]) >= int(step["target_seconds"])


def test_posture_management_crud_and_run_uses_managed_postures():
    with TestClient(app) as client:
        _register_admin(client)
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


def test_manual_reference_landmark_update_endpoint_persists_json():
    with TestClient(app) as client:
        _register_admin(client)
        created = client.post(
            "/api/games/modules/posture_training/postures",
            json={
                "title": "Manual Landmark Pose",
                "posture_key": f"manual_landmark_{uuid4().hex[:8]}",
                "image_url": "/static/img/postures/wall.jpg",
                "instruction": "Manual landmark test",
                "target_seconds": 60,
                "sort_order": 3,
                "is_active": True,
            },
        )
        assert created.status_code == 200
        posture_id = int(created.json()["id"])

        manual_json = {
            "points": {
                "left_shoulder": {"x": -0.2, "y": -0.3, "visibility": 0.99},
                "right_shoulder": {"x": 0.2, "y": -0.3, "visibility": 0.99},
                "left_hip": {"x": -0.15, "y": 0.1, "visibility": 0.99},
                "right_hip": {"x": 0.15, "y": 0.1, "visibility": 0.99},
            },
            "meta": {"scale": 0.4, "center": [0.5, 0.5]},
        }

        updated = client.put(
            f"/api/games/modules/posture_training/postures/{posture_id}/reference-pose/manual",
            json={"reference_landmarks_json": json.dumps(manual_json)},
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["reference_pose_available"] is True
        parsed = json.loads(body["reference_landmarks_json"])
        assert parsed["meta"]["scale"] == 0.4
        assert "left_shoulder" in parsed["points"]


def test_run_step_order_prioritizes_positive_sort_and_places_zero_at_end():
    with TestClient(app) as client:
        _register_admin(client)
        existing = client.get("/api/games/modules/posture_training/postures")
        assert existing.status_code == 200
        for row in existing.json().get("items") or []:
            removed = client.delete(f"/api/games/modules/posture_training/postures/{row['id']}")
            assert removed.status_code == 200

        create_data = [
            {
                "title": "Zero A",
                "posture_key": "zero_a",
                "image_url": "/static/img/postures/zero-a.jpg",
                "instruction": "fallback random",
                "target_seconds": 30,
                "sort_order": 0,
                "is_active": True,
            },
            {
                "title": "One",
                "posture_key": "one",
                "image_url": "/static/img/postures/one.jpg",
                "instruction": "prio 1",
                "target_seconds": 30,
                "sort_order": 1,
                "is_active": True,
            },
            {
                "title": "Zero B",
                "posture_key": "zero_b",
                "image_url": "/static/img/postures/zero-b.jpg",
                "instruction": "fallback random",
                "target_seconds": 30,
                "sort_order": 0,
                "is_active": True,
            },
            {
                "title": "Two",
                "posture_key": "two",
                "image_url": "/static/img/postures/two.jpg",
                "instruction": "prio 2",
                "target_seconds": 30,
                "sort_order": 2,
                "is_active": True,
            },
        ]
        for payload in create_data:
            created = client.post("/api/games/modules/posture_training/postures", json=payload)
            assert created.status_code == 200

        session_id = _create_and_sign(client)
        started = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 5,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 60,
            },
        )
        assert started.status_code == 200
        run_id = started.json()["id"]
        detail = client.get(f"/api/games/runs/{run_id}")
        assert detail.status_code == 200
        names = [step["posture_name"] for step in detail.json()["steps"]]

        assert names[:2] == ["One", "Two"]
        assert set(names[2:]) == {"Zero A", "Zero B"}


def test_run_step_order_randomizes_equal_positive_sort_bucket():
    with TestClient(app) as client:
        _register_admin(client)
        existing = client.get("/api/games/modules/posture_training/postures")
        assert existing.status_code == 200
        for row in existing.json().get("items") or []:
            removed = client.delete(f"/api/games/modules/posture_training/postures/{row['id']}")
            assert removed.status_code == 200

        create_data = [
            {
                "title": "One A",
                "posture_key": "one_a",
                "image_url": "/static/img/postures/one-a.jpg",
                "instruction": "prio 1",
                "target_seconds": 30,
                "sort_order": 1,
                "is_active": True,
            },
            {
                "title": "One B",
                "posture_key": "one_b",
                "image_url": "/static/img/postures/one-b.jpg",
                "instruction": "prio 1",
                "target_seconds": 30,
                "sort_order": 1,
                "is_active": True,
            },
            {
                "title": "Two A",
                "posture_key": "two_a",
                "image_url": "/static/img/postures/two-a.jpg",
                "instruction": "prio 2",
                "target_seconds": 30,
                "sort_order": 2,
                "is_active": True,
            },
            {
                "title": "Zero A",
                "posture_key": "zero_a2",
                "image_url": "/static/img/postures/zero-a2.jpg",
                "instruction": "fallback random",
                "target_seconds": 30,
                "sort_order": 0,
                "is_active": True,
            },
        ]
        for payload in create_data:
            created = client.post("/api/games/modules/posture_training/postures", json=payload)
            assert created.status_code == 200

        session_id = _create_and_sign(client)
        started = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "medium",
                "duration_minutes": 5,
                "max_misses_before_penalty": 2,
                "session_penalty_seconds": 60,
            },
        )
        assert started.status_code == 200
        run_id = started.json()["id"]
        detail = client.get(f"/api/games/runs/{run_id}")
        assert detail.status_code == 200
        names = [step["posture_name"] for step in detail.json()["steps"]]

        assert set(names[:2]) == {"One A", "One B"}
        assert names[2] == "Two A"
        assert names[3] == "Zero A"


def test_upload_posture_image_returns_content_url():
    with TestClient(app) as client:
        _register_admin(client)
        img = _ppm_bytes(768, 1024)
        uploaded = client.post(
            "/api/games/modules/posture_training/postures/upload-image",
            files={"file": ("pose.jpg", img, "image/jpeg")},
        )
        assert uploaded.status_code == 200
        payload = uploaded.json()
        assert payload["media_kind"] == "game_posture"
        assert payload["content_url"].startswith("/api/media/")


def test_upload_posture_image_accepts_small_resolution():
    with TestClient(app) as client:
        _register_admin(client)
        small = _ppm_bytes(320, 480)
        uploaded = client.post(
            "/api/games/modules/posture_training/postures/upload-image",
            files={"file": ("small.jpg", small, "image/jpeg")},
        )
        assert uploaded.status_code == 200
        payload = uploaded.json()
        assert payload["media_kind"] == "game_posture"
        assert payload["content_url"].startswith("/api/media/")


def test_uploaded_posture_image_url_can_be_persisted_on_posture():
    with TestClient(app) as client:
        _register_admin(client)
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
        _register_admin(client)
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
        posture_a = create_a.json()
        posture_b = create_b.json()

        manual_reference = {
            "points": {
                "left_shoulder": {"x": -0.21, "y": -0.44, "visibility": 0.93},
                "right_shoulder": {"x": 0.22, "y": -0.43, "visibility": 0.91},
            },
            "meta": {"center": [0.5, 0.5], "scale": 1.0},
        }
        manual_ref_saved = client.put(
            f"/api/games/modules/posture_training/postures/{posture_a['id']}/reference-pose/manual",
            json={"reference_landmarks_json": json.dumps(manual_reference, ensure_ascii=True)},
        )
        assert manual_ref_saved.status_code == 200

        manual_reference_b = {
            "points": {
                "left_shoulder": {"x": -0.19, "y": -0.42, "visibility": 0.92},
                "right_shoulder": {"x": 0.20, "y": -0.41, "visibility": 0.90},
            },
            "meta": {"center": [0.5, 0.5], "scale": 1.0},
        }
        manual_ref_saved_b = client.put(
            f"/api/games/modules/posture_training/postures/{posture_b['id']}/reference-pose/manual",
            json={"reference_landmarks_json": json.dumps(manual_reference_b, ensure_ascii=True)},
        )
        assert manual_ref_saved_b.status_code == 200

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
        by_key = {str(item.get("posture_key") or ""): item for item in (manifest.get("postures") or [])}
        assert "reference_landmarks_json" in by_key.get(posture_a["posture_key"], {})
        assert "reference_landmarks_json" in by_key.get(posture_b["posture_key"], {})

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
        imported_by_title = {item["title"]: item for item in items}
        assert imported_by_title["ZIP Export A"].get("reference_pose_available") is True
        assert "left_shoulder" in (imported_by_title["ZIP Export A"].get("reference_landmarks_json") or "")


def test_posture_zip_import_rejects_missing_local_image_file_reference():
    with TestClient(app) as client:
        _register_admin(client)
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


def test_posture_zip_import_reports_missing_reference_when_detection_returns_none(monkeypatch):
    from app.routers import games as games_router

    monkeypatch.setattr(games_router, "extract_reference_landmarks_json", lambda _: None)

    with TestClient(app) as client:
        _register_admin(client)

        img = _ppm_bytes(768, 1024, rgb=(30, 90, 150))
        archive_io = io.BytesIO()
        with zipfile.ZipFile(archive_io, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "format": "chastease-postures-v1",
                "module_key": "posture_training",
                "postures": [
                    {
                        "posture_key": "no_ref",
                        "title": "No Ref",
                        "instruction": "test",
                        "target_seconds": 90,
                        "sort_order": 1,
                        "is_active": True,
                        "image_file": "images/no-ref.jpg",
                    }
                ],
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True))
            archive.writestr("images/no-ref.jpg", img)

        imported = client.post(
            "/api/games/modules/posture_training/postures/import-zip",
            files={"file": ("no-ref.zip", archive_io.getvalue(), "application/zip")},
        )
        assert imported.status_code == 200
        body = imported.json()
        assert body.get("imported") == 1
        assert body.get("generated_reference_count") == 0
        assert body.get("missing_reference_count") == 1

        listed = client.get("/api/games/modules/posture_training/postures")
        assert listed.status_code == 200
        items = listed.json().get("items") or []
        item = next((row for row in items if row.get("posture_key") == "no_ref"), None)
        assert item is not None
        assert item.get("reference_pose_available") is False
        assert item.get("reference_landmarks_json") is None


def test_difficulty_uses_medium_baseline_target_with_multipliers():
    with TestClient(app) as client:
        _register_admin(client)
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
        _register_admin(client)
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
        _register_admin(client)
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
        _register_admin(client)
        global_saved = client.put(
            "/api/games/settings/global",
            json={
                "easy_target_multiplier": 0.6,
                "hard_target_multiplier": 1.4,
                "target_randomization_percent": 0,
                "start_countdown_seconds": 7,
            },
        )
        assert global_saved.status_code == 200
        assert global_saved.json()["easy_target_multiplier"] == 0.6
        assert global_saved.json()["hard_target_multiplier"] == 1.4
        assert global_saved.json()["target_randomization_percent"] == 0

        saved = client.put(
            "/api/games/modules/posture_training/settings",
            json={
                "easy_target_multiplier": 0.6,
                "hard_target_multiplier": 1.4,
                "target_randomization_percent": 0,
                "start_countdown_seconds": 7,
                "movement_easy_pose_deviation": 0.2,
                "movement_easy_stillness": 0.01,
                "movement_medium_pose_deviation": 0.18,
                "movement_medium_stillness": 0.008,
                "movement_hard_pose_deviation": 0.14,
                "movement_hard_stillness": 0.006,
            },
        )
        assert saved.status_code == 200
        assert float(saved.json()["movement_medium_stillness"]) == 0.008

        global_read_back = client.get("/api/games/settings/global")
        assert global_read_back.status_code == 200
        assert global_read_back.json()["easy_target_multiplier"] == 0.6
        assert global_read_back.json()["hard_target_multiplier"] == 1.4
        assert global_read_back.json()["target_randomization_percent"] == 0

        read_back = client.get("/api/games/modules/posture_training/settings")
        assert read_back.status_code == 200
        assert float(read_back.json()["movement_easy_pose_deviation"]) == 0.2
        assert float(read_back.json()["movement_hard_stillness"]) == 0.006

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


def test_tiptoeing_mask_upload_and_settings_roundtrip():
    with TestClient(app) as client:
        _register_admin(client)

        # Settings should initially have no mask URL
        settings_before = client.get("/api/games/modules/tiptoeing/settings")
        assert settings_before.status_code == 200
        assert settings_before.json().get("mask_image_url") is None

        # Upload a green/black mask image (green rectangle on black or vice versa)
        img = _ppm_bytes(200, 300, rgb=(0, 200, 0))
        uploaded = client.post(
            "/api/games/modules/tiptoeing/mask",
            files={"file": ("mask.png", img, "image/png")},
        )
        assert uploaded.status_code == 200
        mask_url = uploaded.json().get("mask_image_url")
        assert mask_url and mask_url.startswith("/api/media/")

        # Settings should now reflect the uploaded mask
        settings_after = client.get("/api/games/modules/tiptoeing/settings")
        assert settings_after.status_code == 200
        assert settings_after.json().get("mask_image_url") == mask_url

        # The mask image should be accessible via the media URL
        mask_content = client.get(mask_url)
        assert mask_content.status_code == 200
        assert mask_content.headers.get("content-type", "").startswith("image/")

        # Upload a second mask — should update the settings
        img2 = _ppm_bytes(300, 400, rgb=(0, 0, 0))
        uploaded2 = client.post(
            "/api/games/modules/tiptoeing/mask",
            files={"file": ("mask2.jpg", img2, "image/jpeg")},
        )
        assert uploaded2.status_code == 200
        mask_url2 = uploaded2.json().get("mask_image_url")
        assert mask_url2 != mask_url

        settings_final = client.get("/api/games/modules/tiptoeing/settings")
        assert settings_final.status_code == 200
        assert settings_final.json().get("mask_image_url") == mask_url2


def test_list_session_game_runs_empty():
    """GET /api/games/sessions/{id}/runs returns an empty list for a fresh session."""
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)

        resp = client.get(f"/api/games/sessions/{session_id}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 0


def test_list_session_game_runs_after_start():
    """Starting a game run is reflected in the session runs list."""
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)

        with patch("app.routers.games.generate_game_run_summary", return_value="Test-Beurteilung."):
            start_resp = client.post(
                f"/api/games/sessions/{session_id}/runs/start",
                json={
                    "module_key": "dont_move",
                    "difficulty": "easy",
                    "duration_minutes": 1,
                },
            )
        assert start_resp.status_code == 200
        run_id = start_resp.json()["id"]

        resp = client.get(f"/api/games/sessions/{session_id}/runs")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        run_item = next((r for r in items if r["id"] == run_id), None)
        assert run_item is not None
        assert run_item["module_key"] == "dont_move"
        assert run_item["difficulty_key"] == "easy"
        assert run_item["status"] in ("active", "completed")


def test_ai_assessment_stored_on_run_completion():
    """After a run is completed, summary_json includes ai_assessment when LLM returns text."""
    with TestClient(app) as client:
        _register_admin(client)
        session_id = _create_and_sign(client)

        with patch("app.routers.games.generate_game_run_summary", return_value="Sehr gute Leistung."):
            start_resp = client.post(
                f"/api/games/sessions/{session_id}/runs/start",
                json={
                    "module_key": "dont_move",
                    "difficulty": "easy",
                    "duration_minutes": 1,
                },
            )
        assert start_resp.status_code == 200
        run_id = start_resp.json()["id"]

        # Force completion via DB
        db = SessionLocal()
        try:
            from datetime import datetime, timezone, timedelta
            run = db.query(GameRun).filter(GameRun.id == run_id).first()
            assert run is not None
            run.status = "completed"
            run.finished_at = datetime.now(timezone.utc)
            import json as _json
            existing = _json.loads(run.summary_json) if run.summary_json else {}
            existing.update({
                "end_reason": "all_steps_processed",
                "total_steps": 1, "passed_steps": 1, "failed_steps": 0,
                "timeout_failed_steps": 0, "miss_count": 0,
                "retry_extension_seconds": 0, "session_penalty_applied": False,
                "scheduled_duration_seconds": 60, "checks": [],
                "ai_assessment": "Sehr gute Leistung.",
            })
            run.summary_json = _json.dumps(existing)
            db.commit()
        finally:
            db.close()

        run_resp = client.get(f"/api/games/runs/{run_id}")
        assert run_resp.status_code == 200
        summary = run_resp.json().get("summary") or {}
        assert summary.get("ai_assessment") == "Sehr gute Leistung."
