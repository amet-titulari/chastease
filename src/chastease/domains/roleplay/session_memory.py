import json
from datetime import UTC, datetime

from sqlalchemy import select

from chastease.models import AuditEntry, ChastitySession, Turn

from .models import MemoryEntry, RoleplayTurn, SceneState, SessionSummary


def _compact_text(value: str | None, limit: int = 220) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit]


def _recent_turns(turns: list[RoleplayTurn], limit: int) -> list[RoleplayTurn]:
    return [turn for turn in turns if turn.turn_no > 0][-max(1, limit):]


def _detect_scene_phase(turns: list[RoleplayTurn]) -> str:
    if not turns:
        return "opening"
    combined = " ".join(
        f"{_compact_text(turn.player_action)} {_compact_text(turn.ai_narration)}".lower()
        for turn in turns[-3:]
    )
    if any(keyword in combined for keyword in ("reflect", "reflecting", "aftercare", "review", "debrief")):
        return "reflection"
    if any(keyword in combined for keyword in ("breathe", "breathing", "hold", "still", "wait", "kneel", "report")):
        return "control"
    if len(turns) <= 1:
        return "opening"
    return "active"


def _runtime_scene_overlay(
    policy: dict | None,
    *,
    recent_action_types: list[str] | None = None,
) -> tuple[str | None, str | None, list[str]]:
    if not isinstance(policy, dict):
        return None, None, []
    beats: list[str] = []
    runtime_timer = policy.get("runtime_timer") if isinstance(policy.get("runtime_timer"), dict) else {}
    timer_state = str(runtime_timer.get("state") or "").strip().lower()
    runtime_seal = policy.get("runtime_seal") if isinstance(policy.get("runtime_seal"), dict) else {}
    seal_status = str(runtime_seal.get("status") or "").strip().lower()
    seal_text = str(runtime_seal.get("current_text") or "").strip()
    needs_new_seal = bool(runtime_seal.get("needs_new_seal", False))
    runtime_hygiene = policy.get("runtime_hygiene") if isinstance(policy.get("runtime_hygiene"), dict) else {}
    hygiene_is_open = bool(runtime_hygiene.get("is_open"))
    window_end_at = str(runtime_hygiene.get("window_end_at") or "").strip()
    runtime_limits = policy.get("runtime_opening_limits") if isinstance(policy.get("runtime_opening_limits"), dict) else {}
    open_events = runtime_limits.get("open_events") if isinstance(runtime_limits.get("open_events"), list) else []
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    opening_period = str(limits.get("opening_limit_period") or "day").strip().lower() or "day"
    max_openings_raw = limits.get("max_openings_in_period", limits.get("max_openings_per_day", 0))

    phase = None
    status = None
    if timer_state == "paused":
        phase = "suspension"
        status = "paused"
        beats.append("timer:paused")
    elif timer_state == "running":
        beats.append("timer:running")

    if hygiene_is_open:
        phase = "maintenance"
        status = "hygiene-open"
        beats.append("hygiene:open")
        if window_end_at:
            beats.append(f"hygiene:window:{window_end_at}")
    elif runtime_hygiene:
        beats.append("hygiene:closed")

    try:
        max_openings = max(0, int(max_openings_raw))
    except (TypeError, ValueError):
        max_openings = 0
    used_openings = len([item for item in open_events if isinstance(item, str) and item.strip()])
    if max_openings > 0 or used_openings > 0:
        beats.append(f"openings:{used_openings}/{max_openings}:{opening_period}")
        if max_openings > 0 and used_openings >= max_openings:
            beats.append("openings:limit-reached")

    if seal_status:
        beats.append(f"seal:{seal_status}" + (f":{seal_text}" if seal_text else ""))
    if needs_new_seal and not hygiene_is_open:
        phase = "transition"
        status = "seal-reset"
        beats.append("seal:needs-renewal")
    elif seal_status in {"broken", "open", "unsealed"} and not hygiene_is_open:
        phase = "transition"
        status = "open"
    elif seal_status in {"sealed", "intact", "closed"} and status is None:
        status = "sealed"

    for action_type in (recent_action_types or [])[-2:]:
        normalized = str(action_type or "").strip().lower()
        if normalized:
            beats.append(f"action:{normalized}")
        if normalized == "hygiene_open":
            phase = "maintenance"
            status = "hygiene-open"
        elif normalized == "hygiene_close":
            phase = "transition"
            status = "resealed" if seal_status in {"sealed", "intact", "closed"} else "closed"

    return phase, status, beats


def _recent_manual_action_types(db, session_id: str, *, limit: int = 3) -> list[str]:
    entries = (
        db.scalars(
            select(AuditEntry)
            .where(
                AuditEntry.session_id == session_id,
                AuditEntry.event_type == "activity_manual_execute",
            )
            .order_by(AuditEntry.created_at.desc())
            .limit(max(1, limit))
        )
        .all()
    )
    action_types: list[str] = []
    for entry in reversed(entries):
        try:
            metadata = json.loads(entry.metadata_json or "{}")
        except json.JSONDecodeError:
            metadata = {}
        action_type = str(metadata.get("action_type") or "").strip().lower()
        if action_type:
            action_types.append(action_type)
    return action_types


def _scene_overlay_from_events(events: list[dict]) -> tuple[str | None, str | None, list[str]]:
    phase = None
    status = None
    beats: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type") or "").strip().lower()
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}

        if event_type == "abort_trigger_detected":
            phase = "transition"
            status = "abort-pending"
            beats.append("abort:triggered")
            trigger = str(metadata.get("trigger") or "").strip().lower()
            if trigger:
                beats.append(f"abort:trigger:{trigger}")
            continue

        if event_type == "abort_confirmed":
            phase = "emergency"
            status = "abort-confirmed"
            beats.append("abort:confirmed")
            trigger = str(metadata.get("trigger") or "").strip().lower()
            if trigger:
                beats.append(f"abort:trigger:{trigger}")
            continue

        if event_type == "abort_cancelled":
            phase = "active"
            status = "abort-cancelled"
            beats.append("abort:cancelled")
            continue

        if event_type != "activity_snapshot":
            continue

        pending_actions = metadata.get("pending_actions") if isinstance(metadata.get("pending_actions"), list) else []
        executed_actions = metadata.get("executed_actions") if isinstance(metadata.get("executed_actions"), list) else []
        failed_actions = metadata.get("failed_actions") if isinstance(metadata.get("failed_actions"), list) else []

        for pending_action in pending_actions:
            if not isinstance(pending_action, dict):
                continue
            action_type = str(pending_action.get("action_type") or "").strip().lower()
            payload = pending_action.get("payload") if isinstance(pending_action.get("payload"), dict) else {}
            trigger = str(payload.get("trigger") or payload.get("reason") or "").strip().lower()
            if action_type == "abort_decision":
                phase = "transition"
                status = "abort-pending"
                beats.append("abort:decision-pending")
            if action_type == "hygiene_open" and trigger == "timer_expired":
                phase = "transition"
                status = "timer-expired"
                beats.append("timer:expired")

        for failed_action in failed_actions:
            if not isinstance(failed_action, dict):
                continue
            action_type = str(failed_action.get("action_type") or "unknown").strip().lower() or "unknown"
            payload = failed_action.get("payload") if isinstance(failed_action.get("payload"), dict) else {}
            beats.append(f"failed:{action_type}")
            trigger = str(payload.get("trigger") or "").strip().lower()
            if bool(payload.get("emergency")) or trigger in {"manual_abort", "safeword", "traffic_red"}:
                phase = "emergency"
                status = "abort-blocked"
                beats.append("abort:failed-open")

        for executed_action in executed_actions:
            if not isinstance(executed_action, dict):
                continue
            action_type = str(executed_action.get("action_type") or "unknown").strip().lower() or "unknown"
            if action_type != "image_verification":
                continue
            beats.append("verification:passed")

    return phase, status, beats[-4:]


def _recent_audit_scene_overlay(
    db,
    session_id: str,
    *,
    limit: int = 6,
) -> tuple[str | None, str | None, list[str]]:
    entries = (
        db.scalars(
            select(AuditEntry)
            .where(AuditEntry.session_id == session_id)
            .order_by(AuditEntry.created_at.desc())
            .limit(max(1, limit))
        )
        .all()
    )
    raw_events: list[dict] = []
    for entry in reversed(entries):
        try:
            metadata = json.loads(entry.metadata_json or "{}")
        except json.JSONDecodeError:
            metadata = {}
        raw_events.append({
            "event_type": str(entry.event_type or "").strip().lower(),
            "metadata": metadata,
        })
    return _scene_overlay_from_events(raw_events)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)


def _memory_kind_for_wearer(text: str) -> str:
    normalized = text.lower()
    if any(keyword in normalized for keyword in ("i will", "i vow", "i promise", "i obey", "ich werde", "ich verspreche", "ich gehorche")):
        return "vows"
    if any(keyword in normalized for keyword in ("?", "wonder", "unsure", "ungewiss", "frage", "unclear")):
        return "unresolved_threads"
    if any(keyword in normalized for keyword in ("kneel", "breathe", "breathing", "count", "report", "ritual", "knie", "atem", "zaehl", "melde")):
        return "rituals"
    return "facts"


def _memory_kind_for_keyholder(text: str) -> str:
    normalized = text.lower()
    if any(keyword in normalized for keyword in ("remember", "note", "tracked", "logged", "merken", "notiert", "protokoll")):
        return "facts"
    if any(keyword in normalized for keyword in ("next", "later", "pending", "we will revisit", "spaeter", "anschliessend", "danach")):
        return "unresolved_threads"
    if any(keyword in normalized for keyword in ("breathe", "count", "kneel", "report", "repeat", "ritual", "atem", "zaehl", "melde", "wiederhole")):
        return "rituals"
    return "guidance"


def _memory_tags(kind: str, actor: str) -> list[str]:
    tags = ["recent", actor]
    if kind == "rituals":
        tags.append("continuity")
    if kind == "unresolved_threads":
        tags.append("pending")
    if kind == "vows":
        tags.append("commitment")
    return tags


def _memory_weight(kind: str, actor: str) -> float:
    if kind == "vows":
        return 1.3
    if kind == "rituals":
        return 1.15
    if kind == "unresolved_threads":
        return 1.1
    if actor == "keyholder":
        return 0.95
    return 1.0


def _source_turn_no(source: str) -> int:
    text = str(source or "").strip()
    if not text.startswith("turn:"):
        return 0
    try:
        return int(text.split(":", 1)[1])
    except ValueError:
        return 0


def _tokenize_memory_text(value: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or ""))
    return {token for token in normalized.split() if len(token) >= 3}


def select_scene_beats_for_prompt(
    beats: list[str],
    *,
    action_text: str = "",
    scene_state: SceneState | None = None,
    limit: int = 4,
) -> list[str]:
    cleaned_beats = [str(item).strip() for item in beats if str(item).strip()]
    if not cleaned_beats:
        return []

    action_tokens = _tokenize_memory_text(action_text)
    scene_tokens = set()
    if scene_state is not None:
        scene_tokens |= _tokenize_memory_text(scene_state.phase)
        scene_tokens |= _tokenize_memory_text(scene_state.status)

    scored_beats: list[tuple[float, int, int, str]] = []
    for index, beat in enumerate(cleaned_beats):
        beat_tokens = _tokenize_memory_text(beat)
        score = 0.0

        if beat.startswith("abort:"):
            score += 2.0
        elif beat.startswith("failed:"):
            score += 1.8
        elif beat.startswith("timer:expired"):
            score += 1.7
        elif beat.startswith("action:"):
            score += 1.75
        elif beat.startswith("hygiene:"):
            score += 1.45
        elif beat.startswith("verification:"):
            score += 1.4
        elif beat.startswith("seal:"):
            score += 1.35
        elif beat.startswith("openings:"):
            score += 1.2
        elif beat.startswith("wearer:") or beat.startswith("keyholder:"):
            score += 0.8

        if "limit-reached" in beat:
            score += 0.4
        if scene_state is not None and scene_state.phase == "emergency" and beat.startswith(("abort:", "failed:")):
            score += 0.35
        if scene_state is not None and scene_state.phase == "transition" and beat.startswith(("timer:", "seal:", "action:")):
            score += 0.25
        if scene_state is not None and scene_state.phase == "maintenance" and beat.startswith(("hygiene:", "openings:", "action:")):
            score += 0.25

        if action_tokens:
            score += 0.3 * len(action_tokens & beat_tokens)
        if scene_tokens:
            score += 0.15 * len(scene_tokens & beat_tokens)

        scored_beats.append((score, index, len(cleaned_beats) - index, beat))

    scored_beats.sort(key=lambda item: (item[0], item[2]), reverse=True)
    selected = [beat for _score, _index, _recency, beat in scored_beats[: max(1, limit)]]
    selected.sort(key=lambda beat: cleaned_beats.index(beat))
    return selected


def select_memory_entries_for_prompt(
    entries: list[MemoryEntry],
    *,
    action_text: str = "",
    scene_state: SceneState | None = None,
    limit: int = 4,
) -> list[MemoryEntry]:
    if not entries:
        return []

    action_tokens = _tokenize_memory_text(action_text)
    scene_tokens = set()
    if scene_state is not None:
        scene_tokens |= _tokenize_memory_text(scene_state.phase)
        scene_tokens |= _tokenize_memory_text(scene_state.status)
        for beat in scene_state.beats:
            scene_tokens |= _tokenize_memory_text(beat)

    scored_entries: list[tuple[float, int, int, MemoryEntry]] = []
    for index, entry in enumerate(entries):
        entry_tokens = _tokenize_memory_text(entry.content)
        entry_tokens |= _tokenize_memory_text(entry.kind)
        for tag in entry.tags:
            entry_tokens |= _tokenize_memory_text(tag)

        overlap_score = 0.0
        if action_tokens:
            overlap_score += 0.35 * len(action_tokens & entry_tokens)
        if scene_tokens:
            overlap_score += 0.2 * len(scene_tokens & entry_tokens)

        kind_bonus = 0.0
        if entry.kind == "vows":
            kind_bonus += 0.35
        elif entry.kind == "unresolved_threads":
            kind_bonus += 0.25
        elif entry.kind == "rituals":
            kind_bonus += 0.2
        elif entry.kind == "guidance":
            kind_bonus += 0.1

        if scene_state is not None and scene_state.phase in {"control", "suspension"} and entry.kind == "rituals":
            kind_bonus += 0.15
        if scene_state is not None and scene_state.phase in {"control", "suspension"} and entry.kind == "guidance":
            kind_bonus += 0.1
        if scene_state is not None and scene_state.phase == "transition" and entry.kind == "unresolved_threads":
            kind_bonus += 0.15

        turn_no = _source_turn_no(entry.source)
        recency_bonus = turn_no * 0.01
        tag_bonus = 0.05 * len([tag for tag in entry.tags if tag in {"continuity", "pending", "commitment"}])
        score = float(entry.weight) + overlap_score + kind_bonus + recency_bonus + tag_bonus
        scored_entries.append((score, turn_no, index, entry))

    scored_entries.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    selected = [entry for _score, _turn_no, _index, entry in scored_entries[: max(1, limit)]]
    selected.sort(key=lambda entry: (_source_turn_no(entry.source), entry.kind, entry.content))
    return selected


def build_scene_state(
    turns: list[RoleplayTurn],
    *,
    max_turns: int = 6,
    policy: dict | None = None,
    recent_action_types: list[str] | None = None,
    recent_event_phase: str | None = None,
    recent_event_status: str | None = None,
    recent_event_beats: list[str] | None = None,
) -> SceneState:
    recent_turns = _recent_turns(turns, max_turns)
    phase = _detect_scene_phase(recent_turns)
    beats: list[str] = []
    for turn in recent_turns[-2:]:
        wearer = _compact_text(turn.player_action, limit=120)
        keyholder = _compact_text(turn.ai_narration, limit=120)
        if wearer:
            beats.append(f"wearer:{wearer}")
        if keyholder:
            beats.append(f"keyholder:{keyholder}")
    runtime_phase, runtime_status, runtime_beats = _runtime_scene_overlay(
        policy,
        recent_action_types=recent_action_types,
    )
    if runtime_phase:
        phase = runtime_phase
    beats.extend(runtime_beats)
    if recent_event_phase:
        phase = recent_event_phase
    if recent_event_beats:
        beats.extend([str(item).strip() for item in recent_event_beats if str(item).strip()])
    return SceneState(
        name="active-session",
        phase=phase,
        status=recent_event_status or runtime_status or "active",
        beats=beats[-8:],
    )


def build_session_summary(turns: list[RoleplayTurn], *, max_turns: int = 6) -> SessionSummary | None:
    recent_turns = _recent_turns(turns, max_turns)
    if not recent_turns:
        return None
    lines: list[str] = []
    for turn in recent_turns[-3:]:
        wearer = " ".join(str(turn.player_action or "").split())
        keyholder = " ".join(str(turn.ai_narration or "").split())
        if wearer:
            lines.append(f"Wearer reported: {wearer[:180]}")
        if keyholder:
            lines.append(f"Keyholder replied: {keyholder[:180]}")
    summary_text = "\n".join(f"- {line}" for line in lines[:6]).strip()
    if not summary_text:
        return None
    return SessionSummary(
        summary_text=summary_text,
        source_turn_no=recent_turns[-1].turn_no,
        created_at_iso=datetime.now(UTC).isoformat(),
    )


def build_memory_entries(turns: list[RoleplayTurn], *, max_entries: int = 4) -> list[MemoryEntry]:
    recent_turns = _recent_turns(turns, max_entries)
    entries: list[MemoryEntry] = []
    for turn in recent_turns:
        wearer = _compact_text(turn.player_action)
        keyholder = _compact_text(turn.ai_narration)
        if wearer:
            wearer_kind = _memory_kind_for_wearer(wearer)
            entries.append(
                MemoryEntry(
                    kind=wearer_kind,
                    content=wearer,
                    source=f"turn:{turn.turn_no}",
                    tags=_memory_tags(wearer_kind, "wearer"),
                    weight=_memory_weight(wearer_kind, "wearer"),
                )
            )
        if keyholder:
            keyholder_kind = _memory_kind_for_keyholder(keyholder)
            entries.append(
                MemoryEntry(
                    kind=keyholder_kind,
                    content=keyholder,
                    source=f"turn:{turn.turn_no}",
                    tags=_memory_tags(keyholder_kind, "keyholder"),
                    weight=_memory_weight(keyholder_kind, "keyholder"),
                )
            )
    return entries[-max(1, max_entries):]


def serialize_session_summary(summary: SessionSummary | None) -> dict | None:
    if summary is None:
        return None
    return {
        "summary_text": summary.summary_text,
        "source_turn_no": summary.source_turn_no,
        "created_at_iso": summary.created_at_iso,
    }


def serialize_memory_entries(entries: list[MemoryEntry]) -> list[dict]:
    return [
        {
            "kind": entry.kind,
            "content": entry.content,
            "source": entry.source,
            "tags": list(entry.tags),
            "weight": entry.weight,
        }
        for entry in entries
    ]


def serialize_scene_state(scene_state: SceneState | None) -> dict | None:
    if scene_state is None:
        return None
    return {
        "name": scene_state.name,
        "phase": scene_state.phase,
        "status": scene_state.status,
        "beats": list(scene_state.beats),
    }


def refresh_session_roleplay_state(
    db,
    session: ChastitySession,
    *,
    history_turn_limit: int = 8,
    memory_entry_limit: int = 8,
    recent_action_types: list[str] | None = None,
    pending_audit_events: list[dict] | None = None,
) -> dict:
    recent_turns = (
        db.scalars(
            select(Turn)
            .where(Turn.session_id == session.id)
            .order_by(Turn.turn_no.desc())
            .limit(max(1, history_turn_limit))
        )
        .all()
    )
    turns = [
        RoleplayTurn(
            turn_no=turn.turn_no,
            player_action=turn.player_action,
            ai_narration=turn.ai_narration,
        )
        for turn in reversed(recent_turns)
    ]
    policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
    if not isinstance(policy, dict):
        policy = {}
    summary = build_session_summary(turns, max_turns=history_turn_limit)
    memory_entries = build_memory_entries(turns, max_entries=memory_entry_limit)
    action_types = list(recent_action_types or [])
    if not action_types:
        action_types = _recent_manual_action_types(db, session.id)
    recent_event_phase, recent_event_status, recent_event_beats = _recent_audit_scene_overlay(db, session.id)
    pending_event_phase, pending_event_status, pending_event_beats = _scene_overlay_from_events(pending_audit_events or [])
    scene_state = build_scene_state(
        turns,
        max_turns=history_turn_limit,
        policy=policy,
        recent_action_types=action_types,
        recent_event_phase=pending_event_phase or recent_event_phase,
        recent_event_status=pending_event_status or recent_event_status,
        recent_event_beats=[*recent_event_beats, *pending_event_beats],
    )
    roleplay = policy.get("roleplay") if isinstance(policy.get("roleplay"), dict) else {}
    serialized_summary = serialize_session_summary(summary)
    if serialized_summary is None:
        roleplay.pop("session_summary", None)
    else:
        roleplay["session_summary"] = serialized_summary
    roleplay["memory_entries"] = serialize_memory_entries(memory_entries)
    serialized_scene_state = serialize_scene_state(scene_state)
    if serialized_scene_state is None:
        roleplay.pop("scene_state", None)
    else:
        roleplay["scene_state"] = serialized_scene_state
    policy["roleplay"] = roleplay
    session.policy_snapshot_json = json.dumps(policy)
    return policy