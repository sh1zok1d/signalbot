"""Narrative and figure for the one discovery pass."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def _fmt(value, digits=6) -> str:
    if value is None:
        return "NA"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "NA"
    return f"{number:.{digits}g}"


def _sign_word(value) -> str:
    if value is None or not np.isfinite(float(value)) or float(value) == 0.0:
        return "flat"
    return "positive" if float(value) > 0.0 else "negative"


def write_markdown(result: dict, path: Path) -> None:
    lines = [
        "# PRE_IMPULSE_STATE_ATLAS_V1",
        "",
        "Historical directional discovery. Claim ceiling `DISCOVERY_ONLY`. A shortlisted state is a `DISCOVERY_CANDIDATE`. It is not confirmed, not validated, not a current probability, and not an edge.",
        "",
        result["governing_principle"],
        "",
        f"Read `{result['read_at']}`. Design SHA256 `{result['design_sha256']}`. Ledger `{result['ledger_path']}` SHA256 `{result['ledger_sha256']}`.",
        "",
        "## Sample",
        "",
        f"- Surface `{result['surface']}`, `{result['time_range'][0]}` through `{result['time_range'][1]}` exclusive on decision time T.",
        f"- Anchors: 15-minute closes, N `{result['anchor_n']}`, ISO weeks `{result['anchor_weeks']}`.",
        f"- Horizons: {', '.join(result['horizons'])}. Ranked horizons: {', '.join(result['primary_horizons'])}.",
        f"- Features `{result['feature_count']}`. Feature x horizon x representation cells `{result['cell_count']}`.",
        f"- 2025/2026 opened: `{result['objects_2025_2026_used']}`. Open interest opened: `{result['oi_opened']}`. Level engine used: `{result['level_engine_used']}`. Product code changed: `{result['product_code_changed']}`.",
        "",
        "## Market states discovered",
        "",
        result["narrative"]["states"],
        "",
        "## UP-associated structures",
        "",
    ]
    for row in result["up_associated"][:5]:
        lines.extend(_candidate_block(row))
        lines.append("")
    lines += ["## DOWN-associated structures", ""]
    for row in result["down_associated"][:5]:
        lines.extend(_candidate_block(row))
        lines.append("")
    lines += ["", "## Symmetric and null structures", "", result["narrative"]["nulls"], ""]
    lines += ["## Clock-conditioned structures", "", result["narrative"]["clock"], ""]
    lines += ["## Boundary and acceptance structures", "", result["narrative"]["boundary"], ""]
    lines += ["## Flow and OI interaction structures", "", result["narrative"]["flow_oi"], ""]
    lines += ["## Cross-venue timing structures", "", result["narrative"]["cross_venue"], ""]
    lines += ["## Top successor candidates", ""]
    for row in result["successors"]:
        lines.append(f"- `{row['candidate_id']}` at `{row['horizon']}`, score `{_fmt(row['score'])}`. {row['successor']}")
    lines += ["", "## Top 10 directional structures", ""]
    for i, row in enumerate(result["top10"], start=1):
        lines.append(f"### {i}. `{row['candidate_id']}` / `{row['horizon']}`")
        lines.append("")
        lines.extend(_candidate_block(row))
        lines.append("")
        lines.append("Quintiles, bottom to top:")
        lines.append("")
        table = row.get("quintiles") or {}
        if table.get("degenerate"):
            lines.append("Quintile table is degenerate.")
        else:
            for b in table.get("bins") or []:
                lines.append(
                    f"- bin {b['bin']}: N `{b['n']}`, P(UP) `{_fmt(b['p_up'])}`, mean `{_fmt(b['mean_return'])}`, median `{_fmt(b['median_return'])}`"
                )
        lines.append("")
        lines.append("Years: " + ", ".join(
            f"{y['year']} N {y['n']} {_sign_word(y['spearman'])} `{_fmt(y['spearman'])}`" for y in row["years"]
        ))
        lines.append("")
    lines += ["## Patterns that shrank after a control", "", result["narrative"]["misleading"], ""]
    lines += ["## What is still unknown", "", result["narrative"]["unknown"], ""]
    lines += [
        "## Stop",
        "",
        "Do not execute a successor from this unit. Each successor needs its own frozen design and an owner go.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _candidate_block(row: dict) -> list[str]:
    st = row.get("state") or {}
    boot = row.get("bootstrap") or {}
    sp = (boot.get("spearman") or {})
    return [
        f"- Formula: {row['formula']}",
        f"- Reading: {row['high_means']}",
        f"- Family `{row['family']}`, collision `{row['collision']}`, eligible `{row['eligible']}`.",
        f"- N `{row['n']}`, weeks `{row['n_weeks']}`, Spearman `{_fmt(row['spearman'])}`, weekly mean `{_fmt(row['week_mean'])}`, weekly SE `{_fmt(row['week_se'])}`.",
        f"- State `{st.get('side')}`, N `{st.get('n')}`, P(UP|state) `{_fmt(st.get('p_up'))}`, baseline P(UP) `{_fmt(st.get('baseline_p_up'))}`, delta P `{_fmt(st.get('delta_p'))}`.",
        f"- Mean return in state `{_fmt(st.get('mean_return'))}`, baseline mean `{_fmt(st.get('baseline_mean'))}`, difference `{_fmt(st.get('mean_difference'))}`.",
        f"- Bootstrap Spearman interval `{_fmt(sp.get('lo'))}` to `{_fmt(sp.get('hi'))}`, valid `{sp.get('valid')}` / `{sp.get('draws')}`.",
        f"- Mirror agrees: `{row.get('mirror_agrees')}`.",
        f"- Score `{_fmt(row.get('score'))}`.",
    ]


def write_figure(result: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = result["top10"]
    n = max(1, len(rows))
    fig, axes = plt.subplots(n, 3, figsize=(12, 2.2 * n), squeeze=False)
    for i, row in enumerate(rows):
        table = row.get("quintiles") or {}
        bins_ = table.get("bins") or []
        xs = [b["bin"] for b in bins_]
        means = [b["mean_return"] if b["mean_return"] is not None else np.nan for b in bins_]
        pups = [b["p_up"] if b["p_up"] is not None else np.nan for b in bins_]
        axes[i, 0].plot(xs, means, marker="o")
        axes[i, 0].axhline(0.0, color="0.5", lw=0.6)
        axes[i, 0].set_ylabel(row["candidate_id"][:22])
        axes[i, 1].plot(xs, pups, marker="o")
        base = (row.get("state") or {}).get("baseline_p_up")
        if base is not None:
            axes[i, 1].axhline(base, color="0.5", lw=0.6)
        years = [y for y in row["years"] if y["spearman"] is not None]
        axes[i, 2].bar([str(y["year"]) for y in years], [y["spearman"] for y in years])
        axes[i, 2].axhline(0.0, color="0.5", lw=0.6)
        if i == 0:
            axes[i, 0].set_title("mean future return")
            axes[i, 1].set_title("P(UP)")
            axes[i, 2].set_title("yearly Spearman")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
