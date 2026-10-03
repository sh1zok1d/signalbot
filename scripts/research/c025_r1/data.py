"""Pinned CORE_BTC_BINANCE_V0 1m loader for 2020-01..2024-12 only.

Checksums come from the frozen source inventory. Months from 2025-01 onward
are not selected. Parsed panels are cached under /tmp after verification.
"""

from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from .constants import DATASET_ID, DATASET_MANIFEST_DIGEST, HISTORICAL_WINDOW

REPO = Path(__file__).resolve().parents[3]
INVENTORY = REPO / "docs/research_data/CORE_BTC_BINANCE_V0/SOURCE_INVENTORY_717d37a4.json"
DEFAULT_CACHE = Path("/tmp/c025_r1_cache")
MINUTE_MS = 60_000
DISCOVERY_START_MS = 1577836800000  # 2020-01-01T00:00:00Z
DISCOVERY_END_MS = 1735689600000  # 2025-01-01T00:00:00Z


def legal_months() -> list[str]:
    months = [f"{year}-{month:02d}" for year in range(2020, 2025) for month in range(1, 13)]
    if months[0] != "2020-01" or months[-1] != "2024-12" or any(m >= "2025-01" for m in months):
        raise RuntimeError("legal month list left 2020-01..2024-12")
    if len(months) != 60:
        raise RuntimeError("expected 60 legal months")
    return months


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pinned_sources() -> list[dict]:
    inventory = json.loads(INVENTORY.read_text())
    if inventory.get("dataset_id") != DATASET_ID:
        raise RuntimeError("inventory dataset id drifted")
    by_month = {
        row["source_period"]: row
        for row in inventory["objects"]
        if row.get("archive_class") == "monthly" and row.get("symbol") == "BTCUSDT" and row.get("interval") == "1m"
    }
    pinned = []
    for month in legal_months():
        row = by_month.get(month)
        if row is None:
            raise RuntimeError(f"pinned month {month} is absent")
        if month >= "2025-01":
            raise RuntimeError("protected month selected")
        url = row["source_url"]
        if "2025" in url or "2026" in url or "/1m/" not in url:
            raise RuntimeError(f"refusing url {url}")
        pinned.append({
            "MONTH": month,
            "URL": url,
            "SHA256": row["expected_sha256"],
            "FILENAME": row["expected_zip_filename"],
            "CSV": row["expected_csv_member_name"],
        })
    return pinned


def dataset_digest() -> str:
    body = [{"MONTH": row["MONTH"], "SHA256": row["SHA256"]} for row in pinned_sources()]
    payload = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def fetch_verified_zip(spec: dict, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / spec["FILENAME"]
    if not dest.exists() or _sha256(dest) != spec["SHA256"]:
        urllib.request.urlretrieve(spec["URL"], dest)
    if _sha256(dest) != spec["SHA256"]:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"checksum mismatch for {spec['FILENAME']}")
    return dest


def read_pinned_minutes(path: Path, csv_name: str) -> np.ndarray:
    """Columns: open_time_ms, open, close, quote_volume, taker_buy_quote_volume."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if names != [csv_name]:
            raise RuntimeError(f"unexpected zip members in {path.name}: {names}")
        payload = archive.read(csv_name)
    if payload[:1].isalpha():
        payload = payload.split(b"\n", 1)[1]
    raw = np.loadtxt(io.BytesIO(payload), delimiter=",", usecols=(0, 1, 4, 7, 10))
    if raw.ndim != 2 or raw.shape[1] != 5:
        raise RuntimeError(f"unexpected columns in {path.name}")
    return raw


def load_panel(cache: Path | None = None) -> dict[str, np.ndarray]:
    """Gapless discovery panel. Raises if any 2025/2026 timestamp is present."""
    cache = cache or DEFAULT_CACHE
    digest = dataset_digest()
    parsed = cache / f"panel_{digest[:16]}.npz"
    if parsed.exists():
        loaded = np.load(parsed)
        panel = {key: loaded[key] for key in loaded.files}
        _assert_discovery_bounds(panel)
        return panel

    parts = []
    for spec in pinned_sources():
        path = fetch_verified_zip(spec, cache)
        part = read_pinned_minutes(path, spec["CSV"])
        parts.append(part)
        print(f"C025_R1 loaded {spec['MONTH']} rows={part.shape[0]}", flush=True)
    raw = np.concatenate(parts, axis=0)
    order = np.argsort(raw[:, 0], kind="mergesort")
    raw = raw[order]
    open_ms = np.rint(raw[:, 0]).astype(np.int64)
    panel = {
        "open_ms": open_ms,
        "open": raw[:, 1].astype(np.float64),
        "close": raw[:, 2].astype(np.float64),
        "quote": raw[:, 3].astype(np.float64),
        "taker_quote": raw[:, 4].astype(np.float64),
    }
    _assert_discovery_bounds(panel)
    cache.mkdir(parents=True, exist_ok=True)
    np.savez(parsed, **panel)
    return panel


def _assert_discovery_bounds(panel: dict[str, np.ndarray]) -> None:
    open_ms = panel["open_ms"]
    if open_ms.size == 0:
        raise RuntimeError("empty panel")
    if int(open_ms[0]) != DISCOVERY_START_MS:
        raise RuntimeError("panel does not start at 2020-01-01")
    if int(open_ms[-1]) != DISCOVERY_END_MS - MINUTE_MS:
        raise RuntimeError("panel does not end at 2024-12-31 23:59")
    if int(open_ms.max()) >= DISCOVERY_END_MS:
        raise RuntimeError("2025 or later timestamp entered the discovery panel")
    diffs = np.diff(open_ms)
    if not np.all(diffs == MINUTE_MS):
        raise RuntimeError("discovery minutes are not a gapless 1m grid")
    if np.any(panel["open"] <= 0) or np.any(panel["close"] <= 0):
        raise RuntimeError("non-positive price in the discovery panel")
    if np.any(panel["quote"] < 0) or np.any(panel["taker_quote"] < 0):
        raise RuntimeError("negative volume in the discovery panel")
    if np.any(panel["taker_quote"] > panel["quote"] + 1e-6):
        raise RuntimeError("taker-buy quote exceeds quote volume")


def dataset_identity() -> dict:
    sources = pinned_sources()
    return {
        "DATASET_ID": DATASET_ID,
        "MANIFEST_DIGEST": DATASET_MANIFEST_DIGEST,
        "ZIP_LIST_SHA256": dataset_digest(),
        "HISTORICAL_WINDOW": HISTORICAL_WINDOW,
        "MONTHS": [row["MONTH"] for row in sources],
        "MONTH_SHA256": {row["MONTH"]: row["SHA256"] for row in sources},
        "PROTECTED_2025_2026_SELECTED": False,
    }
