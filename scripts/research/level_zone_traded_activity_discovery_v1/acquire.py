"""Download the months the event windows need, reduce them, delete the raw zip.

python3 -m scripts.research.level_zone_traded_activity_discovery_v1.acquire
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from scripts.research.dh1.data import UA, VISION, _refuse_protected
from scripts.research.dh1 import data as D1

from . import constants as K
from .trades import (
    assert_month_legal, empty_acc, finalize_record, sha256_file, stream_zip,
)
from .windows import build_windows, required_months

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "docs" / "research_data" / K.TRADE_DATASET_ID
AGGREGATES = OUT_DIR / "event_aggregates.json"
INVENTORY = OUT_DIR / "SOURCE_INVENTORY.json"


def _download(key: str, dest: Path) -> str:
    published = D1._get(VISION + key + ".CHECKSUM").decode().split()[0]
    if dest.exists() and sha256_file(dest) == published:
        return published
    tmp = dest.with_suffix(".part")
    request = urllib.request.Request(VISION + key, headers=UA)
    with urllib.request.urlopen(request, timeout=600) as response, open(tmp, "wb") as handle:
        while True:
            chunk = response.read(1 << 22)
            if not chunk:
                break
            handle.write(chunk)
    tmp.replace(dest)
    got = sha256_file(dest)
    if got != published:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"{key}: checksum mismatch")
    return published


def _events_for_month(events: list[dict], month: str) -> list[dict]:
    from .windows import months_covering
    return [ev for ev in events if month in months_covering(ev["pre_ms"], ev["d_ms"])]


def run() -> dict:
    import datetime as dt
    events = build_windows()
    months = required_months(events)
    for month in months:
        assert_month_legal(month)
        _refuse_protected(dt.date.fromisoformat(month + "-01"))
    cache = D1.cache_root() / "zone_trades"
    cache.mkdir(parents=True, exist_ok=True)
    acc: dict = {}
    objects = []
    multi = 0
    assigned = 0
    rows = 0
    try:
        for month in months:
            key = K.UM_KEY.format(m=month)
            path = cache / Path(key).name
            print("download", month, flush=True)
            digest = _download(key, path)
            print("reduce", month, path.stat().st_size, flush=True)
            try:
                stats = stream_zip(path, _events_for_month(events, month), acc, surface_end_ms=K.EVENT_END_MS)
            finally:
                path.unlink(missing_ok=True)
            multi += int(stats["multi_event_trades"])
            assigned += int(stats["assigned_trades"])
            rows += int(stats["rows"])
            objects.append({
                "MONTH": month,
                "KEY": key,
                "SHA256": digest,
                "ROWS": int(stats["rows"]),
                "HEADER": bool(stats["header"]),
                "CHECKSUM_VERIFICATION": "VERIFIED",
                "NOTIONAL_AUDIT": stats.get("notional_audit"),
                "RAW_DELETED": True,
            })
            print("month done", month, stats["rows"], flush=True)
    finally:
        for leftover in cache.glob("*.zip"):
            leftover.unlink(missing_ok=True)
    records = [finalize_record(key, bucket) for key, bucket in acc.items()]
    records.sort(key=lambda row: row["key"])
    covered = {row["key"] for row in records}
    for ev in events:
        if ev["key"] not in covered:
            records.append(finalize_record(ev["key"], empty_acc()))
    records.sort(key=lambda row: row["key"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_id": K.TRADE_DATASET_ID,
        "archive_id": K.ARCHIVE_ID,
        "n_events": len(events),
        "n_records": len(records),
        "n_multi_event_trades": multi,
        "n_assigned_trades": assigned,
        "n_trade_rows": rows,
        "double_counts_across_events": multi > 0,
        "records": records,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    AGGREGATES.write_text(text)
    agg_sha = D1.sha256_bytes(AGGREGATES.read_bytes())
    inventory = {
        "DATASET_ID": K.TRADE_DATASET_ID,
        "ARCHIVE_ID": K.ARCHIVE_ID,
        "SOURCE": VISION,
        "INSTRUMENT": "Binance USD-M BTCUSDT perpetual aggTrades",
        "QUANTITY_UNIT": "BTC base; quote notional = price * quantity USDT",
        "AGGRESSOR_SIDE_USED": False,
        "MONTHS": months,
        "N_EVENTS": len(events),
        "AGGREGATES_FILE": AGGREGATES.name,
        "AGGREGATES_SHA256": agg_sha,
        "N_MULTI_EVENT_TRADES": multi,
        "DOUBLE_COUNTS_ACROSS_EVENTS": multi > 0,
        "OBJECTS": objects,
        "RAW_RETAINED": False,
    }
    inventory["OBJECT_LIST_SHA256"] = D1.sha256_bytes(
        json.dumps([[obj["MONTH"], obj["SHA256"]] for obj in objects], separators=(",", ":")).encode()
    )
    INVENTORY.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    return inventory


if __name__ == "__main__":
    run()
