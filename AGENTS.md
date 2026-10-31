# Repository instructions

## Mission and current boundary

Build the portfolio project described in README using Python ETL, FastAPI, React, and SQLite. Read `docs/IMPLEMENTATION_PLAN.md` and `docs/PRE_PHASE_1_AUDIT.md` first. Phase 2 is authorized for a reusable, mocked-tested public YouTube extraction client and CLI only. Do not implement database loading, analytics, or further phases. Keep live calls opt-in; document policy-review blockers. Do not claim tests passed unless executed and inspected.

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

Start with FastAPI, Uvicorn, HTTPX, Pydantic Settings, pytest, Ruff, React, TypeScript and Vite, adding UI testing tools when UI behavior is implemented. Use SQLAlchemy 2 with the standard-library SQLite driver, as explicitly requested for Phase 1. Use Tailwind CSS for reusable dark theme tokens and Vitest/Testing Library for frontend behavior. Avoid pandas, additional ORM/migration frameworks, job orchestration, distributed infrastructure, and extra services unless a concrete requirement justifies them.

Tests use synthetic fixtures and temporary databases; no network or credentials by default. Test behavior, failure paths and public contracts. Record skipped/live checks separately. Add offline CI checks and keep documented commands synchronized with manifests. All timestamps are UTC; unknown data stays nullable.

## Security and data governance

Keep `YOUTUBE_API_KEY` on the server only. Never expose it through `VITE_*`, browser bundles, API responses, exception text, request URLs in logs, or committed files. Preserve TLS verification. Use environment configuration, placeholder examples, and ignored local secrets. Check presence without printing values.

No OAuth, scraping, or private Analytics assumptions for the public-data workflow. Restrict keys to the intended API and supported application restrictions; set quota alerts. Do not expose collection/refresh as a public unauthenticated route. Local CORS allows only explicitly configured frontend origins. Use parameterized SQL, input bounds and sanitized errors.

Before live collection, verify current official YouTube policies and document freshness, refresh/deletion deadlines, derived-data treatment, backups/exports, attribution, and deletion obligations. Do not retain historical API snapshots by default. Do not substitute zero for unavailable metrics. Keep real API data out of version control and synthetic fixtures clearly labeled.

## Delivery

Implement only the authorized phase. Every phase needs its specified offline checks and documentation. Do not infer actual revenue or audience geography. Review reference licenses before copying content. Public deployment requires a separate review; do not introduce production infrastructure into the local portfolio baseline.
