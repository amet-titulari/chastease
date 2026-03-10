from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class SealHistory(Base):
    __tablename__ = "seal_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    hygiene_opening_id = Column(Integer, ForeignKey("hygiene_openings.id"), nullable=True)
    seal_number = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    invalidated_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
