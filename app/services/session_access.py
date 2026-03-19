from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models.auth_user import AuthUser
from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel


AUTH_COOKIE_NAME = "chastease_auth"


def get_current_session_user(request: Request, db: Session) -> AuthUser | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    return db.query(AuthUser).filter(AuthUser.session_token == token).first()


def require_session_user(request: Request, db: Session) -> AuthUser:
    user = get_current_session_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_session_owner_id(db: Session, session_obj: SessionModel) -> int | None:
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    return profile.auth_user_id if profile else None


def get_accessible_session(
    db: Session,
    session_id: int,
    user: AuthUser | None,
    *,
    allow_anonymous_unowned: bool = True,
) -> SessionModel:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    owner_id = get_session_owner_id(db, session_obj)
    if user is not None:
        if owner_id is not None and owner_id != user.id:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_obj

    if owner_id is not None or not allow_anonymous_unowned:
        raise HTTPException(status_code=401, detail="Authentication required")
    return session_obj


def get_owned_session(request: Request, db: Session, session_id: int) -> SessionModel:
    user = get_current_session_user(request, db)
    return get_accessible_session(db, session_id, user)


def bind_session_profile_to_user(db: Session, session_obj: SessionModel, user: AuthUser) -> None:
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if profile and profile.auth_user_id is None:
        profile.auth_user_id = user.id
        db.add(profile)
