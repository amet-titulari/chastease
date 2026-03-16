from sqlalchemy import Column, DateTime, Float, Integer, String, func

from app.database import Base


class GameModuleSetting(Base):
    __tablename__ = "game_module_settings"

    id = Column(Integer, primary_key=True, index=True)
    module_key = Column(String(120), nullable=False, unique=True, index=True)
    easy_target_multiplier = Column(Float, nullable=False, default=0.85)
    hard_target_multiplier = Column(Float, nullable=False, default=1.25)
    target_randomization_percent = Column(Integer, nullable=False, default=10)
    start_countdown_seconds = Column(Integer, nullable=False, default=5)
    movement_easy_pose_deviation = Column(Float, nullable=True)
    movement_easy_stillness = Column(Float, nullable=True)
    movement_medium_pose_deviation = Column(Float, nullable=True)
    movement_medium_stillness = Column(Float, nullable=True)
    movement_hard_pose_deviation = Column(Float, nullable=True)
    movement_hard_stillness = Column(Float, nullable=True)
    pose_similarity_min_score_easy = Column(Float, nullable=True)
    pose_similarity_min_score_medium = Column(Float, nullable=True)
    pose_similarity_min_score_hard = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
