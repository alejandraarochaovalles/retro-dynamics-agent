# ID/token helpers shared by db_models.py (row defaults) and routes/sessions.py
# (join codes, which aren't a row default since they're regenerated, not
# tied to any single column's default expression).
from __future__ import annotations

import secrets
import uuid


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def new_join_code() -> str:
    return secrets.token_hex(3).upper()  # e.g. "A3F9C1"
