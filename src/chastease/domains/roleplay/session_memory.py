import json
from datetime import UTC, datetime

from sqlalchemy import select

from chastease.models import ChastitySession, Turn

from .models import MemoryEntry, RoleplayTurn, SessionSummary


def build_session_summary(turns: list[RoleplayTurn], *, max_turns: int = 6) -> SessionSummary | None:
    recent_turns = [turn for turn in turns if turn.turn_no > 0][-max(1, max_turns):]
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
    recent_turns = [turn for turn in turns if turn.turn_no > 0][-max(1, max_entries):]
    entries: list[MemoryEntry] = []
    for turn in recent_turns:
        wearer = " ".join(str(turn.player_action or "").split())
        keyholder = " ".join(str(turn.ai_narration or "").split())
        if wearer:
            entries.append(
                MemoryEntry(
                    kind="wearer_state",
                    content=wearer[:220],
                    source=f"turn:{turn.turn_no}",
                    tags=["recent", "wearer"],
                    weight=1.0,
                )
            )
        if keyholder:
            entries.append(
                MemoryEntry(
                    kind="keyholder_guidance",
                    content=keyholder[:220],
                    source=f"turn:{turn.turn_no}",
                    tags=["recent", "guidance"],
                    weight=0.9,
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


def refresh_session_roleplay_state(
    db,
    session: ChastitySession,
    *,
    history_turn_limit: int = 8,
    memory_entry_limit: int = 4,
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
    summary = build_session_summary(turns, max_turns=history_turn_limit)
    memory_entries = build_memory_entries(turns, max_entries=memory_entry_limit)

    policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
    if not isinstance(policy, dict):
        policy = {}
    roleplay = policy.get("roleplay") if isinstance(policy.get("roleplay"), dict) else {}
    serialized_summary = serialize_session_summary(summary)
    if serialized_summary is None:
        roleplay.pop("session_summary", None)
    else:
        roleplay["session_summary"] = serialized_summary
    roleplay["memory_entries"] = serialize_memory_entries(memory_entries)
    policy["roleplay"] = roleplay
    session.policy_snapshot_json = json.dumps(policy)
    return policy