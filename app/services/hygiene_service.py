from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class HygieneStatus:
    due_back_at: datetime
    is_overdue: bool
    overrun_seconds: int


class HygieneService:
    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def calculate_due_back(opened_at: datetime, duration_seconds: int) -> datetime:
        normalized = HygieneService._as_utc(opened_at)
        return normalized + timedelta(seconds=max(60, duration_seconds))

    @staticmethod
    def evaluate_countdown(due_back_at: datetime, now: datetime | None = None) -> HygieneStatus:
        current = now or datetime.now(timezone.utc)
        normalized_due = HygieneService._as_utc(due_back_at)
        delta = int((current - normalized_due).total_seconds())
        if delta > 0:
            return HygieneStatus(due_back_at=normalized_due, is_overdue=True, overrun_seconds=delta)
        return HygieneStatus(due_back_at=normalized_due, is_overdue=False, overrun_seconds=0)
