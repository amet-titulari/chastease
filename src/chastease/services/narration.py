import json
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path

from fastapi import Request
from sqlalchemy import select

from chastease.api.setup_domain import _fixed_soft_limits_text, _lang, _required_contract_consent_text
from chastease.connectors import generate_narration_with_optional_profile
from chastease.models import ChastitySession, Turn, User
from chastease.services.ai.base import StoryTurnContext

logger = logging.getLogger(__name__)


def extract_pending_actions(narration: str) -> tuple[str, list[dict], list[dict]]:
    pattern = re.compile(r"\[\[ACTION:(?P<kind>[\w\-]+)\|(?P<payload>\{.*?\})\]\]", re.DOTALL)
    request_json_pattern = re.compile(
        r"\[\[REQUEST:(?P<kind>[\w\-]+)\|(?P<payload>\{.*?\})\]\]",
        re.DOTALL,
    )
    request_call_pattern = re.compile(
        r"\[REQUEST:\s*(?P<kind>[\w\-]+)\((?P<args>.*?)\)\]",
        re.IGNORECASE | re.DOTALL,
    )
    suggest_pattern = re.compile(
        r"\[Suggest:\s*(?P<kind>[\w\-]+)\((?P<args>.*?)\)\]",
        re.IGNORECASE | re.DOTALL,
    )
    file_pattern = re.compile(r"\[\[FILE\|(?P<payload>\{.*?\})\]\]", re.DOTALL)
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

    def _normalize_action_type(raw: str) -> str:
        action_type = str(raw or "").strip().lower()
        alias_map = {
            "addtime": "add_time",
            "time_add": "add_time",
            "extend_time": "add_time",
            "reducetime": "reduce_time",
            "time_reduce": "reduce_time",
            "pause": "pause_timer",
            "pausetimer": "pause_timer",
            "freeze": "pause_timer",
            "freeze_timer": "pause_timer",
            "resume": "unpause_timer",
            "unpause": "unpause_timer",
            "unpausetimer": "unpause_timer",
            "unfreeze": "unpause_timer",
            "hygieneopen": "hygiene_open",
            "hygiene_open": "hygiene_open",
            "hygieneoeffnung": "hygiene_open",
            "hygiene_oeffnung": "hygiene_open",
            "hygieneöffnung": "hygiene_open",
            "hygiene-close": "hygiene_close",
            "hygieneclose": "hygiene_close",
            "hygiene_close": "hygiene_close",
            "hygieneschliessen": "hygiene_close",
            "hygiene_schliessen": "hygiene_close",
            "hygieneschließen": "hygiene_close",
            "hygiene_schließen": "hygiene_close",
            "ttlockopen": "hygiene_open",
            "ttlock_open": "hygiene_open",
            "ttlock-close": "hygiene_close",
            "ttlockclose": "hygiene_close",
            "ttlock_close": "hygiene_close",
        }
        return alias_map.get(action_type, action_type)

    for match in pattern.finditer(narration):
        action_type = _normalize_action_type(match.group("kind"))
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"raw": payload_text}
        actions.append({"action_type": action_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in request_json_pattern.finditer(narration):
        action_type = _normalize_action_type(match.group("kind"))
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"raw": payload_text}
        actions.append({"action_type": action_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in request_call_pattern.finditer(narration):
        action_type = _normalize_action_type(match.group("kind"))
        args_text = str(match.group("args") or "")
        args = _parse_suggest_args(args_text)
        payload: dict[str, object] = dict(args)
        normalized_type = _normalize_action_type(action_type)
        if normalized_type in {"add_time", "reduce_time"}:
            seconds = _parse_duration_seconds(str(args.get("duration") or args.get("seconds") or ""))
            if seconds is not None and seconds > 0:
                payload = {"seconds": seconds}
        actions.append({"action_type": normalized_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in suggest_pattern.finditer(narration):
        action_type = _normalize_action_type(match.group("kind"))
        args_text = str(match.group("args") or "")
        args = _parse_suggest_args(args_text)
        payload: dict[str, object] = dict(args)
        normalized_type = _normalize_action_type(action_type)
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

    config = request.app.state.config
    history_turn_limit = max(1, int(getattr(config, "LLM_CHAT_HISTORY_TURNS", 3)))
    history_chars = max(80, int(getattr(config, "LLM_CHAT_HISTORY_CHARS_PER_TURN", 280)))
    include_tools_summary = bool(getattr(config, "LLM_CHAT_INCLUDE_TOOLS_SUMMARY", False))

    def _trim(text: str) -> str:
        compact = " ".join(str(text or "").split())
        if len(compact) <= history_chars:
            return compact
        return compact[: max(1, history_chars - 3)].rstrip() + "..."

    recent_turns = (
        db.scalars(
            select(Turn)
            .where(Turn.session_id == session.id)
            .order_by(Turn.turn_no.desc())
            .limit(history_turn_limit)
        )
        .all()
    )
    recent_turns = list(reversed(recent_turns))
    history_lines: list[str] = []
    for turn in recent_turns:
        history_lines.append(f"Wearer: {_trim(turn.player_action)}")
        history_lines.append(f"Keyholder: {_trim(turn.ai_narration)}")
    history_block = "\n".join(history_lines).strip()
    attachment_names = [str(item.get("name", "file")) for item in (attachments or [])]
    attachment_hint = f"\nCurrent attachments: {', '.join(attachment_names)}" if attachment_names else ""
    action_with_context = (
        (f"Recent dialogue:\n{history_block}\n\nCurrent wearer input: {action}{attachment_hint}")
        if history_block
        else f"Current wearer input: {action}{attachment_hint}"
    )
    if include_tools_summary:
        action_with_context = f"{action_with_context}\n\nAvailable tools: {_available_tools_summary(request)}"

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


def _limit_text(text: str, max_chars: int) -> str:
    raw = str(text or "")
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars].rstrip() + "\n\n[... gekuerzt ...]"


def _preview_line(text: str, max_chars: int = 140) -> str:
    single = " ".join(str(text or "").split())
    return single if len(single) <= max_chars else (single[: max_chars - 3] + "...")


def _slugify_heading(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    return slug or "section"


def _extract_json_payload(raw: str) -> dict | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(fenced)
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _contract_edit_targets(contract_text: str, lang: str) -> tuple[dict[str, dict[str, int]], list[str]]:
    text = str(contract_text or "")
    heading_pattern = re.compile(r"^(##|###)\s+(.+?)\s*$", re.MULTILINE)
    headings = list(heading_pattern.finditer(text))
    if not headings:
        return {}, []

    signature_start = len(text)
    for match in headings:
        level, title = match.group(1), match.group(2).strip().lower()
        if level == "##" and title in {"signature", "signatur"}:
            signature_start = match.start()
            break

    targets: dict[str, dict[str, int]] = {}
    order: list[str] = []
    parent_slug = ""
    parent_label = ""

    for index, match in enumerate(headings):
        if match.start() >= signature_start:
            break
        level = 2 if match.group(1) == "##" else 3
        title = match.group(2).strip()
        body_start = match.end()
        if body_start < len(text) and text[body_start] == "\n":
            body_start += 1

        body_end = signature_start
        for next_match in headings[index + 1 :]:
            if next_match.start() >= signature_start:
                break
            next_level = 2 if next_match.group(1) == "##" else 3
            if next_level <= level:
                body_end = next_match.start()
                break

        if level == 2:
            parent_slug = _slugify_heading(title)
            parent_label = title
            target = f"h2_{parent_slug}"
        else:
            child_slug = _slugify_heading(title)
            target = f"h3_{parent_slug}__{child_slug}" if parent_slug else f"h3_{child_slug}"

        targets[target] = {
            "start": body_start,
            "end": body_end,
            "level": level,
        }
        label = f"{target} -> {title}" if level == 2 else f"{target} -> {parent_label} / {title}"
        order.append(label)
    return targets, order


def _apply_contract_edits(
    contract_text: str,
    edits: list[dict],
    targets: dict[str, dict[str, int]],
) -> tuple[str, int]:
    replacements_by_target: dict[str, dict[str, int | str]] = {}
    requested_debug: list[dict[str, str | int | bool]] = []
    for edit in edits:
        target = str(edit.get("target", "")).strip()
        op = str(edit.get("op", "")).strip().lower()
        text = str(edit.get("text", "")).strip()
        accepted = target in targets and op in {"replace", "append", "prepend"} and bool(text)
        requested_debug.append(
            {
                "target": target or "-",
                "op": op or "-",
                "chars": len(text),
                "accepted_basic": accepted,
                "text_preview": _preview_line(text),
            }
        )
        if not accepted:
            continue
        if len(text) > 4000:
            text = text[:4000].rstrip()
        base = targets[target]
        start = int(base["start"])
        end = int(base["end"])
        current = str(contract_text[start:end]).strip()
        if op == "replace":
            updated = text
        elif op == "append":
            updated = f"{current}\n\n{text}" if current else text
        else:
            updated = f"{text}\n\n{current}" if current else text
        replacements_by_target[target] = {
            "start": start,
            "end": end,
            "updated": updated,
            "span": end - start,
            "level": int(base["level"]),
            "target": target,
            "op": op,
            "before_preview": _preview_line(current),
            "after_preview": _preview_line(updated),
        }

    logger.debug("Contract edit requests parsed: %s", requested_debug)

    replacements = sorted(
        replacements_by_target.values(),
        key=lambda item: (int(item["span"]), -int(item["level"])),
    )
    accepted: list[dict[str, int | str]] = []
    for candidate in replacements:
        c_start = int(candidate["start"])
        c_end = int(candidate["end"])
        overlaps = any(
            not (c_end <= int(existing["start"]) or c_start >= int(existing["end"]))
            for existing in accepted
        )
        if not overlaps:
            accepted.append(candidate)
    logger.debug(
        "Contract edits accepted after overlap-filter: %s",
        [
            {
                "target": str(item.get("target", "-")),
                "op": str(item.get("op", "-")),
                "before": str(item.get("before_preview", "")),
                "after": str(item.get("after_preview", "")),
            }
            for item in accepted
        ],
    )

    updated = contract_text
    for candidate in sorted(accepted, key=lambda item: int(item["start"]), reverse=True):
        start = int(candidate["start"])
        end = int(candidate["end"])
        body = str(candidate["updated"]).strip()
        replacement = f"{body}\n" if body else "\n"
        updated = f"{updated[:start]}{replacement}{updated[end:]}"
    return updated, len(accepted)


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
    analysis_for_prompt = _limit_text(analysis, 2000)
    draft_for_prompt = _limit_text(draft, 12000)
    targets, target_labels = _contract_edit_targets(draft, lang)
    if not targets:
        logger.warning("No editable contract targets detected. using unmodified template draft.")
        return draft.strip()
    allowed_targets = "\n".join(f"- {line}" for line in target_labels)
    max_edits = min(24, len(targets))

    action = (
        (
            "You are editing a generated chastity contract draft via structured section edits only. "
            "Do NOT output a contract. Output JSON only with this shape: "
            '{"edits":[{"target":"...","op":"replace|append|prepend","text":"..."}]}. '
            f"You may return 0 to {max_edits} edits. "
            "You may adjust wording freely across all editable sections, but never touch signature/footer blocks. "
            "Keep safety-critical intent and contract dates intact.\n\n"
            "Allowed targets:\n"
            f"{allowed_targets}\n\n"
            f"Provisional end date: {contract.get('proposed_end_date') or 'AI-decides'}.\n"
            f"Psychogram analysis context:\n{analysis_for_prompt}\n\n"
            "DRAFT CONTRACT (for context, do not rewrite fully):\n"
            f"{draft_for_prompt}"
        )
        if lang == "en"
        else (
            "Du bearbeitest einen erzeugten Keuschheitsvertrag-Entwurf nur ueber strukturierte Abschnitts-Edits. "
            "Gib KEINEN kompletten Vertrag aus. Gib nur JSON in diesem Format aus: "
            '{"edits":[{"target":"...","op":"replace|append|prepend","text":"..."}]}. '
            f"Du darfst 0 bis {max_edits} Edits liefern. "
            "Du darfst Formulierungen in allen erlaubten Abschnitten frei anpassen, aber niemals Signatur- oder Footer-Bloecke anfassen. "
            "Safety-Kernabsicht und Vertragsdaten muessen erhalten bleiben.\n\n"
            "Erlaubte Targets:\n"
            f"{allowed_targets}\n\n"
            f"Vorlaeufiges Enddatum: {contract.get('proposed_end_date') or 'KI-entscheidet'}.\n"
            f"Kontext Psychogramm-Analyse:\n{analysis_for_prompt}\n\n"
            "VERTRAGS-ENTWURF (nur Kontext, nicht komplett neu schreiben):\n"
            f"{draft_for_prompt}"
        )
    )
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
    payload = _extract_json_payload(raw)
    if not payload:
        logger.warning("Contract edit payload could not be parsed. using unmodified template draft.")
        return draft.strip()
    logger.debug("Contract edit payload raw JSON keys: %s", list(payload.keys()))
    edits = payload.get("edits")
    if not isinstance(edits, list):
        logger.warning("Contract edit payload missing 'edits' list. using unmodified template draft.")
        return draft.strip()
    logger.debug("Contract edit payload received edits=%s", len(edits))
    edited_contract, applied_count = _apply_contract_edits(draft, edits, targets)
    if applied_count == 0:
        logger.warning("Contract edit payload produced no applicable edits. using unmodified template draft.")
        return draft.strip()
    logger.info("Contract edits applied successfully. applied=%s requested=%s", applied_count, len(edits))
    return edited_contract.strip()
