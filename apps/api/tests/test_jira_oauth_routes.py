# Exercises the "Connect with Jira" round trip against a real Postgres test
# database (see conftest.py) — only the calls out to Atlassian itself
# (exchange_code_for_tokens / get_accessible_resources) are monkeypatched.
from __future__ import annotations

import dataclasses
import urllib.parse

import httpx
import pytest
from cryptography.fernet import Fernet

import crypto
from config import settings
from db_models import Team as TeamRow
from integrations import jira_oauth as jira_oauth_integration
from integrations import oauth_state
from routes import jira_oauth as jira_oauth_routes


@pytest.fixture(autouse=True)
def _configured_oauth(monkeypatch):
    configured = dataclasses.replace(
        settings,
        jira_oauth_client_id="test-client-id",
        jira_oauth_client_secret="test-client-secret",
        jira_oauth_redirect_uri="http://127.0.0.1:8000/api/integrations/jira/callback",
        token_encryption_key=Fernet.generate_key().decode(),
        frontend_base_url="http://localhost:5173",
    )
    for module in (jira_oauth_routes, jira_oauth_integration, oauth_state, crypto):
        monkeypatch.setattr(module, "settings", configured)
    crypto._fernet.cache_clear()
    yield
    crypto._fernet.cache_clear()


def test_connect_redirects_to_atlassian_with_signed_state(client):
    team = client.post("/api/teams", json={"name": "OAuth Team"}).json()

    response = client.get(
        "/api/integrations/jira/connect",
        params={"team_id": team["id"], "session_id": "sess-1", "project_key": "RETRO"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://auth.atlassian.com/authorize?")

    query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(location).query))
    assert query["client_id"] == "test-client-id"
    state_data = oauth_state.verify_state(query["state"])
    assert state_data.team_id == team["id"]
    assert state_data.session_id == "sess-1"
    assert state_data.project_key == "RETRO"


def test_connect_with_unknown_team_redirects_with_error(client):
    response = client.get(
        "/api/integrations/jira/connect",
        params={"team_id": "does-not-exist", "session_id": "sess-1"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "jira_error=team_not_found" in response.headers["location"]


def test_callback_stores_encrypted_tokens_and_redirects(client, db_session, monkeypatch):
    team = client.post("/api/teams", json={"name": "OAuth Team"}).json()
    state = oauth_state.sign_state(team_id=team["id"], session_id="sess-1", project_key="RETRO")

    monkeypatch.setattr(
        jira_oauth_integration,
        "exchange_code_for_tokens",
        lambda code: jira_oauth_integration.TokenResponse(
            access_token="access-token-abc", refresh_token="refresh-token-xyz", expires_in=3600
        ),
    )
    monkeypatch.setattr(
        jira_oauth_integration,
        "get_accessible_resources",
        lambda access_token: [
            jira_oauth_integration.AccessibleResource(
                id="cloud-1", url="https://example.atlassian.net", name="Example"
            )
        ],
    )

    response = client.get(
        "/api/integrations/jira/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "jira_connected=1" in location
    assert "session_id=sess-1" in location

    row = db_session.get(TeamRow, team["id"])
    assert row.integration["provider"] == "jira"
    assert row.integration["config"]["cloud_id"] == "cloud-1"
    assert row.integration["config"]["project_key"] == "RETRO"
    assert row.integration["oauth"]["access_token"] != "access-token-abc"
    assert crypto.decrypt(row.integration["oauth"]["access_token"]) == "access-token-abc"
    assert crypto.decrypt(row.integration["oauth"]["refresh_token"]) == "refresh-token-xyz"


def test_callback_with_error_param_redirects_with_that_error(client):
    response = client.get(
        "/api/integrations/jira/callback", params={"error": "access_denied"}, follow_redirects=False
    )

    assert response.status_code == 302
    assert "jira_error=access_denied" in response.headers["location"]


def test_callback_missing_code_or_state_redirects_with_generic_error(client):
    response = client.get("/api/integrations/jira/callback", follow_redirects=False)

    assert response.status_code == 302
    assert "jira_error=missing_code_or_state" in response.headers["location"]


def test_callback_with_tampered_state_redirects_with_invalid_state(client):
    response = client.get(
        "/api/integrations/jira/callback",
        params={"code": "auth-code", "state": "garbage.garbage"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "jira_error=invalid_state" in response.headers["location"]


def test_callback_exchange_failure_redirects_with_exchange_failed(client, monkeypatch):
    team = client.post("/api/teams", json={"name": "OAuth Team"}).json()
    state = oauth_state.sign_state(team_id=team["id"], session_id="sess-1")

    def _boom(code):
        raise httpx.HTTPStatusError(
            "boom",
            request=httpx.Request("POST", "https://auth.atlassian.com/oauth/token"),
            response=httpx.Response(400),
        )

    monkeypatch.setattr(jira_oauth_integration, "exchange_code_for_tokens", _boom)

    response = client.get(
        "/api/integrations/jira/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "jira_error=exchange_failed" in response.headers["location"]


def test_callback_with_no_accessible_sites_redirects_with_that_error(client, monkeypatch):
    team = client.post("/api/teams", json={"name": "OAuth Team"}).json()
    state = oauth_state.sign_state(team_id=team["id"], session_id="sess-1")

    monkeypatch.setattr(
        jira_oauth_integration,
        "exchange_code_for_tokens",
        lambda code: jira_oauth_integration.TokenResponse(
            access_token="a", refresh_token="b", expires_in=3600
        ),
    )
    monkeypatch.setattr(jira_oauth_integration, "get_accessible_resources", lambda access_token: [])

    response = client.get(
        "/api/integrations/jira/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "jira_error=no_accessible_sites" in response.headers["location"]
