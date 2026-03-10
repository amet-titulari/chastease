from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String(120), nullable=False)
    experience_level = Column(String(50), default="beginner", nullable=False)
    preferences_json = Column(Text, default="{}", nullable=False)
    soft_limits_json = Column(Text, default="[]", nullable=False)
    hard_limits_json = Column(Text, default="[]", nullable=False)
    reaction_patterns_json = Column(Text, default="{}", nullable=False)
    needs_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
