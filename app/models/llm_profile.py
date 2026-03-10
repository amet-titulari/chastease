from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.database import Base


class LlmProfile(Base):
    __tablename__ = "llm_profiles"

    id = Column(Integer, primary_key=True)
    profile_key = Column(String(80), nullable=False, unique=True, default="default")
    provider = Column(String(50), nullable=False, default="stub")
    api_url = Column(String(500), nullable=True)
    api_key = Column(Text, nullable=True)
    chat_model = Column(String(120), nullable=True)
    vision_model = Column(String(120), nullable=True)
    profile_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
