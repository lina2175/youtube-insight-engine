from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from youtube_insight.api.main import create_app
from youtube_insight.config import PROJECT_ROOT, Settings
from youtube_insight.data.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for name in (
        "DATABASE_PATH",
        "CORS_ORIGINS",
        "YOUTUBE_API_KEY",
        "YOUTUBE_CHANNEL_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    return Settings(_env_file=None, database_path=tmp_path / "db.sqlite3")


def test_configuration_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_PATH=from-file.sqlite3\nYOUTUBE_API_KEY=test-only\n")
    monkeypatch.setenv("DATABASE_PATH", "from-process.sqlite3")
    settings = Settings(_env_file=env_file)
    assert settings.database_path == PROJECT_ROOT / "from-process.sqlite3"
    assert (
        Settings(_env_file=env_file, database_path=tmp_path / "explicit").database_path
        == tmp_path / "explicit"
    )
    monkeypatch.delenv("DATABASE_PATH")
    assert (
        Settings(_env_file=env_file).database_path == PROJECT_ROOT / "from-file.sqlite3"
    )
    assert "test-only" not in repr(settings)


@pytest.mark.parametrize(
    "origin", ["*", "https://user:pass@example.com", "http://localhost:5173/path"]
)
def test_cors_rejects_non_origins(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


def test_health_without_credentials_and_no_domain_tables(settings):
    assert settings.youtube_api_key is None
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert str(settings.database_path) not in response.text
        assert inspect(client.app.state.engine).get_table_names() == []
    assert settings.database_path.exists()


def test_cors_allows_only_configured_origin(settings):
    with TestClient(create_app(settings)) as client:
        allowed = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
        assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        denied = client.get("/health", headers={"Origin": "https://untrusted.example"})
        assert "access-control-allow-origin" not in denied.headers


def test_database_failure_is_sanitized(settings):
    with TestClient(create_app(settings)) as client:
        with patch(
            "youtube_insight.api.main.database_is_ready",
            side_effect=OperationalError("secret-path", {}, Exception("private")),
        ):
            response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "Service unavailable"}


def test_sqlite_transactions_and_repeatable_initialization(settings):
    engine = create_database_engine(settings.database_path)
    try:
        initialize_database(engine)
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE fixture (id INTEGER PRIMARY KEY, value TEXT)")
            )
        sessions = create_session_factory(engine)
        with sessions.begin() as session:
            session.execute(
                text("INSERT INTO fixture VALUES (1, :value)"), {"value": "synthetic"}
            )
        with pytest.raises(RuntimeError), sessions.begin() as session:
            session.execute(text("INSERT INTO fixture VALUES (2, 'rollback')"))
            raise RuntimeError("rollback")
        initialize_database(engine)
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT value FROM fixture")
            ).scalars().all() == ["synthetic"]
            assert connection.execute(text("PRAGMA user_version")).scalar_one() == 1
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
    finally:
        engine.dispose()
    reopened = create_database_engine(settings.database_path)
    try:
        with reopened.connect() as connection:
            assert (
                connection.execute(text("SELECT COUNT(*) FROM fixture")).scalar_one()
                == 1
            )
    finally:
        reopened.dispose()


def test_unknown_schema_version_is_preserved(settings):
    engine = create_database_engine(settings.database_path)
    try:
        with engine.begin() as connection:
            connection.execute(text("PRAGMA user_version=99"))
        with pytest.raises(RuntimeError, match="Unsupported database schema"):
            initialize_database(engine)
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA user_version")).scalar_one() == 99
    finally:
        engine.dispose()
