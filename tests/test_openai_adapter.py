from chastease.services.ai.openai_adapter import OpenAIAdapter


def test_extract_reply_text_from_choices_output_text_chunks() -> None:
    data = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "output_text", "text": "Hallo"},
                        {"type": "output_text", "text": "Welt"},
                    ]
                }
            }
        ]
    }

    assert OpenAIAdapter._extract_reply_text(data) == "Hallo\nWelt"


def test_extract_reply_text_from_responses_output_content_chunks() -> None:
    data = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "Antwort aus responses API"},
                ],
            }
        ]
    }

    assert OpenAIAdapter._extract_reply_text(data) == "Antwort aus responses API"
