"""initial schema (consolidated)

Revision ID: 0001
Revises:
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("communication_style", sa.String(120), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("strictness_level", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "player_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nickname", sa.String(120), nullable=False),
        sa.Column("experience_level", sa.String(50), nullable=False),
        sa.Column("preferences_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("soft_limits_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("hard_limits_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reaction_patterns_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("needs_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("persona_id", sa.Integer(), sa.ForeignKey("personas.id"), nullable=False),
        sa.Column("player_profile_id", sa.Integer(), sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("lock_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_end_actual", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timer_frozen", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("freeze_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("min_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("hygiene_limit_daily", sa.Integer(), nullable=True),
        sa.Column("hygiene_limit_weekly", sa.Integer(), nullable=True),
        sa.Column("hygiene_limit_monthly", sa.Integer(), nullable=True),
        sa.Column("ws_auth_token", sa.String(80), nullable=True, unique=True),
        sa.Column("ws_auth_token_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "auth_users",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True, index=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(64), nullable=False),
        sa.Column("password_salt", sa.String(32), nullable=False),
        sa.Column("session_token", sa.String(128), nullable=True, unique=True, index=True),
        sa.Column("setup_completed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("setup_experience_level", sa.String(50), nullable=True),
        sa.Column("setup_style", sa.String(80), nullable=True),
        sa.Column("setup_goal", sa.String(120), nullable=True),
        sa.Column("setup_boundary", sa.Text(), nullable=True),
        sa.Column("active_session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parameters_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "contract_addenda",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("proposed_changes_json", sa.Text(), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=False),
        sa.Column("proposed_by", sa.String(20), nullable=False),
        sa.Column("player_consent", sa.String(20), nullable=False),
        sa.Column("player_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "hygiene_openings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("old_seal_number", sa.String(120), nullable=True),
        sa.Column("new_seal_number", sa.String(120), nullable=True),
        sa.Column("overrun_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penalty_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penalty_applied_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(30), nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "safety_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "seal_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("hygiene_opening_id", sa.Integer(), sa.ForeignKey("hygiene_openings.id"), nullable=True),
        sa.Column("seal_number", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("consequence_type", sa.String(50), nullable=True),
        sa.Column("consequence_value", sa.Integer(), nullable=True),
        sa.Column("consequence_applied_seconds", sa.Integer(), nullable=True),
        sa.Column("consequence_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "verifications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("requested_seal_number", sa.String(120), nullable=True),
        sa.Column("observed_seal_number", sa.String(120), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("ai_response", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False, index=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "llm_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_key", sa.String(80), nullable=False, unique=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("api_url", sa.String(500), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("chat_model", sa.String(120), nullable=True),
        sa.Column("vision_model", sa.String(120), nullable=True),
        sa.Column("profile_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("llm_profiles")
    op.drop_table("push_subscriptions")
    op.drop_table("verifications")
    op.drop_table("tasks")
    op.drop_table("seal_history")
    op.drop_table("safety_logs")
    op.drop_table("messages")
    op.drop_table("hygiene_openings")
    op.drop_table("contract_addenda")
    op.drop_table("contracts")
    op.drop_table("auth_users")
    op.drop_table("sessions")
    op.drop_table("player_profiles")
    op.drop_table("personas")
