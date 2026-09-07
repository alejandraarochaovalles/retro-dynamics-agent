# crypto.py is deliberately lazy (functools.lru_cache) about building its
# Fernet instance, so we clear that cache around every test here — otherwise
# whichever test runs first would "lock in" its settings for the rest of
# the module.
from __future__ import annotations

import dataclasses

import pytest
from cryptography.fernet import Fernet

import crypto
from config import settings


@pytest.fixture(autouse=True)
def _reset_fernet_cache():
    crypto._fernet.cache_clear()
    yield
    crypto._fernet.cache_clear()


def test_decrypt_reverses_encrypt(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto, "settings", dataclasses.replace(settings, token_encryption_key=key))

    token = crypto.encrypt("super-secret-value")

    assert token != "super-secret-value"
    assert crypto.decrypt(token) == "super-secret-value"


def test_encrypt_without_key_raises_not_configured(monkeypatch):
    monkeypatch.setattr(crypto, "settings", dataclasses.replace(settings, token_encryption_key=None))

    with pytest.raises(crypto.EncryptionNotConfigured):
        crypto.encrypt("value")


def test_decrypt_with_wrong_or_rotated_key_raises_not_configured(monkeypatch):
    key_a = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto, "settings", dataclasses.replace(settings, token_encryption_key=key_a))
    token = crypto.encrypt("value")
    crypto._fernet.cache_clear()

    key_b = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto, "settings", dataclasses.replace(settings, token_encryption_key=key_b))

    with pytest.raises(crypto.EncryptionNotConfigured):
        crypto.decrypt(token)
