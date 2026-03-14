"""add game runtime tables

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_runs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_key", sa.String(length=120), nullable=False),
        sa.Column("difficulty_key", sa.String(length=40), nullable=False),
        sa.Column("initiated_by", sa.String(length=20), nullable=False, server_default="player"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("total_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("retry_extension_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_misses_before_penalty", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("miss_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("session_penalty_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("session_penalty_applied", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_game_runs_session_id", "game_runs", ["session_id"])
    op.create_index("ix_game_runs_module_key", "game_runs", ["module_key"])

    op.create_table(
        "game_run_steps",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("game_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("posture_key", sa.String(length=120), nullable=False),
        sa.Column("posture_name", sa.String(length=200), nullable=False),
        sa.Column("posture_image_url", sa.String(length=500), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("target_seconds", sa.Integer(), nullable=False, server_default=sa.text("120")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("verification_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retry_of_step_id", sa.Integer(), sa.ForeignKey("game_run_steps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_analysis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_game_run_steps_run_id", "game_run_steps", ["run_id"])
    op.create_index("ix_game_run_steps_order_index", "game_run_steps", ["order_index"])


def downgrade() -> None:
    op.drop_index("ix_game_run_steps_order_index", table_name="game_run_steps")
    op.drop_index("ix_game_run_steps_run_id", table_name="game_run_steps")
    op.drop_table("game_run_steps")

    op.drop_index("ix_game_runs_module_key", table_name="game_runs")
    op.drop_index("ix_game_runs_session_id", table_name="game_runs")
    op.drop_table("game_runs")
