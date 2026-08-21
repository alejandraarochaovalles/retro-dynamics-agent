from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from db import get_db
from db_models import ActionItem as ActionItemRow
from db_models import RetroSession
from ids import new_id
from models import ActionItem, ActionItemCreate, ActionItemUpdate, DeleteResponse

router = APIRouter(tags=["action-items"])


def _get_session(db: DbSession, session_id: str) -> RetroSession:
    row = db.get(RetroSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return row


def _get_item(db: DbSession, session_id: str, item_id: str) -> ActionItemRow:
    row = db.get(ActionItemRow, item_id)
    if row is None or row.session_id != session_id:
        raise HTTPException(status_code=404, detail="action item not found")
    return row


def _to_out(row: ActionItemRow) -> ActionItem:
    return ActionItem(
        id=row.id,
        group_id=row.group_id,
        title=row.title,
        description=row.description,
        assignee=row.assignee,
        exported=row.exported,
        external_ref=row.external_ref,
    )


@router.post(
    "/sessions/{id}/action-items",
    operation_id="createActionItem",
    response_model=ActionItem,
)
def create_action_item(
    id: str, payload: ActionItemCreate, db: DbSession = Depends(get_db)
) -> ActionItem:
    session_row = _get_session(db, id)
    if not any(g["id"] == payload.group_id for g in session_row.groups):
        raise HTTPException(status_code=404, detail="group not found")
    row = ActionItemRow(
        id=new_id(),
        session_id=id,
        group_id=payload.group_id,
        title=payload.title,
        description=payload.description,
        assignee=payload.assignee,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.patch(
    "/sessions/{id}/action-items/{item_id}",
    operation_id="updateActionItem",
    response_model=ActionItem,
)
def update_action_item(
    id: str, item_id: str, payload: ActionItemUpdate, db: DbSession = Depends(get_db)
) -> ActionItem:
    row = _get_item(db, id, item_id)
    if payload.title is not None:
        row.title = payload.title
    if payload.description is not None:
        row.description = payload.description
    if payload.assignee is not None:
        row.assignee = payload.assignee
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete(
    "/sessions/{id}/action-items/{item_id}",
    operation_id="deleteActionItem",
    response_model=DeleteResponse,
)
def delete_action_item(id: str, item_id: str, db: DbSession = Depends(get_db)) -> DeleteResponse:
    row = _get_item(db, id, item_id)
    db.delete(row)
    db.commit()
    return DeleteResponse(deleted=item_id)
