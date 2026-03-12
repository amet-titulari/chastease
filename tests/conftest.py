"""
Shared pytest fixtures for the chastease test suite.

The persistent SQLite DB (data/) is reused across runs. Sessions.py
auto-creates a Persona stub for any unknown persona_name, so tests that
use fixed names would permanently pollute the personas table.

This conftest records which persona IDs existed *before* the test session
and removes any newly created ones afterwards, keeping the DB clean.
"""
import pytest

from app.database import SessionLocal
from app.models.persona import Persona


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_personas():
    """Delete any Persona rows created during the test run."""
    db = SessionLocal()
    existing_ids = {row.id for row in db.query(Persona.id).all()}
    db.close()

    yield  # ← tests run here

    db = SessionLocal()
    db.query(Persona).filter(Persona.id.notin_(existing_ids)).delete(synchronize_session=False)
    db.commit()
    db.close()
