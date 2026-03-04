from typing import Any, Callable


try:
    from slowapi import Limiter as SlowLimiter, _rate_limit_exceeded_handler as slow_handler
    from slowapi.errors import RateLimitExceeded as SlowRateLimitExceeded
    from slowapi.util import get_remote_address as slow_get_remote_address

    Limiter = SlowLimiter
    RateLimitExceeded = SlowRateLimitExceeded
    _rate_limit_exceeded_handler = slow_handler
    get_remote_address = slow_get_remote_address
except Exception:  # pragma: no cover - fallback for restricted/local test environments
    class RateLimitExceeded(Exception):
        pass

    class Limiter:
        def __init__(self, key_func: Callable[..., str] | None = None, *args: Any, **kwargs: Any):
            self.key_func = key_func
            self.enabled = True

        def limit(self, _rule: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator

    def get_remote_address(*args: Any, **kwargs: Any) -> str:
        return "0.0.0.0"

    async def _rate_limit_exceeded_handler(*args: Any, **kwargs: Any):
        raise RateLimitExceeded()
