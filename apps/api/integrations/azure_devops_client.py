# Azure DevOps REST API client — work item creation for exported action items.
# https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create
from __future__ import annotations

import base64

import httpx

from config import settings


class AzureDevOpsNotConfigured(RuntimeError):
    pass


def create_work_item(project: str, title: str, description: str = "") -> str:
    """Creates a Task work item and returns its id as a string."""
    if not (settings.azure_devops_org_url and settings.azure_devops_pat):
        raise AzureDevOpsNotConfigured(
            "AZURE_DEVOPS_ORG_URL and AZURE_DEVOPS_PAT must be set"
        )

    url = (
        f"{settings.azure_devops_org_url.rstrip('/')}/{project}"
        "/_apis/wit/workitems/$Task?api-version=7.1"
    )
    token = base64.b64encode(f":{settings.azure_devops_pat}".encode()).decode()
    payload = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
        {"op": "add", "path": "/fields/System.Description", "value": description or title},
    ]
    response = httpx.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json-patch+json",
            "Authorization": f"Basic {token}",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return str(response.json()["id"])
