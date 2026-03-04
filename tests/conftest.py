import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from chastease import create_app  # noqa: E402


def _disable_rate_limiters():
    import chastease.api.routers.auth as auth_router
    import chastease.api.routers.story as story_router
    auth_router.limiter.enabled = False
    story_router.limiter.enabled = False


def _enable_rate_limiters():
    import chastease.api.routers.auth as auth_router
    import chastease.api.routers.story as story_router
    auth_router.limiter.enabled = True
    story_router.limiter.enabled = True


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SETUP_STORE_PATH", str(tmp_path / "setup_sessions.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'chastease_test.db'}")
    monkeypatch.setenv("ENABLE_SESSION_KILL", "true")
    _disable_rate_limiters()
    app = create_app()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        _enable_rate_limiters()


@pytest.fixture()
def admin_client(monkeypatch, tmp_path):
    monkeypatch.setenv("SETUP_STORE_PATH", str(tmp_path / "setup_sessions.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'chastease_test.db'}")
    monkeypatch.setenv("ENABLE_SESSION_KILL", "true")
    monkeypatch.setenv("ENABLE_AUDIT_LOG_VIEW", "true")
    _disable_rate_limiters()
    app = create_app()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        _enable_rate_limiters()
