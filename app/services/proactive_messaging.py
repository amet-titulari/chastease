import json
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.scenario import Scenario
from app.models.session import Session as SessionModel
from app.services.ai_gateway import StubAIGateway, get_ai_gateway
from app.services.behavior_profile import (
    behavior_profile_from_entities,
    behavior_profile_from_scenario_key,
    director_profile_from_behavior,
    merge_behavior_profiles,
    reminder_profile_from_behavior,
)
from app.services.context_window import build_context_window
from app.services.prompt_builder import build_prompt_modules
from app.services.relationship_memory import build_relationship_memory
from app.services.roleplay_state import build_roleplay_state


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _persona_opening(persona_name: str, tone: str | None, dominance: str | None) -> str:
    tone_value = str(tone or "").strip().lower()
    dominance_value = str(dominance or "").strip().lower()
    if "warm" in tone_value or "soft" in dominance_value or "supportive" in dominance_value:
        return f"{persona_name}: Ruhig bleiben."
    if "hard" in dominance_value or "firm" in dominance_value or "strict" in tone_value:
        return f"{persona_name}: Haltung halten."
    return f"{persona_name}: Bleib sauber im Protokoll."


def _scenario_for_prefs(db, prefs: dict) -> Scenario | None:
    scenario_key = str((prefs or {}).get("scenario_preset") or "").strip()
    if not scenario_key:
        return None
    return db.query(Scenario).filter(Scenario.key == scenario_key).first()


def _build_reminder(
    db,
    persona: Persona | None,
    player_profile: PlayerProfile | None,
    session_obj: SessionModel,
    now: datetime,
) -> str:
    persona_name = persona.name if persona else "Keyholderin"
    prefs: dict = {}
    if player_profile and player_profile.preferences_json:
        try:
            parsed = json.loads(player_profile.preferences_json or "{}")
            if isinstance(parsed, dict):
                prefs = parsed
        except Exception:
            prefs = {}

    scenario_title = str(prefs.get("scenario_preset") or "").strip() or None
    scenario = _scenario_for_prefs(db, prefs)
    behavior_profile = merge_behavior_profiles(
        behavior_profile_from_entities(persona=persona, scenario=scenario),
        behavior_profile_from_scenario_key(db, prefs.get("scenario_preset")),
    )
    roleplay_state = build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=scenario_title,
        active_phase=None,
        behavior_profile=behavior_profile,
    )
    relationship_memory = build_relationship_memory(db, session_obj)
    reminder_profile = reminder_profile_from_behavior(behavior_profile)
    scene = roleplay_state["scene"]
    relationship = roleplay_state["relationship"]
    protocol = roleplay_state["protocol"]
    opening = (
        f"{persona_name}: "
        + str(
            reminder_profile.get("opening_soft")
            if ("warm" in str(persona.speech_style_tone if persona else "").strip().lower()
                or "soft" in str(persona.speech_style_dominance if persona else "").strip().lower()
                or "supportive" in str(persona.speech_style_dominance if persona else "").strip().lower())
            else (
                reminder_profile.get("opening_firm")
                if ("hard" in str(persona.speech_style_dominance if persona else "").strip().lower()
                    or "firm" in str(persona.speech_style_dominance if persona else "").strip().lower()
                    or "strict" in str(persona.speech_style_tone if persona else "").strip().lower())
                else reminder_profile.get("opening_default")
            )
        ).strip()
    )
    objective = str(scene.get("objective") or "Saubere Compliance halten").strip()
    next_beat = str(scene.get("next_beat") or "Einen kurzen Status geben").strip()
    active_rule = ""
    rules = protocol.get("active_rules") if isinstance(protocol, dict) else []
    if isinstance(rules, list) and rules:
        active_rule = str(rules[0] or "").strip()

    if session_obj.lock_end is None:
        return (
            f"{opening} Szene: {scene.get('title') or 'Einstimmung'}. "
            f"Ziel bleibt: {objective}. "
            f"{'Aktive Regel: ' + active_rule + '. ' if active_rule else ''}"
            f"Naechster Beat: {next_beat}."
        )

    remaining_seconds = int((_as_utc(session_obj.lock_end) - now).total_seconds())
    if remaining_seconds > 0:
        remaining_minutes = max(1, remaining_seconds // 60)
        return (
            f"{opening} Noch ca. {remaining_minutes} Minuten in der Szene "
            f"'{scene.get('title') or 'Einstimmung'}'. "
            f"Ziel: {objective}. "
            f"Kontrollniveau: {relationship.get('control_level') or 'strukturiert'}. "
            f"{'Aktive Regel: ' + active_rule + '. ' if active_rule else ''}"
            f"Melde dich kurz mit deinem Status."
        )

    return (
        f"{opening} Die geplante Zeitmarke ist erreicht. "
        f"Bleib in der Haltung der Szene '{scene.get('title') or 'Einstimmung'}' "
        "und warte auf die naechste Anweisung."
    )


def _build_ai_reminder(
    db,
    persona: Persona | None,
    player_profile: PlayerProfile | None,
    session_obj: SessionModel,
    now: datetime,
    recent_rows: list[Message],
) -> tuple[str, bool, str | None]:
    persona_name = persona.name if persona else "Keyholderin"
    prefs: dict = {}
    hard_limits: list[str] = []
    if player_profile and player_profile.preferences_json:
        try:
            parsed = json.loads(player_profile.preferences_json or "{}")
            if isinstance(parsed, dict):
                prefs = parsed
        except Exception:
            prefs = {}
    if player_profile and player_profile.hard_limits_json:
        try:
            parsed = json.loads(player_profile.hard_limits_json or "[]")
            if isinstance(parsed, list):
                hard_limits = [str(item).strip().lower() for item in parsed if str(item).strip()]
        except Exception:
            hard_limits = []

    scenario_title = str(prefs.get("scenario_preset") or "").strip() or None
    relationship_memory = build_relationship_memory(db, session_obj)
    behavior_profile = merge_behavior_profiles(
        behavior_profile_from_entities(persona=persona, scenario=_scenario_for_prefs(db, prefs)),
        behavior_profile_from_scenario_key(db, prefs.get("scenario_preset")),
    )
    roleplay_state = build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=scenario_title,
        active_phase=None,
        behavior_profile=behavior_profile,
    )
    reminder_profile = reminder_profile_from_behavior(behavior_profile)
    context_items, context_summary = build_context_window(recent_rows, max_messages=8)
    remaining_seconds = None
    if session_obj.lock_end is not None:
        remaining_seconds = int((_as_utc(session_obj.lock_end) - now).total_seconds())
    reminder_instruction = (
        "Erzeuge genau eine kurze proaktive Reminder-Nachricht im Charakter der Persona. "
        "Keine neuen Aufgaben vergeben. Keine JSON-Metakommentare. "
        "Die Nachricht soll sich wie ein natuerlicher Check-in innerhalb der laufenden Szene anfuehlen, "
        f"konkret auf Szene, Ziel, Regel oder Drucklage Bezug nehmen und maximal {max(1, int(reminder_profile.get('max_sentences') or 3))} Saetze haben."
    )
    if remaining_seconds is not None:
        reminder_instruction += f" Verbleibende Zeit in Sekunden: {remaining_seconds}."

    prompt_modules = build_prompt_modules(
        persona_name=persona_name,
        session_status=session_obj.status,
        safety_mode=None,
        scenario_title=scenario_title,
        wearer_nickname=player_profile.nickname if player_profile else None,
        experience_level=player_profile.experience_level if player_profile else None,
        wearer_style=prefs.get("wearer_style"),
        wearer_goal=prefs.get("wearer_goal"),
        wearer_boundary=prefs.get("wearer_boundary"),
        persona_system_prompt=persona.system_prompt if persona else None,
        speech_style_tone=persona.speech_style_tone if persona else None,
        speech_style_dominance=persona.speech_style_dominance if persona else None,
        formatting_style=persona.formatting_style if persona else None,
        verbosity_style=persona.verbosity_style if persona else None,
        praise_style=persona.praise_style if persona else None,
        repetition_guard=persona.repetition_guard if persona else None,
        context_exposition_style=persona.context_exposition_style if persona else None,
        director_profile=director_profile_from_behavior(behavior_profile),
        strictness_level=persona.strictness_level if persona else 3,
        hard_limits=hard_limits or None,
        active_phase=None,
        lorebook_entries=None,
        relationship_state=roleplay_state["relationship"],
        protocol_state=roleplay_state["protocol"],
        scene_state=roleplay_state["scene"],
        relationship_memory=relationship_memory,
    )

    ai = get_ai_gateway(session_obj=session_obj)
    if isinstance(ai, StubAIGateway):
        return _build_reminder(db, persona, player_profile, session_obj, now), False, None
    structured = ai.generate_chat_response(
        persona_name=persona_name,
        user_text=reminder_instruction,
        prompt_modules=prompt_modules.render(),
        formatting_style=persona.formatting_style if persona else None,
        context_items=[
            {
                "role": "system",
                "content": (
                    "Reminder-Kontext: "
                    f"Szene='{roleplay_state['scene'].get('title') or 'Einstimmung'}'; "
                    f"Ziel='{roleplay_state['scene'].get('objective') or '-'}'; "
                    f"NextBeat='{roleplay_state['scene'].get('next_beat') or '-'}'; "
                    f"Regeln={', '.join(roleplay_state['protocol'].get('active_rules') or []) or 'keine'}"
                ),
                "message_type": "reminder_context",
            }
        ] + (context_items or []),
        context_summary=context_summary or "Fortlaufende Session",
    )
    text = str(structured.message or "").strip()
    if text:
        return text, bool(structured.degraded), structured.degraded_reason
    return _build_reminder(db, persona, player_profile, session_obj, now), True, "Leere Reminder-Antwort"


def sweep_proactive_messages_for_active_sessions() -> dict:
    now = datetime.now(timezone.utc)
    cooldown = timedelta(seconds=max(settings.proactive_messages_cooldown_seconds, 0))

    with SessionLocal() as db:
        active_sessions = db.query(SessionModel).filter(SessionModel.status == "active").all()
        sent_count = 0

        for session_obj in active_sessions:
            last_assistant = (
                db.query(Message)
                .filter(Message.session_id == session_obj.id, Message.role == "assistant")
                .order_by(Message.id.desc())
                .first()
            )
            if last_assistant is not None and _as_utc(last_assistant.created_at) > (now - cooldown):
                continue

            # Count how many proactive reminders have been sent since the last user message
            last_user = (
                db.query(Message)
                .filter(Message.session_id == session_obj.id, Message.role == "user")
                .order_by(Message.id.desc())
                .first()
            )
            last_user_id = last_user.id if last_user else 0
            consecutive_reminders = (
                db.query(Message)
                .filter(
                    Message.session_id == session_obj.id,
                    Message.message_type == "proactive_reminder",
                    Message.id > last_user_id,
                )
                .count()
            )
            if consecutive_reminders >= settings.proactive_messages_max_consecutive:
                continue

            persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
            player_profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
            recent_rows = (
                db.query(Message)
                .filter(Message.session_id == session_obj.id)
                .order_by(Message.id.desc())
                .limit(12)
                .all()
            )
            reminder_text, degraded, degraded_reason = _build_ai_reminder(
                db,
                persona,
                player_profile,
                session_obj,
                now,
                list(reversed(recent_rows)),
            )
            reminder = Message(
                session_id=session_obj.id,
                role="assistant",
                content=reminder_text,
                message_type="proactive_reminder",
            )
            db.add(reminder)
            if degraded:
                db.add(
                    Message(
                        session_id=session_obj.id,
                        role="system",
                        content=(
                            "Reminder wurde im degradierten Modus erzeugt. "
                            f"Grund: {degraded_reason or 'temporärer Providerfehler'}."
                        ),
                        message_type="system_warning",
                    )
                )
            sent_count += 1

        if sent_count > 0:
            db.commit()

        return {
            "scanned_sessions": len(active_sessions),
            "sent_messages": sent_count,
        }
