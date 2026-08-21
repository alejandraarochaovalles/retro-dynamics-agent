# 0001 — Separate frontend and backend (SPA + API)

**Status**: Accepted

## Context
The agent needs a real-time collaborative board (notes, votes, grouping) as well as generating dynamics via LLM and creating tickets in Jira/Azure DevOps. Several deployment approaches were evaluated: a server-rendered monolith, a monolith with its own websockets, a backend with real-time delegated to a third party, everything on a VPS, and a frontend SPA separate from the backend.

## Options considered
1. Monolith (server-rendered) + custom websockets on the same process. Simplest deploy, but real-time in a server-rendered app means either polling or hand-rolling a WebSocket layer — undifferentiated work compared to a managed provider.
2. Own backend + real-time delegated to a managed service (Supabase/Liveblocks), with a separate frontend SPA. Two moving parts, but each one does only what it's good at.
3. VPS with Docker Compose (full control, more operational load — patching, uptime, TLS certs — for a project with no ops budget).
4. Fully on-demand serverless, no always-on process (see ADR 0003 for why this ended up being the actual hosting shape).
5. Pure SPA + API, each deployed independently.

## Decision
Frontend as an SPA (React) and backend as a pure API, deployed separately (Option 5, combined with Option 4's serverless backend from ADR 0003). The core product experience is an interactive Miro-style board — that calls for an SPA with solid client-side state handling, not server-rendered HTML. The backend is reduced to what actually needs server-side logic: generating dynamics via Groq, consolidating results on session close, and creating tickets in Jira/Azure DevOps. Everything else — the canvas, drag/drop, live cursors, votes — is handled client-side against Liveblocks (ADR 0002), so the backend never needs to be in the hot path of a user dragging a note.

## Consequences
- Better UX for the part that matters most (live canvas) — the frontend can update at 60fps on every `pointermove` without a round-trip to `apps/api`.
- Secrets (Jira/ADO tokens, Groq API key, Liveblocks secret key) stay naturally isolated in `apps/api`'s environment and are never shipped to the browser bundle — the frontend only ever holds a short-lived Liveblocks token (see `routes/liveblocks_auth.py`).
- Adds the complexity of handling CORS and two deployments instead of one: `apps/api/main.py` explicitly whitelists the frontend's dev origins (`http://localhost:5173`, `http://127.0.0.1:5173`) via `CORSMiddleware`; a production deploy needs the real frontend origin added there too.
- Requires an explicit contract between the two: `packages/contracts/openapi.yaml`, generated from FastAPI's own `app.openapi()` (see `apps/api/scripts/generate_openapi_contract.py`) rather than hand-written, so it can't silently drift from what `apps/api` actually serves — see ADR 0005 for why this matters more here than in a single-language monolith.
- The frontend's `shared/api/client.ts` currently hand-mirrors the backend's Pydantic models rather than being codegen'd from the OpenAPI contract — a manual step that has to be kept in sync by hand until that gap is closed.
