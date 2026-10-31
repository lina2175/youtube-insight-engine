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

## Follow-up review and controlled integration readiness — 2026-10-31

### Commit, cleanliness and publication readiness

Confirmed full commit `d34af1b23d5b578eafadc6552593486475b3576a` on local branch `phase-3a-offline-etl`. `git status --porcelain=v1` was empty before the review and remained empty after executing checks; generated output stayed ignored. Only the review/proposal documents described below were changed afterward.

A fresh remote read showed `main` at `11504ff240f85d8de753adae475b4371b2763fc7` and `phase-2-integration` at `49b888115ae15c98bb687ae4ced17911f6b35e8f`, with no remote `phase-3a-offline-etl`. The default fetch did not populate the Phase 2 tracking ref, so it was fetched explicitly before comparison. `git rev-list --left-right --count origin/phase-2-integration...HEAD` then returned `0 1`, and the ancestry check passed.

`git push --dry-run origin HEAD:refs/heads/phase-3a-offline-etl` succeeded, advertising a new branch. A subsequent `git ls-remote --heads origin phase-3a-offline-etl` returned no ref, confirming the dry run did not publish anything. The reviewed commit can presently be pushed as a new branch with a normal non-force push; recheck remote state if publishing later. Main and the existing Phase 2 branch need not change. No actual push was requested or performed during this review.

Publication command for a later explicit instruction:

```bash
git push -u origin HEAD:refs/heads/phase-3a-offline-etl
```

### Repository hygiene

Repeated the scoped path/signature review across 51 non-ignored candidate files and 67 historical blobs. No recognized Google/GitHub/AWS/private-key signatures or tracked generated/private data types were found. Reviewed fixture source is explicitly fictional; API tests use mocks. Environment examples contain placeholders, not a key. Actual env files, SQLite databases, virtual environments and frontend output are ignored. This is bounded signature/path evidence plus source review, not a universal secret-detection guarantee.

### Repeated demo and complete checks

Executed the installed `youtube-offline-demo` command twice against the same new temporary SQLite file. Results were `(channels, videos, runs) = (2, 3, 1)` then `(2, 3, 2)`. Compared every channel/video field after both invocations, including publication, collection and expiry: all domain values were identical. The second run skipped all five existing observations, and schema version remained 2. The temporary database was removed after verification; it contained no API data.

| Re-executed command/check | Actual result |
| --- | --- |
| `uv sync --project backend --frozen --offline` | Passed; 34 packages checked |
| `uv run --project backend --frozen pytest backend/tests` | **117 passed**, no failures/skips; one existing TestClient deprecation warning |
| `uv run --project backend --frozen ruff check backend` | Passed |
| `uv run --project backend --frozen ruff format --check backend` | Passed; 20 Python files |
| `npm --prefix frontend test` | **8 passed** in 1 file |
| `npm --prefix frontend run typecheck` | Passed |
| `npm --prefix frontend run build` | Passed; 32 modules transformed |
| Offline CLI twice plus full domain-row equality | Passed; stable domain state and additional run evidence |
| API-shaped fictional sample → current synthetic transform | Rejected with `DataQualityError` as designed; manual compatibility probe, not a live test |

All commands ran from the repository root using the existing pinned tools and writable external caches. No additional dependencies, code changes or assertions were introduced. Frontend dependencies were reused for this rerun, not reinstalled; the prior clean-install result remains historical. Hosted Actions for this unpushed commit was not run or verified.

### Official requirements and live readiness — blocked

Fresh attempts to read current official API terms, developer policies, quota rules and the channels.list reference all failed with tunnel HTTP 403 Forbidden on `developers.google.com`. The optional public channel page on `www.youtube.com` and a credentialless API-host probe on `www.googleapis.com` failed with the same restriction. These are network-policy outcomes, not proof that the channel does not exist or that a key is invalid. Current official requirements could not be reviewed; prior discovery-document evidence is not a substitute for current policy review.

Current backend Settings has no nonempty `YOUTUBE_API_KEY` and no selected `YOUTUBE_CHANNEL_ID`; runtime metadata lists no secret bindings. Configuration remains backend-only: key stored as SecretStr, sent through a header rather than a URL, not exposed in frontend environment/configuration, normalized models or allowlisted logs. Root/frontend environment files were not created or printed.

**No live extraction was performed.** There is no live response to validate, and the optional Faouzia channel ID remains unverified. No raw API data, credentialed request or live pipeline success is claimed. Network policy, proxy, CA/TLS settings and secret bindings were not changed or bypassed.

Required external prerequisites remain: secure backend credential configuration; supported network-setting access to the three destinations above; current policy/quota review; explicit selected-channel identity verification. Do not send a key in chat or place it in frontend variables. Once prerequisites and the adapter contract are satisfied, one at-most-five-entry extraction may be verified in memory, separately from any loading decision.

### Contract and retention integration review

The current live-extraction result is **not directly compatible** with Phase 3A, intentionally:

- Phase 2 emits singular `channel` plus videos, playlist coverage and completion metadata; 3A accepts a strict plural-channel `SyntheticBatch` with `dataset_kind='synthetic'`.
- Real provider IDs do not satisfy the synthetic namespace. SQLite v2 also enforces synthetic provenance. These guards must remain; never relabel real data to bypass them.
- API titles/channel associations may be missing; 3A requires a normalized nonblank title and a known channel relationship. Its counts are strict signed Int64, while Phase 2 permits general nonnegative integers. A bridge needs explicit validation/rejection and precision behavior.
- Description, country, uploads playlist, tags, category, duration and coverage do not all have v2 storage columns. Define a deliberate projection/versioned migration rather than silently dropping meaningful provenance or declaring complete coverage.

A fictional API-shaped model was passed to the current transform during this review and was correctly rejected. This proves only the boundary guard, not live compatibility. No adapter was implemented.

Synthetic retention/deletion tests pass: collection-based expiry, exact boundary removal, no replay extension, optional tightening, parent cascade, selective/full deletion and run retention. Those tests do not authorize storing real API data. Before enabling live persistence, resolve current applicable deadlines and refresh rules, read-time stale-data prevention, policy-change cleanup, deletion across future caches/exports/backups, interrupted-run behavior and the distinction between confirmed source deletion versus unavailable IDs in a bounded sample. Current cleanup is pre-load/explicit, not scheduled; SQL deletion is logical, not forensic disk erasure. No persistence switch was enabled.

### Next safe milestone and changed files

Propose **Phase 3B.0: offline API-shaped contract and end-to-end rehearsal**, using MockTransport and fictional data only. Specify the source-aware projection/quality policy, then test client → Pandas → temporary storage → rollback/expiry/deletion without weakening the synthetic path or enabling live provenance. Concrete deliverables and acceptance scenarios are in `PHASE_3B_OFFLINE_CONTRACT_PLAN.md`. It is a proposal for the next instruction, not work implemented in this review.

Review changes are documentation only: appended this report, created `docs/PHASE_3B_OFFLINE_CONTRACT_PLAN.md`, and linked the proposed milestone from `docs/IMPLEMENTATION_PLAN.md`. They remain uncommitted for review; implementation commit d34af1b is unchanged. No dashboard, analytics, revenue feature or live integration was added. Stop here.
