from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from chastease.api.runtime import get_db_session
from chastease.api.schemas import CharacterCreateRequest, UserCreateRequest
from chastease.models import Character, User

router = APIRouter(prefix="/users", tags=["users"])


@router.post("")
def create_user(payload: UserCreateRequest, request: Request) -> dict:
    db = get_db_session(request)
    try:
        existing = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
        if existing is not None:
            return {
                "user_id": existing.id,
                "email": existing.email,
                "display_name": existing.display_name,
                "created": False,
            }

        user = User(
            id=str(uuid4()),
            email=payload.email.strip().lower(),
            display_name=payload.display_name.strip(),
            password_hash="legacy_no_login",
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "created": True,
        }
    finally:
        db.close()


@router.get("/{user_id}")
def get_user(user_id: str, request: Request) -> dict:
    db = get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        characters = db.scalars(select(Character).where(Character.user_id == user_id)).all()
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat(),
            "characters": [
                {
                    "character_id": c.id,
                    "name": c.name,
                    "strength": c.strength,
                    "intelligence": c.intelligence,
                    "charisma": c.charisma,
                    "hp": c.hp,
                }
                for c in characters
            ],
        }
    finally:
        db.close()


@router.post("/{user_id}/characters")
def create_character(user_id: str, payload: CharacterCreateRequest, request: Request) -> dict:
    db = get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        character = Character(
            id=str(uuid4()),
            user_id=user_id,
            name=payload.name.strip(),
            strength=payload.strength,
            intelligence=payload.intelligence,
            charisma=payload.charisma,
            hp=payload.hp,
            created_at=datetime.now(UTC),
        )
        db.add(character)
        db.commit()
        return {
            "character_id": character.id,
            "user_id": user_id,
            "name": character.name,
            "strength": character.strength,
            "intelligence": character.intelligence,
            "charisma": character.charisma,
            "hp": character.hp,
        }
    finally:
        db.close()
