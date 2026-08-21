# Only the "not configured" fallback is deterministic enough for CI — the
# real-key path calls out to api.liveblocks.io and is verified live
# instead (see routes/liveblocks_auth.py's comment on the response shape).
from __future__ import annotations

import dataclasses

from config import settings


def test_liveblocks_auth_without_secret_key_signals_not_configured(client, monkeypatch):
    # settings is a frozen dataclass — swap the module-level name for a
    # copy with the key cleared, rather than mutating the shared instance.
    monkeypatch.setattr(
        "routes.liveblocks_auth.settings",
        dataclasses.replace(settings, liveblocks_secret_key=None),
    )
    response = client.post(
        "/api/liveblocks/auth",
        json={"room": "session-abc123", "participant_name": "Ale"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"token": "", "configured": False}
