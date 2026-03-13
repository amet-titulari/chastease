"""link auth users to player profiles

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
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

    if _table_exists(inspector, "player_profiles") and not _column_exists(inspector, "player_profiles", "auth_user_id"):
        with op.batch_alter_table("player_profiles") as batch_op:
            batch_op.add_column(sa.Column("auth_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_player_profiles_auth_user_id_auth_users",
                "auth_users",
                ["auth_user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "auth_users") and not _column_exists(inspector, "auth_users", "default_player_profile_id"):
        with op.batch_alter_table("auth_users") as batch_op:
            batch_op.add_column(sa.Column("default_player_profile_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_auth_users_default_player_profile_id_player_profiles",
                "player_profiles",
                ["default_player_profile_id"],
                ["id"],
                ondelete="SET NULL",
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "player_profiles") and not _index_exists(inspector, "player_profiles", "ix_player_profiles_auth_user_id"):
        op.create_index("ix_player_profiles_auth_user_id", "player_profiles", ["auth_user_id"], unique=False)

    if _table_exists(inspector, "auth_users") and not _index_exists(inspector, "auth_users", "ix_auth_users_default_player_profile_id"):
        op.create_index("ix_auth_users_default_player_profile_id", "auth_users", ["default_player_profile_id"], unique=False)

    # Backfill known links via active_session_id -> sessions.player_profile_id.
    if _table_exists(inspector, "auth_users") and _table_exists(inspector, "sessions") and _table_exists(inspector, "player_profiles"):
        rows = bind.execute(
            sa.text(
                """
                SELECT u.id AS user_id, s.player_profile_id AS profile_id
                FROM auth_users u
                JOIN sessions s ON s.id = u.active_session_id
                WHERE u.active_session_id IS NOT NULL
                  AND s.player_profile_id IS NOT NULL
                """
            )
        ).mappings().all()
        for row in rows:
            user_id = int(row["user_id"])
            profile_id = int(row["profile_id"])
            bind.execute(
                sa.text(
                    """
                    UPDATE player_profiles
                    SET auth_user_id = COALESCE(auth_user_id, :user_id)
                    WHERE id = :profile_id
                    """
                ),
                {"user_id": user_id, "profile_id": profile_id},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE auth_users
                    SET default_player_profile_id = COALESCE(default_player_profile_id, :profile_id)
                    WHERE id = :user_id
                    """
                ),
                {"user_id": user_id, "profile_id": profile_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "auth_users"):
        if _index_exists(inspector, "auth_users", "ix_auth_users_default_player_profile_id"):
            op.drop_index("ix_auth_users_default_player_profile_id", table_name="auth_users")
        if _column_exists(inspector, "auth_users", "default_player_profile_id"):
            with op.batch_alter_table("auth_users") as batch_op:
                batch_op.drop_constraint("fk_auth_users_default_player_profile_id_player_profiles", type_="foreignkey")
                batch_op.drop_column("default_player_profile_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "player_profiles"):
        if _index_exists(inspector, "player_profiles", "ix_player_profiles_auth_user_id"):
            op.drop_index("ix_player_profiles_auth_user_id", table_name="player_profiles")
        if _column_exists(inspector, "player_profiles", "auth_user_id"):
            with op.batch_alter_table("player_profiles") as batch_op:
                batch_op.drop_constraint("fk_player_profiles_auth_user_id_auth_users", type_="foreignkey")
                batch_op.drop_column("auth_user_id")
