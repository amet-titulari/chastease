import json
import re
from datetime import date
from pathlib import Path

from fastapi import Request
from sqlalchemy import select

from chastease.api.setup_domain import _fixed_soft_limits_text, _lang, _required_contract_consent_text
from chastease.connectors import generate_narration_with_optional_profile
from chastease.models import ChastitySession, Turn, User
from chastease.services.ai.base import StoryTurnContext


def extract_pending_actions(narration: str) -> tuple[str, list[dict], list[dict]]:
    pattern = re.compile(r"\[\[ACTION:(?P<kind>[a-zA-Z0-9_\-]+)\|(?P<payload>\{.*?\})\]\]")
    request_json_pattern = re.compile(r"\[\[REQUEST:(?P<kind>[a-zA-Z0-9_\-]+)\|(?P<payload>\{.*?\})\]\]")
    request_call_pattern = re.compile(r"\[REQUEST:\s*(?P<kind>[a-zA-Z0-9_\-]+)\((?P<args>.*?)\)\]", re.IGNORECASE)
    suggest_pattern = re.compile(r"\[Suggest:\s*(?P<kind>[a-zA-Z0-9_\-]+)\((?P<args>.*?)\)\]", re.IGNORECASE)
    file_pattern = re.compile(r"\[\[FILE\|(?P<payload>\{.*?\})\]\]")
    actions: list[dict] = []
    generated_files: list[dict] = []
    cleaned = narration

    def _parse_suggest_args(raw_args: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for match in re.finditer(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(\"[^\"]*\"|'[^']*'|[^,]+)", raw_args):
            key = str(match.group(1) or "").strip().lower()
            value = str(match.group(2) or "").strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if key:
                parsed[key] = value.strip()
        return parsed

    def _parse_duration_seconds(raw_value: str) -> int | None:
        text = str(raw_value or "").strip().lower()
        if not text:
            return None
        match = re.match(
            r"^(?P<amount>\d+)\s*(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|stunde|stunden|tag|tage)?$",
            text,
        )
        if not match:
            return None
        amount = int(match.group("amount"))
        unit = match.group("unit") or "s"
        factor = {
            "s": 1,
            "sec": 1,
            "secs": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "mins": 60,
            "minute": 60,
            "minutes": 60,
            "h": 3600,
            "hr": 3600,
            "hrs": 3600,
            "hour": 3600,
            "hours": 3600,
            "d": 86400,
            "day": 86400,
            "days": 86400,
            "stunde": 3600,
            "stunden": 3600,
            "tag": 86400,
            "tage": 86400,
        }.get(unit, 1)
        return amount * factor

    for match in pattern.finditer(narration):
        action_type = match.group("kind")
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"raw": payload_text}
        actions.append({"action_type": action_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in request_json_pattern.finditer(narration):
        action_type = str(match.group("kind") or "").strip().lower()
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"raw": payload_text}
        actions.append({"action_type": action_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in request_call_pattern.finditer(narration):
        action_type = str(match.group("kind") or "").strip().lower()
        args_text = str(match.group("args") or "")
        args = _parse_suggest_args(args_text)
        payload: dict[str, object] = dict(args)
        normalized_type = {
            "addtime": "add_time",
            "time_add": "add_time",
            "extend_time": "add_time",
            "reducetime": "reduce_time",
            "time_reduce": "reduce_time",
        }.get(action_type, action_type)
        if normalized_type in {"add_time", "reduce_time"}:
            seconds = _parse_duration_seconds(str(args.get("duration") or args.get("seconds") or ""))
            if seconds is not None and seconds > 0:
                payload = {"seconds": seconds}
        actions.append({"action_type": normalized_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in suggest_pattern.finditer(narration):
        action_type = str(match.group("kind") or "").strip().lower()
        args_text = str(match.group("args") or "")
        args = _parse_suggest_args(args_text)
        payload: dict[str, object] = dict(args)
        normalized_type = {
            "addtime": "add_time",
            "time_add": "add_time",
            "extend_time": "add_time",
            "reducetime": "reduce_time",
            "time_reduce": "reduce_time",
        }.get(action_type, action_type)
        if normalized_type in {"add_time", "reduce_time"}:
            seconds = _parse_duration_seconds(str(args.get("duration") or args.get("seconds") or ""))
            if seconds is not None and seconds > 0:
                payload = {"seconds": seconds}
        actions.append({"action_type": normalized_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in file_pattern.finditer(narration):
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"name": "response.txt", "mime_type": "text/plain", "content": payload_text}
        generated_files.append(
            {
                "name": str(payload.get("name", "response.txt")),
                "mime_type": str(payload.get("mime_type", "text/plain")),
                "content": str(payload.get("content", "")),
            }
        )
        cleaned = cleaned.replace(match.group(0), "").strip()
    return cleaned, actions, generated_files


def _build_ai_context_summary(psychogram: dict, policy: dict) -> str:
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
        f"tone={interaction_policy.get('preferred_tone', 'balanced')}; "
        f"intensity={limits.get('max_intensity_level', 2)}; "
        f"hard_stop={policy.get('hard_stop_enabled', True)}"
    )


def _available_tools_summary(request: Request) -> str:
    registry = getattr(request.app.state, "tool_registry", None)
    if registry is None or not hasattr(registry, "list_tools"):
        return "-"
    execute_tools = registry.list_tools(mode="execute")
    suggest_tools = registry.list_tools(mode="suggest")
    return (
        f"execute={','.join(execute_tools) or '-'}; "
        f"suggest={','.join(suggest_tools) or '-'}; "
        "payload_rules=add_time/reduce_time require {seconds:int>0}; "
        "pause_timer/unpause_timer require {}"
    )


def _resolve_setup_user_display_name(db, setup_session: dict) -> str:
    cached = str(
        setup_session.get("user_display_name")
        or setup_session.get("display_name")
        or setup_session.get("username")
        or ""
    ).strip()
    if cached:
        return cached
    user_id = str(setup_session.get("user_id") or "").strip()
    if not user_id:
        return "sub"
    user = db.get(User, user_id)
    resolved = str((user.display_name if user is not None else "") or "").strip() or user_id
    setup_session["user_display_name"] = resolved
    return resolved


def generate_ai_narration_for_session(
    db, request: Request, session: ChastitySession, action: str, language: str, attachments: list[dict] | None = None
) -> str:
    psychogram = json.loads(session.psychogram_snapshot_json)
    policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
    psychogram_summary = _build_ai_context_summary(psychogram, policy)

    recent_turns = (
        db.scalars(
            select(Turn)
            .where(Turn.session_id == session.id)
            .order_by(Turn.turn_no.desc())
            .limit(6)
        )
        .all()
    )
    recent_turns = list(reversed(recent_turns))
    history_lines: list[str] = []
    for turn in recent_turns:
        history_lines.append(f"Wearer: {turn.player_action}")
        history_lines.append(f"Keyholder: {turn.ai_narration}")
    history_block = "\n".join(history_lines).strip()
    attachment_names = [str(item.get("name", "file")) for item in (attachments or [])]
    attachment_hint = f"\nCurrent attachments: {', '.join(attachment_names)}" if attachment_names else ""
    tools_summary = _available_tools_summary(request)
    action_with_context = (
        (f"Recent dialogue:\n{history_block}\n\nCurrent wearer input: {action}{attachment_hint}")
        if history_block
        else f"Current wearer input: {action}{attachment_hint}"
    )
    action_with_context = f"{action_with_context}\n\nAvailable tools: {tools_summary}"

    context = StoryTurnContext(
        session_id=session.id,
        action=action_with_context,
        language=language,
        psychogram_summary=psychogram_summary,
    )
    return generate_narration_with_optional_profile(
        db,
        request,
        user_id=session.user_id,
        context=context,
        attachments=attachments or [],
    )


def generate_ai_narration_for_setup_preview(
    db,
    request: Request,
    user_id: str,
    action: str,
    language: str,
    psychogram: dict,
    policy: dict,
    attachments: list[dict] | None = None,
) -> str:
    context = StoryTurnContext(
        session_id="setup-preview",
        action=f"{action}\n\nAvailable tools: {_available_tools_summary(request)}",
        language=language,
        psychogram_summary=_build_ai_context_summary(psychogram, policy),
    )
    return generate_narration_with_optional_profile(
        db,
        request,
        user_id=user_id,
        context=context,
        attachments=attachments or [],
    )


def _is_provider_error_text(text: str | None) -> bool:
    if not text:
        return False
    normalized = str(text).strip().lower()
    markers = [
        "provider-anfrage fehlgeschlagen",
        "der provider hat die anfrage abgelehnt",
        "provider request failed",
        "provider rejected the request",
        "provider timeout",
        "provider-timeout",
        "llm-anfrage unerwartet fehlgeschlagen",
        "llm request failed unexpectedly",
    ]
    return any(marker in normalized for marker in markers)


def _default_proposed_end_date(setup_session: dict) -> str | None:
    contract = (setup_session.get("policy_preview") or {}).get("contract") or {}
    if contract.get("end_date"):
        return str(contract.get("end_date"))
    if contract.get("max_end_date"):
        return str(contract.get("max_end_date"))
    if contract.get("min_end_date"):
        return str(contract.get("min_end_date"))
    return None


def _normalize_proposed_end_date(raw_value: str | None, setup_session: dict) -> str | None:
    if not raw_value:
        return _default_proposed_end_date(setup_session)
    value = str(raw_value).strip()
    upper = value.upper()
    if upper in {"AI_DECIDES", "KI_ENTSCHEIDET", "KI-ENTSCHEIDET"}:
        return None
    contract = (setup_session.get("policy_preview") or {}).get("contract") or {}
    try:
        candidate = date.fromisoformat(value)
    except ValueError:
        return _default_proposed_end_date(setup_session)

    try:
        min_end = date.fromisoformat(contract["min_end_date"]) if contract.get("min_end_date") else None
    except ValueError:
        min_end = None
    try:
        max_end = date.fromisoformat(contract["max_end_date"]) if contract.get("max_end_date") else None
    except ValueError:
        max_end = None
    if min_end and candidate < min_end:
        candidate = min_end
    if max_end and candidate > max_end:
        candidate = max_end
    return candidate.isoformat()


def _extract_proposed_end_date(raw_text: str, setup_session: dict) -> tuple[str, str | None]:
    text = (raw_text or "").strip()
    match = re.search(
        r"(?:PROPOSED_END_DATE|VORGESCHLAGENES_ENDDATUM)\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|AI_DECIDES|KI_ENTSCHEIDET)",
        text,
        flags=re.IGNORECASE,
    )
    proposed = _normalize_proposed_end_date(match.group(1) if match else None, setup_session)
    cleaned = text
    if match:
        cleaned = re.sub(
            r"(?:PROPOSED_END_DATE|VORGESCHLAGENES_ENDDATUM)\s*:\s*(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|AI_DECIDES|KI_ENTSCHEIDET)\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
    if not cleaned:
        cleaned = text or "-"
    return cleaned, proposed


def generate_psychogram_analysis_with_end_date_for_setup(
    db, request: Request, setup_session: dict
) -> tuple[str, str | None]:
    psychogram = setup_session.get("psychogram") or {}
    policy = setup_session.get("policy_preview") or {}
    contract = policy.get("contract") or {}
    lang = _lang(setup_session.get("language", "de"))
    action = (
        (
            "Analyze this psychogram for dashboard summary. Provide concise guidance: tone, boundaries, intensity and first steps. "
            f"Choose a provisional session end date within this contract window: start={contract.get('start_date')}, "
            f"min_end={contract.get('min_end_date')}, max_end={contract.get('max_end_date')}. "
            "First line MUST be exactly: PROPOSED_END_DATE: YYYY-MM-DD or PROPOSED_END_DATE: AI_DECIDES."
        )
        if lang == "en"
        else (
            "Analysiere dieses Psychogramm fuer eine Dashboard-Zusammenfassung. Gib kurze Hinweise zu Ton, Grenzen, Intensitaet und ersten Schritten. "
            f"Waehle ein vorlaeufiges Session-Enddatum innerhalb dieses Vertragsfensters: start={contract.get('start_date')}, "
            f"min_end={contract.get('min_end_date')}, max_end={contract.get('max_end_date')}. "
            "Die erste Zeile MUSS exakt sein: VORGESCHLAGENES_ENDDATUM: YYYY-MM-DD oder VORGESCHLAGENES_ENDDATUM: KI_ENTSCHEIDET."
        )
    )
    try:
        raw = generate_ai_narration_for_setup_preview(
            db,
            request,
            setup_session["user_id"],
            action,
            lang,
            psychogram,
            policy,
        )
        if _is_provider_error_text(raw):
            raise RuntimeError(str(raw))
        analysis, proposed_end_date = _extract_proposed_end_date(raw, setup_session)
        return analysis, proposed_end_date
    except Exception:
        interaction = psychogram.get("interaction_preferences", {})
        safety = psychogram.get("safety_profile", {})
        fallback_text = (
            f"Profilanalyse: escalation={interaction.get('escalation_mode', 'moderate')}, "
            f"experience={interaction.get('experience_profile', 'intermediate')}, "
            f"safety={safety.get('mode', 'safeword')}."
        )
        return fallback_text, _default_proposed_end_date(setup_session)


def _contract_template_path(lang: str) -> Path:
    root = Path(__file__).resolve().parents[3]
    filename = "CONTRACT_TEMPLATE_EN.md" if _lang(lang) == "en" else "CONTRACT_TEMPLATE_DE.md"
    return root / "docs" / "templates" / filename


def _strip_front_matter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return text
    return text[end_idx + 5 :].lstrip()


def _looks_like_contract_text(text: str, lang: str) -> bool:
    content = (text or "").strip()
    if len(content) < 350:
        return False
    if _lang(lang) == "en":
        return ("Article 1" in content) and ("Signature" in content)
    return ("Artikel 1" in content) and ("Signatur" in content)


def _build_contract_fallback_text(setup_session: dict) -> str:
    # Reuse the existing strict template renderer so all {{placeholders}} are filled.
    try:
        from chastease.api import routes as legacy_routes

        rendered = str(legacy_routes._render_contract_template(setup_session) or "").strip()
        if rendered:
            return rendered
    except Exception:
        pass

    lang = _lang(setup_session.get("language", "de"))
    template_path = _contract_template_path(lang)
    try:
        raw_template = template_path.read_text(encoding="utf-8")
    except Exception:
        return "Contract template unavailable."
    return _strip_front_matter(raw_template).strip()


def generate_contract_for_setup(db, request: Request, setup_session: dict) -> str:
    setup_session["user_display_name"] = _resolve_setup_user_display_name(db, setup_session)
    psychogram = setup_session.get("psychogram") or {}
    policy = setup_session.get("policy_preview") or {}
    lang = _lang(setup_session.get("language", "de"))
    contract = policy.get("contract") or {}
    analysis = setup_session.get("psychogram_analysis") or psychogram.get("analysis") or ""
    draft = _build_contract_fallback_text(setup_session)
    if not draft.strip():
        return "Contract draft unavailable."

    action = (
        (
            "You are revising a generated chastity contract draft. "
            "You may refine wording and add short useful clarifications when necessary. "
            "Do not remove safety rules, contract dates, or article structure. "
            "Keep markdown and keep headings/articles intact. "
            f"The provisional end date is {contract.get('proposed_end_date') or 'AI-decides'} and may be adjusted by the keyholder within min/max bounds. "
            f"Psychogram analysis context: {analysis}\n\n"
            "DRAFT CONTRACT:\n"
            f"{draft}"
        )
        if lang == "en"
        else (
            "Du ueberarbeitest einen erzeugten Keuschheitsvertrag-Entwurf. "
            "Du darfst Formulierungen verbessern und bei Bedarf kurze sinnvolle Klarstellungen ergaenzen. "
            "Sicherheitsregeln, Vertragsdaten und Artikelstruktur duerfen nicht entfernt werden. "
            "Markdown beibehalten, Ueberschriften/Artikel intakt lassen. "
            f"Das vorlaeufige Enddatum ist {contract.get('proposed_end_date') or 'KI-entscheidet'} und darf durch die Keyholderin innerhalb der Min/Max-Grenzen angepasst werden. "
            f"Kontext Psychogramm-Analyse: {analysis}\n\n"
            "VERTRAGS-ENTWURF:\n"
            f"{draft}"
        )
    )
    try:
        raw = generate_ai_narration_for_setup_preview(
            db,
            request,
            setup_session["user_id"],
            action,
            lang,
            psychogram,
            policy,
        )
        if _is_provider_error_text(raw):
            raise RuntimeError(str(raw))
        if not _looks_like_contract_text(raw, lang):
            raise RuntimeError("contract format validation failed")
        return raw.strip()
    except Exception:
        return draft
