# "Connect with Jira" — OAuth 2.0 (3LO) start + callback. Lets a team
# connect its own Jira account (see integrations/jira_oauth.py) instead of
# the whole deployment sharing one JIRA_API_TOKEN (jira_client.py's
# fallback path, still used by teams that never connect via OAuth, and by
# Azure DevOps unconditionally).
#
# Both endpoints redirect the browser (never return JSON) since this is a
# full-page OAuth round trip, not an API call the frontend fetches. The
# frontend has no persistence of its own — see SessionSetup.tsx — so the
# callback redirect carries `session_id` back in its query string, and the
# frontend just re-fetches GET /sessions/{id} to resume where it left off.
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

import crypto
from config import settings
from db import get_db
from db_models import Team as TeamRow
from integrations import jira_oauth
from integrations.oauth_state import InvalidState, sign_state, verify_state

router = APIRouter(tags=["jira-oauth"])


def _frontend_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_base_url}/?{urlencode(params)}", status_code=302)


@router.get("/integrations/jira/connect", operation_id="startJiraOAuth")
def start_jira_oauth(
    team_id: str, session_id: str, project_key: str = "", db: DbSession = Depends(get_db)
) -> RedirectResponse:
    if db.get(TeamRow, team_id) is None:
        return _frontend_redirect(jira_error="team_not_found")
    try:
        state = sign_state(team_id=team_id, session_id=session_id, project_key=project_key)
        authorize_url = jira_oauth.build_authorize_url(state)
    except (crypto.EncryptionNotConfigured, jira_oauth.JiraOAuthNotConfigured) as exc:
        return _frontend_redirect(jira_error=str(exc))
    return RedirectResponse(authorize_url, status_code=302)


@router.get("/integrations/jira/callback", operation_id="jiraOAuthCallback")
def jira_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: DbSession = Depends(get_db),
) -> RedirectResponse:
    if error or not code or not state:
        return _frontend_redirect(jira_error=error or "missing_code_or_state")

    try:
        data = verify_state(state)
    except InvalidState:
        return _frontend_redirect(jira_error="invalid_state")

    team_row = db.get(TeamRow, data.team_id)
    if team_row is None:
        return _frontend_redirect(jira_error="team_not_found", session_id=data.session_id)

    try:
        tokens = jira_oauth.exchange_code_for_tokens(code)
        resources = jira_oauth.get_accessible_resources(tokens.access_token)
    except httpx.HTTPError:
        return _frontend_redirect(jira_error="exchange_failed", session_id=data.session_id)

    if not resources:
        return _frontend_redirect(jira_error="no_accessible_sites", session_id=data.session_id)

    # Single-Jira-site-per-team assumption — fine for this app's scope; a
    # team connected to a multi-site Atlassian org would need a site picker.
    site = resources[0]

    existing = team_row.integration or {}
    existing_config = existing.get("config", {}) if existing.get("provider") == "jira" else {}
    project_key = data.project_key or existing_config.get("project_key", "")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)
    team_row.integration = {
        "provider": "jira",
        "config": {
            "project_key": project_key,
            "cloud_id": site.id,
            "site_name": site.name,
            "site_url": site.url,
        },
        "oauth": {
            "access_token": crypto.encrypt(tokens.access_token),
            "refresh_token": crypto.encrypt(tokens.refresh_token),
            "expires_at": expires_at.isoformat(),
        },
    }
    db.commit()

    return _frontend_redirect(jira_connected="1", session_id=data.session_id)
