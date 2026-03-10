import base64

import httpx

from app.config import settings


def _heuristic_analysis(requested_seal_number: str | None, observed_seal_number: str | None) -> tuple[str, str]:
    if requested_seal_number and observed_seal_number and requested_seal_number != observed_seal_number:
        return "suspicious", "Plombennummer stimmt nicht ueberein."
    return "confirmed", "Verifikation eingegangen und markiert."


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

    return _heuristic_analysis(
        requested_seal_number=requested_seal_number,
        observed_seal_number=observed_seal_number,
    )
