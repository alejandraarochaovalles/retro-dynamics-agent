from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from agents import consolidator
from db import get_db
from db_models import RetroSession
from models import Group, GroupUpdate, VotesSummaryEntry

router = APIRouter(tags=["consolidation"])


def _get_session(db: DbSession, session_id: str) -> RetroSession:
    row = db.get(RetroSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return row


@router.get("/sessions/{id}/groups", operation_id="listGroups", response_model=list[Group])
def list_groups(id: str, db: DbSession = Depends(get_db)) -> list[Group]:
    return [Group(**g) for g in _get_session(db, id).groups]


@router.patch(
    "/sessions/{id}/groups/{group_id}",
    operation_id="updateGroup",
    response_model=Group,
)
def update_group(
    id: str, group_id: str, payload: GroupUpdate, db: DbSession = Depends(get_db)
) -> Group:
    row = _get_session(db, id)
    groups = row.groups
    group = next((g for g in groups if g["id"] == group_id), None)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    if payload.label is not None:
        group["label"] = payload.label
    if payload.note_ids is not None:
        group["note_ids"] = payload.note_ids
    row.groups = groups  # reassign so SQLAlchemy detects the JSON column changed
    db.commit()
    return Group(**group)


@router.get(
    "/sessions/{id}/votes-summary",
    operation_id="getVotesSummary",
    response_model=list[VotesSummaryEntry],
)
def get_votes_summary(id: str, db: DbSession = Depends(get_db)) -> list[VotesSummaryEntry]:
    row = _get_session(db, id)
    ranked = consolidator.rank_by_votes(row.groups)
    return [VotesSummaryEntry(id=g["id"], label=g["label"], votes=g["votes"]) for g in ranked]
