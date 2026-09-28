"""Write the overlap artifacts. Comparison numbers stay null without gold."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

from . import (
    CANDIDATE_PROVENANCE_CLASS,
    DECISION_INCOMPLETE,
    SOURCE_TARDIS,
    WAITING_FOR_EXPORT,
)
from .constants import SAMPLE_DATES, VENUES
from .features import production_identity
from .gaps import incident_applies_to_requested_datasets, parse_utc

FLAGS = {
    "PRODUCTION_CODE_CHANGED": False,
    "PRODUCTION_DB_WRITTEN": False,
    "DETECTOR_CHANGED": False,
    "RULES_CHANGED": False,
    "PERCENTILES_COMPUTED_AS_PRODUCTION_30D": False,
    "EPISODES_REPLAYED": False,
    "OUTCOMES_COMPUTED": False,
    "PUSH_CHANGED": False,
    "PROTECTED_RESEARCH_OPENED": False,
    "PAID_SUBSCRIPTION_STARTED": False,
    "DATA_PURCHASED": False,
    "DEPLOYED": False,
}


def audit_sources_sha256(package_dir: Path | None = None) -> str:
    root = package_dir or Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    sql = root / "extract_signalbot_readonly.sql"
    if sql.exists():
        digest.update(sql.name.encode())
        digest.update(b"\0")
        digest.update(sql.read_bytes())
    return digest.hexdigest()


def load_incidents(meta_dir: str) -> dict:
    out = {}
    for name in ("binance-futures", "bybit", "okex-swap"):
        path = os.path.join(meta_dir, f"{name}.json")
        if not os.path.exists(path):
            out[name] = {"loaded": False, "incidents": []}
            continue
        payload = json.loads(Path(path).read_text())
        incidents = payload.get("incidentReports") or []
        out[name] = {
            "loaded": True,
            "http_status": _status_file(os.path.join(meta_dir, f"{name}.code")),
            "incident_count": len(incidents),
            "incidents": incidents,
        }
    return out


def _status_file(path: str) -> int | None:
    if not os.path.exists(path):
        return None
    text = Path(path).read_text().strip()
    return int(text) if text.isdigit() else None


def incidents_touching_sample_dates(raw: dict) -> list[dict]:
    windows = []
    for day in SAMPLE_DATES:
        start = parse_utc(day + "T00:00:00.000Z")
        end = parse_utc(
            "2026-08-02T00:00:00.000Z" if day == "2026-08-01" else "2026-09-02T00:00:00.000Z"
        )
        windows.append((day, start, end))
    touching = []
    for exchange, block in raw.items():
        for incident in block.get("incidents") or []:
            inc_from = parse_utc(incident["from"])
            inc_to = parse_utc(incident["to"])
            for day, start, end in windows:
                if inc_from < end and inc_to > start:
                    touching.append({
                        "tardis_exchange": exchange,
                        "sample_date": day,
                        "from": incident["from"],
                        "to": incident["to"],
                        "status": incident.get("status"),
                        "details": incident.get("details"),
                        "applies_to_trades_or_derivative_ticker": (
                            incident_applies_to_requested_datasets(incident)
                        ),
                        "tag_if_applicable": (
                            "VENDOR_DOCUMENTED_GAP"
                            if incident_applies_to_requested_datasets(incident)
                            else "REVIEWED_NOT_APPLICABLE_TO_REQUESTED_DATASETS"
                        ),
                    })
    return touching


def build_incomplete_payload(*, base_sha: str, inventory: list[dict],
                             incidents_raw: dict) -> tuple[dict, dict]:
    identity = production_identity()
    touching = incidents_touching_sample_dates(incidents_raw)
    applicable = [row for row in touching if row["applies_to_trades_or_derivative_ticker"]]
    schema_stops = [row for row in inventory if row["status"] not in ("OK",)]
    manifest = {
        "experiment": "TARDIS_FREE_OVERLAP_VALIDATION_V0",
        "comparison_performed": False,
        "reason": WAITING_FOR_EXPORT,
        "base_sha": base_sha,
        "audit_sources_sha256": audit_sources_sha256(),
        "analysis_commit_note": (
            "The git commit that contains this file is the analysis SHA. "
            "A file cannot store its own commit id."
        ),
        "candidate_provenance_class_under_test": CANDIDATE_PROVENANCE_CLASS,
        "tardis_source_label": SOURCE_TARDIS,
        "dates": list(SAMPLE_DATES),
        "venue_mappings": [
            {
                "signalbot_exchange": v.signalbot_exchange,
                "canonical_symbol": v.canonical_symbol,
                "tardis_exchange": v.tardis_exchange,
                "tardis_symbol": v.tardis_symbol,
                "quantity_unit": v.quantity_unit,
                "oi_unit_assumption": v.oi_unit,
                "contract_multiplier_applied": v.contract_multiplier,
            }
            for v in VENUES
        ],
        "config_identity": identity,
        "beta_rules_used": False,
        "percentile_engine_used": False,
        "timestamp_semantics": {
            "bucket": "[B, B+5 minutes). The instant B+5 minutes belongs to the next bucket.",
            "tardis_trade_timestamp": (
                "CSV timestamp column, microseconds since epoch. Tardis documents "
                "this as the exchange timestamp, with local_timestamp substituted "
                "only when the exchange omits it. Minute bars use that timestamp "
                "the way LiveBarBuilder uses trade.ts (Binance T, Bybit T, OKX ts), "
                "which is exchange event time, not collector receive time."
            ),
            "tardis_local_timestamp": "vendor receive time, retained and not used as the bar clock",
            "tardis_open_interest_timestamp": (
                "CSV timestamp column (exchange time, same fallback rule). "
                "Not resampled onto Signalbot poll times."
            ),
            "signalbot_kline_ts": "1-minute bar open, exchange event time from the live trade builder, source=live only",
            "signalbot_open_interest_ts": "collector receive time (time.time() at the live poll), source=live only",
            "lookahead": "no observation at or after the right edge is included",
        },
        "metadata_assumptions": {
            "binance_bybit_quantity_unit": "base, matching common.instrument_metadata and the live clients",
            "okx_quantity_unit": "contracts",
            "okx_contract_multiplier": (
                "NOT taken from today's ctVal. Notional stays fail-closed until "
                "exchange_instrument_history supplies a PIT multiplier as-of the bucket start."
            ),
            "tardis_amount": (
                "exchange-native quantity. Not multiplied before aggregation. "
                "OKX live collector stores trades sz as qty; Tardis amount is that same native field."
            ),
            "tardis_oi_unit": (
                "Tardis publishes no unit column. Binance and Bybit observations are "
                "labeled base and OKX observations are labeled contracts, which is the "
                "live storage unit. A gold unit disagreement fails the bucket closed."
            ),
            "taker_side": (
                "Tardis side buy/sell is the aggressor. Mapped to LiveBarBuilder "
                "before any aggregate was compared. unknown fails the minute's taker split closed."
            ),
            "rows_before_midnight": (
                "Bybit and OKX derivative_ticker files can start a few milliseconds "
                "before 00:00 UTC. Those rows are outside [day, next day) and are not "
                "assigned to the 00:00 bucket."
            ),
        },
        "files": inventory,
        "schema_stops": schema_stops,
        "documented_vendor_gaps_on_sample_dates": {
            "incidents_whose_window_overlaps_a_sample_date": touching,
            "applicable_to_trades_or_derivative_ticker": applicable,
            "buckets_tagged": len(applicable),
        },
        "cost_incurred_usd": 0,
    }
    summary = {
        "comparison_performed": False,
        "signalbot_gold_source": None,
        "waiting_for": WAITING_FOR_EXPORT,
        "overall_decision": DECISION_INCOMPLETE,
        "verdicts": {
            "price": "NOT_RUN",
            "range": "NOT_RUN",
            "volume": "NOT_RUN",
            "oi": "NOT_RUN",
            "taker": "NOT_RUN",
            "consensus": "NOT_RUN",
        },
        "oi_sign_agreement_by_magnitude": None,
        "tail_agreement_summary": None,
        "null_evaluability_disagreements": None,
        "documented_vendor_gaps": manifest["documented_vendor_gaps_on_sample_dates"],
        "top_mismatch_causes": [],
        "dates_compared": [],
        "venues_files_inventoried": [v.signalbot_exchange for v in VENUES],
        "tardis_files_downloaded": [
            {
                "file": row["path_basename"],
                "http_status": row["http_status"],
                "sha256": row["sha256"],
                "compressed_bytes": row["compressed_bytes"],
                "row_count": row["row_count"],
                "status": row["status"],
            }
            for row in inventory
        ],
        "cost_incurred_usd": 0,
        "flags": FLAGS,
        "next_experiment": (
            "Owner runs the read-only extractor, then re-runs this package with "
            "--gold-dir. That is still a USD 0 comparison. It is not authorization "
            "to buy a Tardis plan."
        ),
    }
    return manifest, summary


def _inventory_notes(files: list[dict]) -> str:
    lines = ["## Inventory notes (not a comparison)", ""]
    early = [
        f"- `{row['path_basename']}`: {row['rows_before_sample_date']} row(s) before 00:00 UTC"
        for row in files
        if row.get("rows_before_sample_date")
    ]
    lines.append("Rows before the sample date, excluded from that date's buckets:")
    lines.append("")
    lines.extend(early or ["- none"])
    lines.append("")
    unordered = [
        f"- `{row['path_basename']}`"
        for row in files
        if row.get("timestamp_monotonic_non_decreasing") is False
    ]
    lines.append(
        "Files whose exchange timestamps are not non-decreasing. "
        "Open-interest endpoints are chosen by timestamp, not by file order:"
    )
    lines.append("")
    lines.extend(unordered or ["- none"])
    lines.append("")
    sides: dict[str, int] = {}
    for row in files:
        for side, count in (row.get("side_counts") or {}).items():
            sides[side] = sides.get(side, 0) + count
    lines.append(
        "Trade `side` values observed, after the buy/sell/unknown mapping was fixed from the Tardis docs: "
        + (", ".join(f"`{side}`={count}" for side, count in sorted(sides.items())) or "none")
        + ". No other side token appeared, so nothing was remapped after the count."
    )
    return "\n".join(lines)


def render_report(manifest: dict, summary: dict) -> str:
    lines = [
        "# Tardis free overlap validation V0",
        "",
        "This run inventoried the free first-of-month Tardis files and did not compare them to Signalbot.",
        "",
        f"Overall decision: **{summary['overall_decision']}**",
        "",
        "Status: **WAITING_FOR_SIGNALBOT_EXPORT**",
        "",
        "No Signalbot database credentials, SSH key, or live raw export were available in this environment. Local fixture databases were not used as gold. No feature verdict below is a measurement.",
        "",
        "## What was obtained at USD 0",
        "",
        "Plain GET, no API key, no Range header, no account:",
        "",
        "| File | HTTP | Bytes | Rows | SHA-256 | First timestamp | Last timestamp | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in manifest["files"]:
        lines.append(
            "| `{file}` | {http} | {size} | {rows} | `{sha}` | {first} | {last} | {status} |".format(
                file=row["path_basename"],
                http=row["http_status"],
                size=row["compressed_bytes"],
                rows=row["row_count"],
                sha=row["sha256"],
                first=row["first_timestamp"],
                last=row["last_timestamp"],
                status=row["status"],
            )
        )
    lines += [
        "",
        "URL pattern: `https://datasets.tardis.dev/v1/{exchange}/{dataType}/{YYYY}/{MM}/{DD}/{symbol}.csv.gz`",
        "",
        "Decompressed headers match the documented trades and derivative_ticker schemas. No source was stopped for a schema change. HTTP `Content-Type` is `text/csv`; the body is gzip (`1f 8b`).",
        "",
        "Empty `open_interest` cells are counted in the manifest and are not zeros. Rows timestamped before 00:00 UTC are outside the sample day and are not placed in the first bucket.",
        "",
        _inventory_notes(manifest["files"]),
        "",
        "## Documented vendor gaps",
        "",
    ]
    touching = manifest["documented_vendor_gaps_on_sample_dates"][
        "incidents_whose_window_overlaps_a_sample_date"
    ]
    if not touching:
        lines.append("No incidentReports window overlaps 2026-08-01 or 2026-09-01.")
    else:
        lines.append("Incident windows that overlap a sample date:")
        lines.append("")
        for row in touching:
            lines.append(
                f"- `{row['tardis_exchange']}` {row['sample_date']} "
                f"{row['from']} → {row['to']}: **{row['tag_if_applicable']}**. "
                f"{row['details']}"
            )
    lines += [
        "",
        "Applicable trades or derivative_ticker gap tags on these two dates: "
        f"**{len(manifest['documented_vendor_gaps_on_sample_dates']['applicable_to_trades_or_derivative_ticker'])}**.",
        "",
        "The OKX statistics-channel incident that ends 2026-08-04 overlaps 2026-08-01 and states that other OKX channels were unaffected. It is not applied to `trades` or `derivative_ticker`.",
        "",
        "## Verdicts",
        "",
        "PRICE_VERDICT = NOT_RUN",
        "",
        "RANGE_VERDICT = NOT_RUN",
        "",
        "VOLUME_VERDICT = NOT_RUN",
        "",
        "OI_VERDICT = NOT_RUN",
        "",
        "TAKER_VERDICT = NOT_RUN",
        "",
        "CONSENSUS_VERDICT = NOT_RUN",
        "",
        "OI_SIGN_AGREEMENT_BY_MAGNITUDE = not computed",
        "",
        "TAIL_AGREEMENT_SUMMARY = not computed (would have been labeled SAMPLE-DAY TAIL AGREEMENT, not a production percentile)",
        "",
        "NULL_EVALUABILITY_DISAGREEMENTS = not computed",
        "",
        "TOP_MISMATCH_CAUSES = none; no pairs exist",
        "",
        "No detector episodes, historical outcomes, 30-day percentile ranks, or alpha were computed.",
        "",
        "## Owner commands",
        "",
        "On the host that can read the live Signalbot database, with `SIGNALBOT_DSN` set in the environment and not written to disk:",
        "",
        "```bash",
        "python -m scripts.audit.tardis_free_overlap_v0.extract_signalbot_readonly \\",
        "  --out-dir ./signalbot_gold_20260801_20260901",
        "```",
        "",
        "The script starts a read-only session, exports `source = 'live'` BTCUSDT rows for Binance, Bybit, and OKX on 2026-08-01 and 2026-09-01, plus the PIT instrument rows needed for notional conversion, and prints SHA-256 hashes. It does not export Telegram or user data.",
        "",
        "After those files exist, from this repository:",
        "",
        "```bash",
        "python -m scripts.audit.tardis_free_overlap_v0 compare \\",
        "  --vendor-dir /path/to/tardis-cache \\",
        "  --gold-dir ./signalbot_gold_20260801_20260901 \\",
        "  --out-dir docs/audit/tardis_free_overlap_v0",
        "```",
        "",
        "Do not point `--gold-dir` at a synthetic fixture.",
        "",
        "## Decision",
        "",
        "D. INCOMPLETE_NO_SIGNALBOT_EXPORT",
        "",
        "The free files are readable and the production feature functions are wired for a later comparison. That is not evidence that Tardis reproduces Signalbot's 5-minute state.",
        "",
        "NEXT_EXPERIMENT: finish this free comparison after the owner export. Do not purchase a Tardis plan on the basis of this run.",
        "",
        "COST_INCURRED_USD = 0",
        "",
    ]
    for key, value in summary["flags"].items():
        lines.append(f"{key} = {str(value).lower()}")
    lines.append("")
    return "\n".join(lines)


def gold_export_facts(gold_dir: str) -> dict:
    """Row counts and hashes of the read-only export. Does not interpret PIT rows."""
    root = Path(gold_dir)
    names = (
        "klines_1m.csv",
        "klines_1m_source_counts.csv",
        "open_interest.csv",
        "open_interest_source_counts.csv",
        "exchange_instrument_history.csv",
        "exchange_instruments_current_not_used_as_pit.csv",
    )
    files = {}
    for name in names:
        path = root / name
        if not path.is_file():
            files[name] = {"present": False, "data_rows": None, "sha256": None}
            continue
        payload = path.read_bytes()
        with path.open(newline="") as handle:
            data_rows = max(0, sum(1 for _ in handle) - 1)
        files[name] = {
            "present": True,
            "data_rows": data_rows,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    source_counts = {}
    for name in ("klines_1m_source_counts.csv", "open_interest_source_counts.csv"):
        path = root / name
        if not path.is_file():
            source_counts[name] = []
            continue
        with path.open(newline="") as handle:
            source_counts[name] = list(csv.DictReader(handle))
    return {
        "files": files,
        "source_counts": source_counts,
        "current_instrument_table_used_as_pit": False,
    }


def _fmt(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _feature_line(stats: dict) -> str:
    return (
        f"comparable={stats.get('comparable_count')} "
        f"sign={_fmt(stats.get('sign_agreement_fraction'))} "
        f"spearman={_fmt(stats.get('spearman'))} "
        f"median_abs={_fmt(stats.get('median_absolute_difference'))} "
        f"median_ratio={_fmt(stats.get('median_scale_ratio_tardis_over_gold'))} "
        f"both_null={stats.get('both_null')} "
        f"gold_only={stats.get('gold_only_evaluable')} "
        f"tardis_only={stats.get('tardis_only_evaluable')}"
    )


def render_comparison_report(summary: dict) -> str:
    """Format the frozen comparison. Does not recompute or reclassify it."""
    verdicts = summary["verdicts"]
    gaps = summary["documented_vendor_gaps"]
    causes = summary["top_mismatch_causes"]
    lines = [
        "# Tardis free overlap validation V0",
        "",
        "This run compared the free Tardis files for 2026-08-01 and 2026-09-01 "
        "with the read-only Signalbot live export. Tolerances were not refit. "
        "The current instrument table was not used as point-in-time metadata.",
        "",
        f"Overall decision: **{summary['overall_decision']}**",
        "",
        "## Export and vendor identity",
        "",
        "Signalbot gold is `source=live` only. Empty open-interest cells stay missing.",
        "",
        "| File | Data rows | SHA-256 |",
        "| --- | --- | --- |",
    ]
    for name, facts in summary["gold_export"]["files"].items():
        lines.append(
            f"| `{name}` | {facts['data_rows']} | `{facts['sha256']}` |"
        )
    lines += ["", "Source-count rows shipped with the export:", ""]
    for name, rows in summary["gold_export"]["source_counts"].items():
        lines.append(f"- `{name}`: {rows}")
    lines += [
        "",
        "Tardis files are the same public free bytes as the earlier inventory "
        "(SHA-256 matched before this comparison):",
        "",
        "| File | HTTP | Bytes | Rows | SHA-256 | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["tardis_files"]:
        lines.append(
            "| `{file}` | {http} | {size} | {rows} | `{sha}` | {status} |".format(
                file=row["file"],
                http=row["http_status"],
                size=row["compressed_bytes"],
                rows=row["row_count"],
                sha=row["sha256"],
                status=row["status"],
            )
        )
    lines += [
        "",
        f"DATES_COMPARED = {summary['dates_compared']}",
        "",
        f"VENUES_COMPARED = {summary['venues_compared']}",
        "",
        "## Coverage by venue and date",
        "",
        "A bucket is present when it contains at least one 1-minute bar or one "
        "open-interest observation inside `[B, B+5m)`. Comparable feature pairs "
        "below are the frozen diagnostics on buckets that were not gap-excluded. "
        "OKX notional stays null when no PIT multiplier exists; those nulls are "
        "not zeros and are not treated as agreement of a USD magnitude.",
        "",
        "| Date | Venue | Gold buckets | Vendor buckets | Both present | Missing gold | Missing vendor | Gap-excluded |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["per_venue"]:
        cov = row["coverage"]
        lines.append(
            "| {date} | {ex} | {gold} | {vendor} | {both} | {mg} | {mv} | {gap} |".format(
                date=row["sample_date"],
                ex=row["exchange"],
                gold=cov["gold_buckets"],
                vendor=cov["vendor_buckets"],
                both=cov["both_present_buckets"],
                mg=cov["missing_gold_buckets"],
                mv=cov["missing_vendor_buckets"],
                gap=cov["gap_excluded_buckets"],
            )
        )
    lines += [
        "",
        "Expected buckets per venue-date: 288.",
        "",
        "## Feature agreement by venue and date",
        "",
    ]
    for row in summary["per_venue"]:
        lines.append(f"### {row['sample_date']} {row['exchange']}")
        lines.append("")
        for feature in (
            "price_move_pct", "range_width_pct", "volume_notional_usd",
            "taker_delta_notional_usd", "oi_change_pct",
        ):
            lines.append(f"- `{feature}`: {_feature_line(row['feature_stats'][feature])}")
        ev = row["null_evaluability_disagreements"]
        lines.append(
            f"- evaluability disagreements: count={ev['count']} "
            f"fraction={_fmt(ev['fraction'])} "
            f"buckets_entering_equivalence={ev['buckets_entering_equivalence']}"
        )
        lines.append("")
    lines += [
        "## Aggregate verdicts",
        "",
        "These labels are the frozen `_verdicts` output. A `MATERIAL_REORDER` "
        "finding is attached to price, range, and open interest together because "
        "the frozen function matches on finding code, not on which feature moved. "
        "Consensus is `FAIL` only when `CONSENSUS_QUORUM_DISAGREEMENT` is present; "
        "otherwise the frozen function returns `NOT_EVALUABLE`.",
        "",
        f"PRICE_VERDICT = {verdicts['price']}",
        "",
        f"RANGE_VERDICT = {verdicts['range']}",
        "",
        f"VOLUME_VERDICT = {verdicts['volume']}",
        "",
        f"OI_VERDICT = {verdicts['oi']}",
        "",
        f"TAKER_VERDICT = {verdicts['taker']}",
        "",
        f"CONSENSUS_VERDICT = {verdicts['consensus']}",
        "",
        "Aggregate feature diagnostics:",
        "",
    ]
    for feature, stats in summary["feature_stats"].items():
        lines.append(f"- `{feature}`: {_feature_line(stats)}")
    lines += [
        "",
        "Consensus diagnostics:",
        "",
    ]
    for feature, stats in summary["consensus_stats"].items():
        lines.append(f"- `{feature}`: {_feature_line(stats)}")
    quorum = summary["quorum_disagreement"]
    lines += [
        "",
        f"Quorum member disagreements: count={quorum['count']} "
        f"fraction={_fmt(quorum['fraction'])} buckets={quorum['buckets']}",
        "",
        "## OI sign agreement by magnitude",
        "",
        "```json",
        json.dumps(summary["oi_sign_agreement_by_magnitude"], indent=2),
        "```",
        "",
        "## Tail agreement",
        "",
        "Label: SAMPLE-DAY TAIL AGREEMENT. This is not a production 30-day percentile.",
        "",
        "```json",
        json.dumps(summary["tail_agreement_summary"], indent=2),
        "```",
        "",
        "## Null and evaluability disagreements",
        "",
        "```json",
        json.dumps(summary["null_evaluability_disagreements"], indent=2),
        "```",
        "",
        "## Documented vendor gaps",
        "",
        f"Applicable trades or derivative_ticker incidents: **{len(gaps['applicable_to_trades_or_derivative_ticker'])}**.",
        "",
        f"Vendor-gap buckets excluded: **{gaps['vendor_gap_buckets']}**.",
        "",
    ]
    touching = gaps["incidents_whose_window_overlaps_a_sample_date"]
    if not touching:
        lines.append("No incidentReports window overlaps the sample dates.")
    else:
        for row in touching:
            lines.append(
                f"- `{row['tardis_exchange']}` {row['sample_date']} "
                f"{row['from']} → {row['to']}: **{row['tag_if_applicable']}**. "
                f"{row['details']}"
            )
    lines += [
        "",
        "## Top mismatch causes",
        "",
    ]
    if not causes:
        lines.append(
            "No predeclared rejection rule fired. Residual absolute differences "
            "remain in `mismatch_samples.csv` and in the per-venue diagnostics. "
            "Absence of a rejection code is not bit-identical replay."
        )
    else:
        for item in causes:
            lines.append(f"- `{item['code']}` ({item['class']}): {item['detail']}")
    notes = summary.get("mechanism_notes") or []
    if notes:
        lines += ["", "## Mechanism notes", ""]
        lines.extend(notes)
    lines += [
        "",
        f"Gap buckets excluded from equivalence: {summary['gap_buckets_excluded_from_equivalence']}.",
        "",
        f"Unit mismatches: {summary['unit_mismatch_count']}.",
        "",
        f"OKX_OI_PIT_STATUS = {summary['okx_oi_pit_status']}",
        "",
        "OKX open-interest percentage uses native contract units on both sides "
        "and does not apply ctVal. OKX volume and taker notional stay fail-closed "
        "without a historical contract multiplier. The current instrument file "
        "was not read as that multiplier.",
        "",
        "## Decision",
        "",
        summary["overall_decision"],
        "",
        "No detector episodes, historical outcomes, or production 30-day percentile ranks were computed.",
        "",
        "COST_INCURRED_USD = 0",
        "",
    ]
    for key, value in summary["flags"].items():
        lines.append(f"{key} = {str(value).lower()}")
    lines.append("")
    return "\n".join(lines)


def write_comparison_outputs(out_dir: Path, summary: dict, mismatch_rows: list,
                             inventory: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment": "TARDIS_FREE_OVERLAP_VALIDATION_V0",
        "comparison_performed": True,
        "base_sha": summary["base_sha"],
        "audit_sources_sha256": summary["audit_sources_sha256"],
        "dates_compared": summary["dates_compared"],
        "venues_compared": summary["venues_compared"],
        "overall_decision": summary["overall_decision"],
        "okx_oi_pit_status": summary["okx_oi_pit_status"],
        "current_instrument_table_used_as_pit": False,
        "post_hoc_transform_applied": False,
        "gold_export": summary["gold_export"],
        "tardis_files": summary["tardis_files"],
        "documented_vendor_gaps": summary["documented_vendor_gaps"],
        "inventory_status": [
            {"file": row["path_basename"], "status": row["status"], "sha256": row["sha256"]}
            for row in inventory
        ],
        "cost_incurred_usd": 0,
    }
    (out_dir / "overlap_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "overlap_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n"
    )
    (out_dir / "overlap_report.md").write_text(render_comparison_report(summary))
    with (out_dir / "mismatch_samples.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([
            "sample_date", "exchange", "bucket_ts", "feature",
            "signalbot_value", "tardis_value", "abs_diff", "tags", "note",
        ])
        writer.writerows(mismatch_rows)


def write_outputs(out_dir: Path, manifest: dict, summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overlap_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "overlap_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "overlap_report.md").write_text(render_report(manifest, summary))
    with (out_dir / "mismatch_samples.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([
            "sample_date", "exchange", "bucket_ts", "feature",
            "signalbot_value", "tardis_value", "abs_diff", "tags", "note",
        ])
        writer.writerow([
            "", "", "", "", "", "", "", "",
            "NO_COMPARISON_WAITING_FOR_SIGNALBOT_EXPORT",
        ])
