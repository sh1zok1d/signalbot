"""Invite codes and rejected-/start digests.

Codes are 12 characters from the Telegram /start payload alphabet. A rejected
/start stores an HMAC of the Telegram id, or a daily count when the salt is
unset. The raw id is never written on that path.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from typing import Mapping, Optional

INVITE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
INVITE_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{12}$")
PRIVACY_NOTICE_VERSION = 4
ACTIVITY_ACTIONS = (
    "cmd_start", "cmd_btc", "cmd_history", "cmd_help", "cmd_terms", "cmd_lang", "cmd_stop",
    "cmd_feedback", "tab_event", "tab_1h", "tab_24h", "btn_details", "btn_useful", "btn_noise",
    "lang_set", "push_delivered", "cmd_catchup", "cmd_brief", "brief_delivered", "cmd_push",
    "cmd_levels", "cmd_risk", "cmd_alert", "cmd_events", "cmd_accuracy", "alert_delivered",
    "btn_levels", "btn_risk",
)


def generate_invite_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(12))


def invite_link(bot_username: str, code: str) -> str:
    return f"t.me/{bot_username}?start={code}"


def start_code(args: str) -> Optional[str]:
    """First token of a /start payload when it is a valid invite code."""
    token = (args or "").split(" ", 1)[0].strip()
    if INVITE_CODE_RE.fullmatch(token):
        return token
    return None


def telemetry_salt(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    source = os.environ if env is None else env
    raw = (source.get("BETA_TELEMETRY_SALT") or "").strip()
    return raw or None


def rejected_hmac(salt: str, telegram_user_id: int) -> str:
    """HMAC-SHA256(salt, decimal telegram id). The id itself is not returned."""
    message = str(int(telegram_user_id)).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), message, hashlib.sha256).hexdigest()
