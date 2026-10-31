"""Synthetic-only Pandas pipeline. No imports of the live extraction client."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, insert, update
from sqlalchemy.exc import SQLAlchemyError

from youtube_insight.data.domain import PipelineRun
from youtube_insight.data.loading import (
    DataConflictError,
    initialize_domain_database,
    load_records,
    purge_expired,
)
from youtube_insight.etl.transform import (
    DataQualityError,
    frame_records,
    require_clock,
    transform_synthetic,
)


class PipelineFailure(RuntimeError):
    def __init__(self, run_id: str, category: str):
        self.run_id = run_id
        self.category = category
        super().__init__(f"Offline pipeline failed ({category}); run {run_id}")


def utc_now() -> datetime:
    return datetime.now(UTC)


def run_synthetic_pipeline(
    engine: Engine,
    payload: dict,
    *,
    retention_days: int = 30,
    clock: Callable[[], datetime] = utc_now,
) -> str:
    started = require_clock(clock())
    initialize_domain_database(engine)
    purge_expired(engine, now=started)
    run_id = str(uuid4())
    input_rows = sum(
        len(payload.get(name, []))
        for name in ("channels", "videos")
        if isinstance(payload, dict) and isinstance(payload.get(name), list)
    )
    with engine.begin() as connection:
        connection.execute(
            insert(PipelineRun).values(
                id=run_id,
                source="synthetic",
                status="running",
                started_at=started,
                input_rows=input_rows,
                output_rows=0,
                duplicate_rows=0,
                skipped_rows=0,
                rejected_rows=0,
            )
        )
    try:
        batch = transform_synthetic(payload, now=started, retention_days=retention_days)
        with engine.begin() as connection:
            skipped = load_records(
                connection, frame_records(batch.channels), frame_records(batch.videos)
            )
            connection.execute(
                update(PipelineRun)
                .where(PipelineRun.id == run_id)
                .values(
                    status="succeeded",
                    finished_at=max(started, require_clock(clock())),
                    input_rows=batch.input_rows,
                    output_rows=len(batch.channels) + len(batch.videos),
                    duplicate_rows=batch.duplicate_rows,
                    skipped_rows=skipped,
                )
            )
    except Exception as error:
        category = (
            "data_quality"
            if isinstance(error, (DataQualityError, DataConflictError))
            else "database"
            if isinstance(error, SQLAlchemyError)
            else "configuration"
            if isinstance(error, ValueError)
            else "unexpected"
        )
        try:
            with engine.begin() as connection:
                connection.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == run_id)
                    .values(
                        status="failed",
                        finished_at=max(started, require_clock(clock())),
                        error_code=category,
                        rejected_rows=input_rows if category == "data_quality" else 0,
                    )
                )
        except (SQLAlchemyError, ValueError):
            raise PipelineFailure(run_id, "audit_unavailable") from None
        raise PipelineFailure(run_id, category) from None
    return run_id
