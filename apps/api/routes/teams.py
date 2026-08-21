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
    row.integration = {"provider": payload.provider, "config": payload.config}
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
