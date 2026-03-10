from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


class HygieneOpening(Base):
    __tablename__ = "hygiene_openings"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    due_back_at = Column(DateTime(timezone=True), nullable=True)
    relocked_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), default="requested", nullable=False)
    old_seal_number = Column(String(120), nullable=True)
    new_seal_number = Column(String(120), nullable=True)
    overrun_seconds = Column(Integer, default=0, nullable=False)
    penalty_seconds = Column(Integer, default=0, nullable=False)
    penalty_applied_at = Column(DateTime(timezone=True), nullable=True)
