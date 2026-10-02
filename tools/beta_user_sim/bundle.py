"""Read-only replay bundle: the historical user-visible material a replay may use.

A bundle is one JSON file. It holds copies of beta_* rows (no Telegram id, no
user_pk) and, optionally, the live 1m klines the existing outcome tracker reads.
It is produced by `export.py` (SELECT-only, READ ONLY transaction) or by
`synthetic.py` (fully synthetic). The harness never opens a database itself.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

BUNDLE_VERSION = "SIM_REPLAY_BUNDLE_V0"
PROVENANCE_EXPORTED = "EXPORTED_READ_ONLY"
PROVENANCE_SYNTHETIC = "FULLY_SYNTHETIC"
PROVENANCES = (PROVENANCE_EXPORTED, PROVENANCE_SYNTHETIC)

_TS_KEYS = frozenset({
    "requested_at", "recorded_at", "opened_bucket", "opened_at", "armed_at", "triggered_at",
    "terminal_at", "last_bucket", "reference_bucket", "decision_bucket", "decision_ts", "created_at",
    "sending_at", "finished_at", "anchor_ts", "window_end", "computed_at", "ts"})
_FORBIDDEN_KEYS = frozenset({"telegram_user_id", "chat_id", "user_pk", "user_hmac", "telegram_message_id"})


class BundleError(ValueError):
    """A malformed or non-isolated bundle (fail loudly; never guess)."""


def parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise BundleError(f"naive timestamp {value!r}")
    return dt.astimezone(timezone.utc)


def _parse_row(row: Mapping[str, Any]) -> dict:
    bad = _FORBIDDEN_KEYS & set(row)
    if bad:
        raise BundleError(f"bundle row carries personal identifiers: {sorted(bad)}")
    return {k: (parse_ts(v) if k in _TS_KEYS else v) for k, v in row.items()}


def _iso(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    if isinstance(v, tuple):
        return list(v)
    return v


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_iso)


@dataclass(frozen=True)
class ReplayBundle:
    provenance: str
    symbol: str
    exported_at: Optional[datetime]
    # Every episode opened at or after this instant is in the bundle (None: every episode).
    episodes_since: Optional[datetime] = None
    btc_views: Sequence[dict] = field(default_factory=tuple)
    episodes: Sequence[dict] = field(default_factory=tuple)
    transitions: Sequence[dict] = field(default_factory=tuple)
    push_decisions: Sequence[dict] = field(default_factory=tuple)
    deliveries: Sequence[dict] = field(default_factory=tuple)
    outcomes: Sequence[dict] = field(default_factory=tuple)
    klines: Sequence[dict] = field(default_factory=tuple)
    digest: str = ""

    def episode(self, episode_pk: int) -> Optional[dict]:
        return next((e for e in self.episodes if e["episode_pk"] == episode_pk), None)

    def episode_by_public_id(self, public_id: str) -> Optional[dict]:
        return next((e for e in self.episodes if e["public_id"] == public_id), None)


def bundle_from_dict(raw: Mapping[str, Any]) -> ReplayBundle:
    if raw.get("bundle_version") != BUNDLE_VERSION:
        raise BundleError(f"unsupported bundle version {raw.get('bundle_version')!r}")
    if raw.get("provenance") not in PROVENANCES:
        raise BundleError(f"unknown provenance {raw.get('provenance')!r}")
    if raw.get("symbol") != "BTCUSDT":
        raise BundleError("bundle symbol must be BTCUSDT")
    tables = {k: tuple(_parse_row(r) for r in raw.get(k) or ())
              for k in ("btc_views", "episodes", "transitions", "push_decisions", "deliveries",
                        "outcomes", "klines")}
    digest = hashlib.sha256(canonical(raw).encode("utf-8")).hexdigest()
    return ReplayBundle(provenance=raw["provenance"], symbol=raw["symbol"],
                        exported_at=parse_ts(raw.get("exported_at")),
                        episodes_since=parse_ts(raw.get("episodes_since")), digest=digest, **tables)


def bundle_to_dict(b: ReplayBundle) -> dict:
    out = {"bundle_version": BUNDLE_VERSION, "provenance": b.provenance, "symbol": b.symbol,
           "exported_at": _iso(b.exported_at), "episodes_since": _iso(b.episodes_since)}
    for k in ("btc_views", "episodes", "transitions", "push_decisions", "deliveries", "outcomes", "klines"):
        out[k] = [{kk: _iso(vv) for kk, vv in r.items()} for r in getattr(b, k)]
    return out


def load_bundle(path: Path) -> ReplayBundle:
    return bundle_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def write_bundle(raw: Mapping[str, Any], path: Path) -> None:
    Path(path).write_text(canonical(raw), encoding="utf-8")
