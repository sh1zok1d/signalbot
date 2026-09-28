"""Gold-vs-Tardis comparison. Not invoked unless a live export is present."""
from __future__ import annotations

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
from .report import (
    FLAGS,
    audit_sources_sha256,
    gold_export_facts,
    incidents_touching_sample_dates,
    load_incidents,
    write_comparison_outputs,
)


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
    feature_names = (
        "price_move_pct", "range_width_pct", "volume_notional_usd",
        "taker_delta_notional_usd", "oi_change_pct",
    )
    feature_pairs = {name: [] for name in feature_names}
    slice_pairs: dict[tuple[str, str], dict[str, list]] = {}
    slice_eval: dict[tuple[str, str], list] = {}
    slice_cov: dict[tuple[str, str], dict] = {}
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
            slice_key = (sample_date, venue.signalbot_exchange)
            slice_pairs[slice_key] = {name: [] for name in feature_names}
            slice_eval[slice_key] = []
            slice_cov[slice_key] = {
                "expected_buckets": 0,
                "gold_buckets": 0,
                "vendor_buckets": 0,
                "both_present_buckets": 0,
                "missing_gold_buckets": 0,
                "missing_vendor_buckets": 0,
                "gap_excluded_buckets": 0,
                "vendor_gap_buckets": 0,
            }
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
                t_bars = _bars_for_bucket(minute_bars, bucket)
                t_oi = _oi_for_bucket(tardis_oi, bucket)
                cov = slice_cov[slice_key]
                cov["expected_buckets"] += 1
                gold_present = bool(g_bars or g_oi)
                vendor_present = bool(t_bars or t_oi)
                if gold_present:
                    cov["gold_buckets"] += 1
                else:
                    cov["missing_gold_buckets"] += 1
                if vendor_present:
                    cov["vendor_buckets"] += 1
                else:
                    cov["missing_vendor_buckets"] += 1
                if gold_present and vendor_present:
                    cov["both_present_buckets"] += 1
                if not gold_present:
                    tags = list(tags) + ["SIGNALBOT_DATA_GAP"]
                t_vector, _t_diag = compute_bucket_features(
                    identity=identity, exchange=venue.signalbot_exchange,
                    bucket_ts=bucket, bars=t_bars, oi=t_oi, metadata=meta,
                )
                g_vector, _g_diag = compute_bucket_features(
                    identity=identity, exchange=venue.signalbot_exchange,
                    bucket_ts=bucket, bars=g_bars, oi=g_oi, metadata=meta,
                )
                key = (sample_date, bucket.isoformat())
                stored_g.setdefault(key, []).append(g_vector)
                stored_t.setdefault(key, []).append(t_vector)
                bucket_gap[key] = bucket_gap.get(key, False) or gap_tagged(tags)
                if VENDOR_GAP_TAG in tags:
                    cov["vendor_gap_buckets"] += 1
                if gap_tagged(tags):
                    gap_buckets += 1
                    cov["gap_excluded_buckets"] += 1
                    continue
                if g_vector.oi_unit and t_vector.oi_unit and g_vector.oi_unit != t_vector.oi_unit:
                    unit_mismatch += 1
                for field in feature_pairs:
                    pair = (getattr(g_vector, field), getattr(t_vector, field))
                    feature_pairs[field].append(pair)
                    slice_pairs[slice_key][field].append(pair)
                    g_val, t_val = pair
                    if g_val is not None and t_val is not None:
                        mismatches.append((
                            abs(float(t_val) - float(g_val)),
                            sample_date, venue.signalbot_exchange, bucket.isoformat(),
                            field, g_val, t_val, "",
                        ))
                g_eval = g_vector.is_usable and g_vector.price_move_pct is not None
                t_eval = t_vector.is_usable and t_vector.price_move_pct is not None
                evaluable_flags.append(g_eval != t_eval)
                slice_eval[slice_key].append(g_eval != t_eval)
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
    per_venue = []
    for (sample_date, exchange), cov in slice_cov.items():
        pairs = slice_pairs[(sample_date, exchange)]
        flags = slice_eval[(sample_date, exchange)]
        per_venue.append({
            "sample_date": sample_date,
            "exchange": exchange,
            "coverage": cov,
            "feature_stats": {
                name: numeric_diagnostics(pairs[name]) for name in feature_names
            },
            "null_evaluability_disagreements": {
                "count": sum(flags),
                "fraction": (sum(flags) / len(flags) if flags else None),
                "buckets_entering_equivalence": len(flags),
            },
        })
    touching = incidents_touching_sample_dates(incidents_raw) if incidents_raw else []
    applicable_gaps = [
        row for row in touching if row["applies_to_trades_or_derivative_ticker"]
    ]
    okx_multiplier_rows = [
        row for row in gold.history
        if row.exchange == "okx"
        and row.contract_multiplier is not None
        and row.contract_multiplier > 0
    ]
    gold_facts = gold_export_facts(gold_dir)
    summary = {
        "comparison_performed": True,
        "overall_decision": decision,
        "dates_compared": list(SAMPLE_DATES),
        "venues_compared": [venue.signalbot_exchange for venue in VENUES],
        "verdicts": _verdicts(stats, findings),
        "feature_stats": stats,
        "per_venue": per_venue,
        "consensus_stats": {
            name: numeric_diagnostics(pairs) for name, pairs in consensus_pairs.items()
        },
        "oi_sign_agreement_by_magnitude": oi_strata,
        "tail_agreement_summary": {"label": "SAMPLE-DAY TAIL AGREEMENT", "features": tails},
        "null_evaluability_disagreements": {
            "count": sum(evaluable_flags),
            "fraction": eval_fraction,
            "definition": (
                "Disagreement of (is_usable and price_move_pct is not None) "
                "on buckets that were not gap-excluded."
            ),
        },
        "quorum_disagreement": {
            "count": sum(quorum_flags),
            "fraction": quorum_fraction,
            "buckets": len(quorum_flags),
        },
        "documented_vendor_gaps": {
            "incidents_whose_window_overlaps_a_sample_date": touching,
            "applicable_to_trades_or_derivative_ticker": applicable_gaps,
            "vendor_gap_buckets": sum(
                row["vendor_gap_buckets"] for row in slice_cov.values()
            ),
        },
        "top_mismatch_causes": [
            {"code": item["code"], "class": item["class"], "detail": item["detail"]}
            for item in findings
        ],
        "gap_buckets_excluded_from_equivalence": gap_buckets,
        "unit_mismatch_count": unit_mismatch,
        "findings": findings,
        "okx_oi_pit_status": (
            "PIT_MULTIPLIER_PRESENT" if okx_multiplier_rows
            else "PIT_BLOCKED_NO_HISTORICAL_CTVAL"
        ),
        "current_instrument_table_used_as_pit": False,
        "post_hoc_transform_applied": False,
        "gold_export": gold_facts,
        "tardis_files": [
            {
                "file": row["path_basename"],
                "sha256": row["sha256"],
                "compressed_bytes": row["compressed_bytes"],
                "row_count": row["row_count"],
                "http_status": row["http_status"],
                "status": row["status"],
            }
            for row in inventory
        ],
        "flags": FLAGS,
        "cost_incurred_usd": 0,
        "base_sha": base_sha,
        "audit_sources_sha256": audit_sources_sha256(),
    }
    mismatches.sort(reverse=True)
    mismatch_rows = [
        [day, exchange, bucket, field, g_val, t_val, abs_diff, tags, ""]
        for abs_diff, day, exchange, bucket, field, g_val, t_val, tags in mismatches[:200]
    ]
    write_comparison_outputs(Path(out_dir), summary, mismatch_rows, inventory)
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
