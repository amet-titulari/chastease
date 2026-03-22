from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel
from app.services.roleplay_state import build_roleplay_state, default_relationship_state


MEMORY_KEYS = ("trust", "obedience", "resistance", "favor", "strictness", "frustration", "attachment")


def _clamp_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _summary_from_deltas(avg_deltas: dict[str, float], dominant_control_level: str | None) -> str:
    trust = avg_deltas.get("trust", 0.0)
    obedience = avg_deltas.get("obedience", 0.0)
    attachment = avg_deltas.get("attachment", 0.0)
    favor = avg_deltas.get("favor", 0.0)
    strictness = avg_deltas.get("strictness", 0.0)
    frustration = avg_deltas.get("frustration", 0.0)
    resistance_relief = -avg_deltas.get("resistance", 0.0)

    positive = trust + obedience + attachment + favor + resistance_relief
    if positive >= 14:
        mood = "Die Dynamik baut ueber Sessions hinweg sichtbar Vertrauen und Compliance auf."
    elif positive >= 6:
        mood = "Die Dynamik zeigt eine vorsichtig stabile Vertiefung von Fuehrung und Bindung."
    elif strictness + frustration >= 12:
        mood = "Die letzten Sessions waren eher korrektiv und von engerer Kontrolle gepraegt."
    else:
        mood = "Die Langzeitdynamik ist noch neutral und formt sich erst."

    if dominant_control_level:
        return f"{mood} Dominanter Stil zuletzt: {dominant_control_level}."
    return mood


def build_relationship_memory(
    db: Session,
    session_obj: SessionModel,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    auth_user_id = getattr(profile, "auth_user_id", None)
    if not auth_user_id:
        return {
            "sessions_considered": 0,
            "summary": "Noch keine Langzeitdynamik verfuegbar.",
            "dominant_control_level": None,
            "metrics": {},
            "highlights": [],
        }

    rows = (
        db.query(SessionModel)
        .join(PlayerProfile, PlayerProfile.id == SessionModel.player_profile_id)
        .filter(
            PlayerProfile.auth_user_id == auth_user_id,
            SessionModel.id != session_obj.id,
            SessionModel.status == "completed",
        )
        .order_by(SessionModel.id.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return {
            "sessions_considered": 0,
            "summary": "Noch keine abgeschlossenen Sessions fuer einen Langzeittrend vorhanden.",
            "dominant_control_level": None,
            "metrics": {},
            "highlights": [],
        }

    defaults = default_relationship_state()
    control_levels: list[str] = []
    collected: dict[str, list[int]] = {key: [] for key in MEMORY_KEYS}
    latest_scores: dict[str, int] = {}

    for idx, row in enumerate(rows):
        state = build_roleplay_state(
            relationship_json=row.relationship_state_json,
            protocol_json=row.protocol_state_json,
            scene_json=row.scene_state_json,
            scenario_title=None,
            active_phase=None,
        )
        relationship = state.get("relationship", {})
        control = str(relationship.get("control_level") or "").strip()
        if control:
            control_levels.append(control)
        for key in MEMORY_KEYS:
            value = _clamp_int(relationship.get(key))
            if value is None:
                continue
            collected[key].append(value)
            if idx == 0:
                latest_scores[key] = value

    metrics: dict[str, dict[str, int]] = {}
    avg_deltas: dict[str, float] = {}
    for key in MEMORY_KEYS:
        values = collected.get(key) or []
        if not values:
            continue
        avg_score = round(sum(values) / len(values))
        default_score = int(defaults.get(key) or 0)
        avg_delta = avg_score - default_score
        latest_score = latest_scores.get(key, avg_score)
        latest_delta = latest_score - default_score
        metrics[key] = {
            "average_score": avg_score,
            "average_delta": avg_delta,
            "latest_score": latest_score,
            "latest_delta": latest_delta,
        }
        avg_deltas[key] = float(avg_delta)

    dominant_control_level = Counter(control_levels).most_common(1)[0][0] if control_levels else None
    highlights: list[str] = []
    for key, label in (
        ("trust", "Trust"),
        ("obedience", "Obedience"),
        ("attachment", "Attachment"),
        ("strictness", "Strictness"),
        ("resistance", "Resistance"),
    ):
        metric = metrics.get(key)
        if not metric:
            continue
        delta = int(metric["average_delta"])
        if key == "resistance":
            if delta < 0:
                highlights.append(f"{label} langfristig niedriger ({delta})")
            elif delta > 0:
                highlights.append(f"{label} langfristig hoeher (+{delta})")
            continue
        if delta > 0:
            highlights.append(f"{label} langfristig hoeher (+{delta})")
        elif delta < 0:
            highlights.append(f"{label} langfristig niedriger ({delta})")
        if len(highlights) >= 3:
            break

    return {
        "sessions_considered": len(rows),
        "summary": _summary_from_deltas(avg_deltas, dominant_control_level),
        "dominant_control_level": dominant_control_level,
        "metrics": metrics,
        "highlights": highlights,
    }
