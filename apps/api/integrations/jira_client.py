# Jira Cloud REST API v3 client — issue creation for exported action items.
# https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
from __future__ import annotations

import httpx

from config import settings


class JiraNotConfigured(RuntimeError):
    pass


def create_issue(project_key: str, summary: str, description: str = "") -> str:
    """Creates a Jira issue and returns its key (e.g. 'RETRO-42')."""
    if not (settings.jira_domain and settings.jira_email and settings.jira_api_token):
        raise JiraNotConfigured("JIRA_DOMAIN, JIRA_EMAIL and JIRA_API_TOKEN must be set")

    url = f"https://{settings.jira_domain}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description or summary}],
                    }
                ],
            },
            "issuetype": {"name": "Task"},
        }
    }
    response = httpx.post(
        url,
        json=payload,
        auth=(settings.jira_email, settings.jira_api_token),
        headers={"Accept": "application/json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["key"]
