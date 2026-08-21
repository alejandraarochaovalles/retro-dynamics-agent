from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from config import settings
from models import LiveblocksAuthRequest, LiveblocksAuthResponse

router = APIRouter(tags=["liveblocks"])


@router.post(
    "/liveblocks/auth",
    operation_id="liveblocksAuth",
    response_model=LiveblocksAuthResponse,
)
def liveblocks_auth(payload: LiveblocksAuthRequest) -> LiveblocksAuthResponse:
    if not settings.liveblocks_secret_key:
        # No secret key in dev: signal "not configured" instead of a 500,
        # so the frontend can fall back to a local-only board.
        return LiveblocksAuthResponse(token="", configured=False)

    response = httpx.post(
        "https://api.liveblocks.io/v2/authorize-user",
        headers={"Authorization": f"Bearer {settings.liveblocks_secret_key}"},
        json={
            "userId": payload.participant_name,
            "permissions": {payload.room: ["room:write"]},
        },
        timeout=10.0,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Liveblocks authorization failed")
    # Verified against a live key: POST /v2/authorize-user responds with a
    # JSON envelope `{"token": "eyJ..."}`, not raw token text — pull the
    # field out rather than forwarding response.text, which would nest the
    # whole envelope as the token string and break the Liveblocks client.
    return LiveblocksAuthResponse(token=response.json()["token"], configured=True)
