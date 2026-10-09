"""Download the frozen Binance Vision kline list. Protected objects are never requested."""

from __future__ import annotations

import gzip
import hashlib
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from beta.history_data import (
    VISION_ROOT,
    checksum_of,
    daily_fallback,
    drop_protected,
    object_protected,
    parse_klines,
    plan_objects,
    url_refusal,
)

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
SERIES_PATH = ROOT / K.SERIES
MANIFEST_PATH = ROOT / K.OBJECTS_MANIFEST
RAW_DIR = Path("/tmp/rp4h-binance-vision")


def planned_klines():
    planned, rejected = plan_objects(date.fromisoformat(K.AS_OF), klines_start=date(2025, 1, 1))
    keep = [obj for obj in planned if obj.kind.startswith("klines")]
    refused = [obj for obj in rejected if obj.kind.startswith("klines")]
    return keep, refused


def _get(url: str) -> bytes | None:
    why = url_refusal(url)
    if why is not None:
        raise SystemExit(f"PROTECTED_URL_REFUSED {why} {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "signalbot-research-range-position/1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _verify(obj) -> tuple[bytes | None, str | None]:
    body = _get(obj.url)
    if body is None:
        return None, None
    chk = _get(obj.url + ".CHECKSUM")
    if chk is None:
        raise SystemExit(f"CHECKSUM_MISSING {obj.key}")
    sha = hashlib.sha256(body).hexdigest()
    if checksum_of(chk.decode("utf-8", "replace")) != sha:
        raise SystemExit(f"CHECKSUM_MISMATCH {obj.key}")
    return body, sha


def materialize() -> dict:
    if object_protected is None:
        raise SystemExit("PLANNER_MISSING")
    planned, refused = planned_klines()
    refused_keys = [obj.key for obj in refused]
    if any(object_protected(obj) is None for obj in refused):
        raise SystemExit("REJECTION_LIST_INCONSISTENT")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    rows_out = []
    pending = list(planned)
    seen = set()
    while pending:
        obj = pending.pop(0)
        if obj.key in seen:
            continue
        seen.add(obj.key)
        if object_protected(obj) is not None:
            raise SystemExit(f"PROTECTED_OBJECT_IN_PLAN {obj.key}")
        body, sha = _verify(obj)
        if body is None:
            records.append({"key": obj.key, "kind": obj.kind, "status": "MISSING", "sha256": None, "rows": 0})
            if obj.kind == "klines_monthly":
                pending[0:0] = daily_fallback(obj)
            continue
        parsed = drop_protected(parse_klines(body), "open_time_ms")
        if any(K.E1_START_MS <= int(row["open_time_ms"]) < K.E1_END_MS for row in parsed):
            raise SystemExit(f"PROTECTED_ROW_SURVIVED {obj.key}")
        (RAW_DIR / obj.key.replace("/", "__")).write_bytes(body)
        records.append({"key": obj.key, "kind": obj.kind, "status": "OK", "sha256": sha, "rows": len(parsed)})
        rows_out.extend(parsed)
    rows_out.sort(key=lambda row: int(row["open_time_ms"]))
    opens = [int(row["open_time_ms"]) for row in rows_out]
    if len(opens) != len(set(opens)):
        raise SystemExit("DUPLICATE_OPEN")
    if any(ms < K.SURFACE_START_MS or ms >= K.SURFACE_END_MS for ms in opens):
        raise SystemExit("ROW_OUTSIDE_SURFACE")
    SERIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SERIES_PATH.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", mtime=0) as gz:
            for row in rows_out:
                line = json.dumps({
                    "open_time_ms": int(row["open_time_ms"]),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                }, separators=(",", ":"), sort_keys=True)
                gz.write(line.encode() + b"\n")
    digest = hashlib.sha256()
    with SERIES_PATH.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    payload = {
        "as_of": K.AS_OF,
        "relation_computed": False,
        "vision_root": VISION_ROOT,
        "requested_rule": "plan_objects klines from 2025-01-01 through yesterday; a missing monthly object falls back to its unprotected days",
        "rejected_not_requested": refused_keys,
        "objects": records,
        "canonical_rows": len(rows_out),
        "canonical_sha256": digest.hexdigest(),
        "first_open_ms": opens[0] if opens else None,
        "last_open_ms": opens[-1] if opens else None,
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"rows {len(rows_out)} objects {len(records)} sha {digest.hexdigest()}", flush=True)
    return payload


if __name__ == "__main__":
    materialize()
