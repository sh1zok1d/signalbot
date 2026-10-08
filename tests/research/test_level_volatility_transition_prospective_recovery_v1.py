"""#368 post-start gap recovery tool. Synthetic archive objects only; no market data, no transition."""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from scripts.research.level_volatility_transition_prospective_confirmation_v1 import recover, surface

UTC = dt.timezone.utc
PKG = Path(recover.__file__).resolve().parent
MANIFEST = surface.load_manifest(surface.MANIFEST)
START = MANIFEST["prospective_start_ms"]


def _iso(ms):
    return surface.to_iso(dt.datetime.fromtimestamp(ms / 1000, UTC))


def _archive(day_ms):
    """A fake daily object: every minute of the UTC day, with its CHECKSUM file."""
    name = "BTCUSDT-1m-" + dt.datetime.fromtimestamp(day_ms / 1000, UTC).strftime("%Y-%m-%d")
    lines = ["open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,"
             "taker_buy_quote_volume,ignore"]
    for m in range(1440):
        t = day_ms + m * 60_000
        lines.append(f"{t},{100 + m},{101 + m},{99 + m},{100.5 + m},{m},{t + 59_999},0,0,0,0,0")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name + ".csv", "\n".join(lines))
    blob = buf.getvalue()
    return {recover.ARCHIVE + name + ".zip": blob,
            recover.ARCHIVE + name + ".zip.CHECKSUM": f"{hashlib.sha256(blob).hexdigest()}  {name}.zip".encode()}


def _fetcher(store, calls):
    def fetch(url):
        calls.append(url)
        return store[url]
    return fetch


def _status(runs, truncated=False):
    return {"forward_panel": {"post_start_coverage": {"missing_runs": runs, "missing_runs_truncated": truncated}}}


def test_the_tool_never_imports_the_estimator_or_outcomes():
    names = []
    for node in ast.walk(ast.parse((PKG / "recover.py").read_text())):
        if isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
            names += [a.name for a in node.names]
        elif isinstance(node, ast.Import):
            names += [a.name for a in node.names]
    joined = " ".join(names)
    for banned in ("evaluate", "claim", "pairing", "rv", "windows", "events", "forward_panel"):
        assert banned not in joined.split(), banned


def test_every_run_is_recovered_from_verified_archive_minutes_and_appended(tmp_path):
    day = START + 86_400_000
    store = {**_archive(START), **_archive(day)}
    calls = []
    runs = [{"from": _iso(day - 120_000), "to": _iso(day + 180_000), "minutes": 5},     # across midnight
            {"from": _iso(START + 600_000), "to": _iso(START + 720_000), "minutes": 2}]
    recs = recover.plan(_status(runs), MANIFEST, fetch=_fetcher(store, calls),
                        now=dt.datetime.fromtimestamp((day + 2 * 86_400_000) / 1000, UTC))
    assert [r["minutes_recovered"] for r in recs] == [2, 5]                            # time order, both runs
    assert [r["rows"][0][0] for r in recs] == [START + 600_000, day - 120_000]
    assert all(r["outcomes_consulted"] is False and r["selection"] == "ALL_MISSING_RUNS_OF_STATUS" for r in recs)
    assert len(recs[1]["objects"]) == 2 and len(calls) == 4                            # each day fetched once
    log = tmp_path / "rec.jsonl"
    assert recover.apply(recs, MANIFEST, path=log) == 2
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert [x["start_ms"] for x in lines] == [START + 600_000, day - 120_000]


def test_refusals_backdating_truncation_checksum_and_unfinished_day():
    store = _archive(START)
    later = dt.datetime.fromtimestamp((START + 3 * 86_400_000) / 1000, UTC)
    with pytest.raises(RuntimeError, match="backdating"):
        recover.plan(_status([{"from": _iso(START - 60_000), "to": _iso(START + 60_000), "minutes": 2}]), MANIFEST,
                     fetch=_fetcher(store, []), now=later)
    with pytest.raises(RuntimeError, match="none chosen"):
        recover.plan(_status([], truncated=True), MANIFEST, fetch=_fetcher(store, []), now=later)
    bad = dict(store)
    key = next(k for k in bad if k.endswith(".CHECKSUM"))
    bad[key] = b"0" * 64
    with pytest.raises(RuntimeError, match="checksum"):
        recover.plan(_status([{"from": _iso(START), "to": _iso(START + 60_000), "minutes": 1}]), MANIFEST,
                     fetch=_fetcher(bad, []), now=later)
    with pytest.raises(RuntimeError, match="not final"):
        recover.plan(_status([{"from": _iso(START), "to": _iso(START + 60_000), "minutes": 1}]), MANIFEST,
                     fetch=_fetcher(store, []), now=dt.datetime.fromtimestamp((START + 3_600_000) / 1000, UTC))
    with pytest.raises(RuntimeError, match="backdating"):
        surface.append_recovery({"start_ms": START - 1}, prospective_start_ms=START, path=Path("/nonexistent"))
