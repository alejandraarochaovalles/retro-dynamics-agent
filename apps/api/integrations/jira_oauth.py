# Jira Cloud OAuth 2.0 (3LO) — "Connect with Jira" for a single team,
# instead of the whole deployment sharing one JIRA_API_TOKEN (see
# jira_client.py). Reference:
# https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from config import settings

AUTH_BASE = "https://auth.atlassian.com"
API_BASE = "https://api.atlassian.com"

SCOPES = "read:jira-work write:jira-work offline_access"


class JiraOAuthNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int  # seconds


@dataclass(frozen=True)
class AccessibleResource:
    id: str  # cloudId — needed to build the API base URL
    url: str
    name: str


def _require_configured() -> None:
    if not (settings.jira_oauth_client_id and settings.jira_oauth_client_secret and settings.jira_oauth_redirect_uri):
        raise JiraOAuthNotConfigured(
            "JIRA_OAUTH_CLIENT_ID, JIRA_OAUTH_CLIENT_SECRET and JIRA_OAUTH_REDIRECT_URI must be set"
        )


def build_authorize_url(state: str) -> str:
    _require_configured()
    params = {
        "audience": "api.atlassian.com",
        "client_id": settings.jira_oauth_client_id,
        "scope": SCOPES,
        "redirect_uri": settings.jira_oauth_redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return f"{AUTH_BASE}/authorize?{urlencode(params)}"


def _token_response(data: dict) -> TokenResponse:
    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"],
    )


def exchange_code_for_tokens(code: str) -> TokenResponse:
    _require_configured()
    response = httpx.post(
        f"{AUTH_BASE}/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": settings.jira_oauth_client_id,
            "client_secret": settings.jira_oauth_client_secret,
            "code": code,
            "redirect_uri": settings.jira_oauth_redirect_uri,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return _token_response(response.json())


def refresh_access_token(refresh_token: str) -> TokenResponse:
    # Atlassian ROTATES refresh tokens on every use — the response's
    # refresh_token is a *new* one that must overwrite the stored one, or
    # the next refresh will fail with an invalid_grant error. Callers must
    # persist both fields of the returned TokenResponse, not just the
    # access_token.
    _require_configured()
    response = httpx.post(
        f"{AUTH_BASE}/oauth/token",
        json={
            "grant_type": "refresh_token",
            "client_id": settings.jira_oauth_client_id,
            "client_secret": settings.jira_oauth_client_secret,
            "refresh_token": refresh_token,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return _token_response(response.json())


def get_accessible_resources(access_token: str) -> list[AccessibleResource]:
    response = httpx.get(
        f"{API_BASE}/oauth/token/accessible-resources",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return [
        AccessibleResource(id=item["id"], url=item["url"], name=item["name"])
        for item in response.json()
    ]
