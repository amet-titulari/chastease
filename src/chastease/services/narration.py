import json
import logging
import re
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import Request

from chastease.api.runtime import find_setup_session_id_for_active_session
from chastease.api.setup_domain import _fixed_soft_limits_text, _lang, _required_contract_consent_text
from chastease.connectors import generate_narration_with_optional_profile
from chastease.domains.roleplay import build_roleplay_context, build_setup_preview_roleplay_context, to_story_turn_context
from chastease.models import ChastitySession, Turn, User
from chastease.repositories.setup_store import load_sessions
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
        except (json.JSONDecodeError, ValueError):
            logger.warning("Ignoring ACTION with invalid JSON payload: %s", payload_text[:200])
            cleaned = cleaned.replace(match.group(0), "").strip()
            continue
        if not isinstance(payload, dict):
            logger.warning("Ignoring ACTION with non-dict payload type: %s", type(payload).__name__)
            cleaned = cleaned.replace(match.group(0), "").strip()
            continue
        actions.append({"action_type": action_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in request_json_pattern.finditer(narration):
        action_type = _normalize_action_type(match.group("kind"))
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Ignoring REQUEST with invalid JSON payload: %s", payload_text[:200])
            cleaned = cleaned.replace(match.group(0), "").strip()
            continue
        if not isinstance(payload, dict):
            logger.warning("Ignoring REQUEST with non-dict payload type: %s", type(payload).__name__)
            cleaned = cleaned.replace(match.group(0), "").strip()
            continue
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

    def _strip_orphan_machine_tags(text: str) -> str:
        if not text:
            return text
        markers = ("[[REQUEST:", "[[ACTION:")
        cleaned_text = text
        while True:
            positions = [idx for idx in (cleaned_text.find(m) for m in markers) if idx >= 0]
            if not positions:
                break
            start = min(positions)
            end = cleaned_text.find("]]", start)
            if end < 0:
                cleaned_text = cleaned_text[:start].rstrip()
                break
            cleaned_text = f"{cleaned_text[:start]}{cleaned_text[end + 2:]}".strip()
        return cleaned_text

    cleaned = _strip_orphan_machine_tags(cleaned)
    return cleaned, actions, generated_files


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


def _sanitize_setup_for_ai(setup_session: dict | None) -> dict | None:
    if not isinstance(setup_session, dict):
        return None
    payload = json.loads(json.dumps(setup_session))
    policy_preview = payload.get("policy_preview")
    if isinstance(policy_preview, dict):
        generated_contract = policy_preview.get("generated_contract")
        if isinstance(generated_contract, dict):
            full_text = str(generated_contract.get("text") or "")
            generated_contract["text"] = None
            generated_contract["text_omitted"] = bool(full_text)
            generated_contract["text_length"] = len(full_text)
    return payload


def _build_live_snapshot_for_ai(session: ChastitySession, mode: str = "light") -> dict:
    """
    Build live session snapshot for AI prompt injection.
    
    mode:
      - 'light': Only session_status and time_context (minimal tokens, ~300-400 chars)
      - 'full': Includes psychogram_summary and setup_session_id (~1200-1400 chars)
    """
    policy_raw = session.policy_snapshot_json if session.policy_snapshot_json else "{}"
    policy = json.loads(policy_raw) if isinstance(policy_raw, str) else (policy_raw or {})
    if not isinstance(policy, dict):
        policy = {}

    runtime_timer = policy.get("runtime_timer") if isinstance(policy.get("runtime_timer"), dict) else {}
    contract = policy.get("contract") if isinstance(policy.get("contract"), dict) else {}

    contract_start = str(contract.get("start_date") or "").strip() or None
    contract_min_end = str(contract.get("min_end_date") or "").strip() or None
    contract_max_end = str(contract.get("max_end_date") or "").strip() or None
    contract_proposed_end = str(contract.get("proposed_end_date") or "").strip() or None
    contract_end = str(contract.get("end_date") or "").strip() or None

    snapshot = {
        "session_id": session.id,
        "session_status": {
            "status": session.status,
            "language": session.language,
            "updated_at": session.updated_at.isoformat(),
        },
        "time_context": {
            "timer_state": str(runtime_timer.get("state") or "running").lower(),
            "is_paused": str(runtime_timer.get("state") or "running").lower() == "paused",
            "target_end_at": runtime_timer.get("effective_end_at") or contract_end or contract_proposed_end,
            "contract_start_date": contract_start,
            "contract_min_end_date": contract_min_end,
            "contract_max_end_date": contract_max_end,
            "contract_proposed_end_date": contract_proposed_end,
            "contract_end_date": contract_end,
            "contract_min_duration_days": _safe_days_between(contract_start, contract_min_end),
            "contract_max_duration_days": _safe_days_between(contract_start, contract_max_end),
            "contract_target_duration_days": _safe_days_between(contract_start, contract_end or contract_proposed_end),
            "runtime_timer": runtime_timer,
        },
    }

    # Add psychogram and setup details only in 'full' mode
    if str(mode).strip().lower() == "full":
        psychogram_raw = session.psychogram_snapshot_json if session.psychogram_snapshot_json else "{}"
        psychogram = json.loads(psychogram_raw) if isinstance(psychogram_raw, str) else (psychogram_raw or {})
        if not isinstance(psychogram, dict):
            psychogram = {}
        
        traits = psychogram.get("traits", {})
        likes = psychogram.get("likes", [])
        interaction_prefs = psychogram.get("interaction_preferences", {})
        compact_psychogram = {
            "top_traits": {k: traits.get(k) for k in likes[:4]} if isinstance(traits, dict) else {},
            "autonomy_profile": interaction_prefs.get("autonomy_profile"),
            "instruction_style": interaction_prefs.get("instruction_style"),
        }
        
        linked_setup_id = find_setup_session_id_for_active_session(session.user_id, session.id)
        
        snapshot["psychogram_summary"] = compact_psychogram
        snapshot["setup_session_id"] = linked_setup_id

    return snapshot


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
    config = request.app.state.config
    history_turn_limit = max(1, int(getattr(config, "LLM_CHAT_HISTORY_TURNS", 3)))
    include_tools_summary = bool(getattr(config, "LLM_CHAT_INCLUDE_TOOLS_SUMMARY", False))
    roleplay_context = build_roleplay_context(
        db,
        request,
        session,
        action,
        language,
        history_turn_limit=history_turn_limit,
        include_tools_summary=include_tools_summary,
        live_snapshot_builder=_build_live_snapshot_for_ai,
    )
    context = to_story_turn_context(roleplay_context)
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
    roleplay_context = build_setup_preview_roleplay_context(
        request,
        action=action,
        language=language,
        psychogram=psychogram,
        policy=policy,
    )
    context = to_story_turn_context(roleplay_context)
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


def _strip_actionable_task_sections(text: str) -> str:
    lines = [line for line in str(text or "").splitlines()]
    if not lines:
        return ""

    blocked_prefixes = (
        "nächste aufgabe",
        "naechste aufgabe",
        "next task",
        "next steps",
        "erste schritte",
        "first steps",
        "aufgabe:",
    )

    filtered: list[str] = []
    skip_indented = False
    for raw_line in lines:
        line = raw_line.strip()
        lower = line.lower().lstrip("-•* ")
        if any(lower.startswith(prefix) for prefix in blocked_prefixes):
            skip_indented = True
            continue
        if skip_indented:
            if not line:
                skip_indented = False
                continue
            if raw_line.startswith((" ", "\t", "-", "*", "•")):
                continue
            skip_indented = False
        filtered.append(raw_line)

    cleaned = "\n".join(filtered).strip()
    return cleaned or "-"


def generate_psychogram_analysis_with_end_date_for_setup(
    db, request: Request, setup_session: dict
) -> tuple[str, str | None]:
    psychogram = setup_session.get("psychogram") or {}
    policy = setup_session.get("policy_preview") or {}
    contract = policy.get("contract") or {}
    lang = _lang(setup_session.get("language", "de"))
    action = (
        (
            "Analyze this psychogram for a dashboard summary. Explain how the values should be interpreted and what effects they have on roleplay style. "
            "Cover tone, boundaries, pacing/intensity and communication style. Do NOT include tasks, commands, assignments or 'next steps'. "
            f"Choose a provisional session end date within this contract window: start={contract.get('start_date')}, "
            f"min_end={contract.get('min_end_date')}, max_end={contract.get('max_end_date')}. "
            "First line MUST be exactly: PROPOSED_END_DATE: YYYY-MM-DD or PROPOSED_END_DATE: AI_DECIDES."
        )
        if lang == "en"
        else (
            "Analysiere dieses Psychogramm fuer eine Dashboard-Zusammenfassung. Erklaere, wie die Werte zu deuten sind und welche Auswirkungen sie auf den Rollenspiel-Stil haben. "
            "Decke Ton, Grenzen, Tempo/Intensitaet und Kommunikationsstil ab. Gib KEINE Aufgaben, Befehle oder 'naechste Schritte' aus. "
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
        analysis = _strip_actionable_task_sections(analysis)
        return analysis, proposed_end_date
    except Exception:
        interaction = psychogram.get("interaction_preferences", {})
        safety = psychogram.get("safety_profile", {})
        fallback_text = (
            f"Profilanalyse: escalation={interaction.get('escalation_mode', 'moderate')}, "
            f"experience={interaction.get('experience_profile', 'intermediate')}, "
            f"safety={safety.get('mode', 'safeword')}. "
            "Deutung fuer das Rollenspiel: klare Struktur, konsistente Grenzen und eine Intensitaetssteuerung passend zur Erfahrungsstufe."
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
    lang = _lang(setup_session.get("language", "de"))
    template_path = _contract_template_path(lang)
    try:
        raw_template = template_path.read_text(encoding="utf-8")
    except Exception:
        return "Contract template unavailable."
    template = _strip_front_matter(raw_template).strip()
    return _render_contract_template_from_setup(setup_session, template)


def _render_contract_template_from_setup(setup_session: dict, template: str) -> str:
    lang = _lang(setup_session.get("language", "de"))
    policy = setup_session.get("policy_preview") if isinstance(setup_session.get("policy_preview"), dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    contract = policy.get("contract") if isinstance(policy.get("contract"), dict) else {}
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    interaction_profile = (
        policy.get("interaction_profile") if isinstance(policy.get("interaction_profile"), dict) else {}
    )
    generated_contract = (
        policy.get("generated_contract") if isinstance(policy.get("generated_contract"), dict) else {}
    )
    consent = generated_contract.get("consent") if isinstance(generated_contract.get("consent"), dict) else {}
    psychogram = setup_session.get("psychogram") if isinstance(setup_session.get("psychogram"), dict) else {}
    safety_profile = psychogram.get("safety_profile") if isinstance(psychogram.get("safety_profile"), dict) else {}
    interaction_prefs = (
        psychogram.get("interaction_preferences")
        if isinstance(psychogram.get("interaction_preferences"), dict)
        else {}
    )
    personal_prefs = (
        psychogram.get("personal_preferences")
        if isinstance(psychogram.get("personal_preferences"), dict)
        else {}
    )

    start_date = str(contract.get("start_date") or setup_session.get("contract_start_date") or "").strip() or None
    min_end_date = (
        str(contract.get("min_end_date") or setup_session.get("contract_min_end_date") or "").strip() or None
    )
    max_end_date = (
        str(contract.get("max_end_date") or setup_session.get("contract_max_end_date") or "").strip() or None
    )
    proposed_end = (
        str(contract.get("proposed_end_date") or setup_session.get("ai_proposed_end_date") or "").strip() or None
    )
    if not proposed_end:
        proposed_end = "AI-decides" if lang == "en" else "KI-entscheidet"

    min_duration_days = _safe_days_between(start_date, min_end_date)
    max_extension_days = _safe_days_between(min_end_date, max_end_date) if min_end_date and max_end_date else None
    integrations = [str(item).strip().lower() for item in (setup_session.get("integrations") or []) if str(item).strip()]
    safety_mode = str(safety_profile.get("mode") or "safeword").strip()
    traffic_words = safety_profile.get("traffic_light_words") if isinstance(safety_profile.get("traffic_light_words"), dict) else {}
    keyholder_name = (
        str(setup_session.get("keyholder_name") or "").strip()
        or ("Mistress" if lang == "en" else "Herrin")
    )
    user_name = str(setup_session.get("user_display_name") or "").strip() or "sub"

    context = {
        "session_id": str(setup_session.get("active_session_id") or "-"),
        "setup_session_id": str(setup_session.get("setup_session_id") or "-"),
        "contract_version": "1.0.1",
        "generated_at_iso": datetime.now(UTC).isoformat(),
        "generated_by": "chastease",
        "contract_start_date": start_date,
        "contract_min_end_date": min_end_date,
        "contract_max_end_date": max_end_date,
        "proposed_end_date_ai": proposed_end,
        "end_date_control_mode": "ai_controls_end_date" if bool(contract.get("ai_controls_end_date", True)) else "fixed",
        "min_duration_days": min_duration_days,
        "max_extension_per_incident_days": max_extension_days if max_extension_days is not None else 7,
        "hard_stop_enabled": "enabled" if bool(setup_session.get("hard_stop_enabled", True)) else "disabled",
        "pause_policy": (
            "Immediate pause on medical or emotional warning signs."
            if lang == "en"
            else "Sofortige Pause bei medizinischen oder emotionalen Warnsignalen."
        ),
        "daily_checkin_required": "yes" if lang == "en" else "ja",
        "inspection_frequency_policy": str(interaction_profile.get("control_frequency_hint") or "medium"),
        "max_openings_in_period": int(limits.get("max_openings_in_period", setup_session.get("max_openings_in_period", 1))),
        "opening_limit_period": str(limits.get("opening_limit_period", setup_session.get("opening_limit_period", "day"))),
        "opening_window_minutes": int(limits.get("opening_window_minutes", setup_session.get("opening_window_minutes", 30))),
        "max_penalty_per_day_minutes": int(
            limits.get("max_penalty_per_day_minutes", setup_session.get("max_penalty_per_day_minutes", 60))
        ),
        "max_penalty_per_week_minutes": int(
            limits.get("max_penalty_per_week_minutes", setup_session.get("max_penalty_per_week_minutes", 240))
        ),
        "reward_policy": "adaptive reinforcement",
        "penalty_policy": "bounded corrective penalties",
        "safety_mode": safety_mode,
        "safeword": str(safety_profile.get("safeword") or ""),
        "traffic_light_words": (
            f"{traffic_words.get('green', 'green')}/{traffic_words.get('yellow', 'yellow')}/{traffic_words.get('red', 'red')}"
            if safety_mode == "traffic_light"
            else ""
        ),
        "hard_limits_text": str(psychogram.get("hard_limits_text") or psychogram.get("taboo_text") or ""),
        "soft_limits_text": str(psychogram.get("soft_limits_text") or _fixed_soft_limits_text(lang)),
        "health_protocol": "stop, evaluate, debrief",
        "psychogram_summary": str(psychogram.get("summary") or ""),
        "psychogram_analysis": str(setup_session.get("psychogram_analysis") or psychogram.get("analysis") or ""),
        "instruction_style": str(
            interaction_prefs.get("instruction_style") or setup_session.get("instruction_style") or "mixed"
        ),
        "escalation_mode": str(
            interaction_prefs.get("escalation_mode") or setup_session.get("escalation_mode") or "moderate"
        ),
        "experience_profile": str(interaction_prefs.get("experience_profile") or "intermediate"),
        "grooming_preference": str(
            personal_prefs.get("grooming_preference") or setup_session.get("grooming_preference") or "no_preference"
        ),
        "tone_profile": str(interaction_profile.get("preferred_tone") or "balanced"),
        "integrations": ", ".join(integrations) if integrations else "none",
        "autonomy_mode": str(setup_session.get("autonomy_mode") or policy.get("autonomy_mode") or "execute"),
        "action_execution_mode": "auto_execute" if str(setup_session.get("autonomy_mode") or "execute") == "execute" else "suggest_only",
        "audit_enabled": "true",
        "amendment_policy": "changes require explicit acknowledgement",
        "termination_policy": "terminate at safety limit or explicit abort",
        "debrief_policy": "post-session review required",
        "sub_name": user_name,
        "user_name": user_name,
        "keyholder_name": keyholder_name,
        "signature_date_sub": str(date.today().isoformat()),
        "signature_sub": "[signature pending]",
        "signature_date_keyholder": str(date.today().isoformat()),
        "signature_keyholder": "[signature pending]",
        "consent_required_text": str(consent.get("required_text") or _required_contract_consent_text(lang)),
        "consent_accepted": "true" if bool(consent.get("accepted")) else "false",
        "consent_text": str(consent.get("consent_text") or ""),
        "consent_accepted_at": str(consent.get("accepted_at") or ""),
    }

    def _fmt(value: object) -> str:
        if value is None:
            return "-"
        text = str(value).strip()
        return text if text else "-"

    rendered = str(template or "")
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", _fmt(value))

    # Strict fill: unresolved placeholders must not remain in final contract text.
    rendered = re.sub(r"\{\{[^{}]+\}\}", "-", rendered)
    return rendered.strip()


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
