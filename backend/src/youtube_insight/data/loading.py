"""Atomic SQLAlchemy upserts and logical deletion for synthetic domain data."""

from datetime import datetime, timedelta

from sqlalchemy import Connection, Engine, delete, inspect, select, text, update
from sqlalchemy.dialects.sqlite import insert

from youtube_insight.data.database import Base, initialize_database
from youtube_insight.data.domain import Channel, PipelineRun, Video

DOMAIN_SCHEMA_VERSION = 2


def initialize_domain_database(engine: Engine) -> None:
    initialize_database(engine)
    with engine.begin() as connection:
        # Explicit transaction makes SQLite DDL and user_version rollback together.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        version = connection.execute(text("PRAGMA user_version")).scalar_one()
        if version not in {1, DOMAIN_SCHEMA_VERSION}:
            raise RuntimeError("Unsupported domain schema version")
        if version == 1 and {"channels", "videos", "pipeline_runs"}.intersection(
            inspect(connection).get_table_names()
        ):
            raise RuntimeError("Domain table collision before schema migration")
        Base.metadata.create_all(connection)
        connection.execute(text("PRAGMA user_version=2"))


class DataConflictError(ValueError):
    """An observation conflicts with stored identity or same-time values."""


def _require_clock(now: datetime) -> datetime:
    from datetime import UTC

    if now.tzinfo is None:
        raise ValueError("Clock must be timezone-aware")
    return now.astimezone(UTC)


def _upsert(connection: Connection, model, record: dict) -> bool:
    existing = (
        connection.execute(select(model.__table__).where(model.id == record["id"]))
        .mappings()
        .first()
    )
    if existing:
        if model is Video and existing["channel_id"] != record["channel_id"]:
            raise DataConflictError("Stored video ownership cannot change")
        if existing["fetched_at"] == record["fetched_at"]:
            # Expiry is deliberately excluded: a different TTL cannot extend a rerun.
            if any(
                existing[name] != value
                for name, value in record.items()
                if name != "expires_at"
            ):
                raise DataConflictError("Stored observation conflicts at the same time")
            if record["expires_at"] < existing["expires_at"]:
                connection.execute(
                    update(model)
                    .where(model.id == record["id"])
                    .values(expires_at=record["expires_at"])
                )
                return True
            return False
        if existing["fetched_at"] > record["fetched_at"]:
            return False
    statement = insert(model).values(**record)
    statement = statement.on_conflict_do_update(
        index_elements=[model.id],
        set_={name: statement.excluded[name] for name in record if name != "id"},
        where=model.fetched_at < statement.excluded.fetched_at,
    )
    connection.execute(statement)
    return True


def load_records(
    connection: Connection, channels: list[dict], videos: list[dict]
) -> int:
    skipped = 0
    for model, records in [(Channel, channels), (Video, videos)]:
        for record in records:
            if not _upsert(connection, model, record):
                skipped += 1
    return skipped


def purge_expired(
    engine: Engine, *, now: datetime, run_retention_days: int = 7
) -> dict[str, int]:
    now = _require_clock(now)
    if (
        isinstance(run_retention_days, bool)
        or not isinstance(run_retention_days, int)
        or not 1 <= run_retention_days <= 30
    ):
        raise ValueError("Run retention must be 1–30 days")
    with engine.begin() as connection:
        # Count cascaded videos explicitly before deleting parents.
        expired_channels = select(Channel.id).where(Channel.expires_at <= now)
        removed_videos = connection.execute(
            delete(Video).where(
                (Video.expires_at <= now) | Video.channel_id.in_(expired_channels)
            )
        ).rowcount
        removed_channels = connection.execute(
            delete(Channel).where(Channel.expires_at <= now)
        ).rowcount
        removed_runs = connection.execute(
            delete(PipelineRun).where(
                PipelineRun.started_at <= now - timedelta(days=run_retention_days)
            )
        ).rowcount
    return {
        "channels": removed_channels,
        "videos": removed_videos,
        "runs": removed_runs,
    }


def delete_channel(engine: Engine, channel_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(delete(Channel).where(Channel.id == channel_id))


def delete_video(engine: Engine, video_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(delete(Video).where(Video.id == video_id))


def purge_all(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(delete(Video))
        connection.execute(delete(Channel))
        connection.execute(delete(PipelineRun))
