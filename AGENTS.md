# Repository instructions

## Mission and current boundary

Build a multi-channel YouTube intelligence portfolio application using Python/Pandas ETL, FastAPI, a premium dark React/TypeScript/Tailwind SaaS interface and SQLAlchemy/SQLite. Faouzia is an optional example, never fixed product scope. The complete product includes video exploration, channel comparison, SQL/statistical analytics, country-aware editable-RPM scenarios, evidence-based recommendations, pipeline monitoring/data quality and reproducible GitHub demonstrations. Read `docs/IMPLEMENTATION_PLAN.md` and `docs/PRE_PHASE_1_AUDIT.md` first. Phase 3A is authorized: offline Pandas validation/transformation, synthetic-only relational domain loading, idempotence/transactions, retention/deletion and pipeline records. Do not fetch or persist live YouTube data. Preserve Phase 1/2 behavior. Do not implement dashboard, analytical services, scenarios, recommendations or later phases. Make a separate Phase 3A development commit; no automatic push. Do not claim tests passed unless executed and inspected.

Use the existing checkout in the isolated cloud task. Do not create a worktree unless the user asks for one. Preserve unrelated user changes.

## Architecture

- `backend/src/youtube_insight/etl/`: collection, normalization, orchestration; no frontend or HTTP handler dependencies.
- `backend/src/youtube_insight/data/`: SQLite connections, SQL schema/versioning, repositories, persistence contracts; no FastAPI dependencies.
- `backend/src/youtube_insight/api/`: versioned request/response models and HTTP handlers; no inline SQL or collection in requests.
- `backend/src/youtube_insight/services/`: shared analysis and scenario calculations; do not duplicate formulas in React.
- `frontend/`: React/TypeScript presentation and API calls; no database access or YouTube credentials.
- Prefer one Python package with separate API and ETL entry points over independently deployed Python services.

## Quality and dependencies

Target Python 3.12 and Node 22. Use uv with committed `uv.lock`, and npm with committed `package-lock.json`. Use frozen installs in CI; pin tested runtime/package-manager versions when implementing. Do not update locks incidentally.

Start with FastAPI, Uvicorn, HTTPX, Pydantic Settings, pytest, Ruff, React, TypeScript and Vite, adding UI testing tools when UI behavior is implemented. Use SQLAlchemy 2 with the standard-library SQLite driver, as explicitly requested for Phase 1. Use Tailwind CSS for reusable dark theme tokens and Vitest/Testing Library for frontend behavior. Pandas is explicitly required for ETL; avoid additional ORM/migration frameworks, job orchestration, distributed infrastructure, and extra services unless a concrete requirement justifies them.

Tests use synthetic fixtures and temporary databases; no network or credentials by default. Test behavior, failure paths and public contracts. Record skipped/live checks separately. Add offline CI checks and keep documented commands synchronized with manifests. All timestamps are UTC; unknown data stays nullable.

## Security and data governance

Keep `YOUTUBE_API_KEY` on the server only. Never expose it through `VITE_*`, browser bundles, API responses, exception text, request URLs in logs, or committed files. Preserve TLS verification. Use environment configuration, placeholder examples, and ignored local secrets. Check presence without printing values.

No OAuth, scraping, or private Analytics assumptions for the public-data workflow. Restrict keys to the intended API and supported application restrictions; set quota alerts. Do not expose collection/refresh as a public unauthenticated route. Local CORS allows only explicitly configured frontend origins. Use parameterized SQL, input bounds and sanitized errors.

Before live collection, verify current official YouTube policies and document freshness, refresh/deletion deadlines, derived-data treatment, backups/exports, attribution, and deletion obligations. Do not retain historical API snapshots by default. Do not substitute zero for unavailable metrics. Keep real API data out of version control and synthetic fixtures clearly labeled.

## Delivery

Implement only the authorized phase. Every phase needs its specified offline checks and documentation. Do not infer actual revenue or audience geography. Review reference licenses before copying content. Public deployment requires a separate review; do not introduce production infrastructure into the local portfolio baseline.

## Phase 3A data contract

Use bundled, labeled multi-channel synthetic fixtures with synthetic IDs. The offline loader must reject live provenance and must not import/invoke the YouTube client. Keep Pandas normalization separate from SQLAlchemy persistence. Preserve nullable integer counts and aware UTC timestamps. Atomic domain upserts must never replace newer observations with older ones or reset expiry on rerun. Explicitly initialize/migrate the domain schema without changing the fresh health-only startup contract. Keep only current observations; no history snapshots.

Record each run separately, including sanitized failures after rollback. Operational records must not retain row payloads/keys. Test expiry, channel/video deletion and cascades, full purge and run-record retention. Synthetic TTLs are engineering tests, not proof of current API compliance. Run all backend/frontend tests and checks; write actual outcomes and remaining limitations in the Phase 3A report. Future live loading requires a separate policy/identity/credentials review.
