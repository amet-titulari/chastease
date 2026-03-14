from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class GameRun(Base):
    __tablename__ = "game_runs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    module_key = Column(String(120), nullable=False, index=True)
    difficulty_key = Column(String(40), nullable=False)
    initiated_by = Column(String(20), nullable=False, default="player")
    status = Column(String(20), nullable=False, default="active")

    total_duration_seconds = Column(Integer, nullable=False)
    retry_extension_seconds = Column(Integer, nullable=False, default=0)
    transition_seconds = Column(Integer, nullable=False, default=8)
    max_misses_before_penalty = Column(Integer, nullable=False, default=3)
    miss_count = Column(Integer, nullable=False, default=0)

    session_penalty_seconds = Column(Integer, nullable=False, default=0)
    session_penalty_applied = Column(Boolean, nullable=False, default=False)

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    summary_json = Column(Text, nullable=True)
