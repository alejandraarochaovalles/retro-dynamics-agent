# Stateless, signed `state` param for the Jira OAuth flow (routes/jira_oauth.py).
# No DB table, no server-side session store: the app is deployed as
# serverless functions (see docs/adr/0003), where nothing persists between
# invocations anyway, so `state` has to carry everything it needs and prove
# it wasn't tampered with, on its own.
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from crypto import EncryptionNotConfigured
from config import settings


class InvalidState(ValueError):
    pass


@dataclass(frozen=True)
class StateData:
    team_id: str
    session_id: str
    project_key: str
    participant_name: str


def _signing_key() -> bytes:
    if not settings.token_encryption_key:
        # OAuth-connect is pointless without a place to encrypt the tokens
        # it would produce, so both features share one required secret
        # rather than adding a second env var just for this.
        raise EncryptionNotConfigured("TOKEN_ENCRYPTION_KEY must be set")
    return hmac.new(
        settings.token_encryption_key.encode(), b"oauth-state-v1", hashlib.sha256
    ).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign_state(
    *,
    team_id: str,
    session_id: str,
    project_key: str = "",
    participant_name: str = "",
    ttl_seconds: int = 600,
) -> str:
    payload = {
        "team_id": team_id,
        "session_id": session_id,
        "project_key": project_key,
        "participant_name": participant_name,
        "iat": time.time(),
        "ttl": ttl_seconds,
    }
    payload_b64 = _b64encode(json.dumps(payload).encode())
    signature = hmac.new(_signing_key(), payload_b64.encode(), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64encode(signature)}"


def verify_state(state: str) -> StateData:
    try:
        payload_b64, signature_b64 = state.split(".", 1)
        expected_signature = hmac.new(_signing_key(), payload_b64.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(signature_b64), expected_signature):
            raise InvalidState("signature mismatch")
        payload = json.loads(_b64decode(payload_b64))
        if time.time() - payload["iat"] > payload["ttl"]:
            raise InvalidState("state expired")
        return StateData(
            team_id=payload["team_id"],
            session_id=payload["session_id"],
            project_key=payload["project_key"],
            # Defaulted for states signed before this field existed (a
            # signature mismatch would already have rejected a tampered
            # payload, so a missing key here just means "older state").
            participant_name=payload.get("participant_name", ""),
        )
    except InvalidState:
        raise
    except Exception as exc:  # malformed base64/json/missing keys, etc.
        raise InvalidState("malformed state") from exc
