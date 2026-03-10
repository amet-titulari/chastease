import json
from datetime import datetime, timezone

from app.config import settings
from app.models.push_subscription import PushSubscription


def _is_dispatch_enabled() -> bool:
    return bool(settings.web_push_enabled and settings.web_push_vapid_private_key and settings.web_push_vapid_public_key)


def dispatch_web_push(subscriptions: list[PushSubscription], title: str, body: str, data: dict | None = None) -> dict:
    payload = {
        "title": title,
        "body": body,
        "data": data or {},
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }

    if not _is_dispatch_enabled():
        return {
            "enabled": False,
            "sent": 0,
            "failed": 0,
            "details": "Web Push nicht konfiguriert (VAPID/feature flag).",
        }

    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        return {
            "enabled": False,
            "sent": 0,
            "failed": 0,
            "details": "pywebpush nicht installiert.",
        }

    sent = 0
    failed = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=settings.web_push_vapid_private_key,
                vapid_claims={"sub": settings.web_push_vapid_claims_sub},
            )
            sub.last_sent_at = datetime.now(timezone.utc)
            sub.last_error = None
            sent += 1
        except WebPushException as exc:
            sub.last_error = str(exc)
            failed += 1
        except Exception as exc:
            sub.last_error = str(exc)
            failed += 1

    return {
        "enabled": True,
        "sent": sent,
        "failed": failed,
        "details": None,
    }
