from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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

    @staticmethod
    def period_start(period: str, now: datetime | None = None) -> datetime:
        """Return the start of the current calendar period (day/week/month) in UTC.

        All boundaries are computed in the configured local timezone so that
        'day' = 00:00 local time, 'week' = Monday 00:00 local time,
        'month' = 1st of month 00:00 local time.
        """
        from app.config import settings
        try:
            tz = ZoneInfo(settings.local_timezone)
        except (ZoneInfoNotFoundError, Exception):
            tz = timezone.utc

        utc_now = HygieneService._as_utc(now or datetime.now(timezone.utc))
        local_now = utc_now.astimezone(tz)

        if period == "day":
            local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            local_day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            local_start = local_day_start - timedelta(days=local_day_start.weekday())
        elif period == "month":
            local_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported period: {period}")

        return local_start.astimezone(timezone.utc)

    @staticmethod
    def next_period_start(period: str, now: datetime | None = None) -> datetime:
        """Return the start of the NEXT calendar period in UTC, DST-safe."""
        from app.config import settings
        try:
            tz = ZoneInfo(settings.local_timezone)
        except (ZoneInfoNotFoundError, Exception):
            tz = timezone.utc

        period_start_utc = HygieneService.period_start(period, now)
        local_start = period_start_utc.astimezone(tz)

        if period == "day":
            # Add 1 day and normalise to midnight (handles DST spring-forward / fall-back)
            next_local = (local_start + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == "week":
            next_local = (local_start + timedelta(days=7)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == "month":
            if local_start.month == 12:
                next_local = local_start.replace(
                    year=local_start.year + 1, month=1, day=1,
                    hour=0, minute=0, second=0, microsecond=0
                )
            else:
                next_local = local_start.replace(
                    month=local_start.month + 1, day=1,
                    hour=0, minute=0, second=0, microsecond=0
                )
        else:
            raise ValueError(f"Unsupported period: {period}")

        return next_local.astimezone(timezone.utc)
