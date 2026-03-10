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
        "Pruefe ob das Bild ein Keuschheitsgeraet zeigt und ob die Plombe erkennbar und unversehrt ist."
    )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url}},
        {"type": "text", "text": prompt},
    ]}]

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(api_url, headers=headers, json={"model": model, "messages": messages})
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()

        # Parse JSON from response (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        parsed = json.loads(text)
        status = str(parsed.get("status", "")).strip().lower()
        analysis = str(parsed.get("analysis", "")).strip()
        if status not in {"confirmed", "suspicious"}:
            return None
        return status, analysis or "KI-Analyse abgeschlossen."
    except Exception:
        return None


def _ollama_analysis(
    image_bytes: bytes,
    filename: str,
    requested_seal_number: str | None,
    observed_seal_number: str | None,
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
) -> tuple[str, str]:
    provider = settings.verification_ai_provider.strip().lower()

    if provider == "ollama":
        try:
            result = _ollama_analysis(
                image_bytes=image_bytes,
                filename=filename,
                requested_seal_number=requested_seal_number,
                observed_seal_number=observed_seal_number,
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
            if profile and profile.api_url and profile.chat_model:
                result = _openai_vision_analysis(
                    image_bytes=image_bytes,
                    filename=filename,
                    requested_seal_number=requested_seal_number,
                    observed_seal_number=observed_seal_number,
                    api_url=profile.api_url,
                    api_key=profile.api_key or "",
                    model=profile.chat_model,
                    timeout=30.0,
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
            )
            if result is not None:
                return result
        except Exception:
            pass

    return _heuristic_analysis(
        requested_seal_number=requested_seal_number,
        observed_seal_number=observed_seal_number,
    )
