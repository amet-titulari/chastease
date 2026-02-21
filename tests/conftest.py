import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from chastease import create_app  # noqa: E402


@pytest.fixture()
def app():
    test_app = create_app()
    test_app.config.update(TESTING=True)
    yield test_app


@pytest.fixture()
def client(app):
    return app.test_client()
