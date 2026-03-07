import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select

from chastease.api.runtime import find_setup_session_id_for_active_session
from chastease.api.setup_domain import _fixed_soft_limits_text
from chastease.domains.characters import CharacterCard, PersonaProfile, SpeechStyle
from chastease.domains.scenarios import LoreEntry, ScenarioDefinition, ScenarioPhase
from chastease.models import ChastitySession, Turn, User
from chastease.repositories.setup_store import load_sessions
from chastease.services.ai.base import StoryTurnContext, TurnHistoryEntry

from .models import MemoryEntry, PromptProfile, RoleplayContext, RoleplayTurn, SceneState, SessionSummary


def _character_card_from_payload(payload: dict[str, Any] | None) -> CharacterCard | None:
    if not isinstance(payload, dict):
        return None
    persona_payload = payload.get("persona") if isinstance(payload.get("persona"), dict) else {}
    speech_payload = persona_payload.get("speech_style") if isinstance(persona_payload.get("speech_style"), dict) else {}
    speech_style = SpeechStyle(
        tone=str(speech_payload.get("tone") or "balanced"),
        dominance_style=str(speech_payload.get("dominance_style") or "measured"),
        ritual_phrases=[str(item) for item in (speech_payload.get("ritual_phrases") or []) if str(item).strip()],
        formatting_style=str(speech_payload.get("formatting_style") or "plain"),
    )
    persona = PersonaProfile(
        name=str(persona_payload.get("name") or payload.get("display_name") or "Keyholder"),
        archetype=str(persona_payload.get("archetype") or "keyholder"),
        description=str(persona_payload.get("description") or ""),
        goals=[str(item) for item in (persona_payload.get("goals") or []) if str(item).strip()],
        speech_style=speech_style,
    )
    return CharacterCard(
        card_id=str(payload.get("card_id") or "builtin-keyholder"),
        display_name=str(payload.get("display_name") or persona.name),
        persona=persona,
        greeting_template=str(payload.get("greeting_template") or ""),
        scenario_hooks=[str(item) for item in (payload.get("scenario_hooks") or []) if str(item).strip()],
        tags=[str(item) for item in (payload.get("tags") or []) if str(item).strip()],
    )


def _scenario_from_payload(payload: dict[str, Any] | None) -> ScenarioDefinition | None:
    if not isinstance(payload, dict):
        return None
    lorebook: list[LoreEntry] = []
    for entry in payload.get("lorebook") or []:
        if not isinstance(entry, dict):
            continue
        lorebook.append(
            LoreEntry(
                key=str(entry.get("key") or "lore"),
                content=str(entry.get("content") or ""),
                triggers=[str(item) for item in (entry.get("triggers") or []) if str(item).strip()],
                priority=int(entry.get("priority") or 0),
            )
        )
    phases: list[ScenarioPhase] = []
    for phase in payload.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        phases.append(
            ScenarioPhase(
                phase_id=str(phase.get("phase_id") or "phase"),
                title=str(phase.get("title") or "Phase"),
                objective=str(phase.get("objective") or ""),
                guidance=str(phase.get("guidance") or ""),
            )
        )
    return ScenarioDefinition(
        scenario_id=str(payload.get("scenario_id") or "session"),
        title=str(payload.get("title") or "Session"),
        summary=str(payload.get("summary") or ""),
        lorebook=lorebook,
        phases=phases,
        tags=[str(item) for item in (payload.get("tags") or []) if str(item).strip()],
    )


def _prompt_profile_from_payload(payload: dict[str, Any] | None) -> PromptProfile:
    if not isinstance(payload, dict):
        return PromptProfile()
    return PromptProfile(
        name=str(payload.get("name") or "default"),
        version=str(payload.get("version") or "v1"),
        mode=str(payload.get("mode") or "session"),
    )


def _session_summary_from_payload(payload: dict[str, Any] | None) -> SessionSummary | None:
    if not isinstance(payload, dict):
        return None
    summary_text = str(payload.get("summary_text") or "").strip()
    if not summary_text:
        return None
    source_turn_no = payload.get("source_turn_no")
    return SessionSummary(
        summary_text=summary_text,
        source_turn_no=int(source_turn_no) if isinstance(source_turn_no, int) else None,
        created_at_iso=str(payload.get("created_at_iso") or "") or None,
    )


def _memory_entries_from_payload(payload: list[dict[str, Any]] | None) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    for entry in payload or []:
        if not isinstance(entry, dict):
            continue
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        entries.append(
            MemoryEntry(
                kind=str(entry.get("kind") or "session"),
                content=content,
                source=str(entry.get("source") or "session"),
                tags=[str(item) for item in (entry.get("tags") or []) if str(item).strip()],
                weight=float(entry.get("weight") or 1.0),
            )
        )
    return entries


def build_psychogram_summary(psychogram: dict, policy: dict) -> str:
    traits = psychogram.get("traits", {})
    top_traits = ", ".join(
        f"{name}:{score}"
        for name, score in sorted(traits.items(), key=lambda item: item[1], reverse=True)[:4]
    )
    interaction = psychogram.get("interaction_preferences", {})
    safety = psychogram.get("safety_profile", {})
    personal = psychogram.get("personal_preferences", {})
    hard_limits = str(psychogram.get("hard_limits_text") or psychogram.get("taboo_text") or "").strip()
    soft_limits = str(psychogram.get("soft_limits_text") or _fixed_soft_limits_text("de")).strip()
    generated_contract = (policy or {}).get("generated_contract", {}) or {}
    contract_consent = generated_contract.get("consent", {}) if isinstance(generated_contract, dict) else {}
    consent_required = str(contract_consent.get("required_text") or "")
    consent_accepted = bool(contract_consent.get("accepted"))
    consent_accepted_at = str(contract_consent.get("accepted_at") or "")
    consent_state = (
        f"accepted@{consent_accepted_at or '-'}"
        if consent_accepted
        else f"pending(required='{consent_required or '-'}')"
    )
    limits = (policy or {}).get("limits", {})
    interaction_policy = (policy or {}).get("interaction_profile", {})
    seal_cfg = (policy or {}).get("seal", {})
    seal_mode = str(seal_cfg.get("mode") or "none").strip().lower()
    runtime_seal = (policy or {}).get("runtime_seal", {})
    seal_status = str(runtime_seal.get("status") or "none").strip().lower()
    seal_text = str(runtime_seal.get("current_text") or "").strip()
    seal_broken = bool(runtime_seal.get("needs_new_seal", False))
    seal_info = (
        f"mode={seal_mode}"
        + (f", status={seal_status}, current_number={seal_text}" if seal_mode != "none" and seal_status and seal_text else "")
        + (", needs_renewal=true" if seal_broken else "")
    )

    safety_mode = safety.get("mode", "safeword")
    safety_text = f"mode={safety_mode}"
    abort_protocol = None
    if safety_mode == "safeword" and safety.get("safeword"):
        safety_text = f"{safety_text}, safeword={safety.get('safeword')}"
        abort_protocol = safety.get("safeword_abort_protocol")
    if safety_mode == "traffic_light" and isinstance(safety.get("traffic_light_words"), dict):
        tl = safety.get("traffic_light_words")
        safety_text = f"{safety_text}, tl={tl.get('green','')}/{tl.get('yellow','')}/{tl.get('red','')}"
        abort_protocol = safety.get("red_abort_protocol")
    if isinstance(abort_protocol, dict):
        q_count = int(abort_protocol.get("confirmation_questions_required", 2))
        reason_required = bool(abort_protocol.get("reason_required", True))
        safety_text = f"{safety_text}, emergency_abort=immediate_after_{q_count}_checks(reason_required={reason_required})"

    return (
        f"summary={psychogram.get('summary', 'n/a')}; "
        f"top_traits={top_traits or 'n/a'}; "
        f"instruction_style={interaction.get('instruction_style', 'mixed')}; "
        f"escalation_mode={interaction.get('escalation_mode', 'moderate')}; "
        f"experience={interaction.get('experience_level', 5)}/"
        f"{interaction.get('experience_profile', 'intermediate')}; "
        f"grooming_preference={personal.get('grooming_preference', 'no_preference')}; "
        f"hard_limits={hard_limits or '-'}; "
        f"soft_limits={soft_limits or '-'}; "
        f"contract_consent={consent_state}; "
        f"safety={safety_text}; "
        f"seal={seal_info}; "
        f"tone={interaction_policy.get('preferred_tone', 'balanced')}; "
        f"intensity={limits.get('max_intensity_level', 2)}; "
        f"hard_stop={policy.get('hard_stop_enabled', True)}"
    )


def _resolve_app(owner: Any) -> Any:
    return getattr(owner, "app", owner)


def build_tools_summary(owner: Any) -> str:
    app = _resolve_app(owner)
    registry = getattr(app.state, "tool_registry", None)
    if registry is None or not hasattr(registry, "list_tools"):
        return "-"
    execute_tools = registry.list_tools(mode="execute")
    suggest_tools = registry.list_tools(mode="suggest")
    return (
        f"execute={','.join(execute_tools) or '-'}; "
        f"suggest={','.join(suggest_tools) or '-'}; "
        "live_session_read=GET /api/v1/sessions/{session_id}/live (?auth_token=wearer_token OR ?ai_access_token=ai_token) "
        "[optional: ?detail_level=light|full (default:light, light=only time/status ~270tok, full=+setup/psychogram ~350tok)]; "
        "seal_status=GET /api/v1/chat/seal/{session_id} (?ai_access_token=ai_token) [returns seal_mode + current_text/status]; "
        "payload_rules=add_time/reduce_time require {seconds:int>0}; "
        "pause_timer/unpause_timer require {}"
    )


def build_turn_history(db, session_id: str, limit: int) -> list[RoleplayTurn]:
    recent_turns = (
        db.scalars(
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(Turn.turn_no.desc())
            .limit(limit)
        )
        .all()
    )
    return [
        RoleplayTurn(
            turn_no=turn.turn_no,
            player_action=turn.player_action,
            ai_narration=turn.ai_narration,
        )
        for turn in reversed(recent_turns)
    ]


def build_roleplay_context(
    db,
    request,
    session: ChastitySession,
    action: str,
    language: str,
    *,
    history_turn_limit: int,
    include_tools_summary: bool,
    live_snapshot_builder: Callable[[ChastitySession], dict[str, Any] | None],
) -> RoleplayContext:
    psychogram_raw = session.psychogram_snapshot_json
    policy_raw = session.policy_snapshot_json if session.policy_snapshot_json else "{}"
    psychogram = json.loads(psychogram_raw) if isinstance(psychogram_raw, str) else (psychogram_raw or {})
    policy = json.loads(policy_raw) if isinstance(policy_raw, str) else (policy_raw or {})
    roleplay_payload = policy.get("roleplay") if isinstance(policy.get("roleplay"), dict) else {}
    return RoleplayContext(
        session_id=session.id,
        action=action,
        language=language,
        psychogram=psychogram,
        policy=policy,
        psychogram_summary=build_psychogram_summary(psychogram, policy),
        turns_history=build_turn_history(db, session.id, max(1, history_turn_limit)),
        live_snapshot=live_snapshot_builder(session),
        tools_summary=build_tools_summary(request) if include_tools_summary else None,
        character_card=_character_card_from_payload(roleplay_payload.get("character_card")),
        scenario=_scenario_from_payload(roleplay_payload.get("scenario")),
        scene_state=SceneState(name="active-session", phase=session.status, status="active"),
        session_summary=_session_summary_from_payload(roleplay_payload.get("session_summary")),
        memory_entries=_memory_entries_from_payload(roleplay_payload.get("memory_entries")),
        prompt_profile=_prompt_profile_from_payload(roleplay_payload.get("prompt_profile")),
    )


def build_setup_preview_roleplay_context(
    request,
    *,
    action: str,
    language: str,
    psychogram: dict,
    policy: dict,
    include_tools_summary: bool = True,
) -> RoleplayContext:
    roleplay_payload = policy.get("roleplay") if isinstance(policy.get("roleplay"), dict) else {}
    return RoleplayContext(
        session_id="setup-preview",
        action=action,
        language=language,
        psychogram=psychogram,
        policy=policy,
        psychogram_summary=build_psychogram_summary(psychogram, policy),
        tools_summary=build_tools_summary(request) if include_tools_summary else None,
        character_card=_character_card_from_payload(roleplay_payload.get("character_card")),
        scenario=_scenario_from_payload(roleplay_payload.get("scenario")),
        scene_state=SceneState(name="setup-preview", phase="preview", status="active"),
        session_summary=_session_summary_from_payload(roleplay_payload.get("session_summary")),
        memory_entries=_memory_entries_from_payload(roleplay_payload.get("memory_entries")),
        prompt_profile=_prompt_profile_from_payload(roleplay_payload.get("prompt_profile")),
    )


def to_story_turn_context(context: RoleplayContext) -> StoryTurnContext:
    return StoryTurnContext(
        session_id=context.session_id,
        action=context.action,
        language=context.language,
        psychogram_summary=context.psychogram_summary,
        turns_history=[
            TurnHistoryEntry(
                turn_no=entry.turn_no,
                player_action=entry.player_action,
                ai_narration=entry.ai_narration,
            )
            for entry in context.turns_history
        ],
        live_snapshot=context.live_snapshot,
        tools_summary=context.tools_summary,
        policy=context.policy,
    )


def _safe_days_between(start_value: str | None, end_value: str | None) -> int | None:
    start_raw = str(start_value or "").strip()
    end_raw = str(end_value or "").strip()
    if not start_raw or not end_raw:
        return None
    try:
        start_date = date.fromisoformat(start_raw)
        end_date = date.fromisoformat(end_raw)
    except ValueError:
        return None
    return (end_date - start_date).days


def sanitize_setup_for_ai(setup_session: dict | None) -> dict | None:
    if not isinstance(setup_session, dict):
        return None
    payload = json.loads(json.dumps(setup_session))
    policy_preview = payload.get("policy_preview")
    if isinstance(policy_preview, dict):
        generated_contract = policy_preview.get("generated_contract")
        if isinstance(generated_contract, dict):
            consent = generated_contract.get("consent")
            if isinstance(consent, dict) and "accepted_text" in consent:
                consent.pop("accepted_text", None)
            generated_contract.pop("signed_markdown", None)
            generated_contract.pop("markdown", None)
    payload.pop("auth_token", None)
    payload.pop("llm_api_key", None)
    payload.pop("provider_api_key", None)
    payload.pop("api_key", None)
    return payload


def build_live_snapshot_for_setup_preview(db, session: ChastitySession) -> dict[str, Any]:
    user = db.get(User, session.user_id)
    setup_session_id = find_setup_session_id_for_active_session(session.user_id, session.id)
    setup_session = None
    if setup_session_id:
        setup_session = load_sessions().get(setup_session_id)
        if isinstance(setup_session, dict):
            setup_session = sanitize_setup_for_ai(setup_session)

    snapshot = {
        "session_id": session.id,
        "status": session.status,
        "language": session.language,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }
    if user is not None:
        snapshot["user"] = {
            "user_id": user.id,
            "display_name": user.display_name,
            "username": user.username,
        }
    if setup_session is not None:
        snapshot["setup_context"] = setup_session
        snapshot["setup_session_id"] = setup_session_id
        contract = (setup_session.get("policy_preview") or {}).get("contract") or {}
        snapshot["contract_window_days"] = _safe_days_between(contract.get("start_date"), contract.get("proposed_end_date"))
    return snapshot
