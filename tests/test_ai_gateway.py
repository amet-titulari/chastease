import httpx
import json

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


def test_stub_chat_response_task_action_is_normalized():
    gateway = StubAIGateway()
    response = gateway.generate_chat_response(
        persona_name="Persona",
        user_text="Bitte Aufgabe: 20 Kniebeugen in 10 Minuten",
    )
    assert response.actions
    action = response.actions[0]
    assert action["type"] == "create_task"
    assert "title" in action


def test_ollama_chat_response_invalid_json_falls_back_to_stub(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "not-json"}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            return DummyResponse()

    monkeypatch.setattr(httpx, "Client", DummyClient)

    gateway = OllamaGateway(
        base_url="http://127.0.0.1:11434",
        model="llama3.1",
        timeout_seconds=5,
    )
    response = gateway.generate_chat_response(
        persona_name="Fallback Persona",
        user_text="Status",
    )
    assert "Fallback Persona" in response.message


def test_ollama_chat_response_drops_unknown_or_invalid_actions(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": json.dumps(
                    {
                        "message": "Antwort",
                        "actions": [
                            {"type": "unknown_action", "foo": "bar"},
                            {"type": "create_task", "title": "", "deadline_minutes": "abc"},
                            {"type": "create_task", "title": "Task A", "deadline_minutes": "15"},
                        ],
                        "mood": "strict",
                        "intensity": "9",
                    }
                )
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            return DummyResponse()

    monkeypatch.setattr(httpx, "Client", DummyClient)

    gateway = OllamaGateway(
        base_url="http://127.0.0.1:11434",
        model="llama3.1",
        timeout_seconds=5,
    )
    response = gateway.generate_chat_response(
        persona_name="Persona",
        user_text="Bitte Aufgabe",
    )
    assert len(response.actions) == 1
    assert response.actions[0]["title"] == "Task A"
    assert response.actions[0]["deadline_minutes"] == 15
    assert response.intensity == 5
