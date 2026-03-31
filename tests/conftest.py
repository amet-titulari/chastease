"""
Shared pytest fixtures for the chastease test suite.

Tests run against a dedicated SQLite database file and media directory to
avoid mutating local runtime data.

This conftest snapshots existing IDs before the test session and removes
all newly created rows afterwards in a FK-safe deletion order.
"""
import os
from pathlib import Path

import pytest

# Must be configured before importing app modules that build SQLAlchemy engine.
TEST_DATA_DIR = Path("data-tests")
TEST_DB_PATH = TEST_DATA_DIR / "chastease-test.db"
TEST_MEDIA_DIR = TEST_DATA_DIR / "media"
TEST_AUDIT_LOG_PATH = TEST_DATA_DIR / "audit.log"

os.environ.setdefault("CHASTEASE_DATABASE_URL", f"sqlite:///./{TEST_DB_PATH.as_posix()}")
os.environ.setdefault("CHASTEASE_MEDIA_DIR", f"./{TEST_MEDIA_DIR.as_posix()}")
os.environ.setdefault("CHASTEASE_AUDIT_LOG_PATH", f"./{TEST_AUDIT_LOG_PATH.as_posix()}")
os.environ.setdefault("CHASTEASE_DEBUG", "true")
os.environ.setdefault("CHASTEASE_SECRET_ENCRYPTION_KEY", "test-secret-key")

TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

from app.database import SessionLocal
from app.models.auth_user import AuthUser
from app.models.contract import Contract, ContractAddendum
from app.models.game_module_setting import GameModuleSetting
from app.models.game_posture_template import GamePostureTemplate
from app.models.game_run import GameRun
from app.models.game_run_step import GameRunStep
from app.models.hygiene_opening import HygieneOpening
from app.models.item import Item
from app.models.llm_profile import LlmProfile
from app.models.media_asset import MediaAsset
from app.models.message import Message
from app.models.persona import Persona
from app.models.persona_task_template import PersonaTaskTemplate
from app.models.player_profile import PlayerProfile
from app.models.push_subscription import PushSubscription
from app.models.safety_log import SafetyLog
from app.models.scenario import Scenario
from app.models.scenario_item import ScenarioItem
from app.models.seal_history import SealHistory
from app.models.session import Session
from app.models.session_item import SessionItem
from app.models.task import Task
from app.models.verification import Verification
from app.services.request_limits import reset_request_limits


SNAPSHOT_MODELS = [
    AuthUser,
    PlayerProfile,
    Persona,
    PersonaTaskTemplate,
    Scenario,
    Item,
    Session,
    Contract,
    ContractAddendum,
    GameModuleSetting,
    GamePostureTemplate,
    GameRun,
    GameRunStep,
    Message,
    Task,
    Verification,
    HygieneOpening,
    SafetyLog,
    PushSubscription,
    SealHistory,
    SessionItem,
    ScenarioItem,
    MediaAsset,
    LlmProfile,
]


# Delete children first, parents last to avoid FK constraint issues.
CLEANUP_ORDER = [
    Message,
    Verification,
    HygieneOpening,
    SafetyLog,
    PushSubscription,
    SealHistory,
    SessionItem,
    ScenarioItem,
    GameModuleSetting,
    GamePostureTemplate,
    GameRunStep,
    GameRun,
    PersonaTaskTemplate,
    ContractAddendum,
    Contract,
    Task,
    Session,
    Item,
    Scenario,
    Persona,
    PlayerProfile,
    MediaAsset,
    AuthUser,
    LlmProfile,
]


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Delete all rows created during this test run."""
    db = SessionLocal()
    existing_ids_by_model: dict[type, set[int]] = {}
    for model in SNAPSHOT_MODELS:
        existing_ids_by_model[model] = {row.id for row in db.query(model.id).all()}
    db.close()

    yield  # ← tests run here

    db = SessionLocal()
    for model in CLEANUP_ORDER:
        existing_ids = existing_ids_by_model.get(model, set())
        query = db.query(model)
        if existing_ids:
            query = query.filter(model.id.notin_(existing_ids))
        query.delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def reset_runtime_limiters():
    reset_request_limits()
    yield
    reset_request_limits()
