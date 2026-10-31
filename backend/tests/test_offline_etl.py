"""Offline synthetic-only ETL/database acceptance and regression tests."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import func, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from youtube_insight.data import loading
from youtube_insight.data.database import create_database_engine, initialize_database
from youtube_insight.data.domain import Channel, PipelineRun, Video
from youtube_insight.data.loading import (
    delete_channel,
    delete_video,
    initialize_domain_database,
    purge_all,
    purge_expired,
)
from youtube_insight.etl.offline_cli import main
from youtube_insight.etl.offline_pipeline import PipelineFailure, run_synthetic_pipeline
from youtube_insight.etl.synthetic import fixture_batch
from youtube_insight.etl.transform import (
    DataQualityError,
    frame_records,
    transform_synthetic,
)

NOW = datetime(2026, 10, 31, 12, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path):
    engine = create_database_engine(tmp_path / "offline.sqlite3")
    yield engine
    engine.dispose()


def run(engine, payload=None, **options):
    return run_synthetic_pipeline(
        engine,
        payload if payload is not None else fixture_batch(NOW),
        clock=lambda: NOW,
        **options,
    )


def count(engine, model):
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(model))


def test_pandas_nullable_precision_normalization_and_utc():
    payload = fixture_batch(NOW)
    payload["videos"][0]["view_count"] = 2**53 + 1
    payload["videos"][0]["published_at"] = "2026-01-01T02:00:00+02:00"
    transformed = transform_synthetic(payload, now=NOW)
    assert isinstance(transformed.videos, pd.DataFrame)
    assert str(transformed.videos.view_count.dtype) == "Int64"
    assert transformed.videos.loc[0, "view_count"] == 2**53 + 1
    assert pd.isna(transformed.videos.loc[1, "view_count"])
    assert transformed.videos.loc[2, "view_count"] == 0
    assert transformed.videos.loc[0, "title"] == "Example One"
    assert transformed.channels.loc[0, "title"] == "Fictional Studio Alpha"
    assert transformed.videos.loc[0, "published_at"] == datetime(2026, 1, 1, tzinfo=UTC)
    records = frame_records(transformed.videos)
    assert records[1]["view_count"] is None
    assert records[0]["fetched_at"].tzinfo is not None
    assert transformed.input_rows == 5


@pytest.mark.parametrize("value", [-1, 1.5, True, "12", 2**63, float("nan")])
def test_invalid_counts_rejected(value):
    payload = fixture_batch(NOW)
    payload["videos"][0]["view_count"] = value
    with pytest.raises(DataQualityError):
        transform_synthetic(payload, now=NOW)


@pytest.mark.parametrize(
    "change",
    [
        {"id": "actual_video"},
        {"title": "  \n "},
        {"fetched_at": "2026-10-31T00:00:00"},
        {"fetched_at": NOW + timedelta(seconds=1)},
        {"published_at": NOW + timedelta(days=1)},
        {"channel_id": "synthetic_missing_channel"},
        {"unknown_field": "not allowed"},
    ],
)
def test_invalid_rows_and_references_rejected(change):
    payload = fixture_batch(NOW)
    payload["videos"][0].update(change)
    with pytest.raises(DataQualityError):
        transform_synthetic(payload, now=NOW)


def test_live_provenance_and_api_sample_shapes_rejected():
    payload = fixture_batch(NOW)
    payload["dataset_kind"] = "youtube"
    with pytest.raises(DataQualityError):
        transform_synthetic(payload, now=NOW)
    with pytest.raises(DataQualityError):
        transform_synthetic({"channel": {}, "videos": []}, now=NOW)


@pytest.mark.parametrize("days", [0, 31, -1, True, 1.5])
def test_invalid_retention_configuration(days):
    with pytest.raises(ValueError):
        transform_synthetic(fixture_batch(NOW), now=NOW, retention_days=days)


def test_missing_publication_date_and_empty_videos_supported():
    payload = fixture_batch(NOW)
    payload["channels"][0]["published_at"] = None
    payload["videos"] = []
    frames = transform_synthetic(payload, now=NOW)
    assert frame_records(frames.channels)[0]["published_at"] is None
    assert frame_records(frames.videos) == []


def test_duplicates_latest_wins_deterministically():
    payload = fixture_batch(NOW)
    older = deepcopy(payload["videos"][0])
    older["fetched_at"] -= timedelta(hours=1)
    older["view_count"] = 7
    payload["videos"].extend([older, deepcopy(payload["videos"][0])])
    result = transform_synthetic(payload, now=NOW)
    assert result.duplicate_rows == 2
    assert len(result.videos) == 3
    assert result.videos.set_index("id").loc["synthetic_video_one", "view_count"] == 100


@pytest.mark.parametrize(
    "field,value",
    [("title", "Conflicting title"), ("channel_id", "synthetic_channel_beta")],
)
def test_conflicting_duplicate_observations_rejected(field, value):
    payload = fixture_batch(NOW)
    duplicate = deepcopy(payload["videos"][0])
    duplicate[field] = value
    payload["videos"].append(duplicate)
    with pytest.raises(DataQualityError):
        transform_synthetic(payload, now=NOW)


def test_idempotent_loading_multi_channel_nullable_storage_and_runs(engine):
    payload = fixture_batch(NOW)
    payload["videos"][0]["view_count"] = 2**53 + 1
    first = run(engine, payload)
    second = run(engine, payload)
    assert first != second
    assert count(engine, Channel) == 2
    assert count(engine, Video) == 3
    assert count(engine, PipelineRun) == 2
    with engine.connect() as connection:
        rows = (
            connection.execute(select(Video.__table__).order_by(Video.id))
            .mappings()
            .all()
        )
        by_id = {row["id"]: row for row in rows}
        assert by_id["synthetic_video_one"]["view_count"] == 2**53 + 1
        assert by_id["synthetic_video_two"]["view_count"] is None
        assert by_id["synthetic_video_three"]["view_count"] == 0
        assert by_id["synthetic_video_three"]["channel_id"] == "synthetic_channel_beta"
        assert by_id["synthetic_video_one"]["fetched_at"].tzinfo == UTC
        record = (
            connection.execute(
                select(PipelineRun.__table__).where(PipelineRun.id == second)
            )
            .mappings()
            .one()
        )
        assert record["status"] == "succeeded"
        assert record["input_rows"] == record["output_rows"] == 5
        assert record["skipped_rows"] == 5
        assert record["finished_at"] == NOW


def test_newer_refresh_and_stale_upsert_preserve_expiry(engine):
    original = fixture_batch(NOW)
    run(engine, original)
    fresh = deepcopy(original)
    fresh["videos"][0].update(view_count=200, fetched_at=NOW)
    run(engine, fresh)
    run(engine, original)
    with engine.connect() as connection:
        video = (
            connection.execute(
                select(Video.__table__).where(Video.id == "synthetic_video_one")
            )
            .mappings()
            .one()
        )
        assert video["view_count"] == 200
        assert video["fetched_at"] == NOW
        assert video["expires_at"] == NOW + timedelta(days=30)


def test_rerun_cannot_extend_expiry_with_different_ttl(engine):
    run(engine, retention_days=1)
    run(engine, retention_days=30)
    with engine.connect() as connection:
        assert connection.scalar(select(Video.expires_at).limit(1)) == fixture_batch(
            NOW
        )["videos"][0]["fetched_at"] + timedelta(days=1)


def test_validation_failure_is_recorded_without_payload_or_rows(engine):
    payload = fixture_batch(NOW)
    payload["videos"][0]["title"] = ""
    with pytest.raises(PipelineFailure) as error:
        run(engine, payload)
    assert error.value.category == "data_quality"
    assert count(engine, Channel) == count(engine, Video) == 0
    with engine.connect() as connection:
        record = connection.execute(select(PipelineRun.__table__)).mappings().one()
        assert record["status"] == "failed"
        assert record["error_code"] == "data_quality"
        assert record["rejected_rows"] == 5
        assert record["output_rows"] == 0


def test_mid_load_failure_rolls_back_all_changes_but_retains_failed_run(
    engine, monkeypatch
):
    run(engine)
    payload = fixture_batch(NOW)
    payload["channels"][0].update(title="Changed", fetched_at=NOW)
    upsert = loading._upsert

    def fail_on_video(connection, model, record):
        if model is Video:
            raise SQLAlchemyError("sensitive fixture failure details")
        return upsert(connection, model, record)

    monkeypatch.setattr(loading, "_upsert", fail_on_video)
    with pytest.raises(PipelineFailure) as error:
        run(engine, payload)
    assert "sensitive" not in str(error.value)
    assert count(engine, Channel) == 2
    assert count(engine, Video) == 3
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(Channel.title).where(Channel.id == "synthetic_channel_alpha")
            )
            == "Fictional Studio Alpha"
        )
        assert (
            connection.scalar(
                select(PipelineRun.status).where(PipelineRun.id == error.value.run_id)
            )
            == "failed"
        )


def test_conflicting_same_time_storage_or_ownership_change_is_rejected(engine):
    run(engine)
    payload = fixture_batch(NOW)
    payload["videos"][0]["view_count"] = 101
    with pytest.raises(PipelineFailure) as conflict:
        run(engine, payload)
    assert conflict.value.category == "data_quality"
    payload["videos"][0].update(channel_id="synthetic_channel_beta", fetched_at=NOW)
    with pytest.raises(PipelineFailure):
        run(engine, payload)


def test_expired_input_rejected_and_expiry_boundary_purged(engine):
    payload = fixture_batch(NOW)
    run(engine, payload)
    deadline = payload["channels"][0]["fetched_at"] + timedelta(days=30)
    assert purge_expired(engine, now=deadline - timedelta(seconds=1))["videos"] == 0
    removed = purge_expired(engine, now=deadline)
    assert removed["channels"] == 2
    assert removed["videos"] == 3
    assert count(engine, Channel) == count(engine, Video) == 0
    with pytest.raises(DataQualityError):
        transform_synthetic(payload, now=deadline)


def test_expired_video_only_and_run_record_retention(engine):
    run_id = run(engine)
    with engine.begin() as connection:
        connection.execute(
            update(Video)
            .where(Video.id == "synthetic_video_one")
            .values(expires_at=NOW)
        )
        connection.execute(
            update(PipelineRun)
            .where(PipelineRun.id == run_id)
            .values(started_at=NOW - timedelta(days=7))
        )
    removed = purge_expired(engine, now=NOW)
    assert removed == {"channels": 0, "videos": 1, "runs": 1}
    assert count(engine, Channel) == 2
    assert count(engine, Video) == 2


def test_channel_cascade_individual_video_and_full_purge(engine):
    run(engine)
    delete_video(engine, "synthetic_video_one")
    assert count(engine, Video) == 2
    delete_channel(engine, "synthetic_channel_alpha")
    assert count(engine, Channel) == count(engine, Video) == 1
    delete_channel(engine, "absent")
    assert count(engine, PipelineRun) == 1
    purge_all(engine)
    assert (
        count(engine, Channel)
        == count(engine, Video)
        == count(engine, PipelineRun)
        == 0
    )


def test_foreign_keys_and_source_constraints_are_enforced(engine):
    run(engine)
    values = {
        "id": "synthetic_orphan",
        "channel_id": "synthetic_absent",
        "title": "Synthetic orphan",
        "source": "synthetic",
        "fetched_at": NOW,
        "expires_at": NOW + timedelta(days=1),
    }
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(Video).values(**values))
    values.update(channel_id="synthetic_channel_alpha", source="youtube")
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(Video).values(**values))


def test_schema_migration_is_repeatable_preserves_foundation_data_and_health_contract(
    engine,
):
    initialize_database(engine)
    assert inspect(engine).get_table_names() == []
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE existing_fixture (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO existing_fixture VALUES (1)"))
    initialize_domain_database(engine)
    initialize_domain_database(engine)
    initialize_database(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM existing_fixture")) == 1
        assert connection.scalar(text("PRAGMA user_version")) == 2
    assert {"channels", "videos", "pipeline_runs"}.issubset(
        inspect(engine).get_table_names()
    )


def test_migration_ddl_failure_rolls_back_schema_and_version(engine):
    def failed_migration(connection):
        connection.execute(text("CREATE TABLE failed_migration (id INTEGER)"))
        raise RuntimeError("synthetic migration failure")

    with patch(
        "youtube_insight.data.loading.Base.metadata.create_all",
        side_effect=failed_migration,
    ):
        with pytest.raises(RuntimeError):
            initialize_domain_database(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA user_version")) == 1
    assert inspect(engine).get_table_names() == []
    initialize_domain_database(engine)


def test_unknown_schema_version_rejected_without_creating_domain_tables(engine):
    with engine.begin() as connection:
        connection.execute(text("PRAGMA user_version=99"))
    with pytest.raises(RuntimeError):
        initialize_domain_database(engine)
    assert inspect(engine).get_table_names() == []


def test_offline_cli_repeatability_without_network_or_credentials(tmp_path, capsys):
    path = tmp_path / "demo.sqlite3"
    assert main(["--database", str(path)]) == 0
    assert main(["--database", str(path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    import json

    summaries = [json.loads(line) for line in lines]
    assert [item["channels"] for item in summaries] == [2, 2]
    assert [item["videos"] for item in summaries] == [3, 3]
    assert [item["runs"] for item in summaries] == [1, 2]
    assert all(item["dataset_kind"] == "synthetic" for item in summaries)


def test_same_observation_can_shorten_but_not_extend_expiry(engine):
    run(engine, retention_days=30)
    run(engine, retention_days=1)
    with engine.connect() as connection:
        assert connection.scalar(select(Channel.expires_at).limit(1)) == fixture_batch(
            NOW
        )["channels"][0]["fetched_at"] + timedelta(days=1)


def test_schema_name_collision_does_not_stamp_or_overwrite_existing_table(engine):
    initialize_database(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE channels (original INTEGER)"))
        connection.execute(text("INSERT INTO channels VALUES (9)"))
    with pytest.raises(RuntimeError, match="collision"):
        initialize_domain_database(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT original FROM channels")) == 9
        assert connection.scalar(text("PRAGMA user_version")) == 1


def test_empty_video_batch_loads_channels_and_records_success(engine):
    payload = fixture_batch(NOW)
    payload["videos"] = []
    run(engine, payload)
    assert count(engine, Channel) == 2
    assert count(engine, Video) == 0


def test_pipeline_start_purges_expired_rows_even_when_new_batch_fails(engine):
    run(engine, retention_days=1)
    later = NOW + timedelta(days=2)
    invalid = fixture_batch(later)
    invalid["dataset_kind"] = "live"
    with pytest.raises(PipelineFailure):
        run_synthetic_pipeline(engine, invalid, clock=lambda: later)
    assert count(engine, Channel) == count(engine, Video) == 0
    assert count(engine, PipelineRun) == 2


def test_foundation_health_accepts_explicitly_initialized_domain_database(engine):
    from fastapi.testclient import TestClient

    from youtube_insight.api.main import create_app
    from youtube_insight.config import Settings

    run(engine)
    settings = Settings(_env_file=None, database_path=engine.url.database)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").json() == {"status": "ok"}
    assert count(engine, Video) == 3
