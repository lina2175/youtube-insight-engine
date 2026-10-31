"""Offline-only built-in fixture demonstration, with an explicit database path."""

import argparse
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from youtube_insight.data.database import create_database_engine
from youtube_insight.data.domain import Channel, PipelineRun, Video
from youtube_insight.etl.offline_pipeline import PipelineFailure, run_synthetic_pipeline
from youtube_insight.etl.synthetic import fixture_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load fictional multi-channel fixtures only; no network"
    )
    parser.add_argument(
        "--database", required=True, type=Path, help="Separate offline SQLite file"
    )
    parser.add_argument("--retention-days", type=int, default=30, choices=range(1, 31))
    args = parser.parse_args(argv)
    engine = create_database_engine(args.database.expanduser().resolve())
    try:
        run_id = run_synthetic_pipeline(
            engine, fixture_batch(), retention_days=args.retention_days
        )
        with engine.connect() as connection:
            counts = {
                name: connection.scalar(select(func.count()).select_from(model))
                for name, model in [
                    ("channels", Channel),
                    ("videos", Video),
                    ("runs", PipelineRun),
                ]
            }
        print(json.dumps({"dataset_kind": "synthetic", "run_id": run_id, **counts}))
        return 0
    except PipelineFailure as error:
        print(
            json.dumps(
                {"status": "failed", "run_id": error.run_id, "category": error.category}
            )
        )
        return 1
    except (SQLAlchemyError, RuntimeError, ValueError):
        print(json.dumps({"status": "failed", "category": "initialization"}))
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
