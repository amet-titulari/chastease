from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
