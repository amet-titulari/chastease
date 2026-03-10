"""initial schema

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("communication_style", sa.String(length=120), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("strictness_level", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "player_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nickname", sa.String(length=120), nullable=False),
        sa.Column("experience_level", sa.String(length=50), nullable=False, server_default="beginner"),
        sa.Column("preferences_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("soft_limits_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("hard_limits_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reaction_patterns_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("needs_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("persona_id", sa.Integer(), sa.ForeignKey("personas.id"), nullable=False),
        sa.Column("player_profile_id", sa.Integer(), sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("lock_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_end_actual", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timer_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("freeze_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("min_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False, unique=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parameters_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "hygiene_openings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="requested"),
        sa.Column("old_seal_number", sa.String(length=120), nullable=True),
        sa.Column("new_seal_number", sa.String(length=120), nullable=True),
        sa.Column("overrun_seconds", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("hygiene_openings")
    op.drop_table("contracts")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("player_profiles")
    op.drop_table("personas")
