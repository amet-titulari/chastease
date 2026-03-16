from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.database import Base


class GamePostureTemplate(Base):
    __tablename__ = "game_posture_templates"

    id = Column(Integer, primary_key=True, index=True)
    module_key = Column(String(120), nullable=False, index=True)
    posture_key = Column(String(120), nullable=False)
    title = Column(String(200), nullable=False)
    image_url = Column(String(500), nullable=True)
    reference_landmarks_json = Column(Text, nullable=True)
    reference_landmarks_detected_at = Column(DateTime(timezone=True), nullable=True)
    instruction = Column(Text, nullable=True)
    target_seconds = Column(Integer, nullable=False, default=120)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
