from fastapi.testclient import TestClient
from pathlib import Path
import re
from unittest.mock import patch

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.verification import Verification


def _create_and_sign_session(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Verification Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_verification_upload_and_seal_mismatch_marks_suspicious():
    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        request_resp = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={"requested_seal_number": "A-2"},
        )
        assert request_resp.status_code == 200
        verification_id = request_resp.json()["verification_id"]

        upload_resp = client.post(
            f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
            files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
            data={"observed_seal_number": "A-9"},
        )
        assert upload_resp.status_code == 200
        data = upload_resp.json()
        assert data["status"] == "suspicious"
        assert "stimmt nicht" in data["analysis"]


def test_verification_upload_is_accessible_without_admin_secret():
    """Upload ist eine Wearer-Aktion und darf kein Admin-Secret erfordern,
    auch wenn ein Admin-Secret konfiguriert ist."""
    previous = settings.admin_secret
    settings.admin_secret = "verify-secret"
    try:
        with TestClient(app) as client:
            session_id = _create_and_sign_session(client)
            request_resp = client.post(
                f"/api/sessions/{session_id}/verifications/request",
                json={"requested_seal_number": "A-2"},
            )
            verification_id = request_resp.json()["verification_id"]

            # Normaler Wearer-Zugriff ohne Admin-Header muss erlaubt sein
            resp = client.post(
                f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
                files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
                data={"observed_seal_number": "A-2"},
            )
            assert resp.status_code == 200
    finally:
        settings.admin_secret = previous


def test_chat_verification_image_path_uses_session_chat_task_timestamp_name():
    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        request_resp = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={"requested_seal_number": "A-2"},
        )
        assert request_resp.status_code == 200
        verification_id = request_resp.json()["verification_id"]

        upload_resp = client.post(
            f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
            files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
            data={"observed_seal_number": "A-2"},
        )
        assert upload_resp.status_code == 200

        db = SessionLocal()
        try:
            row = db.query(Verification).filter(Verification.id == verification_id).first()
            assert row is not None
            image_path = row.image_path or ""
        finally:
            db.close()

        expected_prefix = f"{Path(settings.media_dir)}/verifications/chat/{session_id}/"
        assert image_path.startswith(expected_prefix)
        filename = Path(image_path).name
        assert filename.startswith(f"session{session_id}-chat-task{verification_id}-")
        assert re.search(r"\d{8}-\d{4}", filename) is not None
        assert Path(image_path).is_file()


def test_verification_upload_stamps_required_and_detected_proof_text():
    captured: dict[str, str] = {}

    def _capture_stamp(image_bytes: bytes, *, required_text: str | None = None, detected_text: str | None = None, now=None) -> bytes:
        captured["required_text"] = required_text or ""
        captured["detected_text"] = detected_text or ""
        return image_bytes

    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        request_resp = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={
                "requested_seal_number": "A-2",
                "verification_criteria": "Plombe muss klar lesbar und unbeschaedigt sein.",
            },
        )
        assert request_resp.status_code == 200
        verification_id = request_resp.json()["verification_id"]

        with patch("app.routers.verification.analyze_verification", return_value=("suspicious", "KI sagt: Plombe verdeckt.")):
            with patch("app.routers.verification.stamp_verification_proof", side_effect=_capture_stamp):
                upload_resp = client.post(
                    f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
                    files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
                    data={"observed_seal_number": "A-9"},
                )

        assert upload_resp.status_code == 200
        assert "Soll: A-2" in captured["required_text"]
        assert "Check:" in captured["required_text"]
        assert "lesbar" in captured["required_text"]
        assert "unbeschaedigt" in captured["required_text"]
        assert "Verdacht" in captured["detected_text"]
        assert "Ist: A-9" in captured["detected_text"]
        assert "KI sagt: Plombe verdeckt." in captured["detected_text"]


def test_confirmed_verification_advances_roleplay_state():
    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        request_resp = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={"requested_seal_number": "A-2"},
        )
        assert request_resp.status_code == 200
        verification_id = request_resp.json()["verification_id"]

        upload_resp = client.post(
            f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
            files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
            data={"observed_seal_number": "A-2"},
        )
        assert upload_resp.status_code == 200
        assert upload_resp.json()["status"] == "confirmed"

        session_resp = client.get(f"/api/sessions/{session_id}")
        assert session_resp.status_code == 200
        roleplay = session_resp.json()["roleplay_state"]
        assert roleplay["relationship"]["trust"] == 58
        assert roleplay["relationship"]["obedience"] == 52
        assert "Nachweis" in roleplay["scene"]["last_consequence"]
