"""Outcome-blind materialization of same-class perpetual 5m candles.

Binance USD-M BTCUSDT is not re-downloaded. This script fetches only:

- Bybit public MT4 kline, linear BTCUSDT, 5m, months 2020-04 through 2024-12;
- OKX official history-candles, instId BTC-USDT-SWAP, bar 5m, the same window.

No 2025/2026 object is requested. A fencepost bar at or after 2025-01-01 is
dropped before anything is written. No structural outcome is computed.
"""

from __future__ import annotations

import calendar
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research_data" / "LEVEL_CROSS_VENUE_PERP_5M_V0"
BYBIT_RAW = OUT / "bybit_raw"
SURFACE_END_MS = 1735689600000  # 2025-01-01T00:00:00Z
WINDOW_START_MS = 1585699200000  # 2020-04-01T00:00:00Z labeled; Bybit UTC is 3h earlier
BAR_MS = 300_000
BYBIT_LABEL_OFFSET_MS = -3 * 3_600_000
BYBIT_BASE = "https://public.bybit.com/kline_for_metatrader4/BTCUSDT"
OKX_URL = "https://www.okx.com/api/v5/market/history-candles"
UA = "signalbot-level-cross-venue-observability"


def _get(url: str, retries: int = 6) -> bytes:
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (404, 403):
                raise
            time.sleep(0.4 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 — retry transient network faults
            last = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url} ({last})")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _month_name(year: int, month: int) -> str:
    last = calendar.monthrange(year, month)[1]
    return f"BTCUSDT_5_{year:04d}-{month:02d}-01_{year:04d}-{month:02d}-{last:02d}.csv.gz"


def _months():
    year, month = 2020, 4
    while (year, month) <= (2024, 12):
        yield year, month
        month += 1
        if month == 13:
            year, month = year + 1, 1


def _parse_bybit_time(text: str) -> int:
    stamp = datetime.strptime(text, "%Y.%m.%d %H:%M").replace(tzinfo=timezone.utc)
    ms = int(stamp.timestamp() * 1000)
    if ms % BAR_MS != 0:
        raise RuntimeError(f"Bybit bar is off the 5m grid: {text}")
    return ms


def fetch_bybit() -> dict:
    BYBIT_RAW.mkdir(parents=True, exist_ok=True)
    files = []
    rows: dict[int, tuple[float, float, float, float]] = {}
    dropped_2025 = 0
    for year, month in _months():
        name = _month_name(year, month)
        url = f"{BYBIT_BASE}/{year}/{name}"
        try:
            blob = _get(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                files.append({"name": name, "http": 404})
                continue
            raise
        digest = _sha256(blob)
        text = gzip.decompress(blob).decode("utf-8")
        month_rows = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            parts = line.split(",")
            if len(parts) < 5:
                raise RuntimeError(f"short Bybit row in {name}")
            open_ms = _parse_bybit_time(parts[0]) + BYBIT_LABEL_OFFSET_MS
            ohlc = tuple(float(parts[i]) for i in range(1, 5))
            if open_ms >= SURFACE_END_MS:
                dropped_2025 += 1
                continue
            if open_ms < WINDOW_START_MS + BYBIT_LABEL_OFFSET_MS:
                raise RuntimeError(f"Bybit bar before the declared window in {name}")
            previous = rows.get(open_ms)
            if previous is not None and previous != ohlc:
                raise RuntimeError(f"Bybit OHLC conflict at {open_ms}")
            rows[open_ms] = ohlc
            month_rows += 1
        # Persist the public object only when it contains no 2025 bar.
        path = BYBIT_RAW / name
        # Rewrite without any 2025 row so the pinned bytes stay inside 2020-2024.
        kept = []
        local_drop = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            open_ms = _parse_bybit_time(line.split(",")[0])
            if open_ms >= SURFACE_END_MS:
                local_drop += 1
                continue
            kept.append(line)
        payload = gzip.compress(("\n".join(kept) + "\n").encode("utf-8"), mtime=0)
        path.write_bytes(payload)
        files.append({
            "name": name,
            "http": 200,
            "source_sha256": digest,
            "source_bytes": len(blob),
            "pinned_sha256": _sha256(payload),
            "pinned_bytes": len(payload),
            "rows_kept": month_rows,
            "rows_dropped_at_or_after_2025": local_drop,
        })
        print(f"bybit {name} rows={month_rows} drop2025={local_drop}", flush=True)
    ordered = sorted(rows)
    return {
        "files": files,
        "rows": [(ts, *rows[ts]) for ts in ordered],
        "dropped_2025": dropped_2025,
    }


def _okx_page(after_ms: int) -> list:
    url = f"{OKX_URL}?instId=BTC-USDT-SWAP&bar=5m&limit=100&after={after_ms}"
    payload = json.loads(_get(url).decode("utf-8"))
    if payload.get("code") != "0":
        raise RuntimeError(f"OKX error {payload.get('code')} {payload.get('msg')}")
    return payload.get("data") or []


def _fetch_okx_slice(start_ms: int, end_ms: int) -> list[tuple]:
    cursor = end_ms
    out = []
    seen = set()
    guard = 0
    while cursor > start_ms:
        guard += 1
        if guard > 20000:
            raise RuntimeError("OKX pagination did not terminate")
        page = _okx_page(cursor)
        if not page:
            if guard == 1:
                raise RuntimeError(f"OKX returned no candles before {end_ms}")
            break
        stamps = []
        for row in page:
            if len(row) < 9:
                raise RuntimeError("short OKX candle")
            ts = int(row[0])
            stamps.append(ts)
            if ts >= SURFACE_END_MS:
                raise RuntimeError(f"OKX returned a bar at or after 2025: {ts}")
            if ts < start_ms or ts >= end_ms:
                continue
            if str(row[8]) != "1":
                continue
            if ts in seen:
                continue
            seen.add(ts)
            out.append((ts, float(row[1]), float(row[2]), float(row[3]), float(row[4])))
        oldest = min(stamps)
        if oldest >= cursor:
            raise RuntimeError("OKX pagination cursor did not move backward")
        cursor = oldest
        if oldest <= start_ms:
            break
    return out


def fetch_okx() -> dict:
    slices = []
    for year, month in _months():
        start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
        if month == 12:
            end = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        else:
            end = int(datetime(year, month + 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        end = min(end, SURFACE_END_MS)
        slices.append((start, end))
    merged: dict[int, tuple] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_okx_slice, start, end): (start, end) for start, end in slices}
        for future in as_completed(futures):
            start, end = futures[future]
            rows = future.result()
            for row in rows:
                previous = merged.get(row[0])
                if previous is not None and previous != row[1:]:
                    raise RuntimeError(f"OKX OHLC conflict at {row[0]}")
                merged[row[0]] = row[1:]
            print(f"okx {start} rows={len(rows)}", flush=True)
    ordered = sorted(merged)
    return {"rows": [(ts, *merged[ts]) for ts in ordered]}


def _write_csv(path: Path, rows: list[tuple]) -> str:
    lines = ["open_ms,open,high,low,close"]
    for ts, o, h, l, c in rows:
        if int(ts) >= SURFACE_END_MS:
            raise RuntimeError("refusing to store a 2025 bar")
        lines.append(f"{int(ts)},{o:.10g},{h:.10g},{l:.10g},{c:.10g}")
    blob = gzip.compress(("\n".join(lines) + "\n").encode("utf-8"), mtime=0)
    path.write_bytes(blob)
    return _sha256(blob)


def _gaps(rows: list[tuple]) -> dict:
    if not rows:
        return {"n": 0}
    stamps = [int(row[0]) for row in rows]
    if stamps != sorted(stamps) or len(stamps) != len(set(stamps)):
        raise RuntimeError("canonical series is not a unique ordered grid")
    missing = []
    longest = 0
    run = 0
    for left, right in zip(stamps, stamps[1:]):
        step = (right - left) // BAR_MS
        if (right - left) % BAR_MS != 0 or step < 1:
            raise RuntimeError("off-grid step")
        gap = step - 1
        if gap:
            missing.append({"from_open_ms": left + BAR_MS, "to_open_ms_exclusive": right, "bars": gap})
            run = max(run, gap)
    return {
        "n": len(stamps),
        "first_open_ms": stamps[0],
        "last_open_ms": stamps[-1],
        "first_open": datetime.fromtimestamp(stamps[0] / 1000, timezone.utc).isoformat(),
        "last_open": datetime.fromtimestamp(stamps[-1] / 1000, timezone.utc).isoformat(),
        "missing_bars": int(sum(item["bars"] for item in missing)),
        "missing_runs": len(missing),
        "longest_missing_run_bars": int(run),
        "missing_runs_head": missing[:12],
    }


def _trade_identity(bybit_rows: list[tuple]) -> dict:
    """One UTC day of public trades versus the 5m kline. Provenance only."""
    url = "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2020-04-01.csv.gz"
    blob = _get(url)
    text = gzip.decompress(blob).decode("utf-8").splitlines()
    header = text[0].split(",")
    if header[:6] != ["timestamp", "symbol", "side", "size", "price", "tickDirection"]:
        raise RuntimeError(f"unexpected trade header {header[:6]}")
    buckets: dict[int, list[tuple[float, float]]] = {}
    n_trades = 0
    for line in text[1:]:
        parts = line.split(",")
        if parts[1] != "BTCUSDT":
            raise RuntimeError("trade file is not BTCUSDT")
        ts = float(parts[0])
        px = float(parts[4])
        open_ms = int(ts * 1000) // BAR_MS * BAR_MS
        buckets.setdefault(open_ms, []).append((ts, px))
        n_trades += 1
    kline = {int(row[0]): row[1:5] for row in bybit_rows}
    compared = 0
    matched = 0
    mismatches = []
    for open_ms, prints in sorted(buckets.items()):
        bar = kline.get(open_ms)
        if bar is None:
            continue
        chrono = sorted(prints)
        prices = [px for _, px in chrono]
        o, h, l, c = prices[0], max(prices), min(prices), prices[-1]
        compared += 1
        if (o, h, l, c) == tuple(bar):
            matched += 1
        elif len(mismatches) < 5:
            mismatches.append({"open_ms": open_ms, "trade": [o, h, l, c], "kline": list(bar)})
    return {
        "day": "2020-04-01",
        "source": url,
        "source_sha256": _sha256(blob),
        "trades": n_trades,
        "bars_compared": compared,
        "bars_exact_ohlc_match": matched,
        "exact_match_rate": None if compared == 0 else matched / compared,
        "mismatch_examples": mismatches,
        "note": "Public trade tape sorted by exchange timestamp. OHLC uses the first, max, min and last trade inside each 5m bin. The trade file is not retained.",
    }


def canonical_from_raw() -> list[tuple]:
    """Apply the frozen UTC+3 offset to pinned labeled files. No download."""
    rows: dict[int, tuple] = {}
    for path in sorted(BYBIT_RAW.glob("BTCUSDT_5_*.csv.gz")):
        with gzip.open(path, "rt") as handle:
            for line in handle:
                if not line.strip():
                    continue
                parts = line.strip().split(",")
                open_ms = _parse_bybit_time(parts[0]) + BYBIT_LABEL_OFFSET_MS
                if open_ms >= SURFACE_END_MS or open_ms < WINDOW_START_MS + BYBIT_LABEL_OFFSET_MS:
                    raise RuntimeError(f"pinned Bybit row leaves the UTC window: {parts[0]}")
                ohlc = tuple(float(parts[i]) for i in range(1, 5))
                previous = rows.get(open_ms)
                if previous is not None and previous != ohlc:
                    raise RuntimeError(f"Bybit OHLC conflict at {open_ms}")
                rows[open_ms] = ohlc
    return [(ts, *rows[ts]) for ts in sorted(rows)]


def _close_audit(day: str, trade_path: Path) -> dict:
    from collections import defaultdict
    buckets = defaultdict(list)
    blob = trade_path.read_bytes()
    text = gzip.decompress(blob).decode("utf-8").splitlines()
    for line in text[1:]:
        parts = line.split(",")
        ts = float(parts[0])
        buckets[(int(ts) // 300) * 300 * 1000].append((ts, float(parts[4])))
    trade_close = {key: sorted(values)[-1][1] for key, values in buckets.items()}
    labeled = {}
    year = day[:4]
    raw = next(BYBIT_RAW.glob(f"BTCUSDT_5_{year}-{day[5:7]}*.csv.gz"))
    with gzip.open(raw, "rt") as handle:
        for line in handle:
            parts = line.strip().split(",")
            labeled[_parse_bybit_time(parts[0])] = float(parts[4])
    diffs = []
    for stamp, price in labeled.items():
        utc = stamp + BYBIT_LABEL_OFFSET_MS
        other = trade_close.get(utc)
        if other is None:
            continue
        diffs.append(other - price)
    if not diffs:
        raise RuntimeError(f"no overlap for {day}")
    exact = sum(1 for value in diffs if abs(value) <= 1e-9)
    max_abs = max(abs(value) for value in diffs)
    return {
        "day": day,
        "shift_hours": -3,
        "bars_compared": len(diffs),
        "close_exact": exact,
        "close_match_rate": exact / len(diffs),
        "max_abs_close_diff": max_abs,
        "trade_sha256": _sha256(blob),
    }


def rebuild_clock() -> None:
    rows = canonical_from_raw()
    bybit_sha = _write_csv(OUT / "bybit_btcusdt_linear_5m.csv.gz", rows)
    manifest = json.loads((OUT / "MANIFEST.json").read_text())
    manifest["venues"]["bybit"]["census"] = _gaps(rows)
    manifest["venues"]["bybit"]["canonical_sha256"] = bybit_sha
    manifest["venues"]["bybit"]["clock_offset_hours"] = -3
    manifest["venues"]["bybit"]["timestamp"] = (
        "MT4 label minus 3 hours. The label is a fixed UTC+3 clock, not European DST. "
        "Canonical open_ms is the UTC open."
    )
    manifest["venues"]["okx"]["clock_offset_hours"] = 0
    audits = [
        _close_audit("2020-04-01", Path("/tmp/bybit_trades_20200401.csv.gz")),
        _close_audit("2020-07-15", Path("/tmp/bybit_trades_20200715.csv.gz")),
    ]
    manifest["trade_close_audits"] = audits
    manifest["outcomes_read"] = False
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"census": manifest["venues"]["bybit"]["census"], "audits": audits}, indent=2))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bybit = fetch_bybit()
    okx = fetch_okx()
    bybit_sha = _write_csv(OUT / "bybit_btcusdt_linear_5m.csv.gz", bybit["rows"])
    okx_sha = _write_csv(OUT / "okx_btc_usdt_swap_5m.csv.gz", okx["rows"])
    identity = _trade_identity(bybit["rows"])
    manifest = {
        "dataset_id": "LEVEL_CROSS_VENUE_PERP_5M_V0",
        "tier_candidate": "TIER_A",
        "venues": {
            "bybit": {
                "instrument": "BTCUSDT",
                "contract_type": "linear perpetual",
                "quote_margin": "USDT",
                "source": BYBIT_BASE,
                "native_grain": "5m",
                "kind": "OHLC",
                "timestamp": "bar open, UTC, parsed from YYYY.MM.DD HH:MM",
                "price": "public kline OHLC; identity versus the public trade tape is recorded separately",
                "window": "[2020-04-01T00:00:00Z, 2025-01-01T00:00:00Z)",
                "census": _gaps(bybit["rows"]),
                "files": bybit["files"],
                "canonical_sha256": bybit_sha,
                "rows_dropped_at_or_after_2025": bybit["dropped_2025"],
            },
            "okx": {
                "instrument": "BTC-USDT-SWAP",
                "contract_type": "linear perpetual swap",
                "quote_margin": "USDT",
                "settle_ccy": "USDT",
                "ct_val": "0.01 BTC",
                "source": OKX_URL,
                "native_grain": "5m",
                "kind": "OHLC history-candles, confirm=1 only",
                "timestamp": "candle open time in milliseconds, UTC",
                "price": "instrument last-price candle, not mark-price-candles and not index",
                "window": "[2020-04-01T00:00:00Z, 2025-01-01T00:00:00Z)",
                "census": _gaps(okx["rows"]),
                "canonical_sha256": okx_sha,
            },
        },
        "trade_identity_2020_04_01": identity,
        "protected_2025_2026_requested": False,
        "outcomes_read": False,
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "bybit": manifest["venues"]["bybit"]["census"],
        "okx": manifest["venues"]["okx"]["census"],
        "identity": identity,
    }, indent=2))


if __name__ == "__main__":
    main()
