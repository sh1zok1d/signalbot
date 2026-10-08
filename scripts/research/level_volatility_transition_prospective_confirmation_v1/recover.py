"""Post-start gap recovery for the prospective panel (design §Data; panel binding note).

Protocol, unchanged: a gap after the start is filled only from the official Binance USD-M archive
(data.binance.vision daily 1m klines, checksum-verified), only for open times at or after the
prospective start, and only through `surface.append_recovery` into the recovery log. Every missing
run the owner's `status --live-db` printed is recovered; none is chosen. A truncated run list is
refused (the status lists at most 50). Nothing here reads a transition, an RV, a barrier, a pseudo
or a pair: it copies archive minutes. Default is a dry run; `--apply` appends.

    python -m scripts.research.level_volatility_transition_prospective_confirmation_v1.recover \
        --status status.json [--apply]

This module must not import the transition estimator.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from . import constants as K
from .surface import MANIFEST, RECOVERY_LOG, UTC, append_recovery, load_manifest, parse_utc, to_iso, to_ms

ARCHIVE = "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m/"
SOURCE = "BINANCE_UM_DAILY_KLINES_1M_ARCHIVE"
MINUTE_MS = 60_000
DAY_MS = 86_400_000
RECOVERY_VERSION = "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_RECOVERY_TOOL_V1"

Fetch = Callable[[str], bytes]


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "signalbot-research/368-recovery"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def missing_runs(status: dict) -> list[dict]:
    cov = ((status.get("forward_panel") or {}).get("post_start_coverage")) or {}
    if "missing_runs" not in cov:
        raise RuntimeError("status has no post-start coverage (run status --live-db after the start)")
    if cov.get("missing_runs_truncated"):
        raise RuntimeError("status listed only part of the missing runs; every gap must be recovered, none chosen")
    return list(cov["missing_runs"])


def _day_objects(start_ms: int, end_ms: int) -> list[str]:
    days = range(start_ms // DAY_MS, (end_ms - 1) // DAY_MS + 1)
    return [dt.datetime.fromtimestamp(d * DAY_MS / 1000, UTC).strftime("%Y-%m-%d") for d in days]


def _verified_rows(day: str, fetch: Fetch) -> tuple[list[list], dict]:
    name = f"BTCUSDT-1m-{day}"
    blob = fetch(ARCHIVE + name + ".zip")
    checksum = fetch(ARCHIVE + name + ".zip.CHECKSUM").decode().split()[0].strip().lower()
    sha = hashlib.sha256(blob).hexdigest()
    if sha != checksum:
        raise RuntimeError(f"checksum mismatch for {name}.zip")
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        if archive.namelist() != [name + ".csv"]:
            raise RuntimeError(f"unexpected members in {name}.zip")
        text = archive.read(name + ".csv").decode()
    rows = []
    for line in text.splitlines():
        if not line or line[0].isalpha():
            continue
        f = line.split(",")
        rows.append([int(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[4]), float(f[5])])
    return rows, {"object": name + ".zip", "url": ARCHIVE + name + ".zip", "sha256": sha}


def plan(status: dict, manifest: dict, *, fetch: Fetch = _fetch, now: Optional[dt.datetime] = None) -> list[dict]:
    """One recovery record per missing run, in time order, with the archive minutes of that run."""
    start_ms = int(manifest["prospective_start_ms"])
    now_ms = to_ms(now or dt.datetime.now(UTC))
    status_digest = hashlib.sha256(json.dumps(status, sort_keys=True).encode()).hexdigest()
    cache: dict = {}
    out = []
    for run in sorted(missing_runs(status), key=lambda r: r["from"]):
        lo, hi = to_ms(parse_utc(run["from"])), to_ms(parse_utc(run["to"]))
        if lo < start_ms:
            raise RuntimeError(f"gap {run['from']} starts before the prospective start: backdating")
        if lo >= hi or (hi - lo) // MINUTE_MS != int(run["minutes"]):
            raise RuntimeError(f"malformed run {run}")
        objects, minutes = [], []
        for day in _day_objects(lo, hi):
            if parse_utc(day + "T00:00:00Z").timestamp() * 1000 + DAY_MS > now_ms:
                raise RuntimeError(f"the daily archive of {day} is not final yet; retry after that day")
            if day not in cache:
                cache[day] = _verified_rows(day, fetch)
            rows, meta = cache[day]
            objects.append(meta)
            minutes += [r for r in rows if lo <= r[0] < hi]
        minutes.sort(key=lambda r: r[0])
        out.append({"unit": K.UNIT, "tool": RECOVERY_VERSION, "source": SOURCE, "start_ms": lo, "end_ms": hi,
                    "from": run["from"], "to": run["to"], "minutes_missing": int(run["minutes"]),
                    "minutes_recovered": len(minutes), "objects": objects,
                    "rows_columns": ["open_ms", "open", "high", "low", "close", "volume"], "rows": minutes,
                    "selection": "ALL_MISSING_RUNS_OF_STATUS", "status_digest": status_digest,
                    "outcomes_consulted": False, "recorded_at": to_iso(dt.datetime.fromtimestamp(now_ms / 1000, UTC))})
    return out


def apply(records: list[dict], manifest: dict, *, path: Path = RECOVERY_LOG) -> int:
    for r in records:
        append_recovery(r, prospective_start_ms=int(manifest["prospective_start_ms"]), path=path)
    return len(records)


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", required=True, help="the JSON printed by status --live-db")
    parser.add_argument("--apply", action="store_true", help="append to the recovery log (default: dry run)")
    args = parser.parse_args(argv)
    manifest = load_manifest(MANIFEST)
    records = plan(json.loads(Path(args.status).read_text()), manifest)
    summary = [{k: r[k] for k in ("from", "to", "minutes_missing", "minutes_recovered", "objects")} for r in records]
    if args.apply:
        print(json.dumps({"appended": apply(records, manifest), "runs": summary}, indent=2))
    else:
        print(json.dumps({"dry_run": True, "runs": summary}, indent=2))


if __name__ == "__main__":
    main()
