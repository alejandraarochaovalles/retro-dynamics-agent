from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from db import get_db
from db_models import ActionItem as ActionItemRow
from db_models import RetroSession
from db_models import Team as TeamRow
from integrations import azure_devops_client, jira_client
from models import ExportRequest, ExportResponse, ExportResult

router = APIRouter(tags=["export"])


@router.post(
    "/sessions/{id}/export",
    operation_id="exportActionItems",
    response_model=ExportResponse,
)
def export_action_items(
    id: str, payload: ExportRequest, db: DbSession = Depends(get_db)
) -> ExportResponse:
    session_row = db.get(RetroSession, id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    team_row = db.get(TeamRow, session_row.team_id)
    integration = team_row.integration if team_row else None

    items = db.scalars(
        select(ActionItemRow).where(ActionItemRow.session_id == id)
    ).all()
    ids = set(payload.action_item_ids) or {i.id for i in items}
    results: list[ExportResult] = []

    for item in items:
        if item.id not in ids:
            continue
        if item.exported:
            results.append(
                ExportResult(action_item_id=item.id, status="skipped", detail="already exported")
            )
            continue
        if integration is None:
            results.append(
                ExportResult(
                    action_item_id=item.id,
                    status="failed",
                    detail="team has no Jira/Azure DevOps integration connected",
                )
            )
            continue
        try:
            provider = integration["provider"]
            project = integration["config"].get("project_key") or integration["config"].get("project")
            if not project:
                raise ValueError("integration config is missing a project key")
            if provider == "jira":
                ref = jira_client.create_issue(project, item.title, item.description)
            elif provider == "azure_devops":
                ref = azure_devops_client.create_work_item(project, item.title, item.description)
            else:
                raise ValueError(f"unknown provider '{provider}'")
            item.exported = True
            item.external_ref = ref
            results.append(ExportResult(action_item_id=item.id, status="created", external_ref=ref))
        except Exception as exc:  # jira/ADO not configured, network error, etc.
            results.append(ExportResult(action_item_id=item.id, status="failed", detail=str(exc)))

    db.commit()
    return ExportResponse(results=results)
