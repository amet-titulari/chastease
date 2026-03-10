import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.session import Session as SessionModel


class SessionService:
    @staticmethod
    def sign_contract_and_start(
        db: Session,
        session_obj: SessionModel,
        contract_obj: Contract,
    ) -> SessionModel:
        contract_obj.signed_at = datetime.now(timezone.utc)
        duration = session_obj.min_duration_seconds
        session_obj.lock_start = contract_obj.signed_at
        session_obj.lock_end = contract_obj.signed_at + timedelta(seconds=duration)
        session_obj.status = "active"
        contract_obj.parameters_snapshot = json.dumps(
            {
                "min_duration_seconds": session_obj.min_duration_seconds,
                "max_duration_seconds": session_obj.max_duration_seconds,
                "status": session_obj.status,
            }
        )
        db.add(contract_obj)
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
        return session_obj
