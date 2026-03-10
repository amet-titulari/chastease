from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True)
    content_text = Column(Text, nullable=False)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    parameters_snapshot = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ContractAddendum(Base):
    __tablename__ = "contract_addenda"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    proposed_changes_json = Column(Text, nullable=False)
    change_description = Column(Text, nullable=False)
    proposed_by = Column(String(20), default="ai", nullable=False)
    player_consent = Column(String(20), default="pending", nullable=False)
    player_consent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
