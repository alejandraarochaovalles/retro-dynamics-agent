# 0003 — Hosting without a credit card

**Status**: Accepted and deployed.

- Backend: https://retro-dynamics-agent.vercel.app (`/health`, `/docs`)
- Frontend: https://retro-dynamics-agent-gcdg.vercel.app

## Context
The project is deployed for personal use/portfolio, with zero budget and without wanting to hand over a credit card to providers that ask for one even for their free tier (risk of a charge from a misconfiguration).

## Options considered
- **Fly.io**: good free tier, but asks for a card at signup.
- **Render**: real card-free free tier, but the whole app "sleeps" after inactivity (~30-50s cold start on the first request of the day) — bad first impression for a recruiter clicking a link cold.
- **Koyeb / PythonAnywhere**: card-free alternatives; PythonAnywhere restricts outbound calls to a domain whitelist, a risk for calling Groq/Jira/ADO from the backend.
- **Vercel / Netlify Functions**: no card required, backend as serverless functions instead of an always-on server.

## Decision
Backend as serverless functions on Vercel (or Netlify), not an always-on server. This fits naturally with the rest of the design: the backend only needs to respond at specific moments (generate a dynamic, sync on session close, create tickets), never keep an open connection — real-time is already handled by Liveblocks on the client side (ADR 0002). Cold start becomes per individual function (1-3s) instead of the whole app (30-50s).

## Consequences
- Zero cost, no credit card on any provider in the chain (Vercel, Liveblocks free tier, Supabase/Postgres free tier, Groq free tier).
- Execution time limit per function (10s on Vercel's Hobby plan) — enough for current use cases (a single Groq call for dynamic generation, a handful of DB writes on close), to be watched if dynamic generation grows in complexity or starts chaining multiple LLM calls.
- FastAPI's request/response model maps onto a serverless function per invocation reasonably cleanly, but it does mean no in-process state between requests — `config.py`'s `Settings` (env vars, loaded once at cold start) and each request's own DB session are the only state that exists per invocation; nothing can be cached in memory across calls the way an always-on process could.
- SQLite (the local dev fallback when `DATABASE_URL` is unset) is inappropriate for this target: serverless functions don't share a writable filesystem across invocations, so production always needs the real Postgres URL configured — local-only convenience, not a deployment option.
- Supabase's *direct* connection (port 5432, `db.<project>.supabase.co`) only resolves over IPv6, which made it unusable both from the local machine used to run migrations (no IPv6 route) and would have been equally unusable from Vercel's functions. Two different connection strings ended up needed: the **session pooler** (port 5432, `...pooler.supabase.com`, IPv4) for one-off local work like `alembic upgrade head`, and the **transaction pooler** (port 6543, same host) for `DATABASE_URL` in production. `db.py` detects the `:6543` port and switches to `NullPool` + `prepare_threshold=None`, since PgBouncer's transaction mode doesn't guarantee the same physical connection across queries, which breaks psycopg's default server-side prepared statements.

## Deployment shape

Two separate Vercel projects from the same repo, each with its own **Root Directory**:

- `apps/api` — `@vercel/python` builder via `vercel.json`, dependencies pinned in `requirements.txt` (Vercel's Python builder reads this, not `pyproject.toml`). Env vars: `DATABASE_URL` (transaction pooler, port 6543), `GROQ_API_KEY`, `LIVEBLOCKS_SECRET_KEY`, `FRONTEND_ORIGIN` (the frontend project's URL, so `main.py`'s CORS middleware allows it), and optionally `JIRA_*` / `AZURE_DEVOPS_*`.
- `apps/web` — Vite preset (auto-detected). Env var: `VITE_API_URL` pointing at the backend project's URL — baked into the build at compile time, not read at runtime.

Verified end to end post-deploy: `/health`, a real `POST /api/dynamics/generate` call (confirms `GROQ_API_KEY`), a real `POST /api/teams` write (confirms `DATABASE_URL`/Supabase), and a CORS preflight + real `POST` from the frontend's actual origin (confirms `FRONTEND_ORIGIN`) all succeeded against the live URLs above.
