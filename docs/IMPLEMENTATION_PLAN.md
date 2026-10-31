# YouTube Insight Engine — implementation plan

## Product mission and complete scope

Build a reproducible multi-channel YouTube intelligence portfolio application for exploring videos, comparing channels, understanding content performance, testing revenue assumptions and explaining evidence-based recommendations. Faouzia is an optional example, never a fixed channel or schema assumption. The product should demonstrate data engineering and analytical judgment through meaningful Python/Pandas transformations, relational SQL, statistics and a premium dark React SaaS interface.

Final capabilities:

- Multiple independently selected channels and their public video inventories, with explicit coverage/freshness and comparable date/format filters.
- Premium responsive dark React/TypeScript/Tailwind workspace: channel management, video exploration, channel comparison, accessible interaction, consistent components, loading/empty/stale/error states and clearly labeled synthetic demo mode.
- Python/Pandas ETL, validated records, SQLite relational storage through SQLAlchemy, idempotent refreshes, atomic writes and observable execution/data-quality records.
- Meaningful SQL aggregates (joins, grouping, ranking, window calculations where appropriate) and statistical summaries: distributions, medians/quantiles, variability and sample sizes. Compare like-for-like age/time/format cohorts. Current cumulative counts do not supply historical daily growth.
- Country-aware revenue simulations with editable viewer-country weights, low/base/high effective RPM assumptions, currency and view scope. These are hypothetical scenarios, never actual creator revenue or inferred audience geography.
- Content recommendations supported by explicit comparisons, sample sizes, uncertainty and documented heuristics; avoid causal claims from correlations or generic advice presented as measured evidence.
- Pipeline monitoring and data quality: run outcomes, durations/counts, rejected data, coverage, stale data, quota/errors and safe operator diagnostics.
- GitHub reproduction: frozen installs, offline synthetic fixtures, automated tests/CI, architecture/data dictionary, SQL examples, limitations, attribution and a short portfolio demo narrative.

## Architecture and responsibilities

```text
Synthetic fixtures → Pandas validation/transforms → SQLAlchemy repository → SQLite
YouTube Data API → explicit Python extraction → [future policy-gated loading]
React → FastAPI /api/v1 → analytical services / read repositories → SQLite
```

The operational health route stays `/health`. Frontend never receives credentials, runs SQL, calls YouTube directly or implements independent revenue formulas. FastAPI validates/serializes requests and invokes services; repositories own SQL and transactions; Pandas normalizes/validates data; services will own statistical reasoning and scenarios. Collection runs explicitly outside HTTP GET handlers. One Python package and a local single-writer SQLite database are sufficient; multi-channel does not imply multiple deployments.

Use Python 3.12, uv with `backend/uv.lock`, Node pinned by `.nvmrc`, npm with `frontend/package-lock.json`, FastAPI/Uvicorn, HTTPX, Pydantic Settings, Pandas, SQLAlchemy/SQLite, pytest/Ruff, React/TypeScript/Vite/Tailwind and Vitest/Testing Library. Pandas is now explicitly required. No Spark, Kafka, Airflow, Redis, extra databases, authentication, paid-service integration or deployment system without a demonstrated need and separate authorization.

## Existing phases (preserve)

### Phase 1 — Offline foundation (complete)

FastAPI `/health`, secure optional server configuration, React shell/real backend connection indicator, reusable dark theme, SQLite version initialization, dependency locks, backend/frontend tests and CI. Keep startup and tests working. Foundation startup need not create domain tables; domain initialization is an explicit operation.

### Phase 2 — Public API extraction (complete offline; live verification blocked)

Reusable channels/playlistItems/videos client, bounded pagination/50-ID batching, nullable public metadata and aware UTC timestamps, sanitized structured logging, retry/error classification and opt-in sample CLI. Preserve existing behavior and mocked tests. No loading is coupled to this client in Phase 3A. See `PHASE_2_VERIFICATION.md` for actual release/live limitations.

## Phase 3A — Offline ETL and database development (authorized now)

Only built-in explicitly synthetic multi-channel fixtures may enter this path. No fetching or persistence of live YouTube data. No dashboard, API analytics or revenue/recommendation features.

Deliver:

1. Strict synthetic fixture envelope and typed row validation. IDs must use a synthetic namespace. Reject negative/out-of-range counts, missing identity/reference fields, blank titles, invalid/naive timestamps, future collection times and publication-after-collection. Null counts remain unknown; zero remains zero.
2. Pandas transformations with nullable integer statistics, UTC datetime columns, normalized text, deterministic duplicate resolution (latest collection wins), conflict/orphan checks and data-quality counts. Never silently truncate or coerce invalid counts to zero.
3. SQLAlchemy channels/videos models with channel foreign keys, current-state metadata/statistics, UTC collection/expiry, synthetic provenance and relational/check constraints. No automatic historical snapshots. Pipeline execution records hold operational status/counts and sanitized failure codes, not payloads or secrets.
4. Explicit, transactional version-1-to-version-2 schema initialization that preserves existing foundation data and rejects unknown versions. No migration framework needed for this single additive migration.
5. Atomic idempotent domain loading: unique resource IDs; same/older observations cannot overwrite newer state or extend expiry. Each invocation has a distinct run record. Failure rolls back all data writes and records a failed outcome separately. Validation failures do not create a partially loaded dataset.
6. Clock-testable expiry, explicit channel/video deletion with dependent video cascade, full purge, and bounded operational run-record retention. A synthetic TTL (1–30 days) is test configuration, not reviewed YouTube permission. Expired fixture data is purged before loading; reruns do not reset collection age. No caches/exports/backups are added.
7. An explicit offline demo CLI taking a separate database path and using only bundled fixtures, plus data dictionary and reproduction instructions.

Acceptance: test multiple channels and FK association, null versus zero including large integers, duplicate/conflicting observations, invalid payloads, stale upserts, transaction rollback, preserved schema migration, pipeline successes/failures, expiry boundaries, cascades/full purge and run-record retention. Repeated demo loading changes run history but not domain cardinality or timestamps. Existing Phase 1/2 tests remain passing. Run all backend/frontend tests, Ruff lint/format, TypeScript and production build. Record actual outcomes in `PHASE_3A_VERIFICATION.md`. Commit separately; do not push or start subsequent phases automatically.

## Phase 3B — Policy-gated live loading and operational readiness (not authorized)

Review update: live prerequisites remain blocked. Before live loading, propose Phase 3B.0 as an offline API-shaped contract/end-to-end rehearsal using mocked HTTP and fictional data, followed by a separately gated Phase 3B.1 live verification. See [the proposed contract milestone](PHASE_3B_OFFLINE_CONTRACT_PLAN.md) for deliverables, mapping gaps and acceptance scenarios. This is a proposal only; no adapter or live persistence is authorized or implemented by the review.

Verify selected channel identities and actual API behavior with bounded manual smoke checks. Review current official YouTube terms and quota costs; document concrete refresh/deletion deadlines, attribution and allowed derived uses. Add a separately reviewed bridge from extraction models to validated live storage, including missing/unavailable resource handling and coverage-aware refreshes. Phase 3A deliberately rejects live provenance; do not relabel live data as synthetic. Enforce retention/deletion across related records and any future caches/exports/backups. Distinguish source deletion from transient failure or a limited sample.

Acceptance: policy register dated with applicable clauses; mocked complete/partial/quota/error loading cases; live checks separate from CI; key/permissions restrictions verified; no stale refresh extends expiry; deletion and rollback tests; quota/request budgets documented. No live-use compliance claim from an offline synthetic test.

## Phase 4 — Read API and premium exploration/comparison UI (not authorized)

Define versioned bounded API contracts for channel inventory, filtered/sorted/paginated videos, freshness/coverage and comparisons. Build the premium dark SaaS workspace with multi-channel selection, responsive accessible reusable components and clear synthetic/demo labeling. Support like-for-like filters and explain unknown values. GET must not trigger collection.

Acceptance: SQL/API contracts and pagination/input bounds tested; no secret/path leakage; UI loading/empty/error/stale states and channel switching tested; frontend/backends agree on types; functional fixture demo and production build pass. No misleading live connection labels for fixture data.

## Phase 5 — SQL/statistical analytics and evidence-based recommendations (not authorized)

Implement documented SQL joins/aggregates/rankings and meaningful statistical summaries, respecting coverage, video age, format and observation time. Show denominators/sample sizes and uncertainty. Recommendations cite the exact cohort comparison and metric, minimum sample thresholds and limitations; insufficient evidence produces an explicit no-recommendation outcome. No unsupported causal explanations, private Analytics assumptions, historical growth charts or ML infrastructure by default.

Acceptance: hand-computed synthetic reference results, SQL edge/null/sample cases, cohort boundaries and deterministic recommendation rationales; correlated signals not described as causes; accessible explanatory UI and evidence traceability.

## Phase 6 — Country-aware revenue simulations (not authorized)

Use explicit editable viewer-country weights summing to 100% and low/base/high effective creator RPM per thousand total scenario views. Formula: `views / 1000 × sum(country_weight × effective_RPM_country)`. Keep one backend calculation source and validate finite/nonnegative inputs, ordered scenarios, currency and view scope. Include a rest-of-world option. Do not use creator nationality as viewer geography, call scenarios real earnings, or turn lifetime views into monthly revenue. Shorts need a separate labeled model; music rights/eligibility remain unknown.

Acceptance: deterministic formula cases (100,000 views; equal $1/$3 RPM mix → $200), invalid-input and weight tests; clear low/base/high assumptions and currency/period labels; editable UI; permitted-use policy reviewed before live-derived output.

## Phase 7 — Pipeline monitoring and portfolio release (not authorized)

Expose the existing run/data-quality evidence safely in the UI; add coverage/freshness monitoring and operator actions appropriate to the reviewed scope. Complete clean-clone offline demonstration, optional bounded live setup, architecture/schema diagrams, SQL walkthroughs, screenshots, limitations, references/license attribution and presentation/CV wording that distinguishes implemented evidence from future features.

Acceptance: execute documented clean-checkout fixture demo with lockfiles; all suites/builds pass or failures accurately documented; no keys/private/live output tracked; tested cleanup/retention; hosted CI status verified when accessible. Monitoring storage foundations start in 3A; monitoring screens and analytics wait for this phase. Public deployment needs a separate operations/security decision.

## Data governance and verification across phases

Use UTC timestamps and nullable unknown statistics, parameterized SQL, foreign keys, bounded locks/transactions and one ETL writer. Keep credentials server-side and TLS verification enabled. No OAuth/private Analytics/scraping for the public-data workflow. No unreviewed real API exports, snapshots or indefinite retention. Public APIs do not reveal actual revenue, viewer countries, watch time or retroactive daily metrics.

Official live-use review sources:

- https://developers.google.com/youtube/terms/api-services-terms-of-service
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/v3/docs
- https://developers.google.com/youtube/v3/determine_quota_cost

Required root-level verification:

```bash
uv sync --project backend --frozen
uv run --project backend --frozen pytest backend/tests
uv run --project backend --frozen ruff check backend
uv run --project backend --frozen ruff format --check backend
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
git diff --check
```

Use the existing isolated checkout, not a worktree. Live processes must restart in future tasks. Never label unrun or blocked checks as passing. Optional example channel IDs are not prevalidated identities; no product code should hardcode Faouzia as the application scope.
