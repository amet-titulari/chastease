import json

import httpx

from app.config import settings
from app.services.verification_analysis import analyze_verification


def test_heuristic_marks_mismatch_as_suspicious():
    previous = settings.verification_ai_provider
    settings.verification_ai_provider = "heuristic"
    try:
        status, analysis = analyze_verification(
            image_bytes=b"image",
            filename="proof.jpg",
            requested_seal_number="A-2",
            observed_seal_number="A-9",
        )
        assert status == "suspicious"
        assert "stimmt nicht" in analysis
    finally:
        settings.verification_ai_provider = previous


def test_ollama_mode_falls_back_to_heuristic_on_error(monkeypatch):
    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            raise RuntimeError("connection failed")

    monkeypatch.setattr(httpx, "Client", DummyClient)

    previous = settings.verification_ai_provider
    settings.verification_ai_provider = "ollama"
    try:
        status, _ = analyze_verification(
            image_bytes=b"image",
            filename="proof.jpg",
            requested_seal_number="A-2",
            observed_seal_number="A-2",
        )
        assert status == "confirmed"
    finally:
        settings.verification_ai_provider = previous


def test_ollama_mode_uses_structured_response(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": json.dumps({"status": "suspicious", "analysis": "Plombe unklar sichtbar."})
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            assert url.endswith("/api/generate")
            assert json["model"]
            return DummyResponse()

    monkeypatch.setattr(httpx, "Client", DummyClient)

    previous = settings.verification_ai_provider
    settings.verification_ai_provider = "ollama"
    try:
        status, analysis = analyze_verification(
            image_bytes=b"image",
            filename="proof.jpg",
            requested_seal_number="A-2",
            observed_seal_number="A-2",
        )
        assert status == "suspicious"
        assert "unklar" in analysis
    finally:
        settings.verification_ai_provider = previous
