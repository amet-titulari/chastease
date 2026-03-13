from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True, index=True)
    auth_user_id = Column(Integer, ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    nickname = Column(String(120), nullable=False)
    experience_level = Column(String(50), default="beginner", nullable=False)
    preferences_json = Column(Text, default="{}", nullable=False)
    soft_limits_json = Column(Text, default="[]", nullable=False)
    hard_limits_json = Column(Text, default="[]", nullable=False)
    reaction_patterns_json = Column(Text, default="{}", nullable=False)
    needs_json = Column(Text, default="{}", nullable=False)
    avatar_media_id = Column(Integer, ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
