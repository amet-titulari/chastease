from fastapi import Request

from chastease.api import routes as legacy


def resolve_user_id_from_token(auth_token: str, request: Request) -> str | None:
    return legacy._resolve_user_id_from_token(auth_token, request)


def get_db_session(request: Request):
    return legacy._get_db_session(request)


def sync_setup_snapshot_to_active_session(request: Request, setup_session: dict) -> bool:
    return legacy._sync_setup_snapshot_to_active_session(request, setup_session)


def sync_setup_snapshot_to_active_session_db(db, setup_session: dict) -> bool:
    return legacy._sync_setup_snapshot_to_active_session_db(db, setup_session)
