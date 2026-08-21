# 0005 — Python backend, monorepo with separate apps

**Status**: Accepted · related: [0001](0001-separate-frontend-backend.md)

## Context
With frontend and backend as separate services (see ADR 0001), the backend language choice remained open: TypeScript (sharing types with the frontend within a single Next.js) or Python (the same ecosystem used in other agent/LLM projects in the portfolio). Monorepo vs. polyrepo also had to be decided.

## Options considered
- **Unified Next.js monorepo**: all TypeScript, shared types for free, a single deploy — but backend in TS, and generating dynamics / calling Groq would mean rewriting patterns already established in Python elsewhere in the portfolio.
- **Monorepo with separate apps** (`apps/web` in TS, `apps/api` in Python): two languages, requires an explicit API contract (OpenAPI) to avoid losing shared typing across the language boundary.
- **Polyrepo**: two independent repositories — more decoupling, but fragments the commit history and the project's visibility as a portfolio piece; a reviewer would need two links and two mental models instead of one.

## Decision
Monorepo with separate apps: `apps/web` (React) and `apps/api` (Python/FastAPI), with the shared contract in `packages/contracts`. Priority is given to keeping Python on the backend for consistency with the rest of the portfolio (multi-agent systems in Python), and monorepo over polyrepo because the repo is public for a résumé — one link, one commit history, all the work visible at once.

## Consequences
- Two languages coexisting — the API contract in `packages/contracts/openapi.yaml` is the source of truth to keep frontend and backend from drifting apart. It's generated, not hand-written: `apps/api/scripts/generate_openapi_contract.py` pulls the schema straight from FastAPI's own `app.openapi()`, so a changed field in `models.py` makes the contract visibly outdated rather than silently wrong.
- A single repository makes it easier to show the whole project to whoever is evaluating it (recruiters, other engineers) — one `git clone`, both halves of the stack, the ADRs and the code side by side.
- CI (`.github/workflows/ci.yml`) reflects the two-language split directly: a `web` job (`npm run lint` + `npm run test`) and a separate `api` job that spins up a real `postgres:16` service container rather than mocking the database, matching `tests/conftest.py`'s expectation of a real Postgres to run against.
- Alembic (`apps/api/alembic/`) is the schema source of truth for the Python side — migrations are generated from `db_models.py` via `alembic revision --autogenerate`, applied with `alembic upgrade head`, and are the only sanctioned way to change the schema (no hand-edited SQL).
