# Environment configuration, loaded once and shared across routes/agents/integrations.
# Nothing here is required to boot the app — every integration degrades to a
# clearly-labeled "not configured" response when its env var is missing, so
# `uvicorn main:app --reload` works with an empty .env.
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _split_origins(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None = os.getenv("GROQ_API_KEY") or None
    database_url: str | None = os.getenv("DATABASE_URL") or None
    liveblocks_secret_key: str | None = os.getenv("LIVEBLOCKS_SECRET_KEY") or None
    jira_domain: str | None = os.getenv("JIRA_DOMAIN") or None
    jira_email: str | None = os.getenv("JIRA_EMAIL") or None
    jira_api_token: str | None = os.getenv("JIRA_API_TOKEN") or None
    azure_devops_org_url: str | None = os.getenv("AZURE_DEVOPS_ORG_URL") or None
    azure_devops_pat: str | None = os.getenv("AZURE_DEVOPS_PAT") or None
    # Comma-separated list of extra origins allowed to call this API (e.g. a
    # deployed frontend's URL) — additive to the hardcoded local dev origins
    # in main.py, not a replacement, so `uvicorn main:app --reload` keeps
    # working with an empty .env exactly as before.
    frontend_origins: tuple[str, ...] = _split_origins(os.getenv("FRONTEND_ORIGIN"))


settings = Settings()
