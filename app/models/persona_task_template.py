from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PersonaTaskTemplate(Base):
    __tablename__ = "persona_task_templates"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    deadline_minutes = Column(Integer, nullable=True)
    requires_verification = Column(Boolean, nullable=False, default=False)
    verification_criteria = Column(Text, nullable=True)
    category = Column(String(80), nullable=True)
    tags_json = Column(Text, nullable=False, server_default="[]")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)