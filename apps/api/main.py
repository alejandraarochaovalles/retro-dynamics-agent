# FastAPI entrypoint. Run locally with:
#   uvicorn main:app --reload
# Interactive docs at http://127.0.0.1:8000/docs once running.
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes import (
    action_items,
    consolidation,
    dynamics,
    export,
    jira_oauth,
    liveblocks_auth,
    sessions,
    teams,
)

app = FastAPI(
    title="Retro Dynamics Agent API",
    version="0.1.0",
    description="See packages/contracts/openapi.yaml for the frontend/backend contract.",
)

# Local Vite dev server (either loopback form) is always allowed; a deployed
# frontend's origin is added on top via FRONTEND_ORIGIN (see config.py) once
# a deploy target is chosen (ADR-0003) — e.g. FRONTEND_ORIGIN=
# https://retro-dynamics-agent.vercel.app, comma-separated for more than one.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *settings.frontend_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (teams, dynamics, sessions, liveblocks_auth, consolidation, action_items, export, jira_oauth):
    app.include_router(router.router, prefix="/api")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
