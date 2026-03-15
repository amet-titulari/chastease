from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func

from app.database import Base


class GamePostureModuleAssignment(Base):
    __tablename__ = "game_posture_module_assignments"
    __table_args__ = (
        UniqueConstraint("posture_template_id", "module_key", name="uq_game_posture_module_assignment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    posture_template_id = Column(
        Integer,
        ForeignKey("game_posture_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_key = Column(String(120), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
