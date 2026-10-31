# Pre–Phase 1 audit

Date: 2026-10-31

## Scope and evidence

Reviewed the local checkout of `lina2175/youtube-insight-engine`, commit `11504ff240f85d8de753adae475b4371b2763fc7`. Before this change, `git ls-tree -r --name-only HEAD` listed only `LICENSE`; the working tree was clean. `docs/IMPLEMENTATION_PLAN.md`, `AGENTS.md`, and `README.md` did not exist. Therefore this is an audit of missing planning controls, not a line-by-line review of supplied documents. No existing architectural contradictions, insecure implementation, or unnecessary installed dependencies can be established.

A read-only `git ls-remote origin HEAD refs/heads/main` failed because the configured proxy could not be reached. The course, reference project, channel identity, and current YouTube policies could not be inspected online. Recommendations below are a proposed baseline grounded in the user's stated requirements, not claims that the external project uses this architecture or that policy compliance has been certified.

Mission: build an understandable, reproducible portfolio project analyzing Faouzia's public YouTube channel data; explain it to the project sponsor and demonstrate data engineering skills on GitHub, LinkedIn, and a CV. Preserve Python ETL, FastAPI, React, and SQLite. Do not implement features in this change.

## Findings

### A01 — High: No scope or delivery contract
- Evidence: `README.md` and `docs/IMPLEMENTATION_PLAN.md` were absent; only `LICENSE` was tracked.
- Why it matters: There is no written boundary between a manageable portfolio application and a production analytics platform, nor an agreed Phase 1 deliverable.
- Recommended correction: Document public channel/video analysis, single-channel local deployment, explicit exclusions, phased deliverables, and executable acceptance checks.
- Planning resolution: Added README scope and implementation phases. This baseline remains subject to user review before implementation.

### A02 — High: No architecture or ownership boundaries
- Evidence: All three requested planning files were absent; no package layout or interface contract existed.
- Why it matters: API handlers, collection, SQL, and presentation can become tightly coupled; independent frontend/backend work can drift.
- Recommended correction: Keep ETL and API as separate entry points in one Python package; shared models/repositories own SQLite access. React consumes versioned FastAPI JSON. Run collection explicitly, outside HTTP requests.
- Planning resolution: Defined layout, dependency direction, database ownership, and integration rules in the implementation plan and AGENTS.

### A03 — High: No API credential or operational security rules
- Evidence: No `AGENTS.md`, configuration documentation, or server-side key contract existed.
- Why it matters: A browser key, committed `.env`, logged URL, or open refresh endpoint can expose credentials and consume quota.
- Recommended correction: Server-only `YOUTUBE_API_KEY`, ignored local configuration, sanitized logs, restricted key usage, parameterized SQL, explicit local origins, and no public collection endpoint. No OAuth needed for public data.
- Planning resolution: Documented these rules and future security acceptance checks. They are not yet implemented or tested.

### A04 — High: No freshness, retention, or deletion design
- Evidence: No collection/storage plan or policy register existed.
- Why it matters: Indefinite snapshots, backups, derived values, or exports can retain stale or deleted API data. Historical growth charts are not automatically permissible merely because metrics are public.
- Recommended correction: Verify current official policies before live collection; record policy decisions, source timestamps, refresh eligibility, deletion deadlines, and purge behavior covering caches, derived data, exports, and backups. Treat 30 days as a provisional maximum for stored API data pending policy review, with any stricter rule prevailing. No persistent historical snapshots by default.
- Planning resolution: Added a live-data gate and retention/deletion acceptance tests to Phase 2. Compliance remains unverified until the official rules and implementation are reviewed.

### A05 — High: Public-data and identity assumptions undefined
- Evidence: No data inventory or channel-verification procedure existed.
- Why it matters: Public APIs do not expose another creator's private Analytics, demographics, watch time, actual revenue, or retroactive daily growth. Hidden counts and unavailable videos must not be represented as zero.
- Recommended correction: Verify the supplied channel ID belongs to the intended artist; document nullable fields, visible-video coverage, collection time, and API limitations. Do not scrape missing private metrics.
- Planning resolution: README limitations and Phase 2 identity/coverage checks added.

### A06 — High: Revenue estimation has no defensible contract
- Evidence: No revenue assumptions, formula, or required labels were documented.
- Why it matters: Artist residence and audience geography differ; lifetime public views cannot support a claim about actual monthly earnings. Music rights, monetization, and Shorts materially affect interpretation.
- Recommended correction: A user-supplied scenario uses viewer-country weights and explicit low/base/high effective creator RPM assumptions. Formula: scenario views / 1,000 × weighted RPM. Weights total 100%; views have a clearly labeled scope. Never call it actual earnings or infer geography from nationality.
- Planning resolution: Added a separate scenario phase with formula tests, disclosures, and exclusions.

### A07 — Medium: No testable phase gates
- Evidence: No implementation plan, test commands, or acceptance criteria existed.
- Why it matters: “Working dashboard” does not establish deterministic behavior, contract compatibility, quota handling, or reproducibility.
- Recommended correction: Define offline foundation checks first, then ETL fixtures and deletion tests, API integration tests, and UI checks. Keep live checks optional and credential-gated.
- Planning resolution: Each phase now has concrete outcomes; future verification commands are explicitly labeled unexecuted.

### A08 — Medium: No dependency or code quality policy
- Evidence: No manifests, lockfiles, version pins, or agent guidance existed.
- Why it matters: Unbounded dependencies and inconsistent runtimes undermine reproducibility; unnecessary infrastructure increases integration work.
- Recommended correction: Python 3.12 with uv and a committed lock; Node 22 with npm lock and `npm ci`. Use standard-library SQLite, FastAPI, HTTPX, Pydantic Settings, pytest, Ruff, React/TypeScript/Vite; justify additions. Use a small SQL schema-version mechanism rather than an ORM/migration platform initially.
- Planning resolution: Defined intended toolchain and excluded speculative infrastructure. There are currently no dependencies to remove; pins and lockfiles are Phase 1 deliverables.

### A09 — Medium: GitHub reproduction and portfolio integrity undocumented
- Evidence: No README, sample configuration, contributor instructions, or provenance notes existed.
- Why it matters: Reviewers cannot reproduce results, distinguish synthetic data from live output, or assess original work versus course material.
- Recommended correction: Document clean-checkout commands, fixtures, configuration, limitations, attribution and license review. Exclude keys, databases, logs, and API exports from Git. Avoid claiming verified behavior until checks run.
- Planning resolution: Added documentation requirements and a reproduction gate. External reference license/content review remains outstanding because access failed.

### A10 — Medium: Integration and operating limits unspecified
- Evidence: No database lifecycle, failure handling, API contract, or deployment plan existed.
- Why it matters: Concurrent writes, partial imports, timestamp ambiguity, unbounded listings, and divergent revenue calculations cause later integration failures.
- Recommended correction: Single ETL writer, transactions and idempotent upserts, UTC timestamps, bounded pagination, versioned API and one backend calculation source. Local single-user operation only; public hosting needs a separate security review.
- Planning resolution: Recorded these contracts and acceptance checks. No production infrastructure is required for Phase 1.

## Contradictions and overengineering assessment

No existing plans were available to contradict one another. The new baseline resolves likely tensions explicitly: public data versus private analytics; retention versus historical charts; current totals versus period earnings; local SQLite versus multi-writer deployment. Do not introduce Airflow, Spark, Kafka, Redis, PostgreSQL, Docker orchestration, OAuth, scraping, or an ORM without a demonstrated requirement. The linked reference project's tooling has not been inspected, so these exclusions do not describe its contents.

## Validation and remaining gates

Executed: local file inventory, Git tree/history/status inspection, and read-only remote access attempt. No application tests, installs, builds, or API calls were run. Documentation changes do not establish implementation readiness or policy compliance.

Before live collection: inspect the linked reference project and its license, verify Faouzia's channel identity, review current official policies, and resolve any mismatch with this baseline. Before Phase 1: user gives the next implementation instruction. See `docs/IMPLEMENTATION_PLAN.md` for the exact proposed Phase 1 scope and verification commands.
