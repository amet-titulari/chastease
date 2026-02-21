from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def build_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def init_db(engine) -> None:
    # Import here to ensure model metadata is registered before create_all.
    from chastease import models  # noqa: F401

    _migrate_sqlite_legacy_schema(engine)
    Base.metadata.create_all(bind=engine)


def get_db_session(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _migrate_sqlite_legacy_schema(engine) -> None:
    # Lightweight prototype migration to keep local dev DB usable across schema changes.
    if not str(engine.url).startswith("sqlite"):
        return

    insp = inspect(engine)
    tables = set(insp.get_table_names())

    with engine.begin() as conn:
        if "users" in tables:
            user_cols = {col["name"] for col in insp.get_columns("users")}
            if "display_name" not in user_cols:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN display_name VARCHAR(120) NOT NULL DEFAULT 'Wearer'")
                )
            if "password_hash" not in user_cols:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ''")
                )

        if "chastity_sessions" in tables:
            session_cols = {col["name"] for col in insp.get_columns("chastity_sessions")}
            # Legacy table used `wearer_id` with NOT NULL. For prototype migration,
            # rebuild table by dropping legacy session/turn tables and letting
            # metadata create them with the current schema.
            if "wearer_id" in session_cols:
                conn.execute(text("DROP TABLE IF EXISTS turns"))
                conn.execute(text("DROP TABLE IF EXISTS chastity_sessions"))
                return
            if "user_id" not in session_cols:
                conn.execute(text("ALTER TABLE chastity_sessions ADD COLUMN user_id VARCHAR(36)"))
            if "character_id" not in session_cols:
                conn.execute(text("ALTER TABLE chastity_sessions ADD COLUMN character_id VARCHAR(36)"))
