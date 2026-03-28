import httpx
import json
from types import SimpleNamespace

from app.services.ai_gateway import CustomOpenAIGateway, OllamaGateway, StubAIGateway, _normalize_chat_message


def test_stub_gateway_generates_contract_text():
    gateway = StubAIGateway()
    text = gateway.generate_contract(
        persona_name="Test Persona",
        player_nickname="Tester",
        min_duration_seconds=300,
        max_duration_seconds=600,
        contract_context={
            "keyholder_title": "Mistress",
            "wearer_title": "pet",
            "touch_rules": "Keine Beruehrung ohne Freigabe.",
            "hard_limits": ["public play"],
        },
    )
    assert "KEUSCHHEITS-VERTRAG" in text
    assert "Test Persona" in text
    assert "Mistress" in text
    assert "Keine Beruehrung ohne Freigabe." in text
    assert "Der Keuschgehaltene anerkennt" in text


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
    assert "20 Kniebeugen" not in response.message
    assert response.degraded is True
    action = response.actions[0]
    assert action["type"] == "create_task"
    assert "title" in action


def test_normalize_chat_message_strips_markdown_in_plain_mode():
    result = _normalize_chat_message("**Status**: *gut* `ok`", "fallback")
    assert result == "Status: gut ok"


def test_normalize_chat_message_preserves_markdown_in_markdown_mode():
    result = _normalize_chat_message("**Status**: *gut*", "fallback", formatting_style="markdown")
    assert result == "**Status**: *gut*"


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


def test_ollama_chat_response_normalizes_update_task(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": json.dumps(
                    {
                        "message": "Task angepasst.",
                        "actions": [
                            {
                                "type": "update_task",
                                "task_id": "125",
                                "deadline_minutes": "270",
                                "title": "Task 125 neu",
                            }
                        ],
                        "mood": "strict",
                        "intensity": 3,
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
        user_text="Bitte passe Task 125 auf 270 Minuten an",
    )
    assert len(response.actions) == 1
    action = response.actions[0]
    assert action["type"] == "update_task"
    assert action["task_id"] == 125
    assert action["deadline_minutes"] == 270
    assert action["title"] == "Task 125 neu"


def test_custom_gateway_uses_litellm_client(monkeypatch):
    profile = SimpleNamespace(
        api_url="https://api.x.ai/v1",
        api_key="secret",
        chat_model="grok-4-1-fast-non-reasoning",
        vision_model="grok-4-1-fast-non-reasoning",
    )

    def _fake_complete_text(self, provider, model, messages, api_base=None, api_key=None, response_format=None, max_tokens=None):
        assert provider == "xai"
        assert model == "grok-4-1-fast-non-reasoning"
        assert api_base == "https://api.x.ai/v1"
        assert api_key == "secret"
        assert response_format == {"type": "json_object"}
        assert messages[-1]["role"] == "user"
        assert any(msg["role"] == "system" and "create_task" in str(msg.get("content", "")) for msg in messages)
        return json.dumps(
            {
                "message": "Antwort aus LiteLLM.",
                "actions": [{"type": "create_task", "title": "Task A", "deadline_minutes": "15"}],
                "mood": "strict",
                "intensity": "4",
            }
        )

    monkeypatch.setattr("app.services.llm_client.LiteLLMClient.complete_text", _fake_complete_text)

    gateway = CustomOpenAIGateway(profile=profile, timeout_seconds=5)
    response = gateway.generate_chat_response(persona_name="Persona", user_text="Bitte Aufgabe")

    assert response.message == "Antwort aus LiteLLM."
    assert response.actions == [{"type": "create_task", "title": "Task A", "description": "", "deadline_minutes": 15}]
    assert response.intensity == 4
