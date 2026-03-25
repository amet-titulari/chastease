from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import Request


@dataclass(frozen=True)
class RequestLimitRule:
    key: str
    methods: tuple[str, ...]
    path_prefix: str
    max_requests: int
    window_seconds: int


_RULES: tuple[RequestLimitRule, ...] = (
    RequestLimitRule(
        key="chat_media_upload",
        methods=("POST",),
        path_prefix="/api/sessions/",
        max_requests=10,
        window_seconds=60,
    ),
    RequestLimitRule(
        key="verification_upload",
        methods=("POST",),
        path_prefix="/api/sessions/",
        max_requests=12,
        window_seconds=60,
    ),
    RequestLimitRule(
        key="voice_client_secret",
        methods=("POST",),
        path_prefix="/api/voice/realtime/",
        max_requests=8,
        window_seconds=60,
    ),
)
_STATE: dict[tuple[str, str], deque[float]] = {}
_LOCK = Lock()


def _match_rule(method: str, path: str) -> RequestLimitRule | None:
    if method != "POST":
        return None
    if path.startswith("/api/sessions/") and path.endswith("/messages/media"):
        return _RULES[0]
    if path.startswith("/api/sessions/") and "/verifications/" in path and path.endswith("/upload"):
        return _RULES[1]
    if path.startswith("/api/voice/realtime/") and path.endswith("/client-secret"):
        return _RULES[2]
    return None


def check_request_limit(request: Request) -> tuple[bool, RequestLimitRule | None]:
    rule = _match_rule(request.method.upper(), request.url.path)
    if rule is None:
        return True, None

    client_host = getattr(request.client, "host", None) or "unknown"
    scope = f"{client_host}:{request.url.path}"
    now = monotonic()
    cutoff = now - rule.window_seconds

    with _LOCK:
        bucket = _STATE.setdefault((rule.key, scope), deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= rule.max_requests:
            return False, rule
        bucket.append(now)
    return True, rule


def reset_request_limits() -> None:
    with _LOCK:
        _STATE.clear()
