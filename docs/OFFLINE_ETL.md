# Phase 3A — synthetic offline ETL and relational storage

This module develops the persistence/ETL foundation for the multi-channel product. It neither invokes the Phase 2 YouTube client nor accepts its extraction sample format. No live data, analytics endpoints, dashboard, revenue or recommendations are implemented here.

## Run the demo

From the repository root, after frozen dependency installation:

```bash
uv sync --project backend --frozen
uv run --project backend --frozen youtube-offline-demo \
  --database .local/phase3a-demo.sqlite3
```

Run the last command twice: each prints a synthetic marker and run UUID; both report 2 channels and 3 videos, while runs increase from 1 to 2 on a new database. IDs and names are fictional, not real channels. The explicit file is separate from the foundation's default database and is ignored by Git. No API key, network request or `.env` is needed. The CLI accepts only its built-in fixtures, not an external file or live source. Never relabel real data to pass the synthetic loader.

Fixtures use the current UTC day's midnight as their collection anchor so same-day reruns are stable; a new day generates a new explicitly fictional observation. Tests and reusable calls pass a fixed aware clock for exact reproducibility. `fixture_batch(now)` makes independent dictionaries. `--retention-days` accepts 1–30 (default 30); this is synthetic test configuration, not a verified YouTube storage permission.

## Data flow and responsibilities

`synthetic.fixture_batch` → `transform.transform_synthetic` → `offline_pipeline.run_synthetic_pipeline` → `data.loading.load_records` → SQLite.

Validation requires a `dataset_kind: synthetic` envelope with channel/video lists. Every resource ID has a `synthetic_` namespace, and every video's channel must be in the batch. Row models reject extra fields, missing identity/time fields, blank titles, non-integer/negative/overflow statistics, naive timestamps, future collection, invalid chronology, expired input and conflicting ownership. The envelope caps 100 channel rows and 5,000 video rows; it is a small offline workload.

Pandas normalizes whitespace, UTC timestamp columns, nullable `Int64` statistics and stable latest-observation selection. Object construction avoids rounding large integer counts through floats. Exact duplicates collapse; conflicting same-ID/same-time observations fail. Missing statistics become SQL NULL; known zero remains zero. A missing publication date stays null. Transforms are not analytical scoring or statistical services.

Pandas output becomes plain Python records before the repository boundary. Data access does not depend on ETL types or Pandas. SQLAlchemy handles parameterized statements, foreign keys and database transactions. One ETL writer is supported; distributed/concurrent orchestration is outside this phase.

## Schema and dictionary

Explicit `initialize_domain_database(engine)` upgrades version 1 to 2 using an explicit SQLite transaction; table creation and `user_version` commit together. It preserves unrelated existing tables, rejects colliding domain table names in v1 and refuses unsupported versions. Repeating initialization is safe. Foundation `initialize_database` still leaves a fresh health-only database at v1 with no domain tables, and accepts an explicitly upgraded v2 database without downgrading it.

| Table | Identity / references | Data |
| --- | --- | --- |
| `channels` | `id` primary key | title, synthetic source, nullable view/subscriber counts, optional publication time, collection/expiry times |
| `videos` | `id` primary key; indexed `channel_id` FK → channels, `ON DELETE CASCADE` | title, synthetic source, nullable view/like/comment counts, optional publication time, collection/expiry times |
| `pipeline_runs` | random UUID primary key, no payload-resource FK | synthetic source, running/succeeded/failed status, start/finish time, input/output/duplicate/skipped/rejected counts and sanitized error code |

All data rows represent current state, not historical snapshots. UTCDateTime rejects naive writes and restores aware UTC values when SQLite reads its stored UTC wall times. SQL checks enforce synthetic provenance, nonnegative counts and expiry after collection; input validation enforces additional chronology and signed 64-bit bounds. Video association, expiry and run start have relevant indexes. Additional public fields, live provenance and analytical tables need future explicitly versioned migrations.

## Loading and run evidence

Each pipeline invocation:

1. Validates the aware execution clock, initializes schema, and independently purges expired records.
2. Commits a `running` record so failed data transactions do not erase evidence of invocation.
3. Validates/transforms the whole input before domain writes.
4. Upserts channels then videos in one transaction and marks the run succeeded in that same transaction.
5. On error, rolls back all domain changes, then records a failed status in a separate transaction and raises a sanitized `PipelineFailure`.

Newer observations replace older state. Older ones are skipped. Same-time values must agree with stored values; otherwise loading fails. Same-time expiry may be shortened but never extended. Ownership changes fail. Unique resource keys make domain loading idempotent; run history intentionally grows per invocation.

`input_rows` is the submitted channel+video row count, `output_rows` is the accepted deduplicated count on success, `duplicate_rows` is removed input rows, and `skipped_rows` counts accepted observations that did not update stored state. Thus `output_rows` does not mean newly inserted rows. A data-quality rejection rejects the entire batch and records that submitted count in `rejected_rows`; output remains zero. A database failure records zero output after rollback. Error codes use fixed categories; no rejected row, title, raw exception or credential is retained.

Schema/startup failure before run creation cannot produce a run record. If the database cannot persist the failure audit, a sanitized `audit_unavailable` failure is raised; do not assume an audit was written. A killed process can leave a `running` record, which remains visible until retention cleanup; no scheduler/process recovery is implemented. Run duration can be computed from finish minus start; no monitoring screen exists.

## Retention and deletion

`expires_at = fetched_at + retention_days`. Purge uses `expires_at <= now`, including exact boundaries. Failed refresh/replay cannot reset age. Expired channels remove dependent videos even if a child's individual expiry is later. Purge executes before pipeline loading (even if the new input fails), or explicitly through `purge_expired(engine, now=aware_utc_clock)`.

Operational runs expire after 7 days by default; `run_retention_days` accepts 1–30. Cleanup uses start time and also removes abandoned running records beyond that deadline. No user payload or channel/video identifiers are stored in run records. There is no background purge: explicit execution is required; future API reads must enforce freshness before serving domain data.

The data-layer functions `delete_channel`, `delete_video`, and `purge_all` provide explicit logical deletion. Channel deletion cascades to videos; run summaries remain until their own retention or full purge. Full purge removes channels, videos and runs while retaining schema. Deletion is idempotent. An explicit later fixture load can recreate a deleted fictional row; no source tombstone protocol is claimed.

Example reusable offline operations:

```python
from datetime import datetime, timezone
from pathlib import Path
from youtube_insight.data.database import create_database_engine
from youtube_insight.data.loading import delete_channel, purge_expired
from youtube_insight.etl.offline_pipeline import run_synthetic_pipeline
from youtube_insight.etl.synthetic import fixture_batch

now = datetime.now(timezone.utc)
engine = create_database_engine(Path('.local/separate-offline.sqlite3'))
try:
    run_synthetic_pipeline(engine, fixture_batch(now), clock=lambda: now)
    delete_channel(engine, 'synthetic_channel_alpha')
    purge_expired(engine, now=now)
finally:
    engine.dispose()
```

Deletion is logical SQL deletion, not a forensic erase guarantee for disk pages, journals or external copies. This phase creates no application caches, exports or backups. Any later such artifacts need deletion/retention coverage. Nothing here establishes permission to store live YouTube data: Phase 3B requires current policy review, source identity/credentials/network verification and a separately authorized live loading design.
