import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.verification import Verification


logger = logging.getLogger(__name__)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def prune_expired_verification_media(*, db: Session | None = None) -> int:
    if not settings.verification_media_retention_enabled:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, settings.verification_media_retention_hours))
    own_session = db is None
    session = db or SessionLocal()
    removed = 0
    try:
        rows = (
            session.query(Verification)
            .filter(Verification.image_path.isnot(None))
            .all()
        )
        for row in rows:
            created_at = _as_utc(row.created_at)
            if created_at is None or created_at > cutoff:
                continue
            image_path = str(row.image_path or "").strip()
            if not image_path:
                continue
            candidate = Path(image_path)
            try:
                if candidate.exists():
                    candidate.unlink()
            except OSError:
                logger.warning("Failed to delete expired verification media: %s", candidate)
                continue
            row.image_path = None
            removed += 1
        if removed:
            session.commit()
    finally:
        if own_session:
            session.close()
    return removed
