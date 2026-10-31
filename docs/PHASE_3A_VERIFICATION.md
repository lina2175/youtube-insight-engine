# Phase 3A verification — offline ETL and database foundation

Date: 2026-10-31. Scope: synthetic fixtures only. No live YouTube request or persistence, dashboard, analytics, revenue or recommendation feature was implemented. This report supersedes the earlier fixed-artist product scope; prior verification reports remain historical evidence.

## Product and phase correction

`docs/IMPLEMENTATION_PLAN.md` now describes the complete multi-channel product: premium dark React SaaS interface, exploration/comparison, Python/Pandas ETL, relational SQLite/SQLAlchemy, SQL/statistical analytics, editable country-aware revenue scenarios, evidence-based recommendations, monitoring/data quality and reproducible portfolio delivery. Faouzia is an optional example. AGENTS and README reflect that mission. The foundation shell's artist-specific sentence was generalized, with no new dashboard behavior.

Boundaries are explicit: Phase 3A is offline ETL/storage; 3B is separately authorized policy-gated live loading; later phases cover UI/read API, SQL/statistical analytics/recommendations, revenue simulations and monitoring/portfolio release. Pipeline execution/data-quality records belong to 3A; their UI belongs to a later phase. Existing Phase 1 and Phase 2 capabilities remain available.

## Implemented architecture

Built-in fictional channel/video dictionaries → strict Pydantic validation → Pandas nullable/UTC normalization and deterministic deduplication → plain Python records → SQLAlchemy upserts in SQLite. The synthetic pipeline never imports the live extraction client or reads a key. Only labeled synthetic envelopes and namespaced IDs pass validation; the CLI accepts no external dataset input.

Three relational tables hold current channel/video state and execution records. Channel/video identity is unique, video ownership is a foreign key with deletion cascade, and source/expiry/nonnegative-count checks defend persistence. Aware UTC timestamps survive SQLite round trips. No historical snapshots are stored. See `OFFLINE_ETL.md` for the dictionary and failure/retention contracts.

Explicit domain initialization upgrades schema v1 to v2 transactionally; fresh health-only initialization remains v1 without domain tables. Tests verify repeatability, existing-data preservation, migration rollback, name-collision rejection, unsupported-version rejection and successful `/health` against a migrated v2 database.

Each invocation commits a running record separately; validated domain upserts and the success outcome then commit atomically. Data errors roll back the full domain batch and write a sanitized failed outcome separately. No row payload or exception text is retained in execution records. Older/equal observations are skipped or checked for conflicts; newer data updates current state. Reruns cannot extend expiry, while a shorter same-observation TTL can tighten it.

Retention uses collection-based expiry (synthetic 1–30 days), exact boundary checks and pre-load/explicit cleanup. Channel deletion cascades to videos; individual video deletion and full purge are available. Run metadata expires after 7 days by default (configurable 1–30), including abandoned old running records. These are engineering contracts for synthetic data, not a claim about current YouTube policy.

## Actual verification

All repository commands ran from `/workspace/youtube-insight-engine`. Toolchain: Python 3.12.14, uv 0.12.23, Node 22.23.4 and npm 10.9.4. Commands used the installed Node toolchain via PATH and writable caches outside the checkout. TestClient/worker checks used approved process permissions; real HTTPX transport stays blocked in automated tests.

| Command/check | Actual outcome |
| --- | --- |
| `uv sync --project backend` | Passed; Pandas 2.3.3 and its runtime dependencies installed with verified registry artifacts; lock updated |
| `uv sync --project backend --frozen --offline` | Passed; 34 packages checked |
| `uv lock --project backend --check --offline` | Passed; 35 packages resolved |
| `uv run --project backend --frozen pytest backend/tests` | **117 passed**, no failures or skips; 1 existing TestClient deprecation warning |
| `uv run --project backend --frozen ruff check backend` | Passed |
| `uv run --project backend --frozen ruff format --check backend` | Passed; 20 Python files |
| `npm --prefix frontend ci` | Passed; 178 packages installed from lockfile |
| `npm --prefix frontend test` | **8 passed** in 1 file |
| `npm --prefix frontend run typecheck` | Passed |
| `npm --prefix frontend run build` | Passed; 32 modules transformed |
| `uv run --project backend --frozen youtube-sample --help` | Passed; existing extraction CLI retained |
| Offline demo CLI, two real invocations against a temporary SQLite file | Passed: `(channels, videos, runs)` = `(2, 3, 1)` then `(2, 3, 2)`; schema v2; second run skipped all 5 current observations |
| `git diff --check` and staged whitespace check | Passed |
| Scoped credential/private-file scan | No recognized credential signatures or generated/private data types in candidate files/history; local databases and build artifacts ignored |

The final backend suite consists of 74 preserved Phase 1/2 cases and 43 Phase 3A cases. New coverage includes multiple channels, Pandas types, precision above 2^53, null vs zero, strict counts, namespace/provenance rejection, timestamps/chronology, missing references, duplicate/conflicting observations, empty videos, idempotence, stale updates, TTL tightening/no extension, success/failure counts, atomic rollback after partial writes, expiry boundary and cascading cleanup, individual/full deletion, run retention, FK/source constraints, migration and CLI repeatability. No API key or external service is needed.

No hosted GitHub Actions result is claimed for this local development commit. No push was requested or performed. Existing CI automatically discovers all backend tests and runs frontend checks after the commit is published in a future authorized workflow.

Warnings: the existing Starlette HTTPX TestClient deprecation warning remains non-failing. npm clean install emitted the existing transitive `whatwg-encoding` deprecation warning through jsdom. Neither warning was suppressed; no checks or assertions were disabled.

## Reproduce from the repository root

```bash
uv sync --project backend --frozen
uv run --project backend --frozen pytest backend/tests
uv run --project backend --frozen ruff check backend
uv run --project backend --frozen ruff format --check backend
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
uv run --project backend --frozen youtube-offline-demo \
  --database .local/phase3a-demo.sqlite3
```

Repeat the last command on the same UTC day to see stable domain counts and an additional run record. The CLI's fixture observations anchor to that UTC day's midnight; a new day deliberately creates newer fictional observations. Unit tests use fixed clocks. Use a separate ignored database path; no live input is accepted.

## Files created and modified

Created:

- `backend/src/youtube_insight/data/domain.py`
- `backend/src/youtube_insight/data/loading.py`
- `backend/src/youtube_insight/etl/synthetic.py`
- `backend/src/youtube_insight/etl/transform.py`
- `backend/src/youtube_insight/etl/offline_pipeline.py`
- `backend/src/youtube_insight/etl/offline_cli.py`
- `backend/tests/test_offline_etl.py`
- `docs/OFFLINE_ETL.md`
- `docs/PHASE_3A_VERIFICATION.md`

Modified:

- `AGENTS.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `README.md`
- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/src/youtube_insight/data/database.py`
- `frontend/src/App.tsx` (multi-channel mission copy only)

No real data files, secrets, generated databases, virtual environments or frontend build output are included in the commit.

## Remaining limits and development status

- Phase 3A supports a bounded single-writer offline workload; no scheduler, concurrent-run orchestration or monitoring UI is implemented.
- A process killed mid-run can leave a running record until run retention cleanup. Startup/schema failures before run creation cannot be audited in that database; inability to write failure evidence raises a sanitized `audit_unavailable` category.
- Purge is explicit/pre-load, not a background service. Future API reads must independently enforce freshness. Deletion is logical SQL deletion, not forensic erasure of disk/journal/external copies.
- The fixture schema is a deliberate current-state subset. More public metadata, live provenance and analytical structures require reviewed versioned migrations, not silent changes to the v2 schema.
- Input TTL is applied per observation, not a global retroactive rewrite of every stored policy. Expired rows must be purged explicitly; global policy changes need a separately tested migration/cleanup design.
- Strict synthetic namespace/provenance prevents accidental API sample loading; it cannot prove that a caller has not deliberately relabeled real data. That is prohibited by AGENTS and this phase's scope.
- Live API authentication/channel identity/network/policy status remains as reported in Phase 2; no live smoke test or data loading was attempted here. No live-use compliance claim is made.
- Later product capabilities are planned, not claimed as implemented. Stop after Phase 3A; dashboard/analytics features and live loading require new instructions.

Development artifact: a separate commit titled `feat: add synthetic Phase 3A ETL and relational storage` on local branch `phase-3a-offline-etl`, based on Phase 2 report commit `49b8881`. The commit includes this report; use `git log -1 --oneline` to obtain its immutable SHA. This branch is not pushed automatically.
