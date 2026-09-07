# Pure unit tests for the signed OAuth `state` param (routes/jira_oauth.py)
# — no DB, no HTTP client needed.
from __future__ import annotations

import dataclasses
import time

import pytest

from config import settings
from integrations import oauth_state


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch):
    monkeypatch.setattr(
        oauth_state, "settings", dataclasses.replace(settings, token_encryption_key="test-key-not-a-real-secret")
    )


def test_sign_and_verify_round_trip():
    state = oauth_state.sign_state(team_id="team1", session_id="sess1", project_key="RETRO")

    data = oauth_state.verify_state(state)

    assert data.team_id == "team1"
    assert data.session_id == "sess1"
    assert data.project_key == "RETRO"


def test_tampered_signature_is_rejected():
    state = oauth_state.sign_state(team_id="team1", session_id="sess1")
    payload_b64, _signature_b64 = state.split(".", 1)
    tampered = f"{payload_b64}.not-the-real-signature"

    with pytest.raises(oauth_state.InvalidState):
        oauth_state.verify_state(tampered)


def test_expired_state_is_rejected(monkeypatch):
    state = oauth_state.sign_state(team_id="team1", session_id="sess1", ttl_seconds=1)
    monkeypatch.setattr(oauth_state.time, "time", lambda: time.time() + 10)

    with pytest.raises(oauth_state.InvalidState):
        oauth_state.verify_state(state)


def test_malformed_state_is_rejected():
    with pytest.raises(oauth_state.InvalidState):
        oauth_state.verify_state("not-a-valid-state-token-at-all")
