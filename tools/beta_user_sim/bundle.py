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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

BUNDLE_VERSION = "SIM_REPLAY_BUNDLE_V0"
PROVENANCE_EXPORTED = "EXPORTED_READ_ONLY"
PROVENANCE_SYNTHETIC = "FULLY_SYNTHETIC"
PROVENANCES = (PROVENANCE_EXPORTED, PROVENANCE_SYNTHETIC)

# Export scopes. Sealed 2025/2026 research data is never exportable under any scope;
# the only modern data is operational private-beta data recorded prospectively.
EXPORT_META_VERSION = "SIM_EXPORT_SCOPE_V0"
SCOPE_PRE_2025_UNSEALED = "PRE_2025_UNSEALED"
SCOPE_LIVE_BETA_PROSPECTIVE = "LIVE_BETA_PROSPECTIVE"
EXPORT_SCOPES = (SCOPE_PRE_2025_UNSEALED, SCOPE_LIVE_BETA_PROSPECTIVE)
SEALED_RESEARCH_FROM = datetime(2025, 1, 1, tzinfo=timezone.utc)
# Private beta V0 authorization date (docs/PRIVATE_BETA_V0_RESTART_DECISION.md).
LIVE_BETA_FROM = datetime(2026, 9, 25, tzinfo=timezone.utc)
LIVE_BETA_AUTHORIZATION_REF = "SYNTHETIC_BETA_USER_V0_OWNER_AUTH_2026_10_02"
LIVE_BETA_AUTHORITY_DOC = "docs/PRIVATE_BETA_V0_RESTART_DECISION.md"
# Exported klines extend past the window end by the longest outcome horizon plus this tail.
LONGEST_HORIZON = timedelta(hours=24)
KLINE_TAIL = timedelta(minutes=5)
_EXPORT_META_KEYS = frozenset({"export_meta_version", "export_scope", "authorization_ref", "authority_doc",
                               "requested_start", "requested_end", "exported_at", "live_beta_from"})

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


def check_export_window(scope: str, start: datetime, end: datetime) -> None:
    """The one rule for which windows a scope may cover. Raises BundleError."""
    if end <= start:
        raise BundleError("export window needs end > start")
    if scope == SCOPE_PRE_2025_UNSEALED:
        if end + LONGEST_HORIZON + KLINE_TAIL > SEALED_RESEARCH_FROM:
            raise BundleError(
                "window (with its 24h outcome tail) reaches the sealed 2025+ research period; only "
                f"{SCOPE_LIVE_BETA_PROSPECTIVE} windows starting at or after {LIVE_BETA_FROM.date()} may be "
                "exported after 2024")
    elif scope == SCOPE_LIVE_BETA_PROSPECTIVE:
        if start < LIVE_BETA_FROM:
            raise BundleError(
                f"{SCOPE_LIVE_BETA_PROSPECTIVE} starts at {LIVE_BETA_FROM.isoformat()}; earlier 2025/2026 "
                "windows are sealed research data and are not exportable")
    else:
        raise BundleError(f"unknown export scope {scope!r}")


def export_metadata(scope: str, *, start: datetime, end: datetime, exported_at: datetime) -> dict:
    check_export_window(scope, start, end)
    live = scope == SCOPE_LIVE_BETA_PROSPECTIVE
    return {"export_meta_version": EXPORT_META_VERSION, "export_scope": scope,
            "authorization_ref": LIVE_BETA_AUTHORIZATION_REF if live else None,
            "authority_doc": LIVE_BETA_AUTHORITY_DOC if live else None,
            "requested_start": _iso(start), "requested_end": _iso(end), "exported_at": _iso(exported_at),
            "live_beta_from": _iso(LIVE_BETA_FROM) if live else None}


def _validate_export(raw: Mapping[str, Any], tables: Mapping[str, tuple]) -> Optional[dict]:
    meta = raw.get("export")
    if raw["provenance"] == PROVENANCE_SYNTHETIC:
        if meta is not None:
            raise BundleError("a fully synthetic bundle carries no export metadata")
        return None
    if not isinstance(meta, Mapping) or set(meta) != _EXPORT_META_KEYS:
        raise BundleError("exported bundle needs complete export metadata (scope, authorization, window)")
    if meta["export_meta_version"] != EXPORT_META_VERSION:
        raise BundleError(f"unsupported export metadata version {meta['export_meta_version']!r}")
    scope = meta["export_scope"]
    start, end = parse_ts(meta["requested_start"]), parse_ts(meta["requested_end"])
    exported_at = parse_ts(meta["exported_at"])
    if start is None or end is None or exported_at is None:
        raise BundleError("export metadata needs requested_start, requested_end and exported_at")
    check_export_window(scope, start, end)
    if exported_at != parse_ts(raw.get("exported_at")):
        raise BundleError("export metadata exported_at differs from the bundle exported_at")
    if scope == SCOPE_LIVE_BETA_PROSPECTIVE:
        if (meta["authorization_ref"] != LIVE_BETA_AUTHORIZATION_REF or meta["authority_doc"] != LIVE_BETA_AUTHORITY_DOC
                or parse_ts(meta["live_beta_from"]) != LIVE_BETA_FROM):
            raise BundleError(f"{SCOPE_LIVE_BETA_PROSPECTIVE} bundle lacks the owner authorization "
                              f"{LIVE_BETA_AUTHORIZATION_REF}")
        lo, hi = LIVE_BETA_FROM, None
    else:
        if any(meta[k] is not None for k in ("authorization_ref", "authority_doc", "live_beta_from")):
            raise BundleError(f"{SCOPE_PRE_2025_UNSEALED} bundle must not carry a live-beta authorization")
        lo, hi = None, SEALED_RESEARCH_FROM
    eps = parse_ts(raw.get("episodes_since"))
    stamps = [eps] if eps is not None else []
    stamps += [v for rows in tables.values() for r in rows for k, v in r.items() if k in _TS_KEYS and v is not None]
    for ts in stamps:
        if (lo is not None and ts < lo) or (hi is not None and ts >= hi):
            raise BundleError(f"{scope} bundle holds a row timestamped {ts.isoformat()} outside its scope")
    return dict(meta)


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
    # Export scope and authorization provenance; None only for fully synthetic bundles.
    export: Optional[Mapping[str, Any]] = None
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
    export = _validate_export(raw, tables)
    digest = hashlib.sha256(canonical(raw).encode("utf-8")).hexdigest()
    return ReplayBundle(provenance=raw["provenance"], symbol=raw["symbol"],
                        exported_at=parse_ts(raw.get("exported_at")),
                        episodes_since=parse_ts(raw.get("episodes_since")), export=export, digest=digest, **tables)


def bundle_to_dict(b: ReplayBundle) -> dict:
    out = {"bundle_version": BUNDLE_VERSION, "provenance": b.provenance, "symbol": b.symbol,
           "exported_at": _iso(b.exported_at), "episodes_since": _iso(b.episodes_since)}
    if b.export is not None:
        out["export"] = dict(b.export)
    for k in ("btc_views", "episodes", "transitions", "push_decisions", "deliveries", "outcomes", "klines"):
        out[k] = [{kk: _iso(vv) for kk, vv in r.items()} for r in getattr(b, k)]
    return out


def load_bundle(path: Path) -> ReplayBundle:
    return bundle_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def write_bundle(raw: Mapping[str, Any], path: Path) -> None:
    Path(path).write_text(canonical(raw), encoding="utf-8")
