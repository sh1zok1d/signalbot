"""One historical outcome read of FROZEN_HOUR_EQUAL_WIDTH_V1.

Owner go 2026-10-08. The support census is checked again before any resolution
label. A mismatch stops without a label. A second official write refuses.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from . import census, constants as K

ROOT = Path(__file__).resolve().parents[3]
RESULT_JSON = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_V1_RESULT.md"
MANIFEST_PATH = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_V1_EVALUATOR_MANIFEST.json"
SUPPORT_MISMATCH = "SUPPORT_MISMATCH_STOP_BEFORE_Y"
BOOT_VALID_FRACTION_MIN = 0.9
DESCRIPTIVE_MIN_PAIRS = 30
FROZEN_PAIRED = {"UTC_00": 817, "UTC_12": 833}
FROZEN_WEEKS = {"UTC_00": 123, "UTC_12": 123}
FROZEN_CENSUS_HEAD = "3b02de8380064aa2ce3fe384e86899e08d2b3778"
FROZEN_DESIGN_SHA = "abb3283046277201278f2e952196e870e324009d86e39324d4fdca530b4cfef7"
SUPPORT_COUNT_KEYS = (
    "calendar_days",
    "formation_complete",
    "usable_real_geometry",
    "valid_equal_width_pseudo_geometry",
    "solver_attempts",
    "solver_success",
    "scale_unbounded",
    "scale_tolerance_failed",
    "invalid_partner_geometry",
    "collisions",
    "partner_not_found",
    "lifespan_truncated",
    "first_real_interaction",
    "first_pseudo_interaction",
    "ambiguous_real",
    "ambiguous_pseudo",
    "immediate_real",
    "immediate_pseudo",
    "one_sided_outcome_eligible_real",
    "one_sided_outcome_eligible_pseudo",
    "paired_outcome_eligible",
    "paired_neither_immediate",
    "paired_iso_weeks",
)


def resolution_indicator(high, low, level_high: float, level_low: float, side: str) -> float:
    """4h resolution only. Extension and midpoint reentry are the frozen barriers.

    `high` and `low` are the 48 bars strictly after the touch. Width is this
    arm's own bounds. No other endpoint is returned.
    """
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    if high.shape != (K.HORIZON_BARS,) or low.shape != (K.HORIZON_BARS,):
        raise ValueError("outcome window is not 48 bars")
    width = float(level_high) - float(level_low)
    if not width > 0.0:
        raise ValueError("nonpositive width")
    midpoint = (float(level_high) + float(level_low)) / 2.0
    reach = K.EXTENSION_FRACTION * width
    if side == "high":
        extension = high >= float(level_high) + reach
        reentry = low <= midpoint
    elif side == "low":
        extension = low <= float(level_low) - reach
        reentry = high >= midpoint
    else:
        raise ValueError(side)
    return float(bool(np.any(extension | reentry)))


def _window(series, index: int) -> np.ndarray:
    start = int(index) + 1
    return np.asarray(series[start:start + K.HORIZON_BARS], dtype=np.float64)


def score_pairs(high, low, pairs: list) -> list:
    scored = []
    for pair in pairs:
        y_real = resolution_indicator(
            _window(high, pair["real_index"]),
            _window(low, pair["real_index"]),
            pair["real_high"],
            pair["real_low"],
            pair["real_side"],
        )
        y_pseudo = resolution_indicator(
            _window(high, pair["pseudo_index"]),
            _window(low, pair["pseudo_index"]),
            pair["pseudo_high"],
            pair["pseudo_low"],
            pair["pseudo_side"],
        )
        scored.append({
            "iso_year": pair["iso_year"],
            "iso_week": pair["iso_week"],
            "y_real": y_real,
            "y_pseudo": y_pseudo,
            "delta": y_real - y_pseudo,
            "real_immediate": pair["real_immediate"],
            "pseudo_immediate": pair["pseudo_immediate"],
        })
    return scored


def collect_pairs(high, low, close, t0: int) -> dict:
    found = {}
    for name, offset in K.ANCHORS.items():
        sink: list = []
        counts = census._cell(high, low, close, t0, offset, sink)
        if len(sink) != counts["paired_outcome_eligible"]:
            raise RuntimeError("pair sink does not match paired support")
        found[name] = {"counts": counts, "pairs": sink}
    return found


def _week_sums(scored: list) -> dict:
    sums = {}
    for row in scored:
        key = (int(row["iso_year"]), int(row["iso_week"]))
        total, n = sums.get(key, (0.0, 0))
        sums[key] = (total + float(row["delta"]), n + 1)
    return sums


def _one_mean(sums: dict, mult: dict) -> float | None:
    num = 0.0
    den = 0
    for week, multiplicity in mult.items():
        if multiplicity == 0 or week not in sums:
            continue
        total, n = sums[week]
        num += multiplicity * total
        den += multiplicity * n
    if den == 0:
        return None
    return num / den


def _draw_multiplicity(weeks: list, rng: np.random.Generator) -> dict:
    choice = rng.choice(len(weeks), size=len(weeks), replace=True)
    counts: dict = {}
    for raw in choice:
        week = weeks[int(raw)]
        counts[week] = counts.get(week, 0) + 1
    return counts


def bootstrap_mean(scored: list, *, seed: int) -> dict:
    sums = _week_sums(scored)
    weeks = sorted(sums)
    rng = np.random.default_rng(seed)
    draws = []
    invalid = 0
    for _ in range(K.BOOT_DRAWS):
        got = _one_mean(sums, _draw_multiplicity(weeks, rng))
        if got is None:
            invalid += 1
        else:
            draws.append(got)
    valid = len(draws)
    fraction = valid / K.BOOT_DRAWS
    interpretable = fraction >= BOOT_VALID_FRACTION_MIN and valid > 0
    if interpretable:
        column = np.asarray(draws, dtype=np.float64)
        lo = float(np.quantile(column, 0.025, method="linear"))
        hi = float(np.quantile(column, 0.975, method="linear"))
    else:
        lo = None
        hi = None
    return {
        "draws": K.BOOT_DRAWS,
        "valid_draws": valid,
        "invalid_draws": invalid,
        "valid_fraction": fraction,
        "interpretable": interpretable,
        "lo": lo,
        "hi": hi,
        "seed": seed,
    }


def point_mean(scored: list) -> float:
    if not scored:
        raise RuntimeError("no paired days")
    return float(np.mean([row["delta"] for row in scored]))


def cell_clears(point: float, interval: dict) -> bool:
    if not interval["interpretable"]:
        return False
    lo = interval["lo"]
    hi = interval["hi"]
    if lo is None or hi is None:
        return False
    return abs(point) >= K.PRACTICAL_SCALE and (lo > 0.0 or hi < 0.0)


def descriptive_neither_immediate(scored: list) -> dict:
    """Design §3. Printed mean only at N >= 30. No interval. Not a route input."""
    subset = [row for row in scored if not row["real_immediate"] and not row["pseudo_immediate"]]
    n = len(subset)
    out = {
        "role": "DESCRIPTIVE_NOT_A_CANDIDATE",
        "n": n,
        "printed": n >= DESCRIPTIVE_MIN_PAIRS,
        "paired_mean": None,
    }
    if out["printed"]:
        out["paired_mean"] = float(np.mean([row["delta"] for row in subset]))
    return out


def route_name(primary_clears: bool, *, support_ok: bool) -> str:
    if not support_ok:
        return K.LIMITED
    if primary_clears:
        return "WIDTH_HELD_DIFFERENCE_PRESENT"
    return "NO_WIDTH_HELD_RESOLUTION_DIFFERENCE"


def utc12_note(primary_clears: bool, diagnostic_clears: bool) -> str:
    if primary_clears and diagnostic_clears:
        return "The width-held remainder is not specific to midnight among these two cells."
    if primary_clears and not diagnostic_clears:
        return "The width-held remainder is not shared with noon on this surface."
    if diagnostic_clears:
        return "UTC_12 clears and is reported. It is not adopted."
    return "UTC_12 does not clear and is not adopted."


def interpretation(route: str, point: float, diagnostic_clears: bool) -> str:
    noon = utc12_note(route == "WIDTH_HELD_DIFFERENCE_PRESENT", diagnostic_clears)
    if route == K.LIMITED:
        return "The frozen information floor was not met. No resolution contrast is stated."
    if route == "WIDTH_HELD_DIFFERENCE_PRESENT" and point > 0.0:
        return (
            "On Binance spot 2017–2019, the real frozen hour resolves more often than a pseudo "
            "whose linear width is forced to today's width, and the frozen rule clears. "
            "Linear width alone does not account for this contrast, and the relation is present "
            "on this spot era. A simple width-only account and a pure perpetual-funding-settlement "
            "account are weaker. The result does not separate a special boundary from the geometry "
            "of today's formation or from other information in the real hour. It does not restore "
            "+9.48 pp, does not confirm an opening range, does not identify a funding mechanism, "
            "is not a current probability, and is not a product signal. " + noon
        )
    if route == "WIDTH_HELD_DIFFERENCE_PRESENT" and point < 0.0:
        return (
            "A width-held resolution difference clears, and the real arm resolves less often than "
            "the width-matched pseudo. The frozen route name applies. This is not the positive "
            "contrast from the perpetual discovery surface, and it does not establish a special "
            "boundary. " + noon
        )
    return (
        "On this surface, after holding linear width equal, the frozen 3 pp and interval rule "
        "did not detect a resolution difference. That is compatible with the 2020–2024 perpetual "
        "contrast having depended on width and volatility-regime coupling. It does not prove that "
        "account, because this read also changes the era and the instrument. It does not say that "
        "width completely explains +9.48 pp. " + noon
    )


def require_frozen_support_file(payload: dict) -> None:
    if payload.get("outcome_read") is not False or payload.get("barrier_path_read") is not False:
        raise SystemExit(SUPPORT_MISMATCH)
    if payload.get("head") != FROZEN_CENSUS_HEAD or payload.get("design_sha256") != FROZEN_DESIGN_SHA:
        raise SystemExit(SUPPORT_MISMATCH)
    if payload.get("information_gate") != K.ADEQUATE:
        raise SystemExit(SUPPORT_MISMATCH)
    for name in K.CELLS:
        cell = payload["cells"][name]
        if cell["paired_outcome_eligible"] != FROZEN_PAIRED[name]:
            raise SystemExit(SUPPORT_MISMATCH)
        if cell["paired_iso_weeks"] != FROZEN_WEEKS[name]:
            raise SystemExit(SUPPORT_MISMATCH)
        if cell["information_status"] != K.ADEQUATE:
            raise SystemExit(SUPPORT_MISMATCH)
    months = payload["panel_provenance"]["months"]
    if months[0] != K.FIRST_MONTH or months[-1] != K.LAST_MONTH or len(months) != 28:
        raise SystemExit(SUPPORT_MISMATCH)
    if payload["panel_provenance"].get("off_grid_rows_not_placed") != 241:
        raise SystemExit(SUPPORT_MISMATCH)


def require_live_matches(live: dict, frozen: dict) -> None:
    if live.get("information_gate") != frozen.get("information_gate"):
        raise SystemExit(SUPPORT_MISMATCH)
    for name in K.CELLS:
        got = live["cells"][name]
        ref = frozen["cells"][name]
        for key in SUPPORT_COUNT_KEYS:
            if got[key] != ref[key]:
                raise SystemExit(SUPPORT_MISMATCH)
        if got["information_status"] != ref["information_status"]:
            raise SystemExit(SUPPORT_MISMATCH)


def _cell_report(name: str, scored: list, interval: dict, point: float) -> dict:
    y_real = np.asarray([row["y_real"] for row in scored], dtype=np.float64)
    y_pseudo = np.asarray([row["y_pseudo"] for row in scored], dtype=np.float64)
    weeks = {(row["iso_year"], row["iso_week"]) for row in scored}
    real_rate = float(np.mean(y_real))
    pseudo_rate = float(np.mean(y_pseudo))
    if abs((real_rate - pseudo_rate) - point) > 1e-12:
        raise RuntimeError("paired mean does not match the rate difference")
    seed = K.BOOT_SEED_UTC_00 if name == K.PRIMARY_CELL else K.BOOT_SEED_UTC_12
    clears = cell_clears(point, interval)
    return {
        "cell": name,
        "role": "primary" if name == K.PRIMARY_CELL else "diagnostic_not_adoptable",
        "n": len(scored),
        "iso_weeks": len(weeks),
        "real_resolution_rate": real_rate,
        "pseudo_resolution_rate": pseudo_rate,
        "paired_delta": point,
        "interval_lo": interval["lo"],
        "interval_hi": interval["hi"],
        "interval_interpretable": interval["interpretable"],
        "valid_draws": interval["valid_draws"],
        "boot_seed": seed,
        "clears": clears,
        "immediate_real_rate": float(np.mean([row["real_immediate"] for row in scored])),
        "immediate_pseudo_rate": float(np.mean([row["pseudo_immediate"] for row in scored])),
        "neither_immediate": descriptive_neither_immediate(scored),
    }


def build_result(collected: dict, *, read_at: str, head: str) -> dict:
    reports = {}
    for name in K.CELLS:
        scored = collected[name]["scored"]
        seed = K.BOOT_SEED_UTC_00 if name == K.PRIMARY_CELL else K.BOOT_SEED_UTC_12
        point = point_mean(scored)
        interval = bootstrap_mean(scored, seed=seed)
        reports[name] = _cell_report(name, scored, interval, point)
    primary = reports[K.PRIMARY_CELL]
    diagnostic = reports[K.DIAGNOSTIC_CELL]
    support_ok = (
        primary["n"] >= K.MIN_PAIRED
        and diagnostic["n"] >= K.MIN_PAIRED
        and primary["iso_weeks"] >= K.MIN_ISO_WEEKS
        and diagnostic["iso_weeks"] >= K.MIN_ISO_WEEKS
    )
    route = route_name(primary["clears"], support_ok=support_ok)
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_read": True,
        "barrier_path_read": True,
        "read_at": read_at,
        "pre_outcome_evaluator_commit": head,
        "code_digest": census.code_digest(),
        "design_commit": K.DESIGN_COMMIT,
        "design_sha256": FROZEN_DESIGN_SHA,
        "support_census_head": FROZEN_CENSUS_HEAD,
        "surface": K.SURFACE_ID,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "first_month": K.FIRST_MONTH,
        "last_month": K.LAST_MONTH,
        "practical_scale": K.PRACTICAL_SCALE,
        "boot_draws": K.BOOT_DRAWS,
        "route": route,
        "utc12_note": utc12_note(primary["clears"], diagnostic["clears"]),
        "interpretation": interpretation(route, primary["paired_delta"], diagnostic["clears"]),
        "cells": reports,
        "claim_ceiling": K.CLAIM_CEILING,
        "product_change": "none",
        "successor_started": False,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# FROZEN_HOUR_EQUAL_WIDTH_V1 — one historical outcome read",
        "",
        f"- Unit: `{payload['unit']}`",
        f"- Read at: `{payload['read_at']}`",
        f"- Evaluator commit: `{payload['pre_outcome_evaluator_commit']}`",
        f"- Code digest: `{payload['code_digest']}`",
        f"- Design commit: `{payload['design_commit']}`",
        f"- Design SHA256: `{payload['design_sha256']}`",
        f"- Support census HEAD: `{payload['support_census_head']}`",
        f"- Surface: `{payload['surface']}` `{payload['event_start']}` to `{payload['surface_end_exclusive']}` exclusive, months `{payload['first_month']}`..`{payload['last_month']}`",
        f"- Route: `{payload['route']}`",
        f"- Seeds: UTC_00 `{K.BOOT_SEED_UTC_00}`, UTC_12 `{K.BOOT_SEED_UTC_12}`, B = {payload['boot_draws']}",
        "",
        payload["interpretation"],
        "",
        payload["utc12_note"],
        "",
    ]
    for name in K.CELLS:
        cell = payload["cells"][name]
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- N: {cell['n']}")
        lines.append(f"- ISO weeks: {cell['iso_weeks']}")
        lines.append(f"- real resolution rate: {cell['real_resolution_rate']:.6f}")
        lines.append(f"- pseudo resolution rate: {cell['pseudo_resolution_rate']:.6f}")
        lines.append(f"- paired delta: {cell['paired_delta']:.6f}")
        lines.append(f"- 95% interval: [{cell['interval_lo']}, {cell['interval_hi']}]")
        lines.append(f"- interpretable: {str(cell['interval_interpretable']).lower()}")
        lines.append(f"- clears: {str(cell['clears']).lower()}")
        lines.append(f"- immediate real rate: {cell['immediate_real_rate']:.6f}")
        lines.append(f"- immediate pseudo rate: {cell['immediate_pseudo_rate']:.6f}")
        subset = cell["neither_immediate"]
        lines.append(f"- neither-immediate N: {subset['n']} ({subset['role']})")
        if subset["printed"]:
            lines.append(f"- neither-immediate paired mean: {subset['paired_mean']:.6f}")
        else:
            lines.append("- neither-immediate paired mean: not printed")
        lines.append("")
    lines.append("No year slice, extension-first split, occupancy, excursion, or volatility endpoint is in this file.")
    lines.append("No product change and no successor was started.")
    lines.append("")
    return "\n".join(lines)


def write_result(payload: dict, manifest: dict) -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists() or MANIFEST_PATH.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    RESULT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD.write_text(render_markdown(payload), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if RESULT_JSON.exists() or RESULT_MD.exists() or MANIFEST_PATH.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    census.assert_design_freeze()
    frozen = json.loads(census.FEASIBILITY_JSON.read_text(encoding="utf-8"))
    require_frozen_support_file(frozen)
    from . import data

    panel, provenance = data.load_panel()
    if provenance["months"] != data.allowed_months():
        raise SystemExit(SUPPORT_MISMATCH)
    if provenance["off_grid_rows_not_placed"] != 241:
        raise SystemExit(SUPPORT_MISMATCH)
    live = census.summarize(
        panel.high,
        panel.low,
        panel.close,
        panel.t0,
        provenance=provenance,
        design_sha256_hex=census.design_sha256(),
    )
    require_live_matches(live, frozen)
    collected = collect_pairs(panel.high, panel.low, panel.close, panel.t0)
    for name in K.CELLS:
        if collected[name]["counts"]["paired_outcome_eligible"] != FROZEN_PAIRED[name]:
            raise SystemExit(SUPPORT_MISMATCH)
    for name in K.CELLS:
        collected[name]["scored"] = score_pairs(panel.high, panel.low, collected[name]["pairs"])
    read_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = census._git(["rev-parse", "HEAD"])
    payload = build_result(collected, read_at=read_at, head=head)
    manifest = {
        "unit": K.UNIT,
        "pre_outcome_evaluator_commit": head,
        "code_digest": payload["code_digest"],
        "design_commit": K.DESIGN_COMMIT,
        "design_sha256": FROZEN_DESIGN_SHA,
        "support_census_head": FROZEN_CENSUS_HEAD,
        "support_census_path": "docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_FEASIBILITY.json",
        "surface": K.SURFACE_ID,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "read_at": read_at,
        "boot_seed_utc_00": K.BOOT_SEED_UTC_00,
        "boot_seed_utc_12": K.BOOT_SEED_UTC_12,
        "boot_draws": K.BOOT_DRAWS,
        "route": payload["route"],
        "outcome_files_written_by_this_process": True,
    }
    write_result(payload, manifest)
    print(json.dumps({
        "read_at": read_at,
        "route": payload["route"],
        "utc_00_delta": payload["cells"]["UTC_00"]["paired_delta"],
        "utc_00_clears": payload["cells"]["UTC_00"]["clears"],
        "utc_12_delta": payload["cells"]["UTC_12"]["paired_delta"],
        "utc_12_clears": payload["cells"]["UTC_12"]["clears"],
        "pre_outcome_evaluator_commit": head,
        "code_digest": payload["code_digest"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
