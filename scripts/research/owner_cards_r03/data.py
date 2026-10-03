"""Pinned loaders for the R03 program. Every byte is SHA256-verified against a
committed ledger. No 2025/2026 object is ever selected.

- BTCUSDT perpetual 1m 2020-01..2024-12 (CORE_BTC_BINANCE_V0 inventory);
- BitMEX XBTUSD 5m 2016-05..2019-12 (D2_BITMEX_PRE2020_XBTUSD canonical gz);
- Binance spot USDT daily panel 2019-12..2024-12 (SPRINT04 object ledger);
- NYSE holiday calendar events (NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0).
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from . import constants as K

REPO = Path(__file__).resolve().parents[3]
BTC_INVENTORY = REPO / "docs/research_data/CORE_BTC_BINANCE_V0/SOURCE_INVENTORY_717d37a4.json"
BITMEX_GZ = REPO / "docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz"
BITMEX_AUTHORITY = REPO / "docs/research_data/D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json"
PANEL_LEDGER = REPO / "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/object_ledger.json"
PANEL_EXCLUSIONS = REPO / "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/EXCLUSION_LISTS.json"
NYSE_EVENTS = REPO / "docs/research_data/NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0/EVENTS.json"
S3_ORIGIN = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/"
PROTECTED_RE = re.compile(r"(2025|2026)-\d{2}")


def cache_root() -> Path:
    return Path(os.environ.get("R03_CACHE", "/tmp/owner_cards_r03_cache"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(url: str, dest: Path, expected_sha256: str) -> Path:
    if PROTECTED_RE.search(url):
        raise RuntimeError(f"refusing protected url {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or sha256_file(dest) != expected_sha256:
        req = urllib.request.Request(url, headers={"User-Agent": "signalbot-research/owner-cards-r03"})
        with urllib.request.urlopen(req, timeout=180) as response:
            dest.write_bytes(response.read())
    if sha256_file(dest) != expected_sha256:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"checksum mismatch for {dest.name}")
    return dest


# ---------------------------------------------------------------- BTC 1m
def legal_months() -> list[str]:
    months = [f"{y}-{m:02d}" for y in range(2020, 2025) for m in range(1, 13)]
    if len(months) != 60 or months[-1] != "2024-12":
        raise RuntimeError("legal month list drifted")
    return months


def btc_pinned_sources() -> list[dict]:
    inventory = json.loads(BTC_INVENTORY.read_text())
    if inventory.get("dataset_id") != K.DATASET_BTC:
        raise RuntimeError("BTC inventory dataset id drifted")
    rows = {
        r["source_period"]: r for r in inventory["objects"]
        if r.get("archive_class") == "monthly" and r.get("symbol") == "BTCUSDT" and r.get("interval") == "1m"
    }
    out = []
    for month in legal_months():
        row = rows.get(month)
        if row is None:
            raise RuntimeError(f"pinned month {month} absent")
        key = row["source_url"].split("data.binance.vision/")[1]
        out.append({"MONTH": month, "KEY": key, "SHA256": row["expected_sha256"],
                    "FILENAME": row["expected_zip_filename"], "CSV": row["expected_csv_member_name"]})
    return out


def btc_dataset_digest() -> str:
    body = [{"MONTH": r["MONTH"], "SHA256": r["SHA256"]} for r in btc_pinned_sources()]
    return hashlib.sha256(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def _read_kline_zip(path: Path, csv_name: str, usecols: tuple[int, ...]) -> np.ndarray:
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != [csv_name]:
            raise RuntimeError(f"unexpected members in {path.name}")
        payload = archive.read(csv_name)
    if payload[:1].isalpha():
        payload = payload.split(b"\n", 1)[1]
    raw = np.loadtxt(io.BytesIO(payload), delimiter=",", usecols=usecols, ndmin=2)
    if raw.ndim != 2:
        raise RuntimeError(f"unexpected shape in {path.name}")
    return raw


def load_btc_1m() -> dict[str, np.ndarray]:
    """open_ms, open, high, low, close, quote for 2020-01-01..2024-12-31, gapless."""
    cache = cache_root() / "btc_1m"
    parsed = cache / f"panel_{btc_dataset_digest()[:16]}.npz"
    if parsed.exists():
        loaded = np.load(parsed)
        panel = {k: loaded[k] for k in loaded.files}
        _assert_btc_bounds(panel)
        return panel
    parts = []
    for spec in btc_pinned_sources():
        path = _fetch(S3_ORIGIN + spec["KEY"], cache / spec["FILENAME"], spec["SHA256"])
        parts.append(_read_kline_zip(path, spec["CSV"], (0, 1, 2, 3, 4, 7)))
    raw = np.concatenate(parts, axis=0)
    raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
    panel = {
        "open_ms": np.rint(raw[:, 0]).astype(np.int64),
        "open": raw[:, 1], "high": raw[:, 2], "low": raw[:, 3], "close": raw[:, 4], "quote": raw[:, 5],
    }
    _assert_btc_bounds(panel)
    cache.mkdir(parents=True, exist_ok=True)
    np.savez(parsed, **panel)
    return panel


def _assert_btc_bounds(panel: dict) -> None:
    t = panel["open_ms"]
    if int(t[0]) != K.DISCOVERY_START_MS or int(t[-1]) != K.DISCOVERY_END_MS - K.MINUTE_MS:
        raise RuntimeError("BTC panel bounds are not 2020-01-01..2024-12-31")
    if not np.all(np.diff(t) == K.MINUTE_MS):
        raise RuntimeError("BTC 1m grid has gaps")
    if np.any(panel["low"] <= 0) or np.any(panel["high"] < panel["low"]):
        raise RuntimeError("BTC high/low malformed")


# ---------------------------------------------------------------- BitMEX 5m
def load_bitmex_5m() -> dict[str, np.ndarray]:
    """open_ms, open, high, low, close, trades on a 5m grid; missing buckets are absent."""
    authority = json.loads(BITMEX_AUTHORITY.read_text())
    if sha256_file(BITMEX_GZ) != authority["canonical_jsonl_gz_sha256"]:
        raise RuntimeError("BitMEX canonical gz digest drifted")
    cache = cache_root() / "bitmex_5m.npz"
    if cache.exists():
        loaded = np.load(cache)
        return {k: loaded[k] for k in loaded.files}
    rows = []
    with gzip.open(BITMEX_GZ, "rt") as handle:
        for line in handle:
            r = json.loads(line)
            rows.append((r["open_time_ms"], r["open"], r["high"], r["low"], r["close"], r["trades"]))
    raw = np.array(rows, dtype=np.float64)
    raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
    t = np.rint(raw[:, 0]).astype(np.int64)
    if np.any(np.diff(t) <= 0) or int(t.max()) >= K.DISCOVERY_START_MS:
        raise RuntimeError("BitMEX grid malformed or crosses 2020")
    panel = {"open_ms": t, "open": raw[:, 1], "high": raw[:, 2], "low": raw[:, 3], "close": raw[:, 4],
             "trades": raw[:, 5]}
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **panel)
    return panel


# ---------------------------------------------------------------- panel
def panel_ledger_objects() -> list[dict]:
    ledger = json.loads(PANEL_LEDGER.read_text())
    objs = ledger["objects"]
    for o in objs:
        if PROTECTED_RE.search(o["key"]) or not ("2019-12" <= o["month"] <= "2024-12"):
            raise RuntimeError(f"illegal panel object {o['key']}")
    return objs


def panel_ledger_digest() -> str:
    body = sorted((o["key"], o["expected_sha256"]) for o in panel_ledger_objects())
    return hashlib.sha256(json.dumps(body, separators=(",", ":")).encode()).hexdigest()


def excluded_symbols() -> dict[str, str]:
    return dict(json.loads(PANEL_EXCLUSIONS.read_text())["EXCLUDED_SYMBOLS"])


def load_panel_daily(raw_root: Path | None = None) -> dict[str, dict[str, np.ndarray]]:
    """symbol -> {open_ms, close, quote}. Every zip is verified against the ledger."""
    raw_root = raw_root or Path(os.environ.get("R03_PANEL_RAW", str(cache_root() / "panel_raw")))
    cache = cache_root() / f"panel_daily_{panel_ledger_digest()[:16]}.npz"
    if cache.exists():
        loaded = np.load(cache, allow_pickle=False)
        symbols = [s for s in loaded["symbols"]]
        out = {}
        for s in symbols:
            out[s] = {"open_ms": loaded[f"{s}__t"], "close": loaded[f"{s}__c"], "quote": loaded[f"{s}__q"]}
        return out
    per_symbol: dict[str, list[np.ndarray]] = {}
    verified = 0
    for o in panel_ledger_objects():
        path = raw_root / o["key"]
        if not path.is_file():
            raise RuntimeError(f"panel object missing: {o['key']}")
        if sha256_file(path) != o["expected_sha256"]:
            raise RuntimeError(f"panel sha mismatch: {o['key']}")
        verified += 1
        raw = _read_kline_zip(path, o["key"].rsplit("/", 1)[1].replace(".zip", ".csv"), (0, 4, 7))
        per_symbol.setdefault(o["symbol"], []).append(raw)
    out = {}
    for s, parts in per_symbol.items():
        raw = np.concatenate(parts, axis=0)
        raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
        t = raw[:, 0]
        t = np.where(t > 1e14, t // 1000, t)  # microsecond timestamps appear in late 2024 files
        t = np.rint(t).astype(np.int64)
        if np.any(np.diff(t) <= 0):
            raise RuntimeError(f"duplicate day in {s}")
        if int(t.max()) >= K.DISCOVERY_END_MS:
            raise RuntimeError(f"protected day in {s}")
        out[s] = {"open_ms": t, "close": raw[:, 1], "quote": raw[:, 2]}
    arrays = {"symbols": np.array(sorted(out), dtype="U32")}
    for s, d in out.items():
        arrays[f"{s}__t"] = d["open_ms"]; arrays[f"{s}__c"] = d["close"]; arrays[f"{s}__q"] = d["quote"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **arrays)
    print(f"R03 panel verified objects={verified} symbols={len(out)}", flush=True)
    return out


# ---------------------------------------------------------------- NYSE
def nyse_events() -> list[dict]:
    events = json.loads(NYSE_EVENTS.read_text())
    return [e for e in events if e["EVENT_TYPE"] in ("FULL_DAY_CLOSURE", "EARLY_CLOSE")]


def dataset_identity() -> dict:
    return {
        "BTC": {"DATASET_ID": K.DATASET_BTC, "ZIP_LIST_SHA256": btc_dataset_digest(), "MONTHS": "2020-01..2024-12"},
        "BITMEX": {"DATASET_ID": K.DATASET_BITMEX, "GZ_SHA256": sha256_file(BITMEX_GZ)},
        "PANEL": {"DATASET_ID": K.DATASET_PANEL, "LEDGER_KEYSET_SHA256": panel_ledger_digest(),
                  "OBJECTS": len(panel_ledger_objects())},
        "NYSE": {"DATASET_ID": K.DATASET_NYSE, "EVENTS_SHA256": sha256_file(NYSE_EVENTS)},
        "PROTECTED_2025_2026_SELECTED": False,
    }
