from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Wearer")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    strength: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    charisma: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    hp: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ChastitySession(Base):
    __tablename__ = "chastity_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    character_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("characters.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    policy_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    psychogram_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("session_id", "turn_no", name="uq_turn_session_turn_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chastity_sessions.id"), nullable=False)
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    player_action: Mapped[str] = mapped_column(Text, nullable=False)
    ai_narration: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chastity_sessions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LLMProfile(Base):
    __tablename__ = "llm_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False, default="custom")
    api_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chat_model: Mapped[str] = mapped_column(String(120), nullable=False)
    vision_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    behavior_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
