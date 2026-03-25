from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app, validate_runtime_configuration
from app.models.verification import Verification
from app.services.media_retention import prune_expired_verification_media


def _register_and_finish_setup(client: TestClient, email: str = "hardening@example.com"):
    username = f"hard-{uuid4().hex[:8]}"
    unique_email = email if email != "hardening@example.com" else f"hard-{uuid4().hex[:8]}@example.com"
    existing_bootstrap = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([entry for entry in [existing_bootstrap, unique_email] if entry])

    register_resp = client.post(
        "/auth/register",
        data={
            "username": username,
            "email": unique_email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert register_resp.status_code == 303

    setup_resp = client.post(
        "/setup/complete",
        data={
            "role_style": "structured",
            "primary_goal": "Play",
            "boundary_note": "No work hours",
        },
    )
    assert setup_resp.status_code == 200


def test_runtime_validation_requires_encryption_key_outside_dev_mode(monkeypatch):
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "allow_insecure_dev_mode", False)
    monkeypatch.setattr(settings, "secret_encryption_key", None)

    try:
        validate_runtime_configuration()
        raise AssertionError("validate_runtime_configuration should have raised")
    except RuntimeError as exc:
        assert "CHASTEASE_SECRET_ENCRYPTION_KEY" in str(exc)


def test_media_upload_endpoint_is_rate_limited():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Limit Persona",
                "player_nickname": "Limit Player",
                "min_duration_seconds": 300,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        signed = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert signed.status_code == 200

        for _ in range(10):
            resp = client.post(
                f"/api/sessions/{session_id}/messages/media",
                data={"content": "ping"},
            )
            assert resp.status_code == 200

        limited = client.post(
            f"/api/sessions/{session_id}/messages/media",
            data={"content": "ping"},
        )
        assert limited.status_code == 429
        payload = limited.json()
        assert payload["error"]["code"] == "rate_limited"


def test_verification_media_retention_prunes_old_files():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Retention Persona",
                "player_nickname": "Retention Player",
                "min_duration_seconds": 300,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        verification = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={"requested_seal_number": "R-1"},
        )
        assert verification.status_code == 200
        verification_id = verification.json()["verification_id"]

        db = SessionLocal()
        try:
            row = db.query(Verification).filter(Verification.id == verification_id).first()
            assert row is not None
            target = Path(settings.media_dir) / "verifications" / "chat" / str(session_id) / f"retention-{verification_id}.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"test")
            row.image_path = str(target)
            row.created_at = datetime.now(timezone.utc) - timedelta(hours=settings.verification_media_retention_hours + 2)
            db.add(row)
            db.commit()
        finally:
            db.close()

        removed = prune_expired_verification_media()
        assert removed >= 1
        assert not target.exists()

        db = SessionLocal()
        try:
            refreshed = db.query(Verification).filter(Verification.id == verification_id).first()
            assert refreshed is not None
            assert refreshed.image_path is None
        finally:
            db.close()
