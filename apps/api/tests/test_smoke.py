# End-to-end smoke test exercising the full retro lifecycle against a real
# Postgres test database (see conftest.py): create team -> create session
# -> start -> close -> groups -> action item -> export.
from __future__ import annotations

import dataclasses

import agents.dynamic_generator as dynamic_generator
from db_models import Team as TeamRow


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_retro_lifecycle(client):
    team = client.post("/api/teams", json={"name": "Platform"}).json()

    session = client.post(
        "/api/sessions",
        json={"team_id": team["id"], "title": "Sprint 42 retro"},
    ).json()
    assert session["phase"] == "lobby"

    started = client.post(f"/api/sessions/{session['id']}/start").json()
    assert started["phase"] == "active"

    closed = client.post(
        f"/api/sessions/{session['id']}/close",
        json={"notes": [{"author": "ale", "text": "CI was flaky", "votes": 2}]},
    ).json()
    assert closed["phase"] == "closed"

    groups = client.get(f"/api/sessions/{session['id']}/groups").json()
    assert len(groups) == 1
    group_id = groups[0]["id"]

    item = client.post(
        f"/api/sessions/{session['id']}/action-items",
        json={"group_id": group_id, "title": "Stabilize CI"},
    ).json()
    assert item["exported"] is False

    export = client.post(f"/api/sessions/{session['id']}/export", json={}).json()
    assert export["results"][0]["status"] == "failed"  # no integration connected


def test_join_session_by_code(client):
    team = client.post("/api/teams", json={"name": "Growth"}).json()
    session = client.post(
        "/api/sessions",
        json={"team_id": team["id"], "title": "Sprint 7 retro"},
    ).json()

    joined = client.post(
        "/api/sessions/join",
        json={"join_code": session["join_code"], "participant_name": "Ale"},
    ).json()
    assert joined["id"] == session["id"]


def test_teams_are_actually_persisted_in_postgres(client, db_session):
    created = client.post("/api/teams", json={"name": "Persisted"}).json()

    # Read back through a *separate* DB session, not the app's response —
    # proves the row survives in Postgres, not just in the request's memory.
    row = db_session.get(TeamRow, created["id"])
    assert row is not None
    assert row.name == "Persisted"


def test_only_creator_can_start_and_close_session(client):
    team = client.post("/api/teams", json={"name": "Security"}).json()
    session = client.post(
        "/api/sessions",
        json={"team_id": team["id"], "title": "Sprint 9 retro", "created_by": "Ale"},
    ).json()
    assert session["created_by"] == "Ale"

    # Someone else can't start it...
    denied = client.post(
        f"/api/sessions/{session['id']}/start", json={"participant_name": "Sam"}
    )
    assert denied.status_code == 403
    assert client.get(f"/api/sessions/{session['id']}").json()["phase"] == "lobby"

    # ...but the creator can.
    started = client.post(
        f"/api/sessions/{session['id']}/start", json={"participant_name": "Ale"}
    )
    assert started.status_code == 200
    assert started.json()["phase"] == "active"

    # Same story for closing.
    denied_close = client.post(
        f"/api/sessions/{session['id']}/close",
        json={"notes": [], "participant_name": "Sam"},
    )
    assert denied_close.status_code == 403

    closed = client.post(
        f"/api/sessions/{session['id']}/close",
        json={"notes": [], "participant_name": "Ale"},
    )
    assert closed.status_code == 200
    assert closed.json()["phase"] == "closed"


def test_sessions_without_a_recorded_creator_stay_open_to_anyone(client):
    # Backward compatibility: a session created without `created_by` (an
    # older client, or a caller that just omits it) must not lock everyone
    # out of starting/closing it.
    team = client.post("/api/teams", json={"name": "Legacy"}).json()
    session = client.post(
        "/api/sessions", json={"team_id": team["id"], "title": "No creator recorded"}
    ).json()
    assert session["created_by"] is None

    started = client.post(f"/api/sessions/{session['id']}/start")
    assert started.status_code == 200


def test_notes_keep_their_phase_through_close(client):
    team = client.post("/api/teams", json={"name": "Phase Tracking"}).json()
    session = client.post(
        "/api/sessions", json={"team_id": team["id"], "title": "Sprint 10 retro"}
    ).json()
    client.post(f"/api/sessions/{session['id']}/start")

    closed = client.post(
        f"/api/sessions/{session['id']}/close",
        json={
            "notes": [
                {"author": "Ale", "text": "CI was flaky", "votes": 2, "phase": "stop"},
                {"author": "Sam", "text": "Great pairing", "votes": 1, "phase": "continue"},
            ]
        },
    ).json()
    assert closed["phase"] == "closed"

    groups = {g["text"]: g["phase"] for g in client.get(f"/api/sessions/{session['id']}/groups").json()}
    assert groups["CI was flaky"] == "stop"
    assert groups["Great pairing"] == "continue"


def test_dynamics_generate_falls_back_without_groq_key(client, monkeypatch):
    # `config.settings` is a frozen dataclass built once at import time from
    # the environment (see config.py) — monkeypatch.delenv after import
    # can't reach it, so patch the module-level singleton dynamic_generator
    # actually reads instead of the env var.
    monkeypatch.setattr(
        dynamic_generator,
        "settings",
        dataclasses.replace(dynamic_generator.settings, groq_api_key=None),
    )
    response = client.post("/api/dynamics/generate", json={"context": "quiet sprint"})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fallback"
    assert len(body["proposals"]) > 0
