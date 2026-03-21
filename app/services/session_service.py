import json
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.session import Session as SessionModel


class SessionService:
    @staticmethod
    def choose_session_duration_seconds(
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> int:
        min_seconds = max(60, int(min_duration_seconds or 60))
        if max_duration_seconds is None:
            return min_seconds
        max_seconds = max(min_seconds, int(max_duration_seconds))
        if max_seconds <= min_seconds:
            return min_seconds
        return random.randint(min_seconds, max_seconds)

    @staticmethod
    def clamp_active_duration_seconds(
        current_duration_seconds: int | None,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> int:
        min_seconds = max(60, int(min_duration_seconds or 60))
        current_seconds = max(60, int(current_duration_seconds or min_seconds))
        if max_duration_seconds is None:
            return max(min_seconds, current_seconds)
        max_seconds = max(min_seconds, int(max_duration_seconds))
        return max(min_seconds, min(current_seconds, max_seconds))

    @staticmethod
    def sign_contract_and_start(
        db: Session,
        session_obj: SessionModel,
        contract_obj: Contract,
    ) -> SessionModel:
        contract_obj.signed_at = datetime.now(timezone.utc)
        duration = SessionService.choose_session_duration_seconds(
            session_obj.min_duration_seconds,
            session_obj.max_duration_seconds,
        )
        session_obj.lock_start = contract_obj.signed_at
        session_obj.lock_end = contract_obj.signed_at + timedelta(seconds=duration)
        session_obj.status = "active"
        contract_obj.parameters_snapshot = json.dumps(
            {
                "min_duration_seconds": session_obj.min_duration_seconds,
                "max_duration_seconds": session_obj.max_duration_seconds,
                "selected_duration_seconds": duration,
                "status": session_obj.status,
            }
        )
        db.add(contract_obj)
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
        return session_obj
