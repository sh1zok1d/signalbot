"""Phase A coverage analysis for the live-archive replay preflight.

Reads the owner-produced coverage export and classifies event-family replay
eligibility. It does not open a database, reconstruct detector events, or
compute percentile ranks.

Maturity follows ``analytics.percentile_engine.compute``: a family history is
mature at bucket B only when [B-30d, B) contains at least two non-null samples
and (B - earliest non-null sample) / 86400 seconds is at least
``building_below_days`` (30). The current bucket is not a sample.

Consensus family values exist only when at least ``min_venue_coverage`` venues
contribute (``analytics.feature_engine.consensus``). Volume and taker notionals
require PIT ``exchange_instrument_history``; the current instrument table is
not a substitute. Empty ``connectivity_events`` is not historical proof that
the liquidation heartbeat was healthy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from beta.config import BetaConfig
from beta.models import CORE_FAMILIES

UTC = timezone.utc
ONE_DAY_SECONDS = 86400.0
VENUES = ("binance", "bybit", "okx")
BUCKET = timedelta(minutes=5)
HOUR_BUCKETS = 12
DAY_BUCKETS = 288

FAMILY_FLAG = {
    "price_structure": "price_feature_non_null",
    "oi": "oi_feature_non_null",
    "volume": "volume_notional_non_null",
    "taker_flow": "taker_notional_non_null",
}
EVENT_FAMILIES = {
    "PRICE_OI_CONTRACTION_DOWN": ("price_structure", "oi"),
    "PRICE_OI_CONTRACTION_UP": ("price_structure", "oi"),
    "POSITION_BUILDUP_COMPRESSION": ("price_structure", "oi", "volume"),
    "TAKER_FLOW_EXTREME_BUY": ("taker_flow",),
    "TAKER_FLOW_EXTREME_SELL": ("taker_flow",),
    "LIQUIDATION_STRESS_LONG": ("liquidations",),
    "LIQUIDATION_STRESS_SHORT": ("liquidations",),
}
RULE_ENABLED_KEY = {
    "PRICE_OI_CONTRACTION_DOWN": "PRICE_OI_CONTRACTION_DOWN",
    "PRICE_OI_CONTRACTION_UP": "PRICE_OI_CONTRACTION_UP",
    "POSITION_BUILDUP_COMPRESSION": "POSITION_BUILDUP_COMPRESSION",
    "TAKER_FLOW_EXTREME_BUY": "TAKER_FLOW_EXTREME",
    "TAKER_FLOW_EXTREME_SELL": "TAKER_FLOW_EXTREME",
    "LIQUIDATION_STRESS_LONG": "LIQUIDATION_STRESS",
    "LIQUIDATION_STRESS_SHORT": "LIQUIDATION_STRESS",
}
PIT_REQUIRED_FAMILIES = ("volume", "taker_flow")


def history_is_mature(eligible_times: list[datetime], bucket: datetime, *, maturity_days: int) -> bool:
    """True when the non-null history in [bucket-W, bucket) is mature."""
    if not eligible_times:
        return False
    start = bucket - timedelta(days=maturity_days)
    left = _bisect_left(eligible_times, start)
    right = _bisect_left(eligible_times, bucket)
    sample_size = right - left
    if sample_size < 2:
        return False
    span_days = (bucket - eligible_times[left]).total_seconds() / ONE_DAY_SECONDS
    return span_days >= maturity_days


def first_mature_timestamp(grid: list[datetime], eligible_times: list[datetime], *, maturity_days: int):
    for bucket in grid:
        if history_is_mature(eligible_times, bucket, maturity_days=maturity_days):
            return bucket
    return None


def analyze_export(export_dir: Path, *, cfg: BetaConfig | None = None) -> dict:
    export_dir = Path(export_dir)
    verification = verify_manifest(export_dir)
    if not verification["ok"]:
        raise SystemExit("export manifest hash verification failed")
    cfg = cfg or BetaConfig.load()
    coverage = _read_csv(export_dir / "coverage_5m.csv")
    lookback = _read_csv(export_dir / "maturity_lookback_5m.csv")
    return analyze_frames(
        coverage_rows=coverage,
        lookback_rows=lookback,
        archive_rows=_read_csv(export_dir / "archive_summary.csv"),
        oi_unit_rows=_read_csv(export_dir / "oi_unit_changes.csv"),
        instrument_rows=_read_csv(export_dir / "instrument_history_coverage.csv"),
        connectivity_rows=_read_csv(export_dir / "connectivity_coverage.csv"),
        capability_rows=_read_csv(export_dir / "liquidation_capability.csv"),
        manifest=json.loads((export_dir / "export_manifest.json").read_text()),
        verification=verification,
        cfg=cfg,
    )


def analyze_frames(
    *,
    coverage_rows,
    lookback_rows,
    archive_rows,
    oi_unit_rows,
    instrument_rows,
    connectivity_rows,
    capability_rows,
    manifest,
    verification,
    cfg: BetaConfig,
) -> dict:
    maturity_days = int(cfg["percentile_window"].rstrip("d"))
    if cfg["percentile_window"] != "30d" or maturity_days != 30:
        raise SystemExit("analysis is bound to the current 30d percentile window")
    min_venues = int(cfg.min_venues)
    stages = _stage2_maturity_days(cfg.symbol)
    if stages != maturity_days:
        raise SystemExit("stage2 building_below_days does not match the beta percentile window")
    if tuple(CORE_FAMILIES) != ("price_structure", "oi", "volume"):
        raise SystemExit("CORE_FAMILIES changed; refusing to reinterpret product readiness")

    requested = [_normalize(row) for row in coverage_rows if _is_data_row(row)]
    history_rows = _dedupe(
        [_normalize(row) for row in lookback_rows if _is_data_row(row)] + requested
    )
    grid = sorted({row["bucket_start"] for row in requested})
    if not grid:
        return _incomplete("requested coverage grid is empty", verification, manifest)

    by_bucket_venue = {(row["bucket_start"], row["exchange"]): row for row in requested}
    if len(by_bucket_venue) != len(requested):
        raise SystemExit("duplicate coverage rows for one bucket and venue")
    for bucket in grid:
        for venue in VENUES:
            if (bucket, venue) not in by_bucket_venue:
                raise SystemExit(f"missing venue row {venue} at {iso(bucket)}")

    quorum = {
        family: [sum(1 for venue in VENUES if by_bucket_venue[(bucket, venue)][flag]) >= min_venues
                 for bucket in grid]
        for family, flag in FAMILY_FLAG.items()
    }
    eligible_times = {
        family: _eligible_times(history_rows, flag, min_venues)
        for family, flag in FAMILY_FLAG.items()
    }
    # Code-path liquidation samples: declared feed and logged heartbeat, which
    # treats an empty connectivity log as no outage. That series is reported
    # separately and is not historical proof.
    code_liq_times = _liquidation_code_times(history_rows, min_venues=int(cfg.rule("LIQUIDATION_STRESS")["min_eligible_venues"]))
    code_liq_quorum = [
        _liquidation_code_ok(by_bucket_venue, bucket, min_venues=int(cfg.rule("LIQUIDATION_STRESS")["min_eligible_venues"]))
        for bucket in grid
    ]
    mature = {
        family: [history_is_mature(eligible_times[family], bucket, maturity_days=maturity_days) for bucket in grid]
        for family in FAMILY_FLAG
    }
    connectivity_events = [
        row for row in connectivity_rows if (row.get("record_type") or "") == "event"
    ]
    heartbeat_provable = len(connectivity_events) > 0
    per_venue = _per_venue(grid, by_bucket_venue, archive_rows)
    families = _family_block(grid, quorum, mature)
    predicates = _predicate_counts(grid, by_bucket_venue, min_venues)
    events = _events(
        grid, quorum, mature, code_liq_quorum, code_liq_times, cfg,
        maturity_days=maturity_days, heartbeat_provable=heartbeat_provable,
    )
    archive_start, archive_end = _archive_bounds(archive_rows)
    full, simultaneous = _full_detector(events, families)
    phase = _phase(full, events)
    for event in events.values():
        event.pop("_mask", None)
    product = _product_semantics(families, events)
    blockers = _top_blockers(events, product)
    return {
        "export_hash_verification": verification,
        "manifest_interval": {
            "start": manifest.get("requested_interval_start"),
            "end_exclusive": manifest.get("requested_interval_end_exclusive"),
            "no_market_magnitudes_exported": manifest.get("no_market_magnitudes_exported"),
            "statement": manifest.get("statement"),
        },
        "core_families": list(CORE_FAMILIES),
        "min_venue_coverage": min_venues,
        "maturity_days": maturity_days,
        "pit_required_families": list(PIT_REQUIRED_FAMILIES),
        "archive_observed_start": archive_start,
        "archive_observed_end": archive_end,
        "total_5m_buckets": len(grid),
        "grid_start": iso(grid[0]),
        "grid_end_inclusive": iso(grid[-1]),
        "per_venue": per_venue,
        "oi_units": _oi_units(oi_unit_rows),
        "pit": _pit(instrument_rows, requested),
        "connectivity": {
            "event_count": len(connectivity_events),
            "historical_heartbeat_provable": heartbeat_provable,
            "interpretation": (
                "LOGGED_OUTAGES_PRESENT"
                if heartbeat_provable
                else "NO_EVIDENCE_OF_OUTAGE_HEARTBEAT_NOT_HISTORICALLY_PROVABLE"
            ),
        },
        "predicates": predicates,
        "families": families,
        "liquidation_code_path": _without_mask(_mask_summary(grid, code_liq_quorum)),
        "liquidation_historical_health_provable": heartbeat_provable,
        "first_mature": {
            "price": iso(first_mature_timestamp(grid, eligible_times["price_structure"], maturity_days=maturity_days)),
            "oi": iso(first_mature_timestamp(grid, eligible_times["oi"], maturity_days=maturity_days)),
            "volume": iso(first_mature_timestamp(grid, eligible_times["volume"], maturity_days=maturity_days)),
            "taker": iso(first_mature_timestamp(grid, eligible_times["taker_flow"], maturity_days=maturity_days)),
            "liquidation": None,
        },
        "events": events,
        "simultaneous_enabled_family_buckets": simultaneous,
        "full_current_detector_replay_eligibility": full,
        "product_semantics": product,
        "top_coverage_blockers": blockers,
        "longest_gap_runs": {
            name: {
                "longest_ineligible_run_buckets": event["longest_ineligible_run_buckets"],
                "longest_ineligible_run": event["longest_ineligible_run"],
                "interior_gap_runs": event["interior_gap_runs"],
                "number_of_gap_runs_gt_1_bucket": event["number_of_gap_runs_gt_1_bucket"],
                "number_of_gap_runs_gt_1_hour": event["number_of_gap_runs_gt_1_hour"],
                "number_of_gap_runs_gt_1_day": event["number_of_gap_runs_gt_1_day"],
            }
            for name, event in events.items()
        },
        "phase_a_decision": phase,
        "next_unit": _next_unit(phase, events),
        "replay_authorized": False,
        "source_semantics_changes": False,
        "replay_performed": False,
        "event_counts_computed": False,
        "p4_outcomes_computed": False,
        "production_db_accessed": False,
        "production_db_written": False,
        "detector_changed": False,
        "rules_changed": False,
        "backfill_not_substituted_for_live": True,
        "eligible_before_observed_live_kline_start": _early_eligible(eligible_times, archive_start),
        "capability_rows": [
            {
                "exchange": row.get("exchange"),
                "declared_available": row.get("declared_available"),
                "coverage_type": row.get("coverage_type"),
                "note": row.get("note"),
            }
            for row in capability_rows
        ],
    }


def verify_manifest(export_dir: Path) -> dict:
    manifest = json.loads((export_dir / "export_manifest.json").read_text())
    files = []
    ok = True
    for item in manifest["files"]:
        path = export_dir / item["name"]
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        # CSV row count excludes the header line.
        row_count = max(data.count(b"\n") - 1, 0) if data.endswith(b"\n") else data.count(b"\n")
        match = digest == item["sha256"] and row_count == item["rows"]
        ok = ok and match
        files.append({"name": item["name"], "sha256_ok": digest == item["sha256"], "rows_ok": row_count == item["rows"]})
    return {"ok": ok, "files": files}


def render_markdown(result: dict) -> str:
    lines = [
        "# Live-archive replay preflight — Phase A coverage analysis",
        "",
        "Coverage classification of the owner-run read-only export. Detector events, episode counts, and forward outcomes were not computed. Production was not queried by this analysis.",
        "",
        f"- EXPORT_HASH_VERIFICATION: `{result['export_hash_verification']['ok']}`",
        f"- ARCHIVE_OBSERVED_START: `{result['archive_observed_start']}`",
        f"- ARCHIVE_OBSERVED_END: `{result['archive_observed_end']}`",
        f"- TOTAL_5M_BUCKETS: `{result['total_5m_buckets']}` (`{result['grid_start']}` through `{result['grid_end_inclusive']}`)",
        f"- CORE_FAMILIES: `{', '.join(result['core_families'])}`",
        f"- PIT required for: `{', '.join(result['pit_required_families'])}`",
        f"- CONNECTIVITY_EVENT_COUNT: `{result['connectivity']['event_count']}`",
        f"- CONNECTIVITY_STATUS_INTERPRETATION: `{result['connectivity']['interpretation']}`",
        f"- LIQUIDATION_HISTORICAL_HEALTH_PROVABLE: `{result['liquidation_historical_health_provable']}`",
        f"- FULL_CURRENT_DETECTOR_REPLAY_ELIGIBILITY: `{result['full_current_detector_replay_eligibility']}`",
        f"- PHASE_A_DECISION: `{result['phase_a_decision']}`",
        f"- SOURCE_SEMANTICS_CHANGES: `{result['source_semantics_changes']}`",
        f"- REPLAY_AUTHORIZED: `{result['replay_authorized']}`",
        f"- Quorum buckets starting before the first live kline: `{json.dumps(result['eligible_before_observed_live_kline_start'], sort_keys=True)}`",
        "",
        "A 5-minute bucket can start before the first live 1-minute kline and still contain live observations from later in that bucket. Those buckets are live rows. They are not lookback rows and they are not backfill.",
        "",
        "## Per venue",
        "",
    ]
    for venue, block in result["per_venue"].items():
        lines.append(
            f"- `{venue}` 5/5 `{block['live_bar_5_of_5_count']}` ({block['live_bar_5_of_5_fraction']}) "
            f"OI>=2 `{block['oi_ge_2_count']}` ({block['oi_ge_2_fraction']}) "
            f"mixed OI units `{block['oi_mixed_unit_buckets']}` "
            f"PIT `{block['pit_metadata_available_buckets']}` ({block['pit_metadata_coverage_fraction']}) "
            f"liquidation rows present `{block['liquidation_rows_present']}` "
            f"longest price ineligible `{block['longest_price_ineligible_run_buckets']}` "
            f"price gaps after first eligible `{block['price_gap_runs_after_first_eligible']}` "
            f"(gt 1 bucket `{block['price_gap_runs_gt_1_bucket']}`) "
            f"longest OI ineligible `{block['longest_oi_ineligible_run_buckets']}` "
            f"OI gaps after first eligible `{block['oi_gap_runs_after_first_eligible']}` "
            f"(gt 1 bucket `{block['oi_gap_runs_gt_1_bucket']}`)"
        )
    lines.extend(["", "## OI units and PIT", ""])
    lines.append(f"- Live OI units: `{json.dumps(result['oi_units']['live_units'], sort_keys=True)}`")
    lines.append(f"- Live OI unit transitions: `{json.dumps(result['oi_units']['live_unit_transitions'], sort_keys=True)}`")
    lines.append(f"- PIT: `{json.dumps(result['pit'], sort_keys=True)}`")
    if (
        result["predicates"]["taker_split_complete_quorum_buckets"]
        and result["families"]["taker_flow"]["eligible_buckets"] == 0
    ):
        lines.append(
            "- Taker buy/sell splits meet venue quorum on the counted buckets. "
            "Taker notional stays ineligible because `exchange_instrument_history` has no PIT row. "
            "That blocks `TAKER_FLOW_EXTREME_*` only."
        )
    if result["families"]["volume"]["eligible_buckets"] == 0 and result["predicates"]["bar_5_of_5_quorum_buckets"]:
        lines.append(
            "- Volume notional stays ineligible on every bucket for the same missing PIT history. "
            "That blocks `POSITION_BUILDUP_COMPRESSION` and `CORE_FAMILIES` usability. "
            "It does not block `PRICE_OI_CONTRACTION_*`."
        )
    lines.extend(["", "## Predicates", ""])
    for key, value in result.get("predicates", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Family quorum", ""])
    for name, block in result["families"].items():
        lines.append(
            f"- `{name}` eligible `{block['eligible_buckets']}` ({block['eligible_fraction']}) "
            f"quorum-and-mature `{block['quorum_and_mature_buckets']}` "
            f"first quorum `{block['first_quorum_timestamp']}` "
            f"first mature `{block['first_mature_timestamp']}`"
        )
    lines.extend(["", "## Maturity", ""])
    for key, value in result["first_mature"].items():
        lines.append(f"- FIRST_MATURE_{key.upper()}_TIMESTAMP: `{value}`")
    lines.extend([
        "",
        "## Event families",
        "",
        "The longest ineligible run includes the prefix before the first mature bucket. "
        "Interior gap counts do not include that prefix or a trailing suffix. "
        "A gap greater than 1 hour is longer than 12 buckets. A gap greater than 1 day is longer than 288 buckets.",
        "",
    ])
    for name, event in result["events"].items():
        lines.append(
            f"- `{name}` = `{event['status']}` "
            f"first `{event['first_replayable_timestamp']}` "
            f"last `{event['last_replayable_timestamp']}` "
            f"buckets `{event['replayable_bucket_count']}` "
            f"fraction `{event['replayable_bucket_fraction']}` "
            f"intervals `{event['replayable_interval_count']}` "
            f"blockers `{event['blockers']}` "
            f"longest ineligible `{event['longest_ineligible_run']}` "
            f"interior gaps `{event['interior_gap_runs']}` "
            f"gt_1_bucket `{event['number_of_gap_runs_gt_1_bucket']}` "
            f"gt_1_hour `{event['number_of_gap_runs_gt_1_hour']}` "
            f"gt_1_day `{event['number_of_gap_runs_gt_1_day']}`"
        )
        if event["replayable_interval_count"] <= 8:
            for interval in event["replayable_intervals"]:
                lines.append(
                    f"  - interval `{interval['start']}` through `{interval['end']}` "
                    f"({interval['buckets']} buckets)"
                )
        if event["interior_gap_runs"] <= 8:
            for gap in event["interior_gaps"]:
                lines.append(
                    f"  - interior gap `{gap['start']}` through `{gap['end']}` "
                    f"({gap['buckets']} buckets)"
                )
    product = result["product_semantics"]
    lines.extend([
        "",
        "## Product semantics",
        "",
        f"- NO ACTIVE EVENTS reproducible: `{product['no_active_events_reproducible']}`",
        f"- NO ACTIVE EVENTS blocker: `{product['no_active_events_blocker']}`",
        f"- DATA DEGRADED volume reason follows from coverage: `{product['data_degraded_volume_reason_follows_from_coverage']}`",
        f"- Full status machine replayable: `{product['full_status_machine_replayable']}`",
        f"- Status gates absent from the export: `{product['full_status_machine_not_in_export']}`",
        "",
        "## Blockers",
        "",
    ])
    for blocker in result["top_coverage_blockers"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", f"NEXT_UNIT: `{json.dumps(result['next_unit'], sort_keys=True)}`", ""])
    code = result.get("liquidation_code_path") or {}
    if code:
        lines.append(
            "Liquidation code-path quorum, which treats an empty connectivity log as no outage, "
            f"covers `{code.get('replayable_bucket_count')}` buckets "
            f"in `{code.get('replayable_interval_count')}` interval(s), "
            f"with `{code.get('interior_gap_runs')}` interior gap(s). "
            "That count is not historical feed-health proof and is not liquidation replay eligibility."
        )
        lines.append("")
    lines.append(
        "Empty connectivity is no evidence of an outage and is not historical proof of a healthy liquidation feed. "
        "Backfill rows were not substituted for live rows. Current instrument metadata was not used as PIT. "
        "A 5-minute bucket needs all 5 live minute bars. Open interest needs at least two live observations in one unit. "
        "Venue quorum is 2."
    )
    lines.append("")
    return "\n".join(lines)


def _predicate_counts(grid, by_bucket_venue, min_venues: int) -> dict:
    def quorum(predicate) -> int:
        return sum(
            1 for bucket in grid
            if sum(1 for venue in VENUES if predicate(by_bucket_venue[(bucket, venue)])) >= min_venues
        )

    total = len(grid)
    bar = quorum(lambda row: row["bar_coverage_eligible"])
    price = quorum(lambda row: row["price_feature_non_null"])
    oi_ge2 = quorum(lambda row: row["usable_oi_distinct_timestamps"] >= 2)
    oi = quorum(lambda row: row["oi_feature_non_null"])
    taker_split = quorum(lambda row: row["taker_split_complete_expected_minutes"] >= 5)
    return {
        "bar_5_of_5_quorum_buckets": bar,
        "bar_5_of_5_quorum_fraction": _fraction(bar, total),
        "price_feature_quorum_buckets": price,
        "oi_ge_2_quorum_buckets": oi_ge2,
        "oi_ge_2_quorum_fraction": _fraction(oi_ge2, total),
        "oi_eligible_quorum_buckets": oi,
        "taker_split_complete_quorum_buckets": taker_split,
        "taker_split_complete_quorum_fraction": _fraction(taker_split, total),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase A live-archive coverage analysis")
    parser.add_argument("--export-dir", required=True)
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    args = parser.parse_args(argv)
    result = analyze_export(Path(args.export_dir))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        Path(args.json_out).write_text(text)
    else:
        print(text, end="")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(result))
    return 0


def _events(grid, quorum, mature, code_liq, code_liq_times, cfg, *, maturity_days, heartbeat_provable):
    out = {}
    for name, families in EVENT_FAMILIES.items():
        enabled = _rule_enabled(cfg, RULE_ENABLED_KEY[name])
        if not enabled:
            out[name] = _event_record("DISABLED_IN_CURRENT_CONFIG", grid, [False] * len(grid), ["RULE_DISABLED"])
            continue
        if families == ("liquidations",):
            out[name] = _liquidation_event(grid, code_liq, code_liq_times, maturity_days, heartbeat_provable)
            continue
        mask = []
        for index, bucket in enumerate(grid):
            ok = all(quorum[family][index] and mature[family][index] for family in families)
            mask.append(ok)
        blockers = _family_blockers(families, quorum, mature)
        if any(mask) and _interior_gap_count(mask) == 0 and _true_runs(mask) == 1:
            status = "REPLAYABLE"
            blockers = []
        elif any(mask):
            status = "PARTIALLY_REPLAYABLE_WITH_INTERVAL"
            if _interior_gap_count(mask):
                blockers = blockers + ["INTERIOR_COVERAGE_GAPS"]
        else:
            status = "BLOCKED"
        out[name] = _event_record(status, grid, mask, blockers)
    return out


def _liquidation_event(grid, code_liq, code_liq_times, maturity_days, heartbeat_provable):
    if not heartbeat_provable:
        record = _event_record("INSUFFICIENT_EVIDENCE", grid, [False] * len(grid), [
            "CONNECTIVITY_LOG_EMPTY_HEARTBEAT_NOT_HISTORICALLY_PROVABLE",
        ])
        record["code_path_note"] = (
            "Empty connectivity_events makes outage_overlap false in the current "
            "heartbeat function. That is no evidence of an outage, not proof the "
            "feed was healthy. Code-path quorum counts are reported separately."
        )
        record["code_path_quorum_buckets"] = sum(1 for flag in code_liq if flag)
        record["code_path_first_mature"] = iso(first_mature_timestamp(grid, code_liq_times, maturity_days=maturity_days))
        return record
    # A non-empty log can be evaluated with the same maturity rule. This export
    # has no events; the branch exists so the predicate stays explicit.
    mask = []
    mature_flags = [history_is_mature(code_liq_times, bucket, maturity_days=maturity_days) for bucket in grid]
    for quorum_ok, mature_ok in zip(code_liq, mature_flags):
        mask.append(bool(quorum_ok and mature_ok))
    if any(mask) and _interior_gap_count(mask) == 0 and _true_runs(mask) == 1:
        status = "REPLAYABLE"
        blockers = []
    elif any(mask):
        status = "PARTIALLY_REPLAYABLE_WITH_INTERVAL"
        blockers = ["INTERIOR_COVERAGE_GAPS"] if _interior_gap_count(mask) else []
    else:
        status = "BLOCKED"
        blockers = ["LIQUIDATION_QUORUM_OR_MATURITY"]
    return _event_record(status, grid, mask, blockers)


def _family_blockers(families, quorum, mature) -> list[str]:
    blockers = []
    labels = {
        "price_structure": "PRICE_STRUCTURE",
        "oi": "OI",
        "volume": "VOLUME_PIT_NOTIONAL",
        "taker_flow": "TAKER_FLOW_PIT_NOTIONAL",
    }
    for family in families:
        if not any(quorum[family]):
            if family in PIT_REQUIRED_FAMILIES:
                blockers.append(f"{labels[family]}_NEVER_ELIGIBLE")
            else:
                blockers.append(f"{labels[family]}_QUORUM_NEVER_MET")
        elif not any(flag and mature[family][i] for i, flag in enumerate(quorum[family])):
            blockers.append(f"{labels[family]}_PERCENTILE_NOT_MATURE")
    return blockers


def _event_record(status, grid, mask, blockers) -> dict:
    hits = [bucket for bucket, ok in zip(grid, mask) if ok]
    gaps = _gap_stats(grid, mask)
    intervals = _intervals(grid, mask)
    return {
        "status": status,
        "first_replayable_timestamp": iso(hits[0]) if hits else None,
        "last_replayable_timestamp": iso(hits[-1]) if hits else None,
        "replayable_bucket_count": len(hits),
        "replayable_bucket_fraction": _fraction(len(hits), len(grid)),
        "replayable_intervals": [
            {"start": iso(start), "end": iso(end), "buckets": count}
            for start, end, count in intervals
        ],
        "replayable_interval_count": len(intervals),
        "blockers": blockers,
        "longest_ineligible_run_buckets": gaps["longest"],
        "longest_ineligible_run": gaps["longest_span"],
        "interior_gap_runs": gaps["interior_runs"],
        "number_of_gap_runs_gt_1_bucket": gaps["gt_1_bucket"],
        "number_of_gap_runs_gt_1_hour": gaps["gt_1_hour"],
        "number_of_gap_runs_gt_1_day": gaps["gt_1_day"],
        "interior_gaps": [
            {"start": iso(start), "end": iso(end), "buckets": count}
            for start, end, count in gaps["interior_intervals"]
        ],
        "_mask": list(mask),
    }


def _family_block(grid, quorum, mature) -> dict:
    out = {}
    for family in FAMILY_FLAG:
        eligible = sum(1 for flag in quorum[family] if flag)
        both = sum(1 for flag, mat in zip(quorum[family], mature[family]) if flag and mat)
        first_quorum = next((bucket for bucket, flag in zip(grid, quorum[family]) if flag), None)
        out[family] = {
            "eligible_buckets": eligible,
            "eligible_fraction": _fraction(eligible, len(grid)),
            "venue_quorum_eligible_buckets": eligible,
            "venue_quorum_eligible_fraction": _fraction(eligible, len(grid)),
            "quorum_and_mature_buckets": both,
            "quorum_and_mature_fraction": _fraction(both, len(grid)),
            "first_quorum_timestamp": iso(first_quorum),
            "first_mature_timestamp": iso(next((bucket for bucket, mat in zip(grid, mature[family]) if mat), None)),
            "longest_ineligible_run_buckets": _false_runs(list(quorum[family])),
        }
    return out


def _per_venue(grid, by_bucket_venue, archive_rows) -> dict:
    out = {}
    total = len(grid)
    for venue in VENUES:
        rows = [by_bucket_venue[(bucket, venue)] for bucket in grid]
        five = sum(1 for row in rows if row["bar_coverage_eligible"])
        oi_ge2 = sum(1 for row in rows if row["usable_oi_distinct_timestamps"] >= 2)
        mixed = sum(1 for row in rows if row["oi_mixed_units"])
        pit = sum(1 for row in rows if row["pit_history_present"])
        liq_rows = sum(1 for row in rows if row["liquidation_rows_present"] is True)
        price_mask = [row["price_feature_non_null"] for row in rows]
        oi_mask = [row["oi_feature_non_null"] for row in rows]
        price_runs = _false_runs(price_mask)
        oi_runs = _false_runs(oi_mask)
        price_gaps = _interior_gap_intervals(grid, price_mask)
        oi_gaps = _interior_gap_intervals(grid, oi_mask)
        out[venue] = {
            "live_bar_5_of_5_count": five,
            "live_bar_5_of_5_fraction": _fraction(five, total),
            "oi_ge_2_count": oi_ge2,
            "oi_ge_2_fraction": _fraction(oi_ge2, total),
            "oi_mixed_unit_buckets": mixed,
            "pit_metadata_available_buckets": pit,
            "pit_metadata_coverage_fraction": _fraction(pit, total),
            "liquidation_rows_present_buckets": liq_rows,
            "liquidation_rows_present": _archive_count(archive_rows, "liquidations", venue) > 0,
            "price_feature_non_null_buckets": sum(1 for row in rows if row["price_feature_non_null"]),
            "oi_feature_non_null_buckets": sum(1 for row in rows if row["oi_feature_non_null"]),
            "volume_notional_non_null_buckets": sum(1 for row in rows if row["volume_notional_non_null"]),
            "taker_notional_non_null_buckets": sum(1 for row in rows if row["taker_notional_non_null"]),
            "taker_split_complete_buckets": sum(1 for row in rows if row["taker_split_complete_expected_minutes"] >= 5),
            "code_path_heartbeat_healthy_buckets": sum(1 for row in rows if row["heartbeat_healthy"]),
            "code_path_liquidation_feature_non_null_buckets": sum(1 for row in rows if row["liquidation_feature_non_null"]),
            "longest_price_ineligible_run_buckets": price_runs,
            "longest_oi_ineligible_run_buckets": oi_runs,
            "price_gap_runs_after_first_eligible": len(price_gaps),
            "price_gap_runs_gt_1_bucket": sum(1 for _s, _e, count in price_gaps if count > 1),
            "oi_gap_runs_after_first_eligible": len(oi_gaps),
            "oi_gap_runs_gt_1_bucket": sum(1 for _s, _e, count in oi_gaps if count > 1),
        }
    return out


def _oi_units(rows) -> dict:
    live = {}
    for row in rows:
        if (row.get("source") or "") != "live":
            continue
        live.setdefault(row.get("exchange"), []).append(row.get("oi_unit") or "")
    transitions = {venue: max(len(set(units)) - 1, 0) for venue, units in live.items()}
    return {"live_units": live, "live_unit_transitions": transitions}


def _pit(instrument_rows, requested) -> dict:
    notes = {row.get("exchange"): row.get("note") or "" for row in instrument_rows}
    present = sum(1 for row in requested if row["pit_history_present"])
    return {
        "history_rows_by_venue": notes,
        "pit_history_present_bucket_rows": present,
    }


def _archive_bounds(rows):
    live = [
        row for row in rows
        if row.get("table_name") == "klines_1m" and row.get("source") == "live" and row.get("min_ts")
    ]
    if not live:
        return None, None
    start = min(row["min_ts"] for row in live)
    end = max(row["max_ts"] for row in live)
    return start, end


def _eligible_times(rows, flag: str, min_venues: int) -> list[datetime]:
    counts: dict[datetime, int] = {}
    for row in rows:
        if row[flag]:
            counts[row["bucket_start"]] = counts.get(row["bucket_start"], 0) + 1
    return sorted(bucket for bucket, count in counts.items() if count >= min_venues)


def _liquidation_code_times(rows, *, min_venues: int) -> list[datetime]:
    counts: dict[datetime, int] = {}
    for row in rows:
        if row["liquidation_declared_available"] and row["heartbeat_healthy"]:
            counts[row["bucket_start"]] = counts.get(row["bucket_start"], 0) + 1
    return sorted(bucket for bucket, count in counts.items() if count >= min_venues)


def _liquidation_code_ok(by_bucket_venue, bucket, *, min_venues: int) -> bool:
    count = 0
    for venue in VENUES:
        row = by_bucket_venue[(bucket, venue)]
        if row["liquidation_declared_available"] and row["heartbeat_healthy"]:
            count += 1
    return count >= min_venues


def _full_detector(events, families) -> tuple[str, int]:
    """Full current-detector eligibility is the intersection of enabled families.

    A disabled rule is not a coverage blocker. ``PARTIAL`` is a non-empty
    intersection that is not one clean replayable run of every enabled family.
    An empty intersection, including a core family that is never usable, is
    ``NOT_ELIGIBLE``.
    """
    enabled = [event for event in events.values() if event["status"] != "DISABLED_IN_CURRENT_CONFIG"]
    if not enabled or any("_mask" not in event for event in enabled):
        return "INCOMPLETE", 0
    simultaneous = [all(bits) for bits in zip(*(event["_mask"] for event in enabled))]
    count = sum(1 for flag in simultaneous if flag)
    volume_never = families["volume"]["eligible_buckets"] == 0
    clean = all(event["status"] == "REPLAYABLE" for event in enabled) and not volume_never
    if clean and count > 0 and _true_runs(simultaneous) == 1 and _interior_gap_count(simultaneous) == 0:
        return "ELIGIBLE", count
    if count > 0 and not volume_never:
        return "PARTIAL", count
    return "NOT_ELIGIBLE", count


def _phase(full: str, events: dict) -> str:
    if full == "ELIGIBLE":
        return "ARCHIVE_ELIGIBLE_FOR_FULL_CURRENT_DETECTOR_REPLAY"
    useful = any(
        event["status"] in {"REPLAYABLE", "PARTIALLY_REPLAYABLE_WITH_INTERVAL"}
        for event in events.values()
    )
    if useful:
        return "ARCHIVE_PARTIALLY_ELIGIBLE_FOR_EVENT_FAMILY_REPLAY"
    return "ARCHIVE_NOT_ELIGIBLE_FOR_USEFUL_DETECTOR_REPLAY"


def _incomplete(reason, verification, manifest) -> dict:
    return {
        "export_hash_verification": verification,
        "manifest_interval": manifest,
        "phase_a_decision": "INCOMPLETE_EXPORT_OR_ANALYSIS",
        "full_current_detector_replay_eligibility": "INCOMPLETE",
        "reason": reason,
    }


def _gap_stats(grid, mask: list[bool]) -> dict:
    runs = []
    length = 0
    for flag in mask:
        if not flag:
            length += 1
        elif length:
            runs.append(length)
            length = 0
    if length:
        runs.append(length)
    interior = _interior_gap_intervals(grid, mask)
    lengths = [count for _start, _end, count in interior]
    return {
        "longest": max(runs, default=0),
        "longest_span": _span_label(max(runs, default=0)),
        "interior_runs": len(interior),
        "interior_intervals": interior,
        "gt_1_bucket": sum(1 for item in lengths if item > 1),
        "gt_1_hour": sum(1 for item in lengths if item > HOUR_BUCKETS),
        "gt_1_day": sum(1 for item in lengths if item > DAY_BUCKETS),
    }


def _interior_gap_intervals(grid, mask: list[bool]) -> list[tuple]:
    if not any(mask):
        return []
    first = mask.index(True)
    last = len(mask) - 1 - mask[::-1].index(True)
    window = grid[first:last + 1]
    inverted = [not ok for ok in mask[first:last + 1]]
    return _intervals(window, inverted)


def _interior_gap_count(mask: list[bool]) -> int:
    return len(_interior_gap_intervals(list(range(len(mask))), mask))


def _true_runs(mask: list[bool]) -> int:
    runs = 0
    prev = False
    for flag in mask:
        if flag and not prev:
            runs += 1
        prev = flag
    return runs


def _intervals(grid, mask):
    found = []
    start = None
    prev = None
    count = 0
    for bucket, ok in zip(grid, mask):
        if ok:
            if start is None:
                start = bucket
                count = 1
            else:
                count += 1
            prev = bucket
        elif start is not None:
            found.append((start, prev, count))
            start = None
            prev = None
            count = 0
    if start is not None:
        found.append((start, prev, count))
    return found


def _false_runs(mask: list[bool]) -> int:
    longest = 0
    length = 0
    for flag in mask:
        if not flag:
            length += 1
            longest = max(longest, length)
        else:
            length = 0
    return longest


def _mask_summary(grid, mask) -> dict:
    return _event_record("DIAGNOSTIC", grid, mask, [])


def _rule_enabled(cfg: BetaConfig, key: str) -> bool:
    rule = cfg.rule(key)
    if "enabled" not in rule:
        return True
    return bool(rule["enabled"])


def _stage2_maturity_days(symbol: str) -> int:
    from common.stage2_config import STAGE2_CONFIG_PATH, Stage2Config
    loaded = Stage2Config.load(STAGE2_CONFIG_PATH)
    resolved = loaded.resolve(symbol)
    return int(resolved["percentiles"]["confidence_tiers"]["building_below_days"])


def _dedupe(rows: list[dict]) -> list[dict]:
    by_key = {}
    for row in rows:
        by_key[(row["bucket_start"], row["exchange"])] = row
    return list(by_key.values())


def _without_mask(record: dict) -> dict:
    cleaned = dict(record)
    cleaned.pop("_mask", None)
    return cleaned


def _product_semantics(families, events) -> dict:
    enabled = {
        name: event for name, event in events.items()
        if event["status"] != "DISABLED_IN_CURRENT_CONFIG"
    }
    volume_buckets = families["volume"]["eligible_buckets"]
    core_usable = all(families[family]["eligible_buckets"] > 0 for family in CORE_FAMILIES)
    return {
        "core_families": list(CORE_FAMILIES),
        "all_enabled_event_families_replayable": all(
            event["status"] == "REPLAYABLE" for event in enabled.values()
        ),
        "enabled_event_statuses": {name: event["status"] for name, event in enabled.items()},
        "volume_eligible_buckets": volume_buckets,
        "core_families_simultaneously_usable_somewhere": core_usable and volume_buckets > 0,
        "no_active_events_reproducible": False,
        "no_active_events_blocker": None if volume_buckets else "FAMILY_UNUSABLE:volume",
        "data_degraded_volume_reason_follows_from_coverage": volume_buckets == 0,
        "full_status_machine_replayable": False,
        "full_status_machine_not_in_export": [
            "materialized",
            "stale_barrier",
            "evaluation_fresh",
            "ingestion_heartbeat",
        ],
    }


def _top_blockers(events, product) -> list[str]:
    ordered = []
    for event in events.values():
        for blocker in event["blockers"]:
            if blocker == "RULE_DISABLED" or blocker in ordered:
                continue
            ordered.append(blocker)
    if product["no_active_events_blocker"] == "FAMILY_UNUSABLE:volume":
        ordered.append("CORE_FAMILY_VOLUME_NEVER_USABLE")
    ordered.append("FULL_PRODUCT_STATUS_GATES_NOT_IN_EXPORT")
    return ordered


def _next_unit(phase: str, events: dict):
    useful = [
        name for name, event in events.items()
        if event["status"] in {"REPLAYABLE", "PARTIALLY_REPLAYABLE_WITH_INTERVAL"}
    ]
    if phase == "ARCHIVE_ELIGIBLE_FOR_FULL_CURRENT_DETECTOR_REPLAY":
        return {
            "unit": "LIVE_ARCHIVE_FULL_CURRENT_DETECTOR_REPLAY_ISOLATED_NON_PRODUCTION",
            "families": useful,
            "replay_authorized": False,
            "scope": (
                "Isolated non-production replay of the current detector on the reported "
                "interval. Do not compute P4 outcomes and do not touch production."
            ),
        }
    if phase != "ARCHIVE_PARTIALLY_ELIGIBLE_FOR_EVENT_FAMILY_REPLAY" or not useful:
        return None
    only_price_oi = set(useful) <= {"PRICE_OI_CONTRACTION_DOWN", "PRICE_OI_CONTRACTION_UP"}
    unit = (
        "LIVE_ARCHIVE_PRICE_OI_FAMILY_REPLAY_ISOLATED_NON_PRODUCTION"
        if only_price_oi
        else "LIVE_ARCHIVE_EVENT_FAMILY_REPLAY_ISOLATED_NON_PRODUCTION"
    )
    return {
        "unit": unit,
        "families": useful,
        "replay_authorized": False,
        "scope": (
            "Isolated non-production replay of only the listed families on their reported "
            "intervals. Do not replay blocked or insufficient families, do not compute "
            "episode counts or P4 outcomes, and do not touch production."
        ),
    }


def _early_eligible(eligible_times, archive_start) -> dict:
    if not archive_start:
        return {family: {"count": None, "timestamps": []} for family in eligible_times}
    start = _parse_ts(archive_start)
    out = {}
    for family, times in eligible_times.items():
        early = [iso(ts) for ts in times if ts < start]
        out[family] = {"count": len(early), "timestamps": early}
    return out


def _archive_count(rows, table: str, venue: str) -> int:
    for row in rows:
        if row.get("table_name") == table and row.get("exchange") == venue and row.get("note") != "table_absent":
            try:
                return int(row.get("row_count") or 0)
            except ValueError:
                return 0
    return 0


def _normalize(row: dict) -> dict:
    out = dict(row)
    out["bucket_start"] = _parse_ts(row["bucket_start"])
    out["exchange"] = row["exchange"]
    for key in (
        "bar_coverage_eligible", "price_feature_non_null", "oi_feature_non_null",
        "oi_evaluable", "oi_mixed_units", "volume_notional_non_null", "taker_notional_non_null",
        "pit_history_present", "heartbeat_healthy", "liquidation_feature_non_null",
        "liquidation_declared_available", "missing_pit_history",
    ):
        out[key] = _parse_bool(row.get(key))
    out["usable_oi_distinct_timestamps"] = _parse_int(row.get("usable_oi_distinct_timestamps"))
    out["taker_split_complete_expected_minutes"] = _parse_int(row.get("taker_split_complete_expected_minutes"))
    present = row.get("liquidation_rows_present")
    out["liquidation_rows_present"] = None if present in (None, "") else _parse_bool(present)
    return out


def _is_data_row(row: dict) -> bool:
    return bool(row.get("bucket_start")) and not (row.get("note") or "").startswith("required_input_absent")


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise SystemExit("naive timestamp in coverage export")
    return parsed.astimezone(UTC)


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _parse_int(value) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def _fraction(count: int, total: int):
    if total == 0:
        return None
    return round(count / total, 6)


def _span_label(buckets: int) -> str:
    return str(buckets * 5) + "m"


def iso(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return str(value)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bisect_left(times: list[datetime], target: datetime) -> int:
    lo, hi = 0, len(times)
    while lo < hi:
        mid = (lo + hi) // 2
        if times[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


if __name__ == "__main__":
    raise SystemExit(main())
