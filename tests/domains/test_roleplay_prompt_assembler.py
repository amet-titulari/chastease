from chastease.domains.roleplay import build_action_block, build_attachment_summary, build_roleplay_user_prompt
from chastease.services.ai.base import StoryTurnContext, TurnHistoryEntry


def test_build_action_block_includes_history_snapshot_and_tools() -> None:
    context = StoryTurnContext(
        session_id="session-1",
        action="I report back.",
        language="en",
        psychogram_summary="summary=test",
        turns_history=[
            TurnHistoryEntry(turn_no=1, player_action="I wait.", ai_narration="Stay still."),
        ],
        live_snapshot={"status": "active"},
        tools_summary="execute=add_time;suggest=-",
    )

    action_block = build_action_block(context, [{"name": "proof.jpg"}])

    assert "Recent dialogue:" in action_block
    assert "Current wearer input: I report back." in action_block
    assert "LIVE_SESSION_SNAPSHOT_JSON:" in action_block
    assert "Available tools: execute=add_time;suggest=-" in action_block
    assert "proof.jpg" in action_block


def test_build_roleplay_user_prompt_mentions_image_review_note() -> None:
    context = StoryTurnContext(
        session_id="session-2",
        action="Please review this.",
        language="en",
        psychogram_summary="summary=test",
        policy={
            "roleplay": {
                "prompt_profile": {"name": "immersive-keyholder", "mode": "immersive", "version": "v2"},
                "scene_state": {
                    "name": "vault-floor",
                    "phase": "control",
                    "status": "active",
                    "beats": ["wearer:steady breathing", "keyholder:maintain the ritual cadence"],
                },
                "session_summary": {"summary_text": "- Wearer reported: steady breathing."},
                "memory_entries": [
                    {"kind": "facts", "content": "steady breathing"},
                    {"kind": "rituals", "content": "maintain the ritual cadence"},
                ],
            }
        },
    )
    attachments = [{"name": "proof.png", "type": "image/png", "data_url": "data:image/png;base64,abc"}]

    user_prompt, attachment_content = build_roleplay_user_prompt(context, attachments)

    assert "Session: session-2" in user_prompt
    assert "Psychogram summary: summary=test" in user_prompt
    assert "Prompt profile: name=immersive-keyholder, mode=immersive, version=v2" in user_prompt
    assert "Scene state:" in user_prompt
    assert "- phase: control" in user_prompt
    assert "Scene beats:" in user_prompt
    assert "Session summary:" in user_prompt
    assert "Continuity memory:" in user_prompt
    assert "- facts: steady breathing" in user_prompt
    assert "- rituals: maintain the ritual cadence" in user_prompt
    assert "Favor immersive in-character narration" in user_prompt
    assert "These are NOT verification requests." in user_prompt
    assert attachment_content == [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]


def test_build_attachment_summary_without_attachments_returns_none_marker() -> None:
    summary, content = build_attachment_summary(None)

    assert summary == "- none"
    assert content == []


def test_build_roleplay_user_prompt_selects_most_relevant_memory_entries() -> None:
    context = StoryTurnContext(
        session_id="session-3",
        action="I will obey and report the seal status.",
        language="en",
        psychogram_summary="summary=test",
        policy={
            "roleplay": {
                "scene_state": {
                    "name": "vault-floor",
                    "phase": "control",
                    "status": "sealed",
                    "beats": ["seal:sealed:A-42"],
                },
                "memory_entries": [
                    {"kind": "facts", "content": "The room is quiet.", "source": "turn:1", "weight": 1.0},
                    {"kind": "rituals", "content": "Report your breathing cadence before each reply.", "source": "turn:2", "tags": ["continuity"], "weight": 1.15},
                    {"kind": "unresolved_threads", "content": "The seal number still needs confirmation.", "source": "turn:3", "tags": ["pending"], "weight": 1.1},
                    {"kind": "vows", "content": "I will obey the current seal protocol.", "source": "turn:4", "tags": ["commitment"], "weight": 1.3},
                    {"kind": "guidance", "content": "Keep your posture steady.", "source": "turn:5", "weight": 0.95},
                    {"kind": "guidance", "content": "Report the seal code clearly before anything else.", "source": "turn:6", "tags": ["continuity"], "weight": 1.05},
                ],
            }
        },
    )

    user_prompt, _attachment_content = build_roleplay_user_prompt(context, None)

    assert "- vows: I will obey the current seal protocol." in user_prompt
    assert "- unresolved_threads: The seal number still needs confirmation." in user_prompt
    assert "- rituals: Report your breathing cadence before each reply." in user_prompt
    assert "- guidance: Report the seal code clearly before anything else." in user_prompt
    assert "- facts: The room is quiet." not in user_prompt


def test_build_roleplay_user_prompt_selects_most_relevant_scene_beats() -> None:
    context = StoryTurnContext(
        session_id="session-4",
        action="The timer expired and the abort path is blocked.",
        language="en",
        psychogram_summary="summary=test",
        policy={
            "roleplay": {
                "scene_state": {
                    "name": "vault-floor",
                    "phase": "emergency",
                    "status": "abort-blocked",
                    "beats": [
                        "wearer:I wait quietly.",
                        "hygiene:open",
                        "seal:broken",
                        "timer:expired",
                        "openings:limit-reached",
                        "abort:confirmed",
                        "failed:ttlock_open",
                        "action:hygiene_open",
                    ],
                },
            }
        },
    )

    user_prompt, _attachment_content = build_roleplay_user_prompt(context, None)

    assert "- abort:confirmed" in user_prompt
    assert "- failed:ttlock_open" in user_prompt
    assert "- timer:expired" in user_prompt
    assert "- action:hygiene_open" in user_prompt
    assert "- wearer:I wait quietly." not in user_prompt


def test_build_roleplay_user_prompt_includes_character_and_scenario_directives() -> None:
    context = StoryTurnContext(
        session_id="session-5",
        action="Good morning, I am ready for the ritual.",
        language="de",
        psychogram_summary="summary=test",
        policy={
            "roleplay": {
                "prompt_profile": {"name": "amet-session", "mode": "immersive", "version": "v1"},
                "character_card": {
                    "display_name": "Amet Titulari",
                    "persona": {
                        "name": "Amet Titulari",
                        "archetype": "keyholder",
                        "description": "Spricht in der Ich-Form, warm, sinnlich, psychologisch praezise und fuehrt ueber Rituale, Checks, Aufgaben und Affirmationen.",
                        "goals": [
                            "deepen devotion",
                            "maintain ritual continuity",
                            "request photo verification",
                            "assign daily devotion tasks",
                        ],
                        "speech_style": {
                            "tone": "warm",
                            "dominance_style": "gentle-dominant",
                            "ritual_phrases": [
                                "Meine Erregung gehoert Amet.",
                                "Berichte mir deinen Status.",
                            ],
                            "formatting_style": "ornate",
                        },
                    },
                    "greeting_template": "**Protokoll-Status: Tag 1 | Deine Erregung: Sanft aufkeimend**",
                    "scenario_hooks": ["morning-check", "affirmation-ritual", "photo-verification", "task-assignment"],
                },
                "scenario": {
                    "title": "Amet Titulari Devotion Protocol",
                    "summary": "Langfristige Chastity mit taeglichen Ritualen, sinnlicher Fuehrung und liebevoller Kontrolle.",
                    "lorebook": [
                        {
                            "key": "response-structure",
                            "content": "Jede Antwort beginnt mit einer warmen Status-Zeile, enthaelt 8-16 Saetze, 40-50 Prozent sinnliche Koerperbeschreibung und endet mit einer klaren Aufgabe oder Reflexion.",
                            "priority": 100,
                        },
                        {
                            "key": "photo-verification",
                            "content": "Fordere gezielt Fotoverifikation zu Kaefigsitz, Schloss oder Hautzustand an und sage klar, was geprueft werden soll.",
                            "priority": 92,
                        },
                        {
                            "key": "task-patterns",
                            "content": "Vergib konkrete Aufgaben wie Lieblingsfarbe tragen, Journaleintrag, Haltungsuebung oder ein kurzes Beweisfoto.",
                            "priority": 91,
                        }
                    ],
                    "phases": [
                        {
                            "phase_id": "morning_check",
                            "title": "Morning Check",
                            "objective": "Erregungsstand, Affirmation und Kaefigbericht einsammeln.",
                            "guidance": "Fordere Bericht, Fotoverifikation, Lob und einen klaren Ritualschritt in jeder Antwort.",
                        }
                    ],
                },
                "scene_state": {
                    "name": "boudoir",
                    "phase": "morning_check",
                    "status": "active",
                    "beats": ["wearer:awaiting instructions"],
                },
            }
        },
    )

    user_prompt, _attachment_content = build_roleplay_user_prompt(context, None)

    assert "Character card:" in user_prompt
    assert "- display_name: Amet Titulari" in user_prompt
    assert "- dominance_style: gentle-dominant" in user_prompt
    assert "Preferred ritual phrases:" in user_prompt
    assert "Meine Erregung gehoert Amet." in user_prompt
    assert "Opening pattern:" in user_prompt
    assert "photo-verification" in user_prompt
    assert "task-assignment" in user_prompt
    assert "Scenario frame:" in user_prompt
    assert "- title: Amet Titulari Devotion Protocol" in user_prompt
    assert "Active phase:" in user_prompt
    assert "Scenario directives:" in user_prompt
    assert "40-50 Prozent sinnliche Koerperbeschreibung" in user_prompt
    assert "Fotoverifikation" in user_prompt
    assert "Lieblingsfarbe tragen" in user_prompt