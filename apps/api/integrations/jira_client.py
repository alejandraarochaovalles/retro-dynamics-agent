# Jira Cloud REST API v3 client — issue creation for exported action items.
# https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
#
# Two auth paths, tried in this order:
#   1. Per-team OAuth ("Connect with Jira", see integrations/jira_oauth.py) —
#      Bearer token against api.atlassian.com/ex/jira/{cloud_id}/..., used
#      when the team's stored integration has an "oauth" block.
#   2. The original global JIRA_API_TOKEN (HTTP Basic auth against the
#      team's own {domain}), shared by the whole deployment — unchanged,
#      still the only option for teams that never connect via OAuth.
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx

import crypto
from config import settings
from integrations import jira_oauth

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DbSession

    from db_models import Team as TeamRow


class JiraNotConfigured(RuntimeError):
    pass


def _issue_payload(project_key: str, summary: str, description: str) -> dict:
    return {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description or summary}],
                    }
                ],
            },
            "issuetype": {"name": "Task"},
        }
    }


def _access_token_for(team: "TeamRow", db: "DbSession") -> str:
    # Refresh (and persist the rotated tokens — Atlassian rotates the
    # refresh_token on every use, see jira_oauth.refresh_access_token) if the
    # stored access token is expired or about to expire.
    oauth = team.integration["oauth"]
    expires_at = datetime.fromisoformat(oauth["expires_at"])
    if expires_at - datetime.now(timezone.utc) > timedelta(seconds=60):
        return crypto.decrypt(oauth["access_token"])

    refresh_token = crypto.decrypt(oauth["refresh_token"])
    tokens = jira_oauth.refresh_access_token(refresh_token)
    new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)
    team.integration = {
        **team.integration,
        "oauth": {
            "access_token": crypto.encrypt(tokens.access_token),
            "refresh_token": crypto.encrypt(tokens.refresh_token),
            "expires_at": new_expires_at.isoformat(),
        },
    }
    db.commit()
    return tokens.access_token


def _create_issue_oauth(
    team: "TeamRow", db: "DbSession", project_key: str, summary: str, description: str
) -> str:
    cloud_id = team.integration["config"]["cloud_id"]
    access_token = _access_token_for(team, db)
    url = f"{jira_oauth.API_BASE}/ex/jira/{cloud_id}/rest/api/3/issue"
    response = httpx.post(
        url,
        json=_issue_payload(project_key, summary, description),
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["key"]


def _create_issue_global_token(project_key: str, summary: str, description: str) -> str:
    if not (settings.jira_domain and settings.jira_email and settings.jira_api_token):
        raise JiraNotConfigured("JIRA_DOMAIN, JIRA_EMAIL and JIRA_API_TOKEN must be set")

    url = f"https://{settings.jira_domain}/rest/api/3/issue"
    response = httpx.post(
        url,
        json=_issue_payload(project_key, summary, description),
        auth=(settings.jira_email, settings.jira_api_token),
        headers={"Accept": "application/json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["key"]


def create_issue(
    project_key: str,
    summary: str,
    description: str = "",
    *,
    team: "TeamRow | None" = None,
    db: "DbSession | None" = None,
) -> str:
    """Creates a Jira issue and returns its key (e.g. 'RETRO-42').

    Prefers a team's own "Connect with Jira" OAuth tokens when present,
    otherwise falls back to the single global JIRA_API_TOKEN shared by the
    whole deployment.
    """
    if team is not None and db is not None and (team.integration or {}).get("oauth"):
        return _create_issue_oauth(team, db, project_key, summary, description)
    return _create_issue_global_token(project_key, summary, description)
