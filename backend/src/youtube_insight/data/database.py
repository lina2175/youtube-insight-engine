"""Small synchronous SQLAlchemy layer backed by SQLite, without domain tables."""

from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

SCHEMA_VERSION = 1


class Base(DeclarativeBase):
    """Shared declarative base for future domain models (none in Phase 1)."""


def create_database_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(path)),
        connect_args={"check_same_thread": False, "timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def initialize_database(engine: Engine) -> None:
    """Initialize once; reject unknown versions rather than silently rewriting them."""
    with engine.begin() as connection:
        version = connection.execute(text("PRAGMA user_version")).scalar_one()
        if version not in {0, SCHEMA_VERSION}:
            raise RuntimeError("Unsupported database schema version")
        if version == 0:
            connection.execute(text("PRAGMA user_version=1"))


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def database_is_ready(engine: Engine) -> bool:
    with engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
