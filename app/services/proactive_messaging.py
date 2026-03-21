import json
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel
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


def _build_reminder(
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
    roleplay_state = build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=scenario_title,
        active_phase=None,
    )
    scene = roleplay_state["scene"]
    relationship = roleplay_state["relationship"]
    protocol = roleplay_state["protocol"]
    opening = _persona_opening(
        persona_name=persona_name,
        tone=persona.speech_style_tone if persona else None,
        dominance=persona.speech_style_dominance if persona else None,
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
            reminder = Message(
                session_id=session_obj.id,
                role="assistant",
                content=_build_reminder(persona, player_profile, session_obj, now),
                message_type="proactive_reminder",
            )
            db.add(reminder)
            sent_count += 1

        if sent_count > 0:
            db.commit()

        return {
            "scanned_sessions": len(active_sessions),
            "sent_messages": sent_count,
        }
