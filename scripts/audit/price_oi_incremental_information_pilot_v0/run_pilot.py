"""Owner-executable PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0. Read-only.

Run on the database host from a checkout of this repository, with
``SIGNALBOT_DSN`` already set in the environment (never on the command line):

    python -m scripts.audit.price_oi_incremental_information_pilot_v0.run_pilot \\
        --out-dir /tmp/price_oi_incremental_information_pilot_v0

The session is UTC and read-only; queries are SELECT-only and keep
``source = 'live'``. The DSN is never printed. Output is written only under
``/tmp``. No production table is written. Pilot only; not confirmatory; no
trading claim.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from beta.config import BetaConfig
from beta.state_tape import reference_price
from common.stage2_config import STAGE2_CONFIG_PATH, Stage2Config
from common.versioning import resolve_feature_code_version
from scripts.audit.live_archive_replay_preflight import price_oi_semantic_replay as semantic
from scripts.audit.live_archive_replay_preflight import run_price_oi_semantic_replay as replay
from scripts.audit.live_archive_replay_preflight.extract_coverage_readonly import (
    _connect, _run_select, redact)
from scripts.audit.live_archive_replay_preflight.extract_sql import assert_text_read_only

from . import pilot

UTC = timezone.utc
OWNER_OUT_DIR = "/tmp/price_oi_incremental_information_pilot_v0"
KLINE_SQL = """
SELECT exchange, ts, open, high, low, close, volume
FROM klines_1m
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND source = 'live'
  AND ts >= TIMESTAMPTZ '2026-07-17 19:30:00+00'
  AND ts < TIMESTAMPTZ '2026-09-29 04:00:00+00'
ORDER BY exchange, ts
"""
OBSERVATION_COLUMNS = ("family", "group", "anchor", "exclusion", *pilot.MATCHED_COVARIATES,
                       "log_prior_range_24h", *pilot.TIME_COVARIATES, "range_1h_pct", "range_4h_pct")


def pilot_sql() -> tuple[str, str]:
    for text in (KLINE_SQL, replay.OI_SQL):
        assert_text_read_only(text)
        if "source = 'live'" not in text or "backfill" in text.lower():
            raise ValueError("pilot SQL must keep source = 'live' and never read backfill")
    if "2026-09-29 04:00:00+00" not in KLINE_SQL:
        raise ValueError("kline read end differs from the frozen protocol")
    return KLINE_SQL, replay.OI_SQL


def main(argv: list[str] | None = None, *, connect=None, code_version: str | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Read-only {pilot.PILOT_ID}")
    parser.add_argument("--out-dir", default=OWNER_OUT_DIR)
    args = parser.parse_args(argv)
    out = Path(args.out_dir).resolve()
    if out.parts[:2] != ("/", "tmp"):
        print("--out-dir must be under /tmp", file=sys.stderr)
        return 2
    pilot.check_protocol()
    dsn = os.environ.get("SIGNALBOT_DSN", "").strip()
    if not dsn:
        print("SIGNALBOT_DSN is not set. Refusing to guess a database.", file=sys.stderr)
        return 2
    version = code_version or resolve_feature_code_version()
    try:
        conn, driver = (connect or _connect)(dsn)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"database connection failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    try:
        kline_sql, oi_sql = pilot_sql()
        _h, kline_rows = _run_select(conn, driver, kline_sql)
        _h, oi_rows = _run_select(conn, driver, oi_sql)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"pilot read failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    try:
        result = run(kline_rows, oi_rows, code_version=version)
        write_outputs(out, result)
    except Exception as exc:  # noqa: BLE001
        print(f"pilot failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    print(pilot.assert_allowed_wording(summary_lines(result, out)))
    return 0


def run(kline_rows, oi_rows, *, code_version: str) -> dict:
    cfg = BetaConfig.load()
    stage2 = Stage2Config.load(STAGE2_CONFIG_PATH)
    try:
        rebuilt = replay.build_replay(kline_rows, oi_rows, code_version=code_version)
    except SystemExit as exc:
        return _blocked(f"REPLAY_REFUSED:{exc}")
    prepared = rebuilt["prepared"]
    if len(prepared) != pilot.EXPECTED_AUTHORIZED_BUCKETS:
        return _blocked(f"AUTHORIZED_BUCKETS={len(prepared)}")
    bars, _offslot = replay._group_bars(kline_rows)
    oi = replay._group_oi(oi_rows)
    klines = pilot.KlineIndex(_kline_dicts(kline_rows))
    by_bucket = {item.reconstruction.bucket_ts: item for item in prepared}
    families, observations = {}, []
    for family in pilot.FAMILIES:
        replay_anchors = sorted(item.episode.triggered_at for item in rebuilt["episodes"]
                                if item.episode.event_type == family and item.episode.triggered_at)
        event_anchors = pilot.triggered_anchors(cfg, family, prepared, pilot.event_status)
        blocked = None
        if event_anchors != replay_anchors:
            blocked = "EVENT_LIFECYCLE_DIFFERS_FROM_REPLAY"
        elif len(event_anchors) != pilot.EXPECTED_TRIGGERED[family]:
            blocked = f"TRIGGERED={len(event_anchors)}_EXPECTED={pilot.EXPECTED_TRIGGERED[family]}"
        control_anchors = pilot.triggered_anchors(cfg, family, prepared, pilot.control_status)
        if set(control_anchors) & set(event_anchors):
            raise RuntimeError("event and control anchors overlap; ablation is not disjoint")

        def build(group, anchor):
            item = by_bucket[anchor - pilot.BUCKET]
            ref = _reference(stage2, cfg, item.reconstruction.bucket_ts, bars, oi, code_version)
            return pilot.observe(family, group, anchor, price_move=item.reconstruction.price_median,
                                 reference=ref, klines=klines)

        events = [build("A", a) for a in event_anchors]
        controls = [build("B", a) for a in control_anchors]
        observations.extend(events + controls)
        report = pilot.evaluate_family(family, events, controls, data_blocked_reason=blocked)
        report["p4_eligible_reference"] = pilot.P4_ELIGIBLE[family]
        report["p4_eligible_count_match"] = report.get("events_eligible") == pilot.P4_ELIGIBLE[family]
        report["event_anchors_triggered"] = len(event_anchors)
        report["control_anchors_triggered"] = len(control_anchors)
        families[family] = report
    final = pilot.final_classification({f: r["verdict"] for f, r in families.items()})
    return {**_header(), "families": families, "final_classification": final,
            "observations": observations, "live_kline_rows": len(kline_rows),
            "live_oi_rows": len(oi_rows)}


def _reference(stage2, cfg, bucket, bars, oi, code_version) -> dict:
    vectors = []
    for venue in semantic.VENUES:
        try:
            vectors.append(semantic._venue_feature(stage2, venue, bucket, bars.get(bucket, {}).get(venue, ()),
                                                   oi.get(bucket, {}).get(venue, ()),
                                                   code_version=code_version))
        except Exception:  # noqa: BLE001 - same per-venue tolerance as reconstruct_bucket
            continue
    return reference_price(SimpleNamespace(exchange_features=vectors), cfg)


def _kline_dicts(rows):
    for exchange, ts, _open, high, low, close, _volume in rows:
        moment = replay._utc(ts)
        if moment < pilot.KLINE_READ_END:
            yield {"exchange": exchange, "ts": moment, "high": float(high), "low": float(low),
                   "close": float(close)}


def _header() -> dict:
    return {"pilot_id": pilot.PILOT_ID, "classification": "PILOT_ONLY", "confirmatory": False,
            "trading_claim": False, "provenance": semantic.PROVENANCE,
            "replay_class": semantic.REPLAY_CLASS, "production_tables_written": False,
            "protected_2025_2026_opened": False, "long_history_used": False}


def _blocked(reason: str) -> dict:
    families = {f: pilot.evaluate_family(f, [], [], data_blocked_reason=reason) for f in pilot.FAMILIES}
    return {**_header(), "families": families, "final_classification": pilot.DATA_BLOCKED,
            "observations": []}


def write_outputs(out: Path, result: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    doc = {k: v for k, v in result.items() if k != "observations"}
    (out / "pilot_result.json").write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")
    with (out / "observations.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OBSERVATION_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for o in result["observations"]:
            row = {"family": o.family, "group": o.group, "anchor": pilot._iso(o.anchor),
                   "exclusion": o.exclusion or "", "range_1h_pct": o.ranges.get("1h"),
                   "range_4h_pct": o.ranges.get("4h")}
            row.update({k: o.covariates.get(k) for k in OBSERVATION_COLUMNS if k in o.covariates})
            writer.writerow({k: "" if v is None else v for k, v in row.items()})


def summary_lines(result: dict, out: Path) -> str:
    lines = [f"{pilot.PILOT_ID} (PILOT_ONLY; not confirmatory; no trading claim)"]
    for family, r in result["families"].items():
        line = f"{family} VERDICT={r['verdict']} reason={r['verdict_reason']}"
        if "endpoint" in r:
            line += (f" median_ratio_4h={r['endpoint']['4h']['median_range_ratio']:.3f}"
                     f" median_ratio_1h={r['endpoint']['1h']['median_range_ratio']:.3f}"
                     f" matched={r['support']['matched_events']}"
                     f" clusters_4h={r['declustering']['clusters_4h']}")
        lines.append(line)
    lines.append(f"FINAL_CLASSIFICATION={result['final_classification']}")
    lines.append(f"OUTPUT={out}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
