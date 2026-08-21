from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from agents import consolidator
from db import get_db
from db_models import ActionItem as ActionItemRow
from db_models import RetroSession
from db_models import Team as TeamRow
from ids import new_id, new_join_code
from models import (
    ActionItem,
    Group,
    PhaseAdvance,
    SessionClose,
    SessionCreate,
    SessionJoin,
    SessionOut,
    SessionStart,
    SessionSummary,
)
from utils import now

router = APIRouter(tags=["sessions"])

_NEXT_PHASE = {
    "lobby": "active",
    "active": "consolidation",
    "consolidation": "closed",
}


def _get_session(db: DbSession, session_id: str) -> RetroSession:
    row = db.get(RetroSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return row


def _ensure_creator(row: RetroSession, participant_name: str | None) -> None:
    # Only enforced when the session actually recorded a creator — sessions
    # created before this field existed (or by a caller that omitted it,
    # see SessionCreate.created_by) stay open to anyone, same fallback
    # story as every other optional field added to this API so far.
    if row.created_by and participant_name != row.created_by:
        raise HTTPException(
            status_code=403,
            detail="only the session creator can do this",
        )


def _to_out(row: RetroSession) -> SessionOut:
    return SessionOut(
        id=row.id,
        team_id=row.team_id,
        title=row.title,
        join_code=row.join_code,
        phase=row.phase,
        dynamic=row.dynamic,
        created_at=row.created_at.isoformat(),
        closed_at=row.closed_at.isoformat() if row.closed_at else None,
        created_by=row.created_by,
    )


@router.post("/sessions", operation_id="createSession", response_model=SessionOut)
def create_session(payload: SessionCreate, db: DbSession = Depends(get_db)) -> SessionOut:
    if db.get(TeamRow, payload.team_id) is None:
        raise HTTPException(status_code=404, detail="team not found")
    row = RetroSession(
        id=new_id(),
        team_id=payload.team_id,
        title=payload.title,
        join_code=new_join_code(),
        dynamic=payload.dynamic,
        created_by=payload.created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get("/sessions/{id}", operation_id="getSession", response_model=SessionOut)
def get_session(id: str, db: DbSession = Depends(get_db)) -> SessionOut:
    return _to_out(_get_session(db, id))


@router.post("/sessions/{id}/start", operation_id="startSession", response_model=SessionOut)
def start_session(
    id: str, payload: SessionStart = SessionStart(), db: DbSession = Depends(get_db)
) -> SessionOut:
    row = _get_session(db, id)
    _ensure_creator(row, payload.participant_name)
    if row.phase != "lobby":
        raise HTTPException(status_code=409, detail=f"cannot start from phase '{row.phase}'")
    row.phase = "active"
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/sessions/{id}/phase", operation_id="advancePhase", response_model=SessionOut)
def advance_phase(id: str, payload: PhaseAdvance, db: DbSession = Depends(get_db)) -> SessionOut:
    row = _get_session(db, id)
    expected = _NEXT_PHASE.get(row.phase)
    if payload.phase != expected:
        raise HTTPException(
            status_code=409,
            detail=f"phase '{row.phase}' can only advance to '{expected}'",
        )
    row.phase = payload.phase
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/sessions/join", operation_id="joinSession", response_model=SessionOut)
def join_session(payload: SessionJoin, db: DbSession = Depends(get_db)) -> SessionOut:
    row = db.scalar(
        select(RetroSession).where(RetroSession.join_code == payload.join_code.upper())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="invalid join code")
    return _to_out(row)


@router.post("/sessions/{id}/close", operation_id="closeSession", response_model=SessionOut)
def close_session(id: str, payload: SessionClose, db: DbSession = Depends(get_db)) -> SessionOut:
    row = _get_session(db, id)
    _ensure_creator(row, payload.participant_name)
    notes = [{**note.model_dump(), "id": note.id or new_id()} for note in payload.notes]
    row.notes = notes
    row.groups = consolidator.group_notes(notes)
    row.phase = "closed"
    row.closed_at = now()
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get(
    "/sessions/{id}/summary",
    operation_id="getSessionSummary",
    response_model=SessionSummary,
)
def get_session_summary(id: str, db: DbSession = Depends(get_db)) -> SessionSummary:
    row = _get_session(db, id)
    items = db.scalars(
        select(ActionItemRow).where(ActionItemRow.session_id == id)
    ).all()
    return SessionSummary(
        session_id=row.id,
        title=row.title,
        phase=row.phase,
        groups=[Group(**g) for g in row.groups],
        action_items=[
            ActionItem(
                id=i.id,
                group_id=i.group_id,
                title=i.title,
                description=i.description,
                assignee=i.assignee,
                exported=i.exported,
                external_ref=i.external_ref,
            )
            for i in items
        ],
    )
