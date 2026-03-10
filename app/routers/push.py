from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.push_subscription import PushSubscription
from app.models.session import Session as SessionModel
from app.services.web_push_service import dispatch_web_push

router = APIRouter(tags=["push"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: PushKeys
    user_agent: str | None = None


class PushTestRequest(BaseModel):
    title: str = Field(default="Chastease Erinnerung", min_length=1, max_length=120)
    body: str = Field(default="Bleib fokussiert. Bitte gib einen kurzen Statusbericht.", min_length=1, max_length=400)


def _ensure_session(db: Session, session_id: int) -> None:
    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/api/push/config")
def get_push_config() -> dict:
    return {
        "enabled": bool(settings.web_push_enabled),
        "vapid_public_key": settings.web_push_vapid_public_key,
    }


@router.get("/api/sessions/{session_id}/push/subscriptions")
def list_push_subscriptions(session_id: int, db: Session = Depends(get_db)) -> dict:
    _ensure_session(db, session_id)
    rows = (
        db.query(PushSubscription)
        .filter(PushSubscription.session_id == session_id)
        .order_by(PushSubscription.id.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "items": [
            {
                "id": row.id,
                "endpoint": row.endpoint,
                "enabled": row.enabled,
                "last_error": row.last_error,
                "last_sent_at": str(row.last_sent_at) if row.last_sent_at else None,
                "created_at": str(row.created_at),
            }
            for row in rows
        ],
    }


@router.post("/api/sessions/{session_id}/push/subscriptions")
def upsert_push_subscription(
    session_id: int,
    payload: PushSubscribeRequest,
    db: Session = Depends(get_db),
) -> dict:
    _ensure_session(db, session_id)

    row = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if row is None:
        row = PushSubscription(
            session_id=session_id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent,
            enabled=True,
        )
        db.add(row)
    else:
        row.session_id = session_id
        row.p256dh = payload.keys.p256dh
        row.auth = payload.keys.auth
        row.user_agent = payload.user_agent
        row.enabled = True

    db.commit()
    db.refresh(row)

    return {
        "session_id": session_id,
        "subscription_id": row.id,
        "enabled": row.enabled,
    }


@router.delete("/api/sessions/{session_id}/push/subscriptions/{subscription_id}")
def delete_push_subscription(session_id: int, subscription_id: int, db: Session = Depends(get_db)) -> dict:
    _ensure_session(db, session_id)
    row = (
        db.query(PushSubscription)
        .filter(PushSubscription.id == subscription_id, PushSubscription.session_id == session_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Push subscription not found")

    db.delete(row)
    db.commit()
    return {
        "session_id": session_id,
        "deleted": True,
    }


@router.post("/api/sessions/{session_id}/push/test")
def send_push_test(session_id: int, payload: PushTestRequest, db: Session = Depends(get_db)) -> dict:
    _ensure_session(db, session_id)
    rows = (
        db.query(PushSubscription)
        .filter(PushSubscription.session_id == session_id, PushSubscription.enabled.is_(True))
        .all()
    )

    result = dispatch_web_push(
        subscriptions=rows,
        title=payload.title,
        body=payload.body,
        data={"session_id": session_id, "kind": "test"},
    )

    db.commit()
    return {
        "session_id": session_id,
        "subscriptions": len(rows),
        "dispatch": result,
    }
