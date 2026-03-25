from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    speech_style_tone = Column(String(60), nullable=True)
    speech_style_dominance = Column(String(60), nullable=True)
    formatting_style = Column(String(30), nullable=True)
    verbosity_style = Column(String(30), nullable=True)
    praise_style = Column(String(30), nullable=True)
    repetition_guard = Column(String(30), nullable=True)
    context_exposition_style = Column(String(30), nullable=True)
    behavior_profile_json = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    strictness_level = Column(Integer, default=3, nullable=False)
    avatar_media_id = Column(Integer, ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
