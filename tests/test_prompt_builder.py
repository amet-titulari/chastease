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
        strictness_level=4,
        hard_limits=["blood", "breathplay"],
        active_phase={"title": "Warmup", "objective": "Focus", "guidance": "Steady breathing"},
        lorebook_entries=[{"key": "ritual", "content": "Follow the opening ritual."}],
    )

    rendered = prompt_modules.render()

    assert prompt_modules.version == PROMPT_VERSION
    assert "base_system_prompt.jinja2" in prompt_modules.templates_used
    assert "personas/default.md.jinja2" in prompt_modules.templates_used
    assert "action_contract.jinja2" in prompt_modules.templates_used
    assert "Persona: Default Persona." in rendered
    assert "Safety: mode=yellow." in rendered
    assert "Aktive Phase: Warmup." in rendered
    assert "[ritual]: Follow the opening ritual." in rendered
    assert "create_task" in rendered


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