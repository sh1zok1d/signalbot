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
PRIVACY_NOTICE_VERSION = 7
ACTIVITY_ACTIONS = (
    "cmd_start", "cmd_btc", "cmd_history", "cmd_help", "cmd_terms", "cmd_lang", "cmd_stop",
    "cmd_feedback", "tab_event", "tab_1h", "tab_24h", "btn_details", "btn_useful", "btn_noise",
    "lang_set", "push_delivered", "cmd_catchup", "cmd_brief", "brief_delivered", "cmd_push",
    "cmd_levels", "cmd_risk", "cmd_alert", "cmd_events", "cmd_accuracy", "alert_delivered",
    "btn_levels", "btn_risk", "cmd_research",
    "brief_withheld", "btn_other_assets", "btn_btc_now", "tab_research",
    "cmd_check", "btn_check", "btn_watch", "weekly_delivered",
    "cmd_tz", "set_mute", "set_unmute", "cmd_type", "type_set",
    "cmd_idea", "idea_sent", "reason_set", "cmd_interview", "interview_booked",
    "onboard_btc", "cmd_guide", "plain_text",
)

# Monetization readiness (PRE_BETA_SCOPE_DECISION_V1 §6.5, backlog I1): every feature has a tier in code;
# nothing is gated while `access.tiers_enforced` is false, which it is for the whole beta.
TIERS = ("free", "paid")
FEATURE_TIERS = {"btc": "free", "brief": "free", "alerts": "free", "levels": "free", "risk": "free",
                 "check_one_level": "free", "check_two_levels": "paid", "personal_levels": "free",
                 "weekly": "free"}


def feature_open(cfg, user, feature: str) -> bool:
    """True when the participant's tier opens the feature, or always while tiers are not enforced."""
    if not cfg.section("access").get("tiers_enforced"):
        return True
    need = FEATURE_TIERS.get(feature, "paid")
    return need == "free" or (user or {}).get("tier") == "paid"


# the one-tap mute and its undo under a push (backlog E2): settings, never reactions (review of #373, #375)
MUTE_ACTIONS = ("set_mute", "set_unmute")


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
