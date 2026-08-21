# 0003 — Hosting without a credit card

**Status**: Accepted (design decision) — not yet deployed; see note at the bottom.

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

**Current status**: this ADR records the intended hosting shape; the repository doesn't yet contain a `vercel.json` or a serverless entrypoint for `apps/api` — today it runs as a standard ASGI app (`uvicorn main:app`) for local development only. Turning this into an actual deployment is the next infrastructure step, not yet done.
