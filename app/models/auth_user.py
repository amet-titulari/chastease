from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    email = Column(String(200), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    password_salt = Column(String(32), nullable=False)
    session_token = Column(String(128), nullable=True, unique=True, index=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    setup_completed = Column(Boolean, nullable=False, default=False)
    default_player_profile_id = Column(Integer, ForeignKey("player_profiles.id", ondelete="SET NULL"), nullable=True)
    active_session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
