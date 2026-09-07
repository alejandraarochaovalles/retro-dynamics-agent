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
    # "Connect with Jira" (OAuth 2.0 3LO, see integrations/jira_oauth.py) —
    # lets a team connect its own Jira account instead of relying on the
    # single global JIRA_API_TOKEN above. From developer.atlassian.com/console.
    jira_oauth_client_id: str | None = os.getenv("JIRA_OAUTH_CLIENT_ID") or None
    jira_oauth_client_secret: str | None = os.getenv("JIRA_OAUTH_CLIENT_SECRET") or None
    jira_oauth_redirect_uri: str | None = os.getenv("JIRA_OAUTH_REDIRECT_URI") or None
    # Symmetric key (Fernet) used to encrypt OAuth tokens at rest, and to
    # derive the signing key for the OAuth `state` param — see crypto.py and
    # integrations/oauth_state.py. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str | None = os.getenv("TOKEN_ENCRYPTION_KEY") or None
    # Single canonical URL the Jira OAuth callback redirects the browser back
    # to once tokens are stored — distinct from frontend_origins below (a
    # CORS allowlist that may hold several values, not a redirect target).
    frontend_base_url: str = os.getenv("FRONTEND_BASE_URL") or "http://localhost:5173"
    # Comma-separated list of extra origins allowed to call this API (e.g. a
    # deployed frontend's URL) — additive to the hardcoded local dev origins
    # in main.py, not a replacement, so `uvicorn main:app --reload` keeps
    # working with an empty .env exactly as before.
    frontend_origins: tuple[str, ...] = _split_origins(os.getenv("FRONTEND_ORIGIN"))


settings = Settings()
