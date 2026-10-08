"""Keyed fingerprints (owner, 2026-10-08): "u_" + HMAC-SHA-256(key, telegram id)[:12], the key from the .env secret
BETA_FINGERPRINT_KEY, never printed; no key, no start."""
import hashlib
import hmac

import pytest

import beta.admin as admin
from beta.config import BetaSecrets


@pytest.fixture
def restore_key():
    saved = admin._fingerprint_key
    yield
    admin._fingerprint_key = saved


def test_the_fingerprint_is_keyed_and_cannot_be_recomputed_from_the_id_alone(restore_key):
    admin.set_fingerprint_key("k" * 40)
    fp = admin.fingerprint(123456789)
    assert fp == "u_" + hmac.new(b"k" * 40, b"123456789", hashlib.sha256).hexdigest()[:12]
    assert fp != "u_" + hashlib.sha256(b"signalbot-beta-v0:123456789").hexdigest()[:12]   # the old, unkeyed one
    assert admin.fingerprint(123456789) == fp and admin.fingerprint(123456790) != fp
    admin.set_fingerprint_key("j" * 40)
    assert admin.fingerprint(123456789) != fp                          # another key, another pseudonym
    assert admin.fingerprint(None) == "none"


def test_no_key_no_fingerprint_and_no_start(restore_key, monkeypatch):
    monkeypatch.delenv(admin.FINGERPRINT_KEY_ENV, raising=False)
    admin._fingerprint_key = None
    with pytest.raises(admin.FingerprintKeyError):
        admin.fingerprint(1)
    with pytest.raises(admin.FingerprintKeyError):
        admin.set_fingerprint_key("too-short")
    monkeypatch.setenv("BETA_TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("BETA_ENABLED", "1")
    from runtime import beta_bot
    with pytest.raises(SystemExit, match="BETA_FINGERPRINT_KEY"):
        beta_bot.main()


def test_the_key_never_shows_in_repr():
    s = BetaSecrets.from_env({"BETA_TELEGRAM_BOT_TOKEN": "1:x", "BETA_FINGERPRINT_KEY": "secret" * 8})
    assert s.fingerprint_key == "secret" * 8 and "secret" not in repr(s) and "fingerprint_key=set" in repr(s)
