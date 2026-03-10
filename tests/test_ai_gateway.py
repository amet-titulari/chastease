import httpx

from app.services.ai_gateway import OllamaGateway, StubAIGateway


def test_stub_gateway_generates_contract_text():
    gateway = StubAIGateway()
    text = gateway.generate_contract(
        persona_name="Test Persona",
        player_nickname="Tester",
        min_duration_seconds=300,
        max_duration_seconds=600,
    )
    assert "KEUSCHHEITS-VERTRAG" in text
    assert "Test Persona" in text


def test_ollama_gateway_uses_response_payload(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "KEUSCHHEITS-VERTRAG\nVon Ollama"}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            assert url.endswith("/api/generate")
            assert json["model"] == "llama3.1"
            return DummyResponse()

    monkeypatch.setattr(httpx, "Client", DummyClient)

    gateway = OllamaGateway(
        base_url="http://127.0.0.1:11434",
        model="llama3.1",
        timeout_seconds=5,
    )
    text = gateway.generate_contract(
        persona_name="Persona",
        player_nickname="Wearer",
        min_duration_seconds=300,
        max_duration_seconds=900,
    )
    assert "Von Ollama" in text


def test_ollama_gateway_falls_back_on_failure(monkeypatch):
    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            raise RuntimeError("ollama not reachable")

    monkeypatch.setattr(httpx, "Client", DummyClient)

    gateway = OllamaGateway(
        base_url="http://127.0.0.1:11434",
        model="llama3.1",
        timeout_seconds=5,
    )
    text = gateway.generate_contract(
        persona_name="Fallback Persona",
        player_nickname="Wearer",
        min_duration_seconds=300,
        max_duration_seconds=900,
    )
    assert "KEUSCHHEITS-VERTRAG" in text
    assert "Fallback Persona" in text
