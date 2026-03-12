from fastapi import APIRouter
import httpx

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/llm/test")
def llm_test(body: dict) -> dict:
    """Test LLM connectivity using the given credentials. Returns {ok, error}."""
    provider = str(body.get("provider", "custom")).strip().lower()
    api_url = str(body.get("api_url", "")).strip()
    api_key = str(body.get("api_key", "")).strip()
    chat_model = str(body.get("chat_model", "")).strip()

    if not api_url or not chat_model:
        return {"ok": False, "error": "api_url und chat_model sind erforderlich."}

    try:
        if provider == "ollama":
            base = api_url.rstrip("/").removesuffix("/api/generate")
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{base}/api/tags")
                resp.raise_for_status()
        else:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    api_url,
                    headers=headers,
                    json={
                        "model": chat_model,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 1,
                    },
                )
                resp.raise_for_status()
        return {"ok": True}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:400]}
