from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class GameRunStep(Base):
    __tablename__ = "game_run_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("game_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False, index=True)

    posture_key = Column(String(120), nullable=False)
    posture_name = Column(String(200), nullable=False)
    posture_image_url = Column(String(500), nullable=True)
    instruction = Column(Text, nullable=True)
    target_seconds = Column(Integer, nullable=False, default=120)

    status = Column(String(20), nullable=False, default="pending")
    verification_count = Column(Integer, nullable=False, default=0)
    retry_of_step_id = Column(Integer, ForeignKey("game_run_steps.id", ondelete="SET NULL"), nullable=True)
    last_analysis = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
