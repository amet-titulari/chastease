from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    media_kind = Column(String(30), nullable=False, default="avatar")
    storage_path = Column(Text, nullable=False)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(120), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    visibility = Column(String(20), nullable=False, default="private")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)