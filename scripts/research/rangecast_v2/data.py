"""The product history surface for RANGECAST_V2: Binance USD-M BTCUSDT 5m klines from data.binance.vision,
planned by the product planner (`beta.history_data.plan_objects`), which never plans an object that
overlaps the E1-RUN-001 final holdout. Every request also passes `url_refusal` (fail closed), every object
is checked against its published CHECKSUM, and the zips are cached outside the repository.

This is the surface the production range model is fitted on (PRODUCT_DECISION_V2 §4). It is exposed:
nothing read here is an independent confirmation.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from beta import hist_series as hs
from beta import history_data as hd

DATA_END = date(2026, 10, 12)          # objects through 2026-10-11 (the day before this unit started)


def cache_root() -> Path:
    return Path(os.environ.get("RANGECAST_V2_CACHE", "/tmp/rangecast_v2_cache"))


def kline_objects(today: date = DATA_END) -> tuple:
    planned, rejected = hd.plan_objects(today)
    return [o for o in planned if o.kind.startswith("klines")], [o for o in rejected if o.kind.startswith("klines")]


def _get(url: str) -> Optional[bytes]:
    why = hd.url_refusal(url)
    if why is not None:
        raise hd.ProtectedObjectRefused(f"{why}: {url.rsplit('/', 1)[-1]}")
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def fetch_object(obj) -> dict:
    path = cache_root() / obj.key
    if path.exists() and path.with_suffix(".zip.sha256").exists():
        sha = path.with_suffix(".zip.sha256").read_text().strip()
        if hashlib.sha256(path.read_bytes()).hexdigest() == sha:
            return {"key": obj.key, "sha256": sha, "status": "CACHED"}
    body = _get(obj.url)
    if body is None:
        return {"key": obj.key, "sha256": None, "status": "MISSING"}
    chk = _get(obj.url + ".CHECKSUM")
    sha = hashlib.sha256(body).hexdigest()
    if chk is None or hd.checksum_of(chk.decode("utf-8", "replace")) != sha:
        raise hd.HistoryDataError(f"checksum mismatch or missing for {obj.key}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.with_suffix(".zip.sha256").write_text(sha)
    return {"key": obj.key, "sha256": sha, "status": "FETCHED"}


def sync(today: date = DATA_END, workers: int = 6) -> dict:
    planned, rejected = kline_objects(today)
    with ThreadPoolExecutor(workers) as ex:
        got = list(ex.map(fetch_object, planned))
    manifest = {"source": hd.VISION_ROOT, "symbol": hd.SYMBOL, "data_end_exclusive": today.isoformat(),
                "objects": sorted(got, key=lambda r: r["key"]),
                "refused_before_request": sorted(o.key for o in rejected)}
    body = json.dumps(manifest["objects"], sort_keys=True).encode()
    manifest["objects_sha256"] = hashlib.sha256(body).hexdigest()
    return manifest


def load_bars(today: date = DATA_END) -> tuple:
    """(Bars on the 5m grid from 2020-01-01, manifest). Bars inside a protected window never exist
    (their objects are not requested); rows are dropped again by timestamp as a second guard."""
    manifest = sync(today)
    rows = []
    for rec in manifest["objects"]:
        if rec["sha256"] is None:
            continue
        rows.extend(hd.parse_klines((cache_root() / rec["key"]).read_bytes()))
    rows = hd.drop_protected(rows, "open_time_ms")
    rows.sort(key=lambda r: r["open_time_ms"])
    dedup, seen = [], set()
    for r in rows:
        if r["open_time_ms"] not in seen:
            seen.add(r["open_time_ms"])
            dedup.append(r)
    end_ms = int(datetime(today.year, today.month, today.day, tzinfo=timezone.utc).timestamp() * 1000)
    b = hs.bars_from_rows(dedup, start_ms=int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),
                          end_ms=end_ms)
    return b, manifest
