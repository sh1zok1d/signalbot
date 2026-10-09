"""Markdown for the one BitMEX read. Numbers come from the result dict."""

from __future__ import annotations

from pathlib import Path


def _fmt(value) -> str:
    if value is None:
        return "missing"
    return f"{value:.12g}"


def write_markdown(result: dict, path: Path) -> None:
    q = result["quintiles"]
    lines = [
        "# RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1",
        "",
        f"**Evidence class:** `{result['evidence_class']}`.",
        f"**Claim ceiling:** `{result['claim_ceiling']}`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.",
        f"**Route:** `{result['route']}`.",
        f"**Design SHA256:** `{result['design_sha256']}`.",
        f"**BitMEX SHA256:** `{result['series_sha256']}`.",
        f"**Evaluator digest:** `{result['evaluator_digest']}`.",
        "",
        "One frozen temporal replication. Not a search. Prices are last-trade XBTUSD closes "
        "in price space. The inverse contract was not inverted. D7 was not read.",
        "",
        "## Sample",
        "",
        f"Grid slots `{result['grid_slots']}`, occupied `{result['occupied_bars']}`, holes left missing `{result['holes']}`.",
        f"Phase anchors `{result['phase_anchors']}`. Analysis N `{result['analysis_n']}`. "
        f"ISO weeks `{result['iso_weeks']}`.",
        f"Lost to the 2016 gap `{result['lost_to_gap']}`. "
        f"Lost to incomplete lookback `{result['lost_to_lookback']}`. "
        f"Lost to incomplete future `{result['lost_to_future']}`.",
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
        "## Quintiles",
        "",
        "Full-sample bins of position. Not a route input.",
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
        f"Median T `{halves['median_t']}`.",
        "",
        "| half | N | raw | primary |",
        "|---|---|---|---|",
        f"| first | {halves['first']['n']} | {_fmt(halves['first']['raw'])} | {_fmt(halves['first']['primary'])} |",
        f"| second | {halves['second']['n']} | {_fmt(halves['second']['raw'])} | {_fmt(halves['second']['primary'])} |",
        "",
        "Binance discovery Spearman was `-0.057773446228651215`. "
        "Bybit raw was `-0.05781800690167492`, partial given `RET_4H` `-0.027418341298313498`, "
        "primary `-0.02784152009582924`. This file does not recompute those reads.",
        "",
        f"Scientific status: `{result['scientific_status']}`.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
