"""add posture module assignment table

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


SHARED_POOL_KEYS = {"posture_training", "dont_move"}


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "game_posture_module_assignments"):
        op.create_table(
            "game_posture_module_assignments",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "posture_template_id",
                sa.Integer(),
                sa.ForeignKey("game_posture_templates.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("module_key", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("posture_template_id", "module_key", name="uq_game_posture_module_assignment"),
        )

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "game_posture_module_assignments", "ix_game_posture_module_assignments_posture_template_id"):
        op.create_index(
            "ix_game_posture_module_assignments_posture_template_id",
            "game_posture_module_assignments",
            ["posture_template_id"],
        )
    if not _index_exists(inspector, "game_posture_module_assignments", "ix_game_posture_module_assignments_module_key"):
        op.create_index(
            "ix_game_posture_module_assignments_module_key",
            "game_posture_module_assignments",
            ["module_key"],
        )

    if not _table_exists(inspector, "game_posture_templates"):
        return

    rows = bind.execute(sa.text("SELECT id, module_key FROM game_posture_templates")).fetchall()
    for row in rows:
        posture_id = int(row[0])
        module_key = str(row[1] or "").strip()
        allowed = SHARED_POOL_KEYS if module_key in SHARED_POOL_KEYS else {module_key}
        for key in sorted(k for k in allowed if k):
            bind.execute(
                sa.text(
                    """
                    INSERT OR IGNORE INTO game_posture_module_assignments (posture_template_id, module_key)
                    VALUES (:posture_id, :module_key)
                    """
                ),
                {"posture_id": posture_id, "module_key": key},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "game_posture_module_assignments"):
        return

    if _index_exists(inspector, "game_posture_module_assignments", "ix_game_posture_module_assignments_module_key"):
        op.drop_index("ix_game_posture_module_assignments_module_key", table_name="game_posture_module_assignments")
    if _index_exists(inspector, "game_posture_module_assignments", "ix_game_posture_module_assignments_posture_template_id"):
        op.drop_index("ix_game_posture_module_assignments_posture_template_id", table_name="game_posture_module_assignments")

    op.drop_table("game_posture_module_assignments")
