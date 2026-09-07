# Symmetric encryption for secrets we store at rest (currently: per-team
# Jira OAuth access/refresh tokens on teams.integration, see
# integrations/jira_oauth.py and routes/jira_oauth.py). Deliberately lazy
# about TOKEN_ENCRYPTION_KEY being unset — same "not configured" philosophy
# as every other integration in config.py — so the app keeps booting with an
# empty .env, and only actually using OAuth-connect fails loudly.
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from config import settings


class EncryptionNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise EncryptionNotConfigured("TOKEN_ENCRYPTION_KEY must be set")
    return Fernet(settings.token_encryption_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        # Covers both "never configured" (wrong/placeholder key) and "key
        # rotated since this token was stored" — either way, the caller
        # can't recover the plaintext, so treat it the same as unconfigured.
        raise EncryptionNotConfigured("could not decrypt token — wrong or rotated TOKEN_ENCRYPTION_KEY") from exc
