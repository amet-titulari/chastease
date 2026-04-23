from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from app.database import Base


class OtcSettings(Base):
    __tablename__ = "otc_settings"

    id = Column(Integer, primary_key=True, index=True)
    singleton_key = Column(String(32), nullable=False, unique=True, default="default")
    enabled = Column(Boolean, nullable=False, default=False)
    otc_url = Column(String(512), nullable=True)
    channel = Column(String(4), nullable=False, default="A")
    intensity_fail = Column(Integer, nullable=False, default=40)
    intensity_penalty = Column(Integer, nullable=False, default=70)
    intensity_pass = Column(Integer, nullable=False, default=20)
    ticks_fail = Column(Integer, nullable=False, default=20)
    ticks_penalty = Column(Integer, nullable=False, default=40)
    ticks_pass = Column(Integer, nullable=False, default=10)
    pattern_fail = Column(String(120), nullable=False, default="经典")
    pattern_penalty = Column(String(120), nullable=False, default="经典")
    pattern_pass = Column(String(120), nullable=False, default="经典")
    # Continuous background stimulus (fired at each new game step)
    intensity_continuous = Column(Integer, nullable=False, default=30)
    ticks_continuous = Column(Integer, nullable=False, default=50)
    pattern_continuous = Column(String(120), nullable=False, default="经典")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
