# Implementation plan

## Mission and decisions

Create a small, explainable portfolio application for Faouzia's public YouTube channel. Demonstrate collection, normalization, persistence, API design, UI presentation, and honest analysis. Use Python ETL, FastAPI, React/TypeScript, and SQLite. Local single-user development is the deployment target. This plan is a new baseline because the requested planning files were absent; external reference instructions remain unverified.

Phase 1 has now been explicitly authorized. The user additionally requested SQLAlchemy, Tailwind CSS, Vitest, and the unversioned `/health` endpoint. These supersede the earlier no-ORM recommendation and `/api/v1/health` proposal. Phase 2 is now explicitly authorized for extraction only; database loading and analytics are excluded.

## Architecture and contracts

```text
YouTube Data API v3 → Python ETL → data repositories → SQLite
React → FastAPI /api/v1 → analysis services / data repositories → SQLite
```

ETL runs as a separate explicit CLI process, never as an API request side effect. It shares one Python package and the data-access layer with FastAPI. API handlers validate requests and serialize responses; services calculate metrics; repositories own parameterized SQL, transactions, and connections. React handles display and user input only. No credentials or database access in the browser.

Planned layout:

```text
backend/pyproject.toml, uv.lock
backend/src/youtube_insight/{api,data,etl,services}/
backend/tests/
frontend/package.json, package-lock.json
frontend/src/
docs/
```

Use Python 3.12, uv, Node 22, npm; record exact tested versions and package-manager pins during Phase 1. The small baseline uses FastAPI/Uvicorn, HTTPX, Pydantic Settings, pytest, Ruff, React/TypeScript/Vite, SQLAlchemy 2 with Python `sqlite3`, Tailwind CSS, and Vitest/Testing Library. No additional ORM/migration framework, pandas, Airflow, Spark, Kafka, Redis, OAuth, scraping, containers, or cloud deployment by default.

SQLite: one ETL writer; short transactions, bounded busy timeout, foreign keys enabled, unique channel/video IDs, idempotent upserts, schema version tracked with a small explicit initialization mechanism. API reads use their own short-lived connections; no shared connection across request threads. Collection failures must not overwrite a complete dataset with partial results. Database path is configurable outside source directories. Review locking and transaction behavior before introducing concurrent collection.

The operational `/health` endpoint is unversioned; future domain routes use `/api/v1`. Before Phase 2, define nullable fields and response models: UTC `fetched_at`, freshness/expiry, source/channel identity, coverage status and collection outcome. Collections have bounded pagination and deterministic ordering. API routes live under `/api/v1`; frontend types must match OpenAPI contracts. Revenue calculations have one backend source of truth. Health output contains no credentials or absolute local paths.

## Public-data and policy gate

Before live collection, inspect the reference project's instructions/license and verify channel `UCLwbyg15zJgjtNL0EErkOPA` belongs to the intended Faouzia profile. Review and date a policy register using current official sources:

- https://developers.google.com/youtube/terms/api-services-terms-of-service
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/v3/docs
- https://developers.google.com/youtube/v3/determine_quota_cost

Record applicable clauses and concrete operational rules rather than asserting generic compliance. The review must cover permitted derived metrics/revenue scenarios, attribution/display, storage, refresh, deletion, and any privacy/disclosure obligations. If a planned feature conflicts, defer it and revise the plan before implementing it.

Provisional storage design: refresh displayed API data within 24 hours where quota permits; label data older than that stale and hide it after its policy deadline. Store API data no longer than 30 days since successful refresh unless the verified applicable rule requires a shorter period. A failed refresh does not reset expiry. The 30-day value is a conservative planning cap, not a legal conclusion or permission for every data type. Enforce deletion on ETL startup and before serving expired data; purge expired rows rather than merely filtering the UI. Do not persist raw responses, automatic historical snapshots, API exports, or database backups by default.

Deletion includes dependent rows, derived caches, logs containing data, and any later exports/backups; any such feature needs an explicit deletion design first. Confirmed unavailable/deleted source resources trigger removal; transient network failures and quota exhaustion must not be mistaken for confirmed deletion. Provide an explicit local purge command and documented deletion procedure. Preserve only non-sensitive run status needed to diagnose outcomes. Test with a controlled clock. No historical growth chart until retention and derived-data permission are resolved.

Public endpoints may expose available channel/video metadata, current public counts, and clearly scoped computed summaries. They cannot obtain third-party private Analytics, actual earnings, viewer countries, watch time or retroactive daily growth. Hidden counts remain null. Enumerating the uploads playlist is preferred over quota-heavy search; handle pagination, unavailable videos and partial coverage explicitly. Use timeouts, bounded backoff for retryable errors, quota accounting, and distinguish invalid credentials, quota exhaustion, missing resources and transient failures.

## Phase 1 — Offline development foundation

Required deliverables:

1. Python package skeleton with pinned toolchain, dependency manifest/lock, Ruff and pytest configuration; React/TypeScript/Vite skeleton with npm lock and type/build scripts.
2. Configuration loader with configurable SQLite path, API bind/origin settings, optional server-only YouTube key/channel ID. A missing key must not prevent offline startup. Document placeholder configuration and precedence.
3. Idempotent SQLite initialization and schema-version mechanism only; no YouTube tables or data ingestion yet. A repository-layer connection helper uses a configured temporary/local path. Prove SQLite can perform a transaction in an integration test.
4. `GET /health` with a stable status response and a React shell that shows backend health or a clear unavailable state. This is infrastructure smoke validation, not an analytics dashboard.
5. Ignored secrets, local database/journal/WAL files, virtual environments, build output and logs; offline CI and a clean-checkout README. Include synthetic data only if a test needs it, clearly labeled.

Acceptance criteria:

- Frozen installs succeed from the committed locks on documented tool versions; no lock changes after installation.
- Backend tests cover config precedence, missing-key offline startup, sanitized health response, SQLite transaction persistence in a temporary database, and repeated initialization without data loss. No test contacts YouTube.
- Backend health returns HTTP 200 with `{"status":"ok"}`. Frontend dev server serves the app and it displays that status when the backend runs; when stopped, the UI displays an unavailable state. Do not claim browser behavior based on an HTML request alone; verify it in a browser or a meaningful UI test.
- Ruff, frontend TypeScript checking, production build and offline CI checks pass. Verify no secret is included in tracked files or generated browser configuration.
- README commands work from their stated directories. Record executed outcomes, versions and any skipped checks. Git changes contain only intended foundation deliverables.

### Proposed Phase 1 verification commands

The Phase 1 implementation supplies these commands; actual outcomes are recorded in `PHASE_1_VERIFICATION.md`. Run from the repository root:

```bash
uv sync --project backend --frozen
uv run --project backend --frozen ruff check backend
uv run --project backend --frozen ruff format --check backend
uv run --project backend --frozen pytest backend/tests
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Start in separate terminals from the repository root:

```bash
uv run --project backend --frozen python -m uvicorn youtube_insight.api.main:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Configure the frontend's non-secret API base URL for port 8000 and allow exactly the local frontend origin in backend development CORS. Verify internally:

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:5173/
git diff --check
git status --short
```

Assert the health JSON equals the documented response, and use browser/UI verification for health/unavailable display. Local requests validate services; do not publish loopback preview links. Use the existing isolated checkout, not a new worktree. Processes must be restarted in future cloud tasks; installation artifacts alone do not imply running services.

Excluded from Phase 1: live YouTube calls, ETL implementation, analytics tables, channel/video API routes, charts, revenue calculations, scheduled collection, public hosting and authentication.

## Phase 2 — Public YouTube extraction client (authorized scope)

The user's Phase 2 instruction narrows the original ETL/persistence phase to extraction only. Implement a reusable Python YouTube Data API v3 client, typed public channel/video metadata, UTC collection timestamps, and an explicitly invoked bounded CLI sample. Do not load the database, add domain tables or API routes, or implement analytics.

Use `channels.list` to obtain the uploads playlist, `playlistItems.list` with page tokens, and `videos.list` in batches of at most 50 IDs. Keep credentials server-side, out of URLs/logs/errors; use explicit timeouts, bounded retry/backoff, typed authentication/quota/HTTP/network errors, and an HTTP transport injectable for offline tests. Preserve null optional statistics, requested order and unavailable IDs. Bound both selected entries and playlist pages; expose incomplete coverage rather than promising a complete channel inventory.

Acceptance: mocked success, pagination, empty/unavailable entries, absent statistics, invalid keys, HTTP errors, timeouts, quota errors, retry bounds and 50-ID batches all pass. CLI emits a normalized limited sample to stdout and sanitized structured events to stderr, with no persistence. Frozen installation, all backend tests and Ruff checks pass. Live integration is separately opt-in and unverified when a key or policy review is unavailable. See `YOUTUBE_EXTRACTION.md` and `PHASE_2_VERIFICATION.md`.

Live-use gates remain: inspect current official policies and reference-project licensing before reuse, verify the selected artist channel, restrict the key and review quota/freshness/deletion obligations. Offline client implementation does not certify compliance. Persistence, refresh/purge commands and retention enforcement are deferred to a separately authorized loading phase; these must be designed before any stored API data is introduced.

## Phase 3 — Read-only API and analytical UI

Release-review prerequisite: Phase 2 is extraction-only and introduces no domain tables or loading. Before implementing this phase, agree on a separately authorized persistence step or an explicitly fixture-only API/UI scope. Live-backed functionality also requires validated channel identity, working key/network access and reviewed retention/deletion rules. Do not infer that a completed extraction client supplies a populated database.

Expose channel overview and paginated video listings through `/api/v1`; React displays nullable metrics, freshness, coverage, loading, empty, stale and error states. Only repositories touch SQL. No collection triggered by GET requests and no public refresh route.

Acceptance: API integration tests use a temporary SQLite fixture and validate schema, order, pagination bounds, nulls, expired-data behavior and sanitized failures. Frontend tests cover representative states and API contract compatibility; production build passes. A functional end-to-end flow uses synthetic seeded data, then optional policy-compliant live data. Label fixture mode clearly.

## Phase 4 — Illustrative revenue scenarios

Only after confirming policy permits the planned derived output, accept scenario view count/scope, viewer-country percentage weights, currency, and low/base/high effective creator RPM per country. Weights are user assumptions, never inferred audience data. Require weights to sum to 100% within a documented small tolerance; reject negatives, non-finite inputs and inverted ranges. Include an explicit rest-of-world category where needed.

For scenario s: `estimated_revenue_s = scenario_views / 1000 × sum(country_weight × effective_RPM_country_s)`. Effective RPM is assumed creator revenue per thousand total scenario views; do not silently add CPM-to-RPM or monetized-share multipliers. Scope views by format; exclude Shorts from the baseline or supply a separately labeled model. Lifetime-view scenarios are hypothetical, never monthly earnings. No period estimate without a valid period view input.

Acceptance: deterministic formula tests (100,000 views; 50% at $1 and 50% at $3 effective RPM → $200), low ≤ base ≤ high, invalid-input tests, clear currency/period/format labels and visible assumptions. UI explains unknown real audience distribution, rights splits and eligibility, and that outputs are not Faouzia's actual earnings. No undocumented “industry average” presented as fact; any presets require attributed, dated sources and remain editable assumptions.

## Phase 5 — Reproducibility and presentation

Document clean-clone installation, config, offline fixture demo, live opt-in workflow, quota handling, freshness and deletion operations, architecture, limitations and reference attribution/license obligations. Provide a concise demonstration narrative and screenshots from a clearly identified mode with no secrets or misleading earnings claims.

Acceptance: execute the documented offline demo from a clean checkout using locks; all required suites/builds pass or documented repository defects are diagnosed honestly. Record real commands and outcomes, verify no API data/credentials/databases are tracked, and demonstrate purge behavior. Public deployment is outside this plan and needs a separate security/operations review.
