"""Owner-executable semantic PRICE_OI replay. Read-only. No production writes.

Run on the database host, from a checkout of this repository, with
``SIGNALBOT_DSN`` already set:

    python -m scripts.audit.live_archive_replay_preflight.run_price_oi_semantic_replay \\
        --out-dir /tmp/live_archive_price_oi_semantic_replay_v0

The session is UTC and read-only. Queries are SELECT-only and keep
``source = 'live'``. Volume is selected only because the current bar
validator requires a finite volume; instrument metadata is not loaded, so
volume and taker notionals are not computed. Open-interest magnitudes and
OHLC values are not written to the output.

After it finishes, copy the directory to the cursor account:

    mkdir -p /home/cursor/exports && cp -a /tmp/live_archive_price_oi_semantic_replay_v0 /home/cursor/exports/live_archive_price_oi_semantic_replay_v0

The output is a reconstructed semantic replay. It is not a record of alerts
the production runtime certainly emitted.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from analytics.feature_engine.models import KlineBar, OpenInterestObservation
from beta.config import BetaConfig
from common.stage2_config import STAGE2_CONFIG_PATH, Stage2Config
from common.versioning import resolve_feature_code_version

from .extract_coverage_readonly import _connect, _run_select, redact
from .extract_sql import assert_text_read_only
from .price_oi_semantic_replay import (
    AUTHORIZED_FAMILIES,
    HISTORY_START,
    INTERVALS,
    PHASE_A_AUTHORIZED_BUCKETS,
    PROVENANCE,
    REPLAY_CLASS,
    SEMANTIC_DISCLAIMER,
    BucketReconstruction,
    PreparedBucket,
    authorized_buckets,
    current_percentiles,
    history_buckets,
    in_frozen_gap,
    iso,
    metrics_of,
    reconstruct_bucket,
    replay_series,
    samples_before,
    source_interval,
)

UTC = timezone.utc
OWNER_OUT_DIR = "/tmp/live_archive_price_oi_semantic_replay_v0"
HISTORY_END_EXCLUSIVE = INTERVALS[-1][1] + timedelta(minutes=5)
KLINE_SQL = """
SELECT exchange, ts, open, high, low, close, volume
FROM klines_1m
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND source = 'live'
  AND ts >= TIMESTAMPTZ '2026-07-17 19:30:00+00'
  AND ts < TIMESTAMPTZ '2026-09-29 00:00:00+00'
ORDER BY exchange, ts
"""
OI_SQL = """
SELECT exchange, ts, oi_raw, oi_unit
FROM open_interest
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND source = 'live'
  AND oi_raw IS NOT NULL
  AND oi_unit IS NOT NULL
  AND ts >= TIMESTAMPTZ '2026-07-17 19:30:00+00'
  AND ts < TIMESTAMPTZ '2026-09-29 00:00:00+00'
ORDER BY exchange, ts
"""
EVALUATION_COLUMNS = (
    "bucket_ts", "event_type", "rule_status", "reason", "streak",
    "price_move_pct_median", "oi_change_pct_median",
    "price_percentile_rank", "oi_percentile_rank", "price_maturity", "oi_maturity",
    "price_contributing_venues", "oi_contributing_venues", "source_interval",
    "provenance", "replay_class", "historical_freshness_state",
    "historical_coherence_race_state", "historical_alert_delivery",
)
EPISODE_COLUMNS = (
    "episode_id", "event_type", "state", "opened_bucket", "armed_at", "triggered_at",
    "terminal_at", "terminal_reason", "qualifying_bucket_count", "source_interval",
    "provenance", "replay_class", "historical_freshness_state",
    "historical_coherence_race_state", "historical_alert_delivery",
)


def replay_sql() -> tuple[str, str]:
    assert_text_read_only(KLINE_SQL)
    assert_text_read_only(OI_SQL)
    for text in (KLINE_SQL, OI_SQL):
        if "source = 'live'" not in text:
            raise ValueError("replay SQL must keep source = 'live'")
        if "backfill" in text.lower():
            raise ValueError("replay SQL must not mention backfill")
    return KLINE_SQL, OI_SQL


def main(argv: list[str] | None = None, *, connect=None, code_version: str | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only PRICE_OI semantic reconstruction")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    dsn = os.environ.get("SIGNALBOT_DSN", "").strip()
    if not dsn:
        print("SIGNALBOT_DSN is not set. Refusing to guess a database.", file=sys.stderr)
        return 2
    version = code_version or resolve_feature_code_version()
    opener = connect or _connect
    try:
        conn, driver = opener(dsn)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"database connection failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    try:
        try:
            kline_sql, oi_sql = replay_sql()
            _kline_header, kline_rows = _run_select(conn, driver, kline_sql)
            _oi_header, oi_rows = _run_select(conn, driver, oi_sql)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"replay read failed: {redact(str(exc))}", file=sys.stderr)
            return 1
    finally:
        conn.close()
    try:
        result = build_replay(kline_rows, oi_rows, code_version=version)
        write_outputs(Path(args.out_dir), result)
    except Exception as exc:  # noqa: BLE001
        print(f"replay reconstruction failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    print(SEMANTIC_DISCLAIMER)
    print(f"REPLAY_CLASS={REPLAY_CLASS}")
    print(f"AUTHORIZED_BUCKETS={result['authorized_bucket_count']}")
    for name, gate in result["gates"].items():
        print(
            f"{name} P4_SAMPLE_GATE={gate['p4_sample_gate']} "
            f"episodes={gate['total_episodes']} dates={gate['distinct_episode_dates_utc']}"
        )
    print("REPLAY_COMPLETE")
    print("EVENT_OUTCOMES_COMPUTED=false")
    print("P4_PERFORMANCE_COMPUTED=false")
    return 0


def build_replay(kline_rows, oi_rows, *, code_version: str) -> dict:
    buckets = authorized_buckets()
    if len(buckets) != PHASE_A_AUTHORIZED_BUCKETS:
        raise SystemExit(
            f"authorized bucket count {len(buckets)} != frozen Phase A count {PHASE_A_AUTHORIZED_BUCKETS}"
        )
    cfg = BetaConfig.load()
    stage2 = Stage2Config.load(STAGE2_CONFIG_PATH)
    if int(cfg.min_venues) != int(stage2.resolve(cfg.symbol)["data_confidence"]["minimum_exchange_coverage"]):
        raise SystemExit("beta min_venue_coverage and stage2 minimum_exchange_coverage differ")
    if cfg["percentile_window"] != "30d":
        raise SystemExit("replay is bound to the current 30d percentile window")
    bars, offslot = _group_bars(kline_rows)
    oi = _group_oi(oi_rows)
    history = []
    prepared = []
    unexpected_gap = []
    maturity_days = int(cfg["percentile_window"].rstrip("d"))
    for index, bucket in enumerate(history_buckets()):
        reconstruction = reconstruct_bucket(
            stage2, bucket, bars.get(bucket, {}), oi.get(bucket, {}), code_version=code_version,
        )
        if in_frozen_gap(bucket) and (reconstruction.price_available >= cfg.min_venues
                                      or reconstruction.oi_available >= cfg.min_venues):
            unexpected_gap.append(iso(bucket))
        if source_interval(bucket) is not None:
            window = samples_before(history, bucket, maturity_days=maturity_days)
            percentiles = current_percentiles(
                stage2, cfg, reconstruction, window, code_version=code_version,
            )
            prepared.append(_prepare(reconstruction, percentiles))
        history.append((bucket, metrics_of(reconstruction)))
        if index and index % 2000 == 0:
            print(f"reconstructed {index} history buckets", file=sys.stderr)
    result = replay_series(cfg, prepared)
    result["prepared"] = prepared  # in-memory only; write_outputs does not export it
    result["offslot_live_bars_ignored"] = offslot
    result["unexpected_gap_quorum_buckets"] = unexpected_gap
    result["history_start"] = iso(HISTORY_START)
    result["history_end_exclusive"] = iso(HISTORY_END_EXCLUSIVE)
    result["live_kline_rows"] = len(kline_rows)
    result["live_oi_rows"] = len(oi_rows)
    result["backfill_rows_read"] = 0
    result["production_tables_written"] = False
    return result


def write_outputs(out: Path, result: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "rule_evaluations.csv", EVALUATION_COLUMNS, result["evaluations"])
    _write_csv(out / "episodes.csv", EPISODE_COLUMNS, [_episode_row(item) for item in result["episodes"]])
    gate_doc = {
        "replay_class": REPLAY_CLASS,
        "provenance": PROVENANCE,
        "disclaimer": result["disclaimer"],
        "families": result["gates"],
        "event_outcomes_computed": False,
        "p4_performance_computed": False,
        "gate_meaning": "sample availability only; not profitability, prediction, or a validated edge",
    }
    (out / "p4_sample_gate.json").write_text(json.dumps(gate_doc, indent=2, sort_keys=True) + "\n")
    manifest = {
        "replay_class": REPLAY_CLASS,
        "provenance": PROVENANCE,
        "disclaimer": SEMANTIC_DISCLAIMER,
        "authorized_families": list(AUTHORIZED_FAMILIES),
        "authorized_intervals": [
            {"start": iso(start), "end": iso(end)} for start, end in INTERVALS
        ],
        "authorized_bucket_count": result["authorized_bucket_count"],
        "phase_a_authorized_buckets": PHASE_A_AUTHORIZED_BUCKETS,
        "non_evaluable_buckets": result["non_evaluable_buckets"],
        "unexpected_gap_quorum_buckets": result["unexpected_gap_quorum_buckets"],
        "offslot_live_bars_ignored": result["offslot_live_bars_ignored"],
        "live_kline_rows": result["live_kline_rows"],
        "live_oi_rows": result["live_oi_rows"],
        "backfill_rows_read": 0,
        "production_tables_written": False,
        "event_outcomes_computed": False,
        "p4_performance_computed": False,
        "historical_freshness_state": "NOT_IN_ARCHIVE",
        "historical_coherence_race_state": "NOT_IN_ARCHIVE",
        "historical_alert_delivery": "NOT_PROVEN",
        "history_start": result["history_start"],
        "history_end_exclusive": result["history_end_exclusive"],
    }
    (out / "replay_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _prepare(reconstruction: BucketReconstruction, percentiles: dict) -> PreparedBucket:
    price = percentiles.get("c:price_move_pct_median") or {}
    oi = percentiles.get("c:oi_change_pct_median") or {}
    return PreparedBucket(
        reconstruction=reconstruction,
        price_rank=price.get("rank"),
        oi_rank=oi.get("rank"),
        price_tier=price.get("tier"),
        oi_tier=oi.get("tier"),
    )


def _episode_row(item) -> dict:
    episode = item.episode
    return {
        "episode_id": episode.public_id,
        "event_type": episode.event_type,
        "state": episode.state,
        "opened_bucket": iso(episode.opened_bucket),
        "armed_at": iso(episode.armed_at),
        "triggered_at": iso(episode.triggered_at),
        "terminal_at": iso(episode.terminal_at),
        "terminal_reason": episode.terminal_reason,
        "qualifying_bucket_count": item.qualifying_bucket_count,
        "source_interval": item.source_interval,
        "provenance": PROVENANCE,
        "replay_class": REPLAY_CLASS,
        "historical_freshness_state": "NOT_IN_ARCHIVE",
        "historical_coherence_race_state": "NOT_IN_ARCHIVE",
        "historical_alert_delivery": "NOT_PROVEN",
    }


def _group_bars(rows):
    grouped = defaultdict(lambda: defaultdict(list))
    offslot = 0
    for exchange, ts, open_, high, low, close, volume in rows:
        moment = _utc(ts)
        bucket = moment.replace(second=0, microsecond=0)
        bucket = bucket - timedelta(minutes=bucket.minute % 5)
        slots = {bucket + timedelta(minutes=n) for n in range(5)}
        if moment not in slots:
            offslot += 1
            continue
        grouped[bucket][exchange].append(KlineBar(
            moment, float(open_), float(high), float(low), float(close), float(volume),
        ))
    return grouped, offslot


def _group_oi(rows):
    grouped = defaultdict(lambda: defaultdict(list))
    for exchange, ts, raw, unit in rows:
        if raw is None or unit in (None, ""):
            continue
        moment = _utc(ts)
        if not (HISTORY_START <= moment < HISTORY_END_EXCLUSIVE):
            continue
        bucket = moment.replace(second=0, microsecond=0)
        bucket = bucket - timedelta(minutes=bucket.minute % 5)
        if not (bucket <= moment < bucket + timedelta(minutes=5)):
            continue
        grouped[bucket][exchange].append(OpenInterestObservation(moment, float(raw), str(unit)))
    return grouped


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise SystemExit("naive timestamp from a live-archive read")
    return value.astimezone(UTC)


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: "" if row.get(column) is None else row.get(column) for column in columns})


if __name__ == "__main__":
    raise SystemExit(main())
