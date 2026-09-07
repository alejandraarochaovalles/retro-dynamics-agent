# Retro Dynamics Agent

[🇪🇸 Español](README.md) | 🇬🇧 English

Generates unusual, engaging retrospective dynamics, facilitates them on a real-time collaborative board (free-position canvas, Miro-style), and turns the outcomes into Jira or Azure DevOps tickets.

**Live demo**: [retro-dynamics-agent-gcdg.vercel.app](https://retro-dynamics-agent-gcdg.vercel.app) — backend at [retro-dynamics-agent.vercel.app](https://retro-dynamics-agent.vercel.app/health) / [docs](https://retro-dynamics-agent.vercel.app/docs).

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
  integrations/                  → jira_client.py, jira_oauth.py ("Connect with Jira"), oauth_state.py, azure_devops_client.py
  crypto.py                      → Fernet encryption for OAuth tokens at rest
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

`apps/web` is no longer just the shell: the `SessionSetup` screen ([src/features/session-setup](apps/web/src/features/session-setup/SessionSetup.tsx)) calls the real backend through [shared/api/client.ts](apps/web/src/shared/api/client.ts) and covers the full flow from team creation to a closed session's summary:

1. checks `/health` on mount and shows whether the backend is `online`/`offline`,
2. creates a team (`POST /teams`),
3. generates a batch of 3 dynamic proposals (`POST /dynamics/generate`) and lets the user pick one — or fetch 3 more (deduped by name) to grow the pool to 6, 9, etc. — then creates the session with the chosen dynamic attached (`POST /sessions`), showing the `join_code` — or joins an existing one by code (`POST /sessions/join`),
4. starts the session (`POST /sessions/{id}/start`) — once phase is `active`, mounts the live board (`BoardScreen`, see below),
5. once the session is `closed`, shows `SessionSummaryScreen` ([src/features/summary](apps/web/src/features/summary/SessionSummaryScreen.tsx)): the consolidated notes and votes (`GET /sessions/{id}/summary`), a "+ Action item" button per note (`POST /sessions/{id}/action-items`), and a form to connect the team's Jira/Azure DevOps project (`POST /teams/{id}/integration`) plus per-item or bulk export (`POST /sessions/{id}/export`) — export is idempotent and surfaces exactly why an item failed (no integration connected, missing credentials, etc.) instead of failing silently.

CORS on `apps/api` already accepts both `http://localhost:5173` and `http://127.0.0.1:5173` (Vite's dev server can start on either).

### Connecting Jira via OAuth 2.0 ("Connect with Jira")

Exporting to Jira used to depend on a single global token (`JIRA_API_TOKEN`), set by hand by whoever had access to the Vercel dashboard — a non-starter if other teams (or other companies) want to use the app with their own Jira account. Now any team can connect its own Jira with a real **OAuth 2.0 (3LO)** flow against Atlassian, with no env vars to touch and no code access needed:

- **"Connect with Jira" button** on `SessionSummaryScreen`: redirects to `auth.atlassian.com`, the user consents on Atlassian's own site, and comes back authenticated — the backend never sees or stores their password.
- **Signed `state`, no server-side sessions** ([integrations/oauth_state.py](apps/api/integrations/oauth_state.py)): HMAC-SHA256 + TTL, consistent with the rest of the app (serverless on Vercel, no state across invocations — see ADR-0003). The `state` also carries the retro's `session_id`: since the frontend has no persistence of its own (no localStorage, no router), that's what lets it land back on the exact same screen after the Atlassian redirect.
- **Tokens encrypted at rest** ([crypto.py](apps/api/crypto.py)): symmetric Fernet encryption over `access_token`/`refresh_token` — never stored as plain JSON in the database.
- **Refresh token rotation**: Atlassian issues a new `refresh_token` on every refresh; [jira_client.py](apps/api/integrations/jira_client.py) always persists the rotated pair, not just the new `access_token`.
- **Fallback unchanged**: if a team never connects via OAuth, `jira_client.create_issue` still uses the global `JIRA_API_TOKEN` exactly as before. The manual form ("Advanced / manual setup") stays available as a plan B, and it's still the only path for Azure DevOps (its OAuth requires registering an app in Microsoft Entra ID, out of scope for this pass).
- **Test coverage**: `test_oauth_state.py`, `test_crypto.py`, `test_jira_oauth_routes.py`, and `test_jira_client_oauth.py` cover state signing/verification, encryption, the full `/connect` → `/callback` round trip (with the Atlassian calls mocked), and both of `create_issue`'s paths (OAuth and global token).

### Live board (Liveblocks)

`features/board` covers the **desktop canvas**: free-position sticky notes, live drag (position syncs on every `pointermove`, not just on release — that's exactly what ADR-0002 uses to justify Liveblocks over Supabase Realtime), toggleable voting (ADR-0004), and other participants' live cursors.

- **Liveblocks data model** (see [types.ts](apps/web/src/features/board/types.ts)): `notes: LiveList<LiveObject<Note>>`, `votes: LiveMap<participant, LiveList<noteId>>` (each participant writes only their own entry, no write conflicts), `phaseIndex: LiveObject<{value}>` (durable). Presence (ephemeral): `{name, cursor}`.
- **Auth**: `apps/api`'s `/api/liveblocks/auth` already existed but had never been verified live — reading the `@liveblocks/node` SDK's source (no official Python SDK exists) turned up that the real Liveblocks endpoint's response is raw text (the JWT itself), not `{"token": ...}` as the original code assumed; fixed in [routes/liveblocks_auth.py](apps/api/routes/liveblocks_auth.py).
- **Typing**: every Liveblocks hook (`useStorage`, `useMutation`, etc.) is typed app-wide via declaration merging (`declare global { interface Liveblocks {...} } }` in `types.ts`), not per-call generics. `npx tsc --noEmit` passes clean against the real installed `@liveblocks/core@2.24.4` types.
- **Scope of this pass**: desktop canvas, now with basic mobile-viewport responsiveness (composer and buttons wrap and stay usable below 640px) and a clearer connection-status message (via `useStatus()`) when a corporate network/VPN blocks the Liveblocks WebSocket, instead of hanging on "Connecting…" forever. The dedicated mobile list view and lasso-based grouping (ADR-0006) are still a follow-up — see [features/board/README.md](apps/web/src/features/board/README.md) for exactly what's missing.
- **Verification**: with no real Liveblocks account on hand, this was verified by types (`tsc`) and pure logic (`votes.ts`, unit-tested) rather than live. `npm run verify:board` (two real Liveblocks connections, no browser, proving a note/vote/phase-change from one is seen by the other) is ready to run as soon as a real `LIVEBLOCKS_SECRET_KEY` is in `.env`.

### Behavior without credentials

Each external integration degrades to a clear response instead of breaking the flow:

| Missing variable | Effect |
|---|---|
| `GROQ_API_KEY` | `POST /dynamics/generate` returns 3 fixed dynamics (Sailboat, 4Ls, Mad/Sad/Glad) with `source: "fallback"` |
| `LIVEBLOCKS_SECRET_KEY` | `POST /liveblocks/auth` returns `configured: false` instead of failing |
| `JIRA_*` (team hasn't connected via OAuth) / `AZURE_DEVOPS_*` | `POST /sessions/{id}/export` marks each item `status: "failed"` with a detail of what's missing |
| `DATABASE_URL` | the backend uses a local SQLite file (`apps/api/dev.db`) instead of Postgres — see [db.py](apps/api/db.py) |

Jira is the exception: a team can avoid this dependency entirely by connecting its own account via OAuth ("Connect with Jira", see above) instead of relying on the global token.

## Project status

🚧 Under construction, but **deployed to production** (see ADR-0003): backend and frontend run on Vercel (serverless functions + static Vite build), with real Postgres on Supabase, Groq and Liveblocks configured and verified end to end. The backend (`apps/api`) exposes the contract's endpoints with real persistence in Postgres (SQLAlchemy + Alembic), and the frontend now has the full flow through to the live board and a post-session summary screen (create/join session → desktop canvas with Liveblocks → consolidated summary with Jira/Azure DevOps export). Mobile-viewport responsiveness (layout, buttons) is fixed, though the dedicated mobile canvas view from ADR-0006 is still not built. Jira export works end to end in production: any team can connect its own account via OAuth 2.0 ("Connect with Jira") without relying on any global credentials. Azure DevOps, by contrast, still depends on the manual global token (`AZURE_DEVOPS_*`), which is unset in production, so those exports currently fail with a clear "not configured" message until it gets its own OAuth flow. The full design is documented in [docs/adr](docs/adr/README.md).

## License

MIT — see [LICENSE](LICENSE).
