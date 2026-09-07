from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from db import get_db
from db_models import RetroSession
from db_models import Team as TeamRow
from ids import new_id
from models import IntegrationConnect, SessionListItem, Team, TeamCreate

router = APIRouter(tags=["teams"])


def _to_out(row: TeamRow) -> Team:
    return Team(
        id=row.id,
        name=row.name,
        integration=row.integration,
        created_at=row.created_at.isoformat(),
    )


@router.post("/teams", operation_id="createTeam", response_model=Team)
def create_team(payload: TeamCreate, db: DbSession = Depends(get_db)) -> Team:
    row = TeamRow(id=new_id(), name=payload.name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get("/teams/{team_id}", operation_id="getTeam", response_model=Team)
def get_team(team_id: str, db: DbSession = Depends(get_db)) -> Team:
    row = db.get(TeamRow, team_id)
    if row is None:
        raise HTTPException(status_code=404, detail="team not found")
    return _to_out(row)


@router.post(
    "/teams/{team_id}/integration",
    operation_id="connectIntegration",
    response_model=Team,
)
def connect_integration(
    team_id: str, payload: IntegrationConnect, db: DbSession = Depends(get_db)
) -> Team:
    row = db.get(TeamRow, team_id)
    if row is None:
        raise HTTPException(status_code=404, detail="team not found")
    # Only enforced when session_id resolves to a real session that
    # actually recorded a creator — same fallback story as
    # routes/sessions.py's _ensure_creator, so old/no-session callers keep
    # working unchanged.
    if payload.session_id:
        session_row = db.get(RetroSession, payload.session_id)
        if session_row and session_row.created_by and payload.participant_name != session_row.created_by:
            raise HTTPException(
                status_code=403,
                detail="only the session facilitator can connect an integration",
            )
    existing = row.integration or {}
    new_integration: dict = {"provider": payload.provider, "config": payload.config}
    # Preserve OAuth tokens (see routes/jira_oauth.py) if this call is just
    # updating the manual config (e.g. the project key) for the same
    # provider — otherwise resubmitting the "Advanced / manual setup" form
    # would silently disconnect a team's "Connect with Jira" tokens.
    if existing.get("provider") == payload.provider and "oauth" in existing:
        new_integration["oauth"] = existing["oauth"]
    row.integration = new_integration
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get(
    "/teams/{team_id}/sessions",
    operation_id="listTeamSessions",
    response_model=list[SessionListItem],
)
def list_team_sessions(team_id: str, db: DbSession = Depends(get_db)) -> list[SessionListItem]:
    if db.get(TeamRow, team_id) is None:
        raise HTTPException(status_code=404, detail="team not found")
    rows = db.scalars(
        select(RetroSession).where(RetroSession.team_id == team_id)
    ).all()
    return [
        SessionListItem(id=r.id, title=r.title, phase=r.phase, created_at=r.created_at.isoformat())
        for r in rows
    ]
