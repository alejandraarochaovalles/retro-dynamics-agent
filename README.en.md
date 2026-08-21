# Retro Dynamics Agent

[🇪🇸 Español](README.md) | 🇬🇧 English

Generates unusual, engaging retrospective dynamics, facilitates them on a real-time collaborative board (free-position canvas, Miro-style), and turns the outcomes into Jira or Azure DevOps tickets.

## Why it exists

Retros tend to repeat the same format (Start/Stop/Continue) until they stop producing new insights. This agent suggests different dynamics based on the sprint's context (incidents, a quiet sprint, a new team, etc.), facilitates the live session regardless of where the team is — same room or not — and closes the loop by creating the resulting action items directly in the backlog.

## Architecture

```
apps/web/                     → frontend (real-time board, free-position canvas)
  src/shared/api/client.ts       → HTTP client to apps/api (types mirror models.py)
  src/shared/components/organisms/ → StickyNote (canvas variant), see its README
  src/features/session-setup/    → real screen: create team, create/join session
  src/features/board/            → live board — desktop canvas (see its README)
  scripts/verify-board-sync.mjs  → two-client, no-browser real-time sync proof
apps/api/                      → Python backend (FastAPI)
  main.py                        → entrypoint, mounts the routers under /api
  config.py                      → environment variables (all optional)
  db.py                          → SQLAlchemy engine/session (Postgres, or SQLite if DATABASE_URL is unset)
  db_models.py                   → ORM tables: Team, RetroSession, ActionItem
  alembic/                       → migrations (source of truth for the schema)
  models.py                      → pydantic schemas for the contract
  routes/                        → one endpoint (or group) per file, see table below
  agents/                        → dynamic_generator.py, consolidator.py
  integrations/                  → jira_client.py, azure_devops_client.py
  tests/                         → pytest + FastAPI TestClient tests, against real Postgres
packages/contracts/            → shared API contract (OpenAPI)
docs/adr/                       → documented architecture decisions
```

See [docs/adr](docs/adr/README.md) for the reasoning behind each decision.

## Stack

- **Frontend**: React + Liveblocks (realtime, free-position canvas) — deployed on Vercel
- **Backend**: Python, serverless functions (LLM-based dynamic generation, consolidation, integrations)
- **Database**: Postgres (Supabase)
- **Integrations**: Jira Cloud and Azure DevOps

## Running it

```bash
# Local Postgres (one-time) — or use your own Supabase/Postgres and skip this
brew install postgresql@16 && brew services start postgresql@16
createuser -s user 2>/dev/null; psql postgres -c "ALTER ROLE \"user\" WITH PASSWORD 'password'"
createdb -O user retro_dynamics        # matches .env.example
createdb -O user retro_dynamics_test   # pytest only, see tests/conftest.py

# Backend (apps/api)
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../../.env.example ../../.env   # optional: without GROQ/LIVEBLOCKS/JIRA/ADO, each integration falls back to "not configured"
alembic upgrade head                # creates the schema in Postgres
uvicorn main:app --reload          # http://127.0.0.1:8000/docs

# Frontend (apps/web), in another terminal
cd apps/web
npm install
cp .env.example .env                # optional: only needed if the backend isn't on 127.0.0.1:8000
npm run dev                        # http://127.0.0.1:5173
```

For the live board with real sync (not just type-verified): create a free project at [liveblocks.io](https://liveblocks.io), copy the **secret key** into `LIVEBLOCKS_SECRET_KEY` in the repo root's `.env`, restart `uvicorn`, and run `npm run verify:board` from `apps/web` for the two-client proof.

```bash
# Backend tests
cd apps/api && source .venv/bin/activate && pytest

# Frontend lint + tests
cd apps/web && npm run lint && npm run test -- --run
```

### Persistence

State no longer lives in memory: `apps/api` uses SQLAlchemy + Alembic on top of Postgres.

- **Schema**: 3 tables — `teams`, `sessions`, `action_items` (FK `sessions.team_id → teams.id`, `action_items.session_id → sessions.id`). `notes`/`groups` stay as JSON columns on `sessions` rather than their own tables: `agents/consolidator.py` produces them wholesale when a session closes and they're read back the same way, not queried note-by-note — see the comment in [db_models.py](apps/api/db_models.py).
- **Migrations**: `alembic upgrade head` applies the schema; `alembic revision --autogenerate -m "..."` generates a new one after changing `db_models.py`. `alembic/env.py` reads the URL from `DATABASE_URL`, not from `alembic.ini` (unused placeholder).
- **No `DATABASE_URL`**: falls back to a local SQLite file (`apps/api/dev.db`, gitignored) so the backend still boots with zero config — same as every other integration.
- **Tests**: run against a real, separate Postgres database (`retro_dynamics_test` by default, override with `TEST_DATABASE_URL`), not SQLite or mocks — see [tests/conftest.py](apps/api/tests/conftest.py). CI spins up a Postgres container for the `api` job (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).

### Formalized OpenAPI contract

`packages/contracts/openapi.yaml` is no longer just the list of paths — `components.schemas` now has all 28 real schemas, generated from `apps/api/models.py` (via FastAPI's own `app.openapi()`), not hand-written. That means the contract can't silently drift from the code: change a field in `models.py` and the old contract becomes visibly stale, not invisibly wrong.

To regenerate after changing `models.py` or an endpoint's signature (never edit the schemas here by hand):

```bash
cd apps/api && source .venv/bin/activate
python scripts/generate_openapi_contract.py   # needs no server or DB running
```

The script pulls the schema straight from `app.openapi()`, strips the `/api` prefix off each path (the contract keeps `servers: [{url: /api}]` + relative paths), keeps each `operationId`'s human `summary` (defined in the script itself), and strips the cosmetic `title` FastAPI stamps on every schema node — carefully, so it doesn't touch models that have a real *field* named `title` (`ActionItem.title`, `SessionOut.title`, etc.), which the first version of this script nearly deleted.

Note: bumped the file from `openapi: 3.0.3` to `3.1.0` because that's what FastAPI + Pydantic v2 emit natively (nullable via `anyOf`/`type: null`, not `nullable: true`) — forcing 3.0.3 would have meant hand-rewriting that semantics.

### Implemented endpoints

All 19 operations (18 paths) in the contract ([packages/contracts/openapi.yaml](packages/contracts/openapi.yaml)) are implemented on top of Postgres:

| Resource | Endpoints |
|---|---|
| Teams ([routes/teams.py](apps/api/routes/teams.py)) | `POST /teams`, `POST /teams/{id}/integration`, `GET /teams/{id}/sessions` |
| Dynamics ([routes/dynamics.py](apps/api/routes/dynamics.py)) | `POST /dynamics/generate` |
| Sessions ([routes/sessions.py](apps/api/routes/sessions.py)) | `POST /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/start`, `POST /sessions/{id}/phase`, `POST /sessions/join`, `POST /sessions/{id}/close`, `GET /sessions/{id}/summary` |
| Liveblocks ([routes/liveblocks_auth.py](apps/api/routes/liveblocks_auth.py)) | `POST /liveblocks/auth` |
| Consolidation ([routes/consolidation.py](apps/api/routes/consolidation.py)) | `GET /sessions/{id}/groups`, `PATCH /sessions/{id}/groups/{group_id}`, `GET /sessions/{id}/votes-summary` |
| Action items ([routes/action_items.py](apps/api/routes/action_items.py)) | `POST /sessions/{id}/action-items`, `PATCH .../{item_id}`, `DELETE .../{item_id}` |
| Export ([routes/export.py](apps/api/routes/export.py)) | `POST /sessions/{id}/export` |

All under the `/api` prefix (plus `GET /health` with no prefix). Interactive docs at `/docs` once the server is running.

### Frontend wired to the backend

`apps/web` is no longer just the shell: the `SessionSetup` screen ([src/features/session-setup](apps/web/src/features/session-setup/SessionSetup.tsx)) calls the real backend through [shared/api/client.ts](apps/web/src/shared/api/client.ts) and covers the full flow up to the lobby:

1. checks `/health` on mount and shows whether the backend is `online`/`offline`,
2. creates a team (`POST /teams`),
3. creates a session: generates a dynamic (`POST /dynamics/generate`, takes the first proposal) and creates the session with it attached (`POST /sessions`), showing the `join_code` — or joins an existing one by code (`POST /sessions/join`),
4. starts the session (`POST /sessions/{id}/start`) — once phase is `active`, mounts the live board (`BoardScreen`, see below).

CORS on `apps/api` already accepts both `http://localhost:5173` and `http://127.0.0.1:5173` (Vite's dev server can start on either).

### Live board (Liveblocks)

`features/board` covers the **desktop canvas**: free-position sticky notes, live drag (position syncs on every `pointermove`, not just on release — that's exactly what ADR-0002 uses to justify Liveblocks over Supabase Realtime), toggleable voting (ADR-0004), and other participants' live cursors.

- **Liveblocks data model** (see [types.ts](apps/web/src/features/board/types.ts)): `notes: LiveList<LiveObject<Note>>`, `votes: LiveMap<participant, LiveList<noteId>>` (each participant writes only their own entry, no write conflicts), `phaseIndex: LiveObject<{value}>` (durable). Presence (ephemeral): `{name, cursor}`.
- **Auth**: `apps/api`'s `/api/liveblocks/auth` already existed but had never been verified live — reading the `@liveblocks/node` SDK's source (no official Python SDK exists) turned up that the real Liveblocks endpoint's response is raw text (the JWT itself), not `{"token": ...}` as the original code assumed; fixed in [routes/liveblocks_auth.py](apps/api/routes/liveblocks_auth.py).
- **Typing**: every Liveblocks hook (`useStorage`, `useMutation`, etc.) is typed app-wide via declaration merging (`declare global { interface Liveblocks {...} } }` in `types.ts`), not per-call generics. `npx tsc --noEmit` passes clean against the real installed `@liveblocks/core@2.24.4` types.
- **Scope of this pass**: desktop canvas only. Mobile list view and lasso-based grouping (ADR-0006) are a follow-up — see [features/board/README.md](apps/web/src/features/board/README.md) for exactly what's missing.
- **Verification**: with no real Liveblocks account on hand, this was verified by types (`tsc`) and pure logic (`votes.ts`, unit-tested) rather than live. `npm run verify:board` (two real Liveblocks connections, no browser, proving a note/vote/phase-change from one is seen by the other) is ready to run as soon as a real `LIVEBLOCKS_SECRET_KEY` is in `.env`.

### Behavior without credentials

Each external integration degrades to a clear response instead of breaking the flow:

| Missing variable | Effect |
|---|---|
| `GROQ_API_KEY` | `POST /dynamics/generate` returns 3 fixed dynamics (Sailboat, 4Ls, Mad/Sad/Glad) with `source: "fallback"` |
| `LIVEBLOCKS_SECRET_KEY` | `POST /liveblocks/auth` returns `configured: false` instead of failing |
| `JIRA_*` / `AZURE_DEVOPS_*` | `POST /sessions/{id}/export` marks each item `status: "failed"` with a detail of what's missing |
| `DATABASE_URL` | the backend uses a local SQLite file (`apps/api/dev.db`) instead of Postgres — see [db.py](apps/api/db.py) |

## Project status

🚧 Under construction — the backend (`apps/api`) exposes the contract's endpoints with real persistence in Postgres (SQLAlchemy + Alembic), and the frontend now has the full flow through to the live board (create/join session → desktop canvas with Liveblocks). Still missing: the mobile view, grouping/consolidation after closing a session, and external integration credentials (Liveblocks, Groq, Jira/ADO). The full design is documented in [docs/adr](docs/adr/README.md).

## License

MIT — see [LICENSE](LICENSE).
