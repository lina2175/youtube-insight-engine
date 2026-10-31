# YouTube Insight Engine

A multi-channel YouTube intelligence portfolio application built with Python/Pandas ETL, FastAPI, SQLAlchemy/SQLite and a premium dark React/TypeScript/Tailwind interface. The complete roadmap includes video exploration, channel comparison, meaningful SQL/statistical analytics, country-aware editable-RPM scenarios, evidence-based recommendations and pipeline monitoring. Faouzia is an optional example, not fixed application scope.

**Phase 3A:** the offline ETL and relational storage foundation is implemented using explicitly fictional multi-channel fixtures only. Phase 1's web shell/health checks and Phase 2's opt-in extraction client remain intact. No live data is fetched or loaded in Phase 3A. Dashboard/analytics/revenue/recommendation features remain future work. See the [complete plan](docs/IMPLEMENTATION_PLAN.md), [offline ETL guide](docs/OFFLINE_ETL.md), [Phase 3A verification](docs/PHASE_3A_VERIFICATION.md), [audit](docs/PRE_PHASE_1_AUDIT.md), and earlier [Phase 1](docs/PHASE_1_VERIFICATION.md)/[Phase 2](docs/PHASE_2_VERIFICATION.md) evidence.

## Requirements and installation

Use Python 3.12, uv 0.12.23, Node 22 (22.12 or newer within major 22), and npm 10.9.4. `.python-version`, `.nvmrc`, and package manifests describe the toolchain; `backend/uv.lock` and `frontend/package-lock.json` lock dependencies. Install uv using its official instructions. With nvm available, run `nvm install` and `nvm use` from the repository root, then `npm install --global npm@10.9.4`.

From the repository root:

```bash
uv sync --project backend --frozen
npm --prefix frontend ci
```

Optional configuration (do not overwrite an existing local file):

```bash
cp -n .env.example .env
cp -n frontend/.env.example frontend/.env
```

Defaults work without either file or any credentials. The backend reads the root `.env` regardless of launch directory. Precedence is explicit constructor settings (tests), process environment, root `.env`, then defaults. Relative `DATABASE_PATH` resolves against the repository root. Its default is `.local/youtube-insight.sqlite3`; the parent directory and database initialize on backend startup. Fresh foundation initialization sets `PRAGMA user_version=1` and creates no domain tables. The explicit offline ETL initializer upgrades its selected database to v2 with domain tables; the health app also accepts v2. Unknown schema versions fail startup rather than being silently migrated.

`CORS_ORIGINS` is a JSON list of exact frontend origins, default `["http://127.0.0.1:5173"]`. If using `localhost` instead of `127.0.0.1`, configure the matching origin explicitly. Backend bind/port are Uvicorn command-line options.

The frontend reads only its own Vite environment file. `VITE_API_BASE_URL` is a **public, non-secret** backend base URL, default `http://127.0.0.1:8000`. Restart Vite after configuration changes; rebuild for production changes. Never place credentials in any `VITE_*` variable. The `YOUTUBE_API_KEY` and `YOUTUBE_CHANNEL_ID` placeholders are backend-only. They are unnecessary for app startup and all automated checks; only explicitly invoked live extraction needs a key. Actual `.env` files and databases are ignored by Git.

## Start locally

Run in two terminals, both from the repository root:

```bash
uv run --project backend --frozen python -m uvicorn youtube_insight.api.main:app --host 127.0.0.1 --port 8000
```

```bash
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

The shell checks `GET /health` immediately, every 10 seconds, and when “Check connection” is clicked. It shows checking, connected only after a valid `{"status":"ok"}` response, or unavailable after a network error, non-success response, invalid body, or four-second timeout. Backend health includes a database connectivity check. Stop the backend and wait for the next check to see the unavailable state; restart and check again to recover. “Connected” refers to this local backend, not YouTube. Use Ctrl+C to stop each service.

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/health
```

Expected HTTP 200 body: `{"status":"ok"}`. Database failures return a sanitized HTTP 503. No secret or database path is returned. The development server is local-only; no public deployment is configured.

## Checks from the repository root

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

Pytest uses temporary SQLite databases and synthetic transaction records. Vitest/Testing Library exercises real React rendering with controlled HTTP responses, including polling, failure, recovery, and timeout. Neither suite contacts YouTube or requires secrets. CI runs the same required test/lint/type/build checks in separate backend/frontend jobs. Installing dependencies requires registry access; running installed tests does not. The verification report distinguishes automated component checks from a browser check against real local services.

## Architecture

- `backend/src/youtube_insight/config.py`: validated server configuration; secrets use redacted types.
- `backend/src/youtube_insight/api/`: FastAPI health route and application lifecycle. Future domain routes use `/api/v1`; operational health is `/health`.
- `backend/src/youtube_insight/data/`: SQLAlchemy engine, declarative base, session factory, SQLite pragmas and version initialization. Explicit v2 domain models store synthetic channels, videos and pipeline runs; see the offline ETL guide. Connections use a five-second lock timeout and enforce foreign keys.
- `frontend/src/`: React shell, reusable panel/status components, health request adapter, and Tailwind theme tokens for surfaces, typography, borders, focus and status colors. No external fonts, images or UI framework are needed.
- `backend/src/youtube_insight/etl/`: public YouTube client, normalized metadata models, and opt-in CLI. The live extraction client still does not write SQLite. A separate synthetic-only Pandas pipeline now validates/transforms/loads fictional fixtures. Live loading and analytical features remain deferred.

The browser asks FastAPI whether it is healthy. FastAPI checks SQLite through the shared data layer. The browser never opens the database or receives server secrets. SQLAlchemy is included at the user's request; no migration platform or additional database service is needed for this foundation.

## Offline multi-channel ETL demo (Phase 3A)

```bash
uv run --project backend --frozen youtube-offline-demo \
  --database .local/phase3a-demo.sqlite3
```

Run twice on a fresh path: both runs report 2 fictional channels and 3 videos, with 1 then 2 execution records. The data path is ignored by Git. No key or network is used. Same-day fixtures are stable; tests use fixed clocks. The [offline ETL guide](docs/OFFLINE_ETL.md) explains validation, Pandas nullable types, migration, idempotent transactions, quality records and retention/deletion. Synthetic TTLs do not certify live API compliance.

## Public YouTube extraction

See [endpoint, pagination, retry and security documentation](docs/YOUTUBE_EXTRACTION.md) and the [Phase 2 verification report](docs/PHASE_2_VERIFICATION.md).

```bash
uv run --project backend --frozen youtube-sample --help
```

After configuring `YOUTUBE_API_KEY` securely on the server, reviewing current policies and verifying the intended channel, a deliberate live sample is:

```bash
uv run --project backend --frozen youtube-sample \
  --channel-id UCLwbyg15zJgjtNL0EErkOPA --max-videos 5 --live
```

The CLI retrieves a channel's uploads playlist, traverses bounded pages, and fetches metadata in batches of at most 50 video IDs. It prints normalized JSON with UTC collection timestamps and unavailable-ID coverage, with sanitized JSON logs on stderr. It never loads SQLite. Missing counts remain unknown. `--live` is required; no live sample has been verified. Do not retain/commit API output before policy-compliant retention/deletion handling is reviewed.

## Public-data limitations and later policy gates

Public data cannot reveal another creator's actual revenue, viewer countries, private Analytics, watch time, or retroactive daily growth. Hidden metrics are unknown, not zero. Any future revenue output must be labeled as a scenario using explicit viewer-country and effective RPM assumptions, never a creator's actual earnings. Artist nationality is not audience geography.

Before live collection, verify each selected channel, inspect current YouTube terms and the reference project's license, and implement reviewed freshness/retention/deletion rules. No historical snapshots or live exports are included. Keep real API data, secrets and databases out of Git. Do not claim policy compliance until reviewed.

## Learning references and provenance

- [DataExpert-io handbook](https://github.com/DataExpert-io/data-engineer-handbook): the user followed the four-week summer camp.
- [Reference YouTube project](https://github.com/Proggleb/youtube_data_engineering_project): inspiration; external content/license review remains a gate before reuse.
- [Proposed Faouzia channel](https://www.youtube.com/channel/UCLwbyg15zJgjtNL0EErkOPA): identity verification deferred to the live-data phase.

No reference-project code was copied for Phase 1. Attribute future adaptations according to their license. This repository's MIT license does not automatically relicense third-party content or YouTube data.
