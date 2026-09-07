# jira_client.create_issue's two auth paths: a team's own OAuth tokens
# (see integrations/jira_oauth.py), and the original global-token fallback.
# All actual HTTP calls (issue creation, token refresh) are monkeypatched.
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet

import crypto
from db_models import Team as TeamRow
from integrations import jira_client
from integrations import jira_oauth


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto, "settings", dataclasses.replace(crypto.settings, token_encryption_key=key))
    crypto._fernet.cache_clear()
    yield
    crypto._fernet.cache_clear()


def test_create_issue_with_oauth_uses_bearer_auth_against_cloud_id(client, db_session, monkeypatch):
    team = client.post("/api/teams", json={"name": "OAuth Export Team"}).json()
    row = db_session.get(TeamRow, team["id"])

    future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    row.integration = {
        "provider": "jira",
        "config": {"project_key": "RETRO", "cloud_id": "cloud-123", "site_name": "x", "site_url": "y"},
        "oauth": {
            "access_token": crypto.encrypt("valid-access-token"),
            "refresh_token": crypto.encrypt("valid-refresh-token"),
            "expires_at": future_expiry.isoformat(),
        },
    }
    db_session.commit()

    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        return httpx.Response(200, json={"key": "RETRO-1"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = jira_client.create_issue("RETRO", "Do the thing", team=row, db=db_session)

    assert result == "RETRO-1"
    assert captured["url"] == "https://api.atlassian.com/ex/jira/cloud-123/rest/api/3/issue"
    assert captured["headers"]["Authorization"] == "Bearer valid-access-token"


def test_create_issue_with_expired_token_refreshes_and_persists_rotated_tokens(client, db_session, monkeypatch):
    team = client.post("/api/teams", json={"name": "OAuth Refresh Team"}).json()
    row = db_session.get(TeamRow, team["id"])

    expired = datetime.now(timezone.utc) - timedelta(seconds=5)
    row.integration = {
        "provider": "jira",
        "config": {"project_key": "RETRO", "cloud_id": "cloud-123", "site_name": "x", "site_url": "y"},
        "oauth": {
            "access_token": crypto.encrypt("stale-access-token"),
            "refresh_token": crypto.encrypt("old-refresh-token"),
            "expires_at": expired.isoformat(),
        },
    }
    db_session.commit()

    monkeypatch.setattr(
        jira_oauth,
        "refresh_access_token",
        lambda refresh_token: jira_oauth.TokenResponse(
            access_token="new-access-token", refresh_token="rotated-refresh-token", expires_in=3600
        ),
    )

    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["headers"] = headers
        return httpx.Response(200, json={"key": "RETRO-2"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = jira_client.create_issue("RETRO", "Refreshed", team=row, db=db_session)

    assert result == "RETRO-2"
    assert captured["headers"]["Authorization"] == "Bearer new-access-token"

    db_session.refresh(row)
    assert crypto.decrypt(row.integration["oauth"]["access_token"]) == "new-access-token"
    assert crypto.decrypt(row.integration["oauth"]["refresh_token"]) == "rotated-refresh-token"


def test_create_issue_without_team_falls_back_to_global_token_path(monkeypatch):
    # Regression guard: omitting team/db (as every pre-OAuth call site did,
    # and as export.py still does for teams that never connected via OAuth)
    # must keep hitting the original global-token path unchanged.
    monkeypatch.setattr(
        jira_client,
        "settings",
        dataclasses.replace(jira_client.settings, jira_domain=None, jira_email=None, jira_api_token=None),
    )

    with pytest.raises(jira_client.JiraNotConfigured):
        jira_client.create_issue("RETRO", "No integration")
