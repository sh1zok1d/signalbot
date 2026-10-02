"""The only data shape Role A ever receives: what a Telegram user can see.

Messages are plain text (Telegram HTML rendered to text), a visible timestamp,
visible button labels with opaque per-run button ids, and whether the message
arrived while the user was AVAILABLE, BUSY or SLEEPING. Real callback data is
never exposed (it carries internal row ids); the harness keeps the mapping.
"""
from __future__ import annotations

import html as _html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional, Sequence

from beta.i18n import fmt_kyiv_date_hm

AVAILABLE, BUSY, SLEEPING = "AVAILABLE", "BUSY", "SLEEPING"
ATTENTION_STATES = (AVAILABLE, BUSY, SLEEPING)
NOTICE_NO_REPLY = "Your last action produced no visible reply."
NOTICES = (NOTICE_NO_REPLY,)


@dataclass(frozen=True)
class VisibleButton:
    button_id: str
    label: str


@dataclass(frozen=True)
class VisibleMessage:
    message_id: str
    received_at: str
    arrived_while: str
    text: str
    buttons: Sequence[VisibleButton] = ()
    edit_of: Optional[str] = None


@dataclass(frozen=True)
class UserTurn:
    now: str
    new_messages: Sequence[VisibleMessage] = ()
    notices: Sequence[str] = ()
    popups: Sequence[str] = ()

    def to_json(self) -> str:
        data = asdict(self)
        assert_role_a_safe(data)
        return json.dumps(data, ensure_ascii=False, sort_keys=True)


def visible_time(dt: datetime) -> str:
    return fmt_kyiv_date_hm(dt, "en")


def html_to_text(html_text: str) -> str:
    text = re.sub(r"<[^>]+>", "", html_text or "")
    return _html.unescape(text).strip()


# Content that never appears in any rendered Signalbot string but would identify
# internals: repository paths, file names, full digests / commit ids, store keys,
# raw callback data with row ids, research vocabulary and outcome field names.
_LEAK_PATTERNS = [
    r"/workspace", r"(?<![\w])(?:docs|beta|runtime|storage|tools|scripts|config|tests)/[\w./-]+",
    r"\b[\w-]+\.(?:py|md|json|ya?ml|sql|parquet)\b", r"\b[0-9a-f]{40}\b", r"\b[0-9a-f]{64}\b",
    r"\b(?:view_pk|episode_pk|user_pk|payload_digest|rules_digest|config_digest|state_digest|"
    r"outcome_version|outcome_digest|max_up_pct|max_down_pct|close_return_pct|realized_range_pct|"
    r"evaluation_class|claim_id|directional_claim)\b",
    r"\b[oe]:\d+:(?:event|1h|24h)\b", r"\bRESEARCH_LEDGER\b", r"\bMARKET-0\d\b", r"\bRULE_1\b",
    r"\bDESCRIPTIVE_MONITORING\b", r"\bSYNTHETIC\b", r"\bROLE_B\b", r"\bbaseline_version\b",
]


class LeakError(AssertionError):
    pass


def _strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def assert_role_a_safe(obj: Any) -> Any:
    for s in _strings(obj):
        for pat in _LEAK_PATTERNS:
            if re.search(pat, s):
                raise LeakError(f"Role A context leak matched {pat!r}")
    return obj
