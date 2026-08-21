# FastAPI entrypoint. Run locally with:
#   uvicorn main:app --reload
# Interactive docs at http://127.0.0.1:8000/docs once running.
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import (
    action_items,
    consolidation,
    dynamics,
    export,
    liveblocks_auth,
    sessions,
    teams,
)

app = FastAPI(
    title="Retro Dynamics Agent API",
    version="0.1.0",
    description="See packages/contracts/openapi.yaml for the frontend/backend contract.",
)

# Local Vite dev server (either loopback form); tighten this once a deploy
# target is chosen (ADR-0003).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (teams, dynamics, sessions, liveblocks_auth, consolidation, action_items, export):
    app.include_router(router.router, prefix="/api")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
