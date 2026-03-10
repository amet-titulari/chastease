from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    communication_style = Column(String(120), nullable=True)
    system_prompt = Column(Text, nullable=True)
    strictness_level = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
