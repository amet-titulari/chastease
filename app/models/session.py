from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base
from app.services.secret_crypto import EncryptedText


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    player_profile_id = Column(Integer, ForeignKey("player_profiles.id"), nullable=False)
    status = Column(String(50), default="draft", nullable=False)
    lock_start = Column(DateTime(timezone=True), nullable=True)
    lock_end = Column(DateTime(timezone=True), nullable=True)
    lock_end_actual = Column(DateTime(timezone=True), nullable=True)
    timer_frozen = Column(Boolean, default=False, nullable=False)
    freeze_start = Column(DateTime(timezone=True), nullable=True)
    min_duration_seconds = Column(Integer, nullable=False)
    max_duration_seconds = Column(Integer, nullable=True)
    hygiene_limit_daily = Column(Integer, nullable=True)
    hygiene_limit_weekly = Column(Integer, nullable=True)
    hygiene_limit_monthly = Column(Integer, nullable=True)
    hygiene_opening_max_duration_seconds = Column(Integer, nullable=True)
    llm_provider = Column(String(50), nullable=True)
    llm_api_url = Column(String(500), nullable=True)
    llm_api_key = Column(EncryptedText(), nullable=True)
    llm_chat_model = Column(String(120), nullable=True)
    llm_vision_model = Column(String(120), nullable=True)
    llm_profile_active = Column(Boolean, default=False, nullable=False)
    ws_auth_token = Column(String(80), nullable=True, unique=True)
    ws_auth_token_created_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
