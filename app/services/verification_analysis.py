import base64
import json

import httpx

from app.config import settings


def _heuristic_analysis(requested_seal_number: str | None, observed_seal_number: str | None) -> tuple[str, str]:
    if requested_seal_number and observed_seal_number and requested_seal_number != observed_seal_number:
        return "suspicious", "Plombennummer stimmt nicht ueberein."
    return "confirmed", "Verifikation eingegangen und markiert."


def _openai_vision_analysis(
    image_bytes: bytes,
    filename: str,
    requested_seal_number: str | None,
    observed_seal_number: str | None,
    api_url: str,
    api_key: str,
    model: str,
    timeout: float = 30.0,
    verification_criteria: str | None = None,
) -> tuple[str, str] | None:
    """OpenAI-compatible vision analysis (works with Grok/xAI, OpenAI, OpenRouter, etc.)."""
    if not image_bytes:
        return None

    # Detect mime type from filename
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    prompt = (
        "Du analysierst ein Verifikationsbild fuer eine Chastity-Session. "
        "Antworte NUR als JSON mit zwei Schluesseln: 'status' (confirmed oder suspicious) und 'analysis' (kurze Begruendung auf Deutsch). "
        f"Erwartete Plombennummer: '{requested_seal_number or 'nicht angegeben'}'. "
        f"Beobachtete Plombennummer laut Wearer: '{observed_seal_number or 'nicht angegeben'}'. "
    )
    if verification_criteria:
        prompt += f"Pruefkriterien laut Keyholderin: {verification_criteria} "
    else:
        prompt += "Pruefe ob das Bild ein Keuschheitsgeraet zeigt und ob die Plombe erkennbar und unversehrt ist."

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url}},
        {"type": "text", "text": prompt},
    ]}]

    def _extract_status_and_analysis(text: str) -> tuple[str, str] | None:
        candidate = (text or "").strip()
        if not candidate:
            return None

        # If the model wrapped JSON in markdown code fences, unwrap first.
        if "```" in candidate:
            parts = candidate.split("```")
            if len(parts) >= 2:
                candidate = parts[1].strip()
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()

        # Try strict JSON first.
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                status = str(parsed.get("status", "")).strip().lower()
                analysis = str(parsed.get("analysis", "")).strip()
                if status in {"confirmed", "suspicious"}:
                    return status, (analysis or "KI-Analyse abgeschlossen.")
        except Exception:
            pass

        # Fallback: infer status from plain text output.
        plain = candidate.strip()
        lowered = plain.lower()
        if "suspicious" in lowered or "verdaechtig" in lowered or "verdachtig" in lowered:
            return "suspicious", (plain or "KI-Analyse abgeschlossen.")
        return "confirmed", (plain or "KI-Analyse abgeschlossen.")

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(api_url, headers=headers, json={"model": model, "messages": messages})
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
        return _extract_status_and_analysis(text)
    except Exception:
        return None


def _ollama_analysis(
    image_bytes: bytes,
    filename: str,
    requested_seal_number: str | None,
    observed_seal_number: str | None,
    verification_criteria: str | None = None,
) -> tuple[str, str] | None:
    if not image_bytes:
        return None

    prompt = (
        "Du analysierst ein Verifikationsbild fuer eine Chastity-Session. "
        "Antworte als kompaktes JSON mit Schluesseln status und analysis. "
        "status muss confirmed oder suspicious sein. "
        "requested_seal_number kann leer sein. "
        f"requested_seal_number={requested_seal_number or ''}, observed_seal_number={observed_seal_number or ''}, filename={filename}."
    )
    if verification_criteria:
        prompt += f" Pruefkriterien: {verification_criteria}"

    payload = {
        "model": settings.verification_ollama_model,
        "prompt": prompt,
        "stream": False,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "format": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "analysis": {"type": "string"},
            },
            "required": ["status", "analysis"],
        },
    }

    with httpx.Client(timeout=settings.verification_ollama_timeout_seconds) as client:
        response = client.post(f"{settings.ai_ollama_base_url.rstrip('/')}/api/generate", json=payload)
        response.raise_for_status()
        body = response.json()

    raw_response = body.get("response")
    if not isinstance(raw_response, str) or not raw_response.strip():
        return None

    # Ollama returns JSON as string in response when format is used.
    import json

    parsed = json.loads(raw_response)
    status = str(parsed.get("status", "")).strip().lower()
    analysis = str(parsed.get("analysis", "")).strip()
    if status not in {"confirmed", "suspicious"}:
        return None
    if not analysis:
        analysis = "KI-Analyse abgeschlossen."
    return status, analysis


def analyze_verification(
    image_bytes: bytes,
    filename: str,
    requested_seal_number: str | None,
    observed_seal_number: str | None,
    verification_criteria: str | None = None,
    allow_heuristic_fallback: bool = True,
) -> tuple[str, str]:
    provider = settings.verification_ai_provider.strip().lower()

    if provider == "ollama":
        try:
            result = _ollama_analysis(
                image_bytes=image_bytes,
                filename=filename,
                requested_seal_number=requested_seal_number,
                observed_seal_number=observed_seal_number,
                verification_criteria=verification_criteria,
            )
            if result is not None:
                return result
        except Exception:
            pass

    if provider in ("custom", "openai", "auto"):
        # Read active LLM profile from DB for API URL / key / model
        try:
            from app.database import SessionLocal
            from app.models.llm_profile import LlmProfile as LlmProfileModel
            db = SessionLocal()
            try:
                profile = db.query(LlmProfileModel).filter(LlmProfileModel.profile_key == "default").first()
            finally:
                db.close()
            if profile and profile.api_url and (profile.vision_model or profile.chat_model):
                result = _openai_vision_analysis(
                    image_bytes=image_bytes,
                    filename=filename,
                    requested_seal_number=requested_seal_number,
                    observed_seal_number=observed_seal_number,
                    api_url=profile.api_url,
                    api_key=profile.api_key or "",
                    model=profile.vision_model or profile.chat_model,
                    timeout=30.0,
                    verification_criteria=verification_criteria,
                )
                if result is not None:
                    return result
        except Exception:
            pass

    # "auto": also try ollama as fallback if not already tried
    if provider == "auto":
        try:
            result = _ollama_analysis(
                image_bytes=image_bytes,
                filename=filename,
                requested_seal_number=requested_seal_number,
                observed_seal_number=observed_seal_number,
                verification_criteria=verification_criteria,
            )
            if result is not None:
                return result
        except Exception:
            pass

    if allow_heuristic_fallback:
        return _heuristic_analysis(
            requested_seal_number=requested_seal_number,
            observed_seal_number=observed_seal_number,
        )

    return (
        "suspicious",
        "AI-Pruefung nicht verfuegbar. Bitte Vision-Provider konfigurieren und erneut pruefen.",
    )


def generate_game_run_summary(summary: dict, module_title: str) -> str:
    """Generate a German AI text assessment of a completed game run (text-only, no images).

    Returns an empty string if no LLM is reachable or the call fails.
    """
    total = int(summary.get("total_steps") or 0)
    scheduled = int(summary.get("scheduled_steps") or total)
    unplayed = int(summary.get("unplayed_steps") or max(0, scheduled - total))
    passed = int(summary.get("passed_steps") or 0)
    failed = int(summary.get("failed_steps") or 0)
    miss_count = int(summary.get("miss_count") or 0)
    retry_extension = int(summary.get("retry_extension_seconds") or 0)
    penalty_applied = bool(summary.get("session_penalty_applied"))
    end_reason = str(summary.get("end_reason") or "all_steps_processed")
    scheduled_duration = int(summary.get("scheduled_duration_seconds") or 0)

    checks = summary.get("checks")
    if not isinstance(checks, list):
        checks = []

    violations = [c for c in checks if isinstance(c, dict) and c.get("violation_detected")]
    confirmations = [c for c in checks if isinstance(c, dict) and not c.get("violation_detected")]

    def _short_text(value: str | None, max_chars: int = 180) -> str:
        compact = " ".join(str(value or "").replace("\n", " ").split())
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3].rstrip() + "..."

    reason_counts: dict[str, int] = {}
    for entry in violations:
        reason = _short_text(
            str(entry.get("violation_reason") or entry.get("analysis") or "Unklare Ursache"),
            max_chars=120,
        )
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    top_reasons = sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:6]

    per_step: dict[int, dict] = {}
    for entry in checks:
        if not isinstance(entry, dict):
            continue
        step_id = int(entry.get("step_id") or 0)
        if step_id <= 0:
            continue
        row = per_step.get(step_id)
        if row is None:
            row = {
                "step_id": step_id,
                "posture_name": str(entry.get("posture_name") or f"Step {step_id}"),
                "attempts": 0,
                "ok": 0,
                "fail": 0,
                "scores": [],
                "last_analysis": "",
            }
            per_step[step_id] = row
        row["attempts"] += 1
        if entry.get("violation_detected"):
            row["fail"] += 1
        else:
            row["ok"] += 1
        score = entry.get("pose_score")
        if isinstance(score, (int, float)):
            row["scores"].append(float(score))
        analysis = str(entry.get("analysis") or "").strip()
        if analysis:
            row["last_analysis"] = analysis

    step_breakdown: list[str] = []
    for step_id in sorted(per_step.keys()):
        row = per_step[step_id]
        score_text = ""
        scores = row["scores"]
        if scores:
            best = max(scores)
            avg = sum(scores) / len(scores)
            score_text = f", score best/avg={best:.1f}/{avg:.1f}"
        detail = _short_text(row["last_analysis"], max_chars=90)
        if detail:
            detail = f", letzter Check: {detail}"
        step_breakdown.append(
            f"- Step {row['step_id']} ({row['posture_name']}): Versuche={row['attempts']}, ok={row['ok']}, fail={row['fail']}{score_text}{detail}"
        )

    recent_checks = [entry for entry in checks if isinstance(entry, dict)][-8:]
    recent_lines: list[str] = []
    for entry in recent_checks:
        step_id = int(entry.get("step_id") or 0)
        posture_name = str(entry.get("posture_name") or f"Step {step_id}")
        status_label = "FAIL" if entry.get("violation_detected") else "OK"
        pose_score = entry.get("pose_score")
        score_text = ""
        if isinstance(pose_score, (int, float)):
            threshold = entry.get("pose_threshold")
            if isinstance(threshold, (int, float)):
                score_text = f" (score {float(pose_score):.1f}/{float(threshold):.1f})"
            else:
                score_text = f" (score {float(pose_score):.1f})"
        reason = _short_text(str(entry.get("analysis") or "-"), max_chars=110)
        recent_lines.append(f"- {status_label} · Step {step_id} ({posture_name}){score_text}: {reason}")

    lines = [
        f"Spiel: {module_title}",
        f"Beendigungsgrund: {'Zeit abgelaufen' if end_reason == 'time_elapsed' else 'Alle Schritte abgeschlossen'}",
        f"Geplante Gesamtdauer: {scheduled_duration}s",
        f"Gespielte Schritte: {total} ({passed} bestanden, {failed} fehlgeschlagen)",
        f"Verfehlungen gesamt: {miss_count}",
        f"Strafzeitverlaengerung erhalten: {retry_extension}s",
        f"Session-Penalty ausgeloest: {'Ja' if penalty_applied else 'Nein'}",
        f"Checks: {len(checks)} insgesamt ({len(confirmations)} bestanden, {len(violations)} Verstoss)",
    ]
    if unplayed > 0:
        lines.append(f"Nicht mehr gespielte Schritte wegen Zeitende: {unplayed} von {scheduled}")
    if top_reasons:
        lines.append("Haeufigste Verstossgruende:")
        lines.extend([f"- {count}x {reason}" for reason, count in top_reasons])
    if step_breakdown:
        lines.append("Step-Analyse:")
        lines.extend(step_breakdown[:8])
    if recent_lines:
        lines.append("Letzte Checks (Timeline):")
        lines.extend(recent_lines)

    prompt = (
        "Du beurteilst das Ergebnis eines Koerperhaltungs-Spiels fuer eine Chastity-Session. "
        "Erstelle eine konkrete, ausfuehrliche Bewertung (6-10 Saetze) auf Deutsch. "
        "Nutze die Daten unten und werde spezifisch statt allgemein. "
        "Bewerte Leistung, Verstossmuster, Disziplintrend und ob Strafen angemessen waren. "
        "Nenne zum Schluss genau zwei klare Trainingsfoki fuer den naechsten Run. "
        "Antworte direkt mit dem Bewertungstext, keine Einleitung, kein JSON.\n\n"
        + "\n".join(lines)
    )

    provider = settings.verification_ai_provider.strip().lower()

    if provider in ("custom", "openai", "auto"):
        try:
            from app.database import SessionLocal
            from app.models.llm_profile import LlmProfile as LlmProfileModel

            db = SessionLocal()
            try:
                profile = db.query(LlmProfileModel).filter(LlmProfileModel.profile_key == "default").first()
            finally:
                db.close()
            if profile and profile.api_url and profile.chat_model:
                headers = {"Content-Type": "application/json"}
                if profile.api_key:
                    headers["Authorization"] = f"Bearer {profile.api_key}"
                messages = [{"role": "user", "content": prompt}]
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        profile.api_url,
                        headers=headers,
                        json={"model": profile.chat_model, "messages": messages},
                    )
                    resp.raise_for_status()
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    if text:
                        return text
        except Exception:
            pass

    if provider in ("ollama", "auto"):
        try:
            payload = {
                "model": settings.verification_ollama_model,
                "prompt": prompt,
                "stream": False,
            }
            with httpx.Client(timeout=float(settings.verification_ollama_timeout_seconds)) as client:
                response = client.post(
                    f"{settings.ai_ollama_base_url.rstrip('/')}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                text = response.json().get("response", "").strip()
                if text:
                    return text
        except Exception:
            pass

    return ""
