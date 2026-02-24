from chastease.services.narration import extract_pending_actions


def test_extract_pending_actions_parses_suggest_add_time_duration() -> None:
    narration = (
        "Eine Stunde klingt gut.\n\n"
        "[Suggest: add_time(duration=1h, reason=Test der Faehigkeiten)]\n\n"
        "Was moechtest du als Naechstes?"
    )
    cleaned, actions, generated_files = extract_pending_actions(narration)

    assert generated_files == []
    assert len(actions) == 1
    assert actions[0]["action_type"] == "add_time"
    assert actions[0]["payload"] == {"seconds": 3600}
    assert actions[0]["requires_execute_call"] is True
    assert "Suggest:" not in cleaned


def test_extract_pending_actions_still_parses_machine_action_format() -> None:
    narration = 'Bitte bestaetige.\n[[ACTION:add_time|{"seconds":120}]]'
    cleaned, actions, _ = extract_pending_actions(narration)

    assert actions == [{"action_type": "add_time", "payload": {"seconds": 120}, "requires_execute_call": True}]
    assert "[[ACTION:" not in cleaned


def test_extract_pending_actions_parses_request_json_format() -> None:
    narration = 'Verstanden.\n[[REQUEST:add_time|{"amount":1,"unit":"hour","reason":"test"}]]'
    cleaned, actions, _ = extract_pending_actions(narration)

    assert len(actions) == 1
    assert actions[0]["action_type"] == "add_time"
    assert actions[0]["payload"] == {"amount": 1, "unit": "hour", "reason": "test"}
    assert "[[REQUEST:" not in cleaned


def test_extract_pending_actions_parses_request_call_format() -> None:
    narration = "OK.\n[REQUEST: add_time(duration=1h, reason=Tooltest)]"
    cleaned, actions, _ = extract_pending_actions(narration)

    assert len(actions) == 1
    assert actions[0]["action_type"] == "add_time"
    assert actions[0]["payload"] == {"seconds": 3600}
    assert "[REQUEST:" not in cleaned


def test_extract_pending_actions_parses_image_verification_request() -> None:
    narration = (
        "Bitte Bild senden.\n"
        '[[REQUEST:image_verification|{"request":"Zeige das Schloss frontal.","verification_instruction":"Pruefe sichtbares geschlossenes Schloss."}]]'
    )
    cleaned, actions, _ = extract_pending_actions(narration)

    assert len(actions) == 1
    assert actions[0]["action_type"] == "image_verification"
    assert actions[0]["payload"]["request"] == "Zeige das Schloss frontal."
    assert actions[0]["payload"]["verification_instruction"] == "Pruefe sichtbares geschlossenes Schloss."
    assert "[[REQUEST:" not in cleaned


def test_extract_pending_actions_parses_multiline_request_payload() -> None:
    narration = (
        "Ich pruefe das.\n"
        "[[REQUEST:image_verification|{\n"
        '"request":"geschlossener Lock mit Uhrzeit",\n'
        '"verification_instruction":"Pruefe Lock und Rasur."\n'
        "}]]"
    )
    cleaned, actions, _ = extract_pending_actions(narration)

    assert len(actions) == 1
    assert actions[0]["action_type"] == "image_verification"
    assert actions[0]["payload"]["request"] == "geschlossener Lock mit Uhrzeit"
    assert actions[0]["payload"]["verification_instruction"] == "Pruefe Lock und Rasur."
    assert "[[REQUEST:" not in cleaned
