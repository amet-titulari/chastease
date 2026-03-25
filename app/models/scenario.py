from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    key = Column(String(120), unique=True, nullable=False)
    summary = Column(Text, nullable=True)
    lorebook_json = Column(Text, nullable=False, server_default="[]")
    phases_json = Column(Text, nullable=False, server_default="[]")
    tags_json = Column(Text, nullable=False, server_default="[]")
    behavior_profile_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
