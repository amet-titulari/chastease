"""inventory tables and avatar media support

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "media_assets"):
        op.create_table(
            "media_assets",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("media_kind", sa.String(length=30), nullable=False, server_default="avatar"),
            sa.Column("storage_path", sa.Text(), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=True),
            sa.Column("mime_type", sa.String(length=120), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("visibility", sa.String(length=20), nullable=False, server_default="private"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not _table_exists(inspector, "items"):
        op.create_table(
            "items",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("key", sa.String(length=120), nullable=False, unique=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "items", "ix_items_key"):
        op.create_index("ix_items_key", "items", ["key"], unique=True)

    if not _table_exists(inspector, "scenario_items"):
        op.create_table(
            "scenario_items",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("default_quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("phase_id", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "scenario_items", "ix_scenario_items_scenario_id"):
        op.create_index("ix_scenario_items_scenario_id", "scenario_items", ["scenario_id"], unique=False)
    if not _index_exists(inspector, "scenario_items", "ix_scenario_items_item_id"):
        op.create_index("ix_scenario_items_item_id", "scenario_items", ["item_id"], unique=False)

    if not _table_exists(inspector, "session_items"):
        op.create_table(
            "session_items",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="available"),
            sa.Column("is_equipped", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("linked_scenario_item_id", sa.Integer(), sa.ForeignKey("scenario_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "session_items", "ix_session_items_session_id"):
        op.create_index("ix_session_items_session_id", "session_items", ["session_id"], unique=False)
    if not _index_exists(inspector, "session_items", "ix_session_items_item_id"):
        op.create_index("ix_session_items_item_id", "session_items", ["item_id"], unique=False)

    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "personas", "avatar_media_id"):
        with op.batch_alter_table("personas") as batch_op:
            batch_op.add_column(sa.Column("avatar_media_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_personas_avatar_media_id_media_assets",
                "media_assets",
                ["avatar_media_id"],
                ["id"],
                ondelete="SET NULL",
            )
    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "player_profiles", "avatar_media_id"):
        with op.batch_alter_table("player_profiles") as batch_op:
            batch_op.add_column(sa.Column("avatar_media_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_player_profiles_avatar_media_id_media_assets",
                "media_assets",
                ["avatar_media_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("player_profiles") as batch_op:
        batch_op.drop_constraint("fk_player_profiles_avatar_media_id_media_assets", type_="foreignkey")
        batch_op.drop_column("avatar_media_id")

    with op.batch_alter_table("personas") as batch_op:
        batch_op.drop_constraint("fk_personas_avatar_media_id_media_assets", type_="foreignkey")
        batch_op.drop_column("avatar_media_id")

    op.drop_index("ix_session_items_item_id", table_name="session_items")
    op.drop_index("ix_session_items_session_id", table_name="session_items")
    op.drop_table("session_items")

    op.drop_index("ix_scenario_items_item_id", table_name="scenario_items")
    op.drop_index("ix_scenario_items_scenario_id", table_name="scenario_items")
    op.drop_table("scenario_items")

    op.drop_index("ix_items_key", table_name="items")
    op.drop_table("items")

    op.drop_table("media_assets")
