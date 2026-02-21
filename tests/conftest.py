import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from chastease import create_app  # noqa: E402


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
