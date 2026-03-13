from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(120), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False)
    category = Column(String(80), nullable=True)
    description = Column(Text, nullable=True)
    tags_json = Column(Text, nullable=False, server_default="[]")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)