"""Participant pseudonyms (owner decision 2026-10-08): `u_` + HMAC-SHA-256(key, str(telegram_user_id)) hex[:12].

A keyed pseudonym, not anonymous data: whoever holds the key can recompute it. The key is the .env secret
BETA_FINGERPRINT_KEY (at least 32 bytes, hex or base64), read once at process start by the bot, the beta
CLI (notifier and every --beta-* command) and the user simulator. It is held only in this module, never
printed, logged, or put in errors, health or reports. Without a key `fingerprint` refuses (fail closed).

Twelve hex characters (48 bits) as before: for the beta's tens to hundreds of participants the birthday
chance of a collision is about n²/2^49 (≈ 2·10⁻¹⁰ at 250), and `/admin_reply` refuses an ambiguous one.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import re
from typing import Mapping, Optional

KEY_ENV = "BETA_FINGERPRINT_KEY"
MIN_KEY_BYTES = 32
GENERATE_HINT = "generate one with: openssl rand -hex 32"

_KEY: Optional[bytes] = None


class FingerprintKeyError(ValueError):
    """The key is missing or malformed. The message never carries the value."""


def parse_key(raw: Optional[str]) -> bytes:
    raw = (raw or "").strip()
    if not raw:
        raise FingerprintKeyError(f"{KEY_ENV} is not set; {GENERATE_HINT}")
    key = None
    if re.fullmatch(r"[0-9a-fA-F]+", raw) and len(raw) % 2 == 0:
        key = bytes.fromhex(raw)
    else:
        try:
            key = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            key = None
    if key is None or len(key) < MIN_KEY_BYTES:
        raise FingerprintKeyError(f"{KEY_ENV} must be at least {MIN_KEY_BYTES} bytes of hex or base64; "
                                  f"{GENERATE_HINT}")
    return key


def install_key(key: bytes) -> None:
    global _KEY
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
        raise FingerprintKeyError(f"the fingerprint key must be at least {MIN_KEY_BYTES} bytes")
    _KEY = bytes(key)


def install_key_from_env(env: Optional[Mapping[str, str]] = None) -> None:
    """At process start. Raises FingerprintKeyError (no value in the message) when missing or malformed."""
    install_key(parse_key((os.environ if env is None else env).get(KEY_ENV)))


def key_installed() -> bool:
    return _KEY is not None


def clear_key() -> None:
    """Tests only: back to the no-key state."""
    global _KEY
    _KEY = None


def legacy_pseudonym(telegram_user_id: int) -> str:
    """The unkeyed form printed before the switch: audit rows written then still hold it, so the deletion path
    de-identifies both forms (#420). Never used for a new row."""
    return "u_" + hashlib.sha256(f"signalbot-beta-v0:{int(telegram_user_id)}".encode()).hexdigest()[:12]


def pseudonym(telegram_user_id: int) -> str:
    if _KEY is None:
        raise FingerprintKeyError(f"{KEY_ENV} was not loaded at start; fingerprints are refused")
    return "u_" + hmac.new(_KEY, str(int(telegram_user_id)).encode(), hashlib.sha256).hexdigest()[:12]
