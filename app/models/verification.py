from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class Verification(Base):
    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    image_path = Column(Text, nullable=True)
    requested_seal_number = Column(String(120), nullable=True)
    observed_seal_number = Column(String(120), nullable=True)
    status = Column(String(30), default="pending", nullable=False)
    ai_response = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
