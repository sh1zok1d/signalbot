"""Gold-vs-Tardis comparison. Not invoked unless a live export is present."""
from __future__ import annotations

import csv
import json
from datetime import timedelta
from pathlib import Path

from analytics.feature_engine.models import KlineBar, OpenInterestObservation

from . import SOURCE_SIGNALBOT_GOLD, SOURCE_TARDIS
from .compare import (
    COMPARED_FAMILIES,
    evaluate_principles,
    gap_tagged,
    magnitude_strata,
    numeric_diagnostics,
    overall_decision,
    tail_overlap,
)
from .constants import SAMPLE_DATES, VENDOR_GAP_TAG, VENUES, vendor_filename
from .features import (
    compute_bucket_features,
    consensus_for_vectors,
    day_start,
    iter_day_buckets,
    minute_bar_to_kline,
    oi_rows_to_observations,
    production_identity,
    structural_metadata,
    vector_public_dict,
)
from .gaps import bucket_tags, incident_applies_to_requested_datasets
from .gold import load_gold_dir
from .inventory import inventory_vendor_dir
from .parsing import (
    aggregate_trades,
    bucket_bounds,
    exchange_us_to_datetime,
    in_half_open_bucket,
    iter_open_interest,
    iter_trades,
)
from .report import FLAGS, audit_sources_sha256, load_incidents


def _sha_for(inventory: list[dict], venue, data_type: str, sample_date: str) -> str:
    name = vendor_filename(venue, data_type, sample_date)
    for row in inventory:
        if row["path_basename"] == name:
            if row["status"] != "OK" or not row["sha256"]:
                raise RuntimeError(f"{name} is not an OK inventory row: {row['status']}")
            return row["sha256"]
    raise RuntimeError(f"{name} missing from inventory")


def _bars_for_bucket(minute_bars: dict, bucket_ts) -> list[KlineBar]:
    _, end = bucket_bounds(bucket_ts)
    selected = [
        minute_bar_to_kline(bar)
        for minute, bar in minute_bars.items()
        if bucket_ts <= minute < end
    ]
    return sorted(selected, key=lambda bar: bar.ts)


def _oi_for_bucket(observations, bucket_ts) -> list[OpenInterestObservation]:
    return [obs for obs in observations if in_half_open_bucket(obs.ts, bucket_ts)]


def run_gold_comparison(*, vendor_dir: str, gold_dir: str, exchange_meta_dir: str | None,
                        out_dir: str, base_sha: str) -> int:
    inventory = inventory_vendor_dir(vendor_dir)
    if any(row["status"] != "OK" for row in inventory):
        blocked = [row["path_basename"] for row in inventory if row["status"] != "OK"]
        raise SystemExit(f"REPAIR_AND_REPEAT_FREE_VALIDATION schema or download stop: {blocked}")
    gold = load_gold_dir(gold_dir)
    identity = production_identity()
    incidents_raw = load_incidents(exchange_meta_dir) if exchange_meta_dir else {}
    incidents_by_exchange = {
        venue.tardis_exchange: [
            inc for inc in (incidents_raw.get(venue.tardis_exchange, {}).get("incidents") or [])
            if incident_applies_to_requested_datasets(inc)
        ]
        for venue in VENUES
    }
    feature_pairs = {
        name: [] for name in (
            "price_move_pct", "range_width_pct", "volume_notional_usd",
            "taker_delta_notional_usd", "oi_change_pct",
        )
    }
    consensus_pairs = {
        name: [] for name in (
            "price_move_pct_median", "range_width_pct_median",
            "oi_change_pct_median", "volume_notional_usd_sum",
            "taker_delta_notional_usd_sum",
        )
    }
    unit_mismatch = 0
    evaluable_flags = []
    quorum_flags = []
    gap_buckets = 0
    mismatches = []
    stored_g: dict[tuple[str, str], list] = {}
    stored_t: dict[tuple[str, str], list] = {}
    bucket_gap: dict[tuple[str, str], bool] = {}
    for sample_date in SAMPLE_DATES:
        for venue in VENUES:
            trade_sha = _sha_for(inventory, venue, "trades", sample_date)
            oi_sha = _sha_for(inventory, venue, "derivative_ticker", sample_date)
            trade_path = str(Path(vendor_dir) / vendor_filename(venue, "trades", sample_date))
            oi_path = str(Path(vendor_dir) / vendor_filename(venue, "derivative_ticker", sample_date))
            trades = list(iter_trades(
                trade_path, sha256=trade_sha, sample_date=sample_date,
                tardis_exchange=venue.tardis_exchange, tardis_symbol=venue.tardis_symbol,
            ))
            day0 = day_start(sample_date)
            day1 = day0 + timedelta(days=1)
            trades = [
                row for row in trades
                if day0 <= exchange_us_to_datetime(row.exchange_timestamp_us) < day1
            ]
            minute_bars = aggregate_trades(trades)
            oi_rows = [
                row for row in iter_open_interest(
                    oi_path, sha256=oi_sha, sample_date=sample_date,
                    tardis_exchange=venue.tardis_exchange,
                    tardis_symbol=venue.tardis_symbol,
                )
                if row.open_interest is not None
                and day0 <= exchange_us_to_datetime(row.exchange_timestamp_us) < day1
            ]
            tardis_oi = oi_rows_to_observations(oi_rows, venue)
            gold_oi = [
                obs for obs in gold.oi[venue.signalbot_exchange]
                if day0 <= obs.ts < day1
            ]
            for bucket in iter_day_buckets(sample_date):
                tags = bucket_tags(
                    incidents_by_exchange[venue.tardis_exchange],
                    bucket, bucket + timedelta(minutes=5),
                )
                meta = gold.metadata_asof(venue.signalbot_exchange, bucket)
                if meta is None:
                    meta = structural_metadata(
                        venue, contract_multiplier=None, metadata_source="manual",
                        note="missing",
                    )
                g_bars = [
                    bar for (ex, ts), bar in gold.bars.items()
                    if ex == venue.signalbot_exchange and in_half_open_bucket(ts, bucket)
                ]
                g_oi = _oi_for_bucket(gold_oi, bucket)
                if not g_bars and not g_oi:
                    tags = list(tags) + ["SIGNALBOT_DATA_GAP"]
                t_vector, _t_diag = compute_bucket_features(
                    identity=identity, exchange=venue.signalbot_exchange,
                    bucket_ts=bucket, bars=_bars_for_bucket(minute_bars, bucket),
                    oi=_oi_for_bucket(tardis_oi, bucket), metadata=meta,
                )
                g_vector, _g_diag = compute_bucket_features(
                    identity=identity, exchange=venue.signalbot_exchange,
                    bucket_ts=bucket, bars=g_bars, oi=g_oi, metadata=meta,
                )
                key = (sample_date, bucket.isoformat())
                stored_g.setdefault(key, []).append(g_vector)
                stored_t.setdefault(key, []).append(t_vector)
                bucket_gap[key] = bucket_gap.get(key, False) or gap_tagged(tags)
                if gap_tagged(tags):
                    gap_buckets += 1
                    continue
                if g_vector.oi_unit and t_vector.oi_unit and g_vector.oi_unit != t_vector.oi_unit:
                    unit_mismatch += 1
                for field in feature_pairs:
                    feature_pairs[field].append((
                        getattr(g_vector, field), getattr(t_vector, field),
                    ))
                    g_val = getattr(g_vector, field)
                    t_val = getattr(t_vector, field)
                    if g_val is not None and t_val is not None:
                        mismatches.append((
                            abs(float(t_val) - float(g_val)),
                            sample_date, venue.signalbot_exchange, bucket.isoformat(),
                            field, g_val, t_val, "",
                        ))
                g_eval = g_vector.is_usable and g_vector.price_move_pct is not None
                t_eval = t_vector.is_usable and t_vector.price_move_pct is not None
                evaluable_flags.append(g_eval != t_eval)
                _ = vector_public_dict(
                    t_vector, source=SOURCE_TARDIS, instrument=venue.tardis_symbol,
                    sample_date=sample_date, source_file_sha256=trade_sha,
                    exchange_timestamp_role="exchange_event_time",
                )
                _ = vector_public_dict(
                    g_vector, source=SOURCE_SIGNALBOT_GOLD, instrument=venue.canonical_symbol,
                    sample_date=sample_date, source_file_sha256=None,
                    exchange_timestamp_role="live_bar_open_and_collector_receive_time",
                )
    for key, g_vectors in stored_g.items():
        if bucket_gap.get(key):
            continue
        t_vectors = stored_t[key]
        if len(g_vectors) != len(VENUES) or len(t_vectors) != len(VENUES):
            continue
        bucket = g_vectors[0].bucket_ts
        g_cons, _ = consensus_for_vectors(identity, bucket, g_vectors)
        t_cons, _ = consensus_for_vectors(identity, bucket, t_vectors)
        for field in consensus_pairs:
            consensus_pairs[field].append((getattr(g_cons, field), getattr(t_cons, field)))
        differ = False
        for family in COMPARED_FAMILIES:
            g_members = g_cons.provenance_by_metric[family].contributing
            t_members = t_cons.provenance_by_metric[family].contributing
            if g_members != t_members:
                differ = True
        quorum_flags.append(differ)
    stats = {name: numeric_diagnostics(pairs) for name, pairs in feature_pairs.items()}
    oi_strata = magnitude_strata(feature_pairs["oi_change_pct"])
    tails = {
        name: {
            "top_bottom_5pct": tail_overlap(pairs, 0.05),
            "top_bottom_10pct": tail_overlap(pairs, 0.10),
        }
        for name, pairs in feature_pairs.items()
    }
    eval_fraction = (
        sum(evaluable_flags) / len(evaluable_flags) if evaluable_flags else None
    )
    quorum_fraction = (
        sum(quorum_flags) / len(quorum_flags) if quorum_flags else None
    )
    findings = evaluate_principles(
        stats, oi_strata=oi_strata,
        evaluable_disagreement_fraction=eval_fraction,
        quorum_disagreement_fraction=quorum_fraction,
        unit_mismatch_count=unit_mismatch,
        post_hoc_transform_applied=False,
    )
    decision = overall_decision(comparison_performed=True, findings=findings)
    summary = {
        "comparison_performed": True,
        "overall_decision": decision,
        "verdicts": _verdicts(stats, findings),
        "feature_stats": stats,
        "consensus_stats": {
            name: numeric_diagnostics(pairs) for name, pairs in consensus_pairs.items()
        },
        "oi_sign_agreement_by_magnitude": oi_strata,
        "tail_agreement_summary": {"label": "SAMPLE-DAY TAIL AGREEMENT", "features": tails},
        "null_evaluability_disagreements": {
            "count": sum(evaluable_flags),
            "fraction": eval_fraction,
        },
        "gap_buckets_excluded_from_equivalence": gap_buckets,
        "unit_mismatch_count": unit_mismatch,
        "findings": findings,
        "flags": FLAGS,
        "cost_incurred_usd": 0,
        "base_sha": base_sha,
        "audit_sources_sha256": audit_sources_sha256(),
    }
    mismatches.sort(reverse=True)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "overlap_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with (out / "mismatch_samples.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "sample_date", "exchange", "bucket_ts", "feature",
            "signalbot_value", "tardis_value", "abs_diff", "tags", "note",
        ])
        for abs_diff, day, exchange, bucket, field, g_val, t_val, tags in mismatches[:200]:
            writer.writerow([day, exchange, bucket, field, g_val, t_val, abs_diff, tags, ""])
    print(decision)
    return 0


def _verdicts(stats: dict, findings: list[dict]) -> dict:
    codes = {item["code"] for item in findings}

    def one(feature: str, bad_codes: set[str]) -> str:
        if codes & bad_codes:
            return "FAIL"
        if (stats.get(feature) or {}).get("comparable_count", 0) == 0:
            return "NOT_EVALUABLE"
        return "PASS_ON_PREDECLARED_PRINCIPLES"

    return {
        "price": one("price_move_pct", {"MATERIAL_REORDER"}),
        "range": one("range_width_pct", {"MATERIAL_REORDER"}),
        "volume": one("volume_notional_usd", {"SYSTEMATIC_SCALE_ERROR", "METADATA_SCALE_SUSPECT"}),
        "oi": one("oi_change_pct", {
            "PERSISTENT_UNIT_MISMATCH", "OI_SIGN_DISAGREEMENT_OUTSIDE_TINY", "MATERIAL_REORDER",
        }),
        "taker": one("taker_delta_notional_usd", {
            "PERSISTENT_TAKER_INVERSION", "SYSTEMATIC_SCALE_ERROR", "METADATA_SCALE_SUSPECT",
        }),
        "consensus": "NOT_EVALUABLE" if "CONSENSUS_QUORUM_DISAGREEMENT" not in codes else "FAIL",
    }


# Re-export so a later gold run and the tests share one consensus entry point.
compare_consensus = consensus_for_vectors
