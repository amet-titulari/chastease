from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    email = Column(String(200), nullable=False, unique=True, index=True)
    password_hash = Column(String(64), nullable=False)
    password_salt = Column(String(32), nullable=False)
    session_token = Column(String(128), nullable=True, unique=True, index=True)
    setup_completed = Column(Boolean, nullable=False, default=False)
    setup_experience_level = Column(String(50), nullable=True)
    setup_style = Column(String(80), nullable=True)
    setup_goal = Column(String(120), nullable=True)
    setup_boundary = Column(Text, nullable=True)
    active_session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
