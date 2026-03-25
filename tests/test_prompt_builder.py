from app.services.prompt_builder import PROMPT_VERSION, build_prompt_modules


def test_prompt_builder_uses_external_templates_and_metadata():
    prompt_modules = build_prompt_modules(
        persona_name="Default Persona",
        session_status="active",
        safety_mode="yellow",
        scenario_title="Training",
        wearer_nickname="Tester",
        experience_level="advanced",
        wearer_style="strict",
        wearer_goal="discipline",
        wearer_boundary="no injury",
        speech_style_tone="calm",
        speech_style_dominance="firm",
        formatting_style="plain",
        verbosity_style="brief",
        praise_style="minimal",
        repetition_guard="strong",
        context_exposition_style="minimal",
        strictness_level=4,
        hard_limits=["blood", "breathplay"],
        active_phase={"title": "Warmup", "objective": "Focus", "guidance": "Steady breathing"},
        lorebook_entries=[{"key": "ritual", "content": "Follow the opening ritual."}],
        relationship_state={"trust": 61, "obedience": 74, "resistance": 12, "favor": 48, "strictness": 70, "frustration": 18, "attachment": 52, "control_level": "ritual"},
        protocol_state={"active_rules": ["Hands visible"], "blocked_actions": ["Keine Freigabe"], "open_orders": ["Knie nieder"], "reward_focus": "Lob", "consequence_focus": "enger fuehren"},
        scene_state={"title": "Inspection", "arc": "Ametara", "objective": "Pose pruefen", "pressure": "mittel", "last_consequence": "strenger Ton", "next_beat": "naechste Order"},
        relationship_memory={"sessions_considered": 2, "summary": "Fuehrung wird stabiler.", "dominant_control_level": "ritual"},
    )

    rendered = prompt_modules.render()

    assert prompt_modules.version == PROMPT_VERSION
    assert "base_system_prompt.jinja2" in prompt_modules.templates_used
    assert "personas/default.md.jinja2" in prompt_modules.templates_used
    assert "action_contract.jinja2" in prompt_modules.templates_used
    assert "Persona: Default Persona." in rendered
    assert "Safety: mode=yellow." in rendered
    assert "Director-Modus:" in rendered
    assert "Szene: Inspection." in rendered
    assert "Offene Anweisungen: Knie nieder." in rendered
    assert "Abgeschlossene Vergleichssessions: 2." in rendered
    assert "Langzeitbild: Fuehrung wird stabiler." in rendered
    assert "Dominanter Kontrollstil: ritual." in rendered
    assert "Aktive Phase: Warmup." in rendered
    assert "[ritual]: Follow the opening ritual." in rendered
    assert "create_task" in rendered
    assert "Schreibe im Chat als Klartext, nicht als Markdown." in rendered
    assert "Lob nur selten und nur bei klar erkennbarer Leistung. Keine Lobeshymnen." in rendered
    assert "Wiederhole oder paraphrasiere die letzte Nutzernachricht nicht." in rendered
    assert "Nenne Szene, Statuswerte, Regeln oder Metadaten nur dann, wenn sie fuer die aktuelle Antwort zwingend noetig sind." in rendered
    assert "Wiederhole nicht in jeder Antwort die komplette Statuslage" in rendered


def test_prompt_builder_uses_persona_specific_template_when_available():
    prompt_modules = build_prompt_modules(
        persona_name="Iron Coach Mara",
        session_status="active",
        safety_mode=None,
        scenario_title=None,
        speech_style_tone="direct",
        speech_style_dominance="hard-dominant",
        strictness_level=5,
    )

    rendered = prompt_modules.render()

    assert "personas/iron_coach_mara.md.jinja2" in prompt_modules.templates_used
    assert "strenge Drill-Coachin" in rendered
