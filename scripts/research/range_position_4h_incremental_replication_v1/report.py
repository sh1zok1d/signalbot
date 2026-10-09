"""Markdown for the one Bybit read. Numbers come from the result dict."""

from __future__ import annotations

from pathlib import Path


def _fmt(value) -> str:
    if value is None:
        return "missing"
    return f"{value:.12g}"


def write_markdown(result: dict, path: Path) -> None:
    q = result["quintiles"]
    lines = [
        "# RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1",
        "",
        f"**Evidence class:** `{result['evidence_class']}`.",
        f"**Claim ceiling:** `{result['claim_ceiling']}`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.",
        f"**Route:** `{result['route']}`.",
        f"**Design SHA256:** `{result['design_sha256']}`.",
        f"**Bybit SHA256:** `{result['series_sha256']}`.",
        f"**Evaluator digest:** `{result['evaluator_digest']}`.",
        "",
        "One frozen check. Not a discovery scan. Rejection and bars-since were not read. "
        "2025/2026 was not read. Binance outcomes were not loaded. Fees were not computed.",
        "",
        "## Sample",
        "",
        f"Grid slots `{result['grid_slots']}`, occupied `{result['occupied_bars']}`, holes left missing `{result['holes']}`.",
        f"Phase anchors `{result['phase_anchors']}`. Analysis N `{result['analysis_n']}`. "
        f"ISO weeks `{result['iso_weeks']}`.",
        f"T from `{result['first_t']}` through `{result['last_t']}`. Years `{result['years_present']}`.",
        "",
        "## Estimates",
        "",
        f"Raw Spearman `{_fmt(result['raw_spearman'])}`. "
        f"Interval `{_fmt(result['bootstrap']['raw']['lo'])}` to `{_fmt(result['bootstrap']['raw']['hi'])}` "
        f"({result['bootstrap']['raw']['valid']} / {result['bootstrap']['raw']['draws']} draws).",
        "",
        f"Partial given `RET_4H` `{_fmt(result['secondary_partial_ret'])}`. "
        f"Interval `{_fmt(result['bootstrap']['secondary']['lo'])}` to `{_fmt(result['bootstrap']['secondary']['hi'])}`. "
        "Not used for the route. Canonical one-covariate helper matches.",
        "",
        f"Primary partial given `RET_4H` and `RV_4H` `{_fmt(result['primary_partial'])}`. "
        f"Interval `{_fmt(result['bootstrap']['primary']['lo'])}` to `{_fmt(result['bootstrap']['primary']['hi'])}`.",
        "",
        f"Raw minus the `RET_4H` partial: `{_fmt(result['attenuation_by_ret'])}`. "
        f"Share of the raw association: `{_fmt(result['share_removed_by_ret'])}`.",
        "",
        f"Spearman of position with `RANGE_WIDTH_4H`: `{_fmt(result['width_spearman_with_rp'])}`. "
        f"Partial also given width: `{_fmt(result['width_partial'])}`. Diagnostic only.",
        "",
        "## Quintiles",
        "",
        "Full-sample bins of position. Not a threshold.",
        "",
        "| bin | N | P(UP) | mean R | median R |",
        "|---|---|---|---|---|",
    ]
    if q.get("degenerate"):
        lines.append("| degenerate | | | | |")
    else:
        for row in q["bins"]:
            lines.append(
                f"| {row['bin']} | {row['n']} | {_fmt(row['p_up'])} | {_fmt(row['mean_return'])} | {_fmt(row['median_return'])} |"
            )
    lines.extend(["", "## Years", "", "| year | N | raw | primary |", "|---|---|---|---|"])
    for row in result["yearly"]:
        lines.append(f"| {row['year']} | {row['n']} | {_fmt(row['raw'])} | {_fmt(row['primary'])} |")
    halves = result["halves"]
    lines.extend([
        "",
        "## Halves",
        "",
        f"Median T ms `{_fmt(halves['median_t_ms'])}`.",
        "",
        "| half | N | raw | primary |",
        "|---|---|---|---|",
        f"| first | {halves['first']['n']} | {_fmt(halves['first']['raw'])} | {_fmt(halves['first']['primary'])} |",
        f"| second | {halves['second']['n']} | {_fmt(halves['second']['raw'])} | {_fmt(halves['second']['primary'])} |",
        "",
        "Parent Binance discovery Spearman was `-0.057773446228651215`, discovery only. "
        "This file does not recompute it.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
