"""items owned by auth user

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
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

    if not _table_exists(inspector, "items"):
        return

    if not _column_exists(inspector, "items", "owner_user_id"):
        with op.batch_alter_table("items") as batch_op:
            batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_items_owner_user_id_auth_users",
                "auth_users",
                ["owner_user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    inspector = sa.inspect(bind)
    if _index_exists(inspector, "items", "ix_items_owner_user_id") is False:
        op.create_index("ix_items_owner_user_id", "items", ["owner_user_id"], unique=False)

    # Backfill existing items to first available user so legacy rows remain usable.
    first_user_id = bind.execute(sa.text("SELECT id FROM auth_users ORDER BY id ASC LIMIT 1")).scalar()
    if first_user_id is not None:
        bind.execute(
            sa.text("UPDATE items SET owner_user_id = :uid WHERE owner_user_id IS NULL"),
            {"uid": int(first_user_id)},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "items"):
        return

    if _index_exists(inspector, "items", "ix_items_owner_user_id"):
        op.drop_index("ix_items_owner_user_id", table_name="items")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "items", "owner_user_id"):
        with op.batch_alter_table("items") as batch_op:
            batch_op.drop_constraint("fk_items_owner_user_id_auth_users", type_="foreignkey")
            batch_op.drop_column("owner_user_id")
