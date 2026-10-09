"""One outcome read of FORMATION_WIDTH_REGIME_V1.

The route is amendment_a2.assign_route. This module does not define another
route. A second official run returns REFUSING_RERUN before loading the panel.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.opening_range_object_v1 import census as parent_census
from scripts.research.opening_range_object_v1 import constants as PARENT

from . import amendment_a1 as A1
from . import amendment_a2 as A2
from . import census as census_mod
from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_DESIGN.md"
A1_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1.md"
A2_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_AMENDMENT_A2.md"
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_RESULT.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_RESULT.md"
OUT_MANIFEST = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_EVALUATOR_MANIFEST.json"
UTC = dt.timezone.utc

DESIGN_SHA = "64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6"
A1_SHA = "a2e00c68e4360fe08db89ade31e4f222dc148ace0aea58e9143a27d4d386d49e"
A2_SHA = "a76c0a891fedb7a907544878ef49cd136d3831fb6782d89e56a00ce96e49e07a"
EXPECTED_N = 1820
EXPECTED_WEEKS = 262
MIN_VALID_FRACTION = 0.90
DRAW_STAT_ORDER = (
    "foundation_activity",
    "foundation_displacement",
    "incremental_activity",
    "incremental_displacement",
)
ENDPOINT_KEYS = (("ACTIVITY", "activity"), ("DISPLACEMENT", "displacement"))

INTERPRETATION = {
    A2.ROUTE_PRESENT: (
        "Formation width historically carried monotone information about at least one "
        "predeclared next-hour observable beyond contemporaneous realized volatility of "
        "the same formation hour, on this exposed discovery surface."
    ),
    A2.ROUTE_REDUNDANT: (
        "Width had a raw relationship with future behaviour, but V1 did not detect "
        "width-specific information beyond a simple contemporaneous formation-volatility descriptor."
    ),
    A2.ROUTE_NO_DETECTABLE: (
        "The bounded map shows no foundation cell clearing the frozen rule on this surface."
    ),
    A2.ROUTE_UNSTABLE: (
        "A pooled foundation association is not stable under the frozen year-sign rule."
    ),
    A2.ROUTE_NOT_SPECIFIC: (
        "An association may be present, but the frozen lag diagnostic does not support "
        "calling it specific to the state at T."
    ),
    A2.ROUTE_INFORMATION_LIMITED: "The frozen information floor is not met.",
}
NOT_ESTABLISHED = (
    "This read does not establish a forecast, a current probability, an edge, a causal "
    "mechanism, or a trading signal."
)
NO_SUCCESSOR = (
    "No successor is started. A later question needs its own design and a separate owner go."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pearson(left: np.ndarray, right: np.ndarray) -> float:
    a = left - left.mean()
    b = right - right.mean()
    denom = math.sqrt(float(np.dot(a, a) * np.dot(b, b)))
    if denom == 0.0 or not math.isfinite(denom):
        return float("nan")
    return float(np.dot(a, b) / denom)


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation of average ranks. Ties use the A1 average-rank rule."""
    values_x = np.asarray(x, dtype=np.float64)
    values_y = np.asarray(y, dtype=np.float64)
    if len(values_x) < 3 or len(values_x) != len(values_y):
        return float("nan")
    return _pearson(A1.average_ranks(values_x), A1.average_ranks(values_y))


def partial_rho(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    got = A1.partial_spearman(x, y, z)
    if got["degenerate"] or got["rho"] is None:
        return float("nan")
    return float(got["rho"])


def family_bounds(samples: np.ndarray) -> dict:
    column = np.asarray(samples, dtype=np.float64)
    finite = column[np.isfinite(column)]
    fraction = float(len(finite) / len(column)) if len(column) else 0.0
    if fraction < MIN_VALID_FRACTION or len(finite) == 0:
        return {"lo": None, "hi": None, "valid_fraction": fraction, "interpretable": False}
    lo, hi = np.quantile(
        finite,
        [K.FAMILY_ALPHA_QUANTILE, 1.0 - K.FAMILY_ALPHA_QUANTILE],
        method="linear",
    )
    return {
        "lo": float(lo),
        "hi": float(hi),
        "valid_fraction": fraction,
        "interpretable": True,
    }


def interval_excludes_zero(bounds: dict) -> bool:
    if not bounds["interpretable"]:
        return False
    return bounds["lo"] > 0.0 or bounds["hi"] < 0.0


def cell_clears(rho: float, bounds: dict) -> bool:
    if not math.isfinite(rho):
        return False
    return abs(rho) >= K.PRACTICAL_ABS_RHO and interval_excludes_zero(bounds)


def year_is_unstable(by_year: dict) -> bool:
    signs = []
    for row in by_year.values():
        if not row["counts_for_stability"]:
            continue
        rho = row["rho"]
        if rho is None or not math.isfinite(rho) or rho == 0.0:
            continue
        signs.append(1 if rho > 0.0 else -1)
    return any(sign > 0 for sign in signs) and any(sign < 0 for sign in signs)


def yearly_spearman(year: np.ndarray, state: np.ndarray, outcome: np.ndarray, *, min_n: int) -> dict:
    table = {}
    for value in K.YEARS:
        mask = year == value
        n = int(np.count_nonzero(mask))
        counts = n >= min_n
        rho = spearman(state[mask], outcome[mask]) if counts else None
        if counts and rho is not None and not math.isfinite(rho):
            rho = None
        table[str(value)] = {"n": n, "counts_for_stability": counts, "rho": rho}
    return table


def lag_day_pairs(day_ms: np.ndarray) -> list[tuple[int, int]]:
    """(today, previous analysis day). Calendar holes stay holes."""
    stamps = [int(value) for value in day_ms]
    return [(stamps[i], stamps[i - 1]) for i in range(1, len(stamps))]


def lag_placebo(state: np.ndarray, outcome: np.ndarray) -> float:
    if len(state) < 4:
        return float("nan")
    return spearman(state[1:], outcome[:-1])


def information_limited(n: int, weeks: int, state: np.ndarray) -> bool:
    if n < K.MIN_ANALYSIS_N or weeks < K.MIN_ISO_WEEKS:
        return True
    lo, hi = np.quantile(np.asarray(state, dtype=np.float64), [0.1, 0.9], method="linear")
    if not math.isfinite(lo) or lo <= 0.0:
        return True
    return float(hi) / float(lo) < K.DEGENERATE_P90_P10


def _week_groups(week_keys: list[tuple[int, int]]) -> tuple[list, dict]:
    weeks = sorted(set(week_keys))
    groups = {week: [] for week in weeks}
    for index, week in enumerate(week_keys):
        groups[week].append(index)
    return weeks, {week: np.asarray(indexes, dtype=np.int64) for week, indexes in groups.items()}


def draw_indices(week_keys: list[tuple[int, int]], multiplicity: np.ndarray) -> np.ndarray:
    weeks, groups = _week_groups(week_keys)
    parts = [groups[weeks[int(choice)]] for choice in multiplicity]
    return np.concatenate(parts)


def one_draw_stats(
    state: np.ndarray,
    activity: np.ndarray,
    displacement: np.ndarray,
    rv_formation: np.ndarray,
    indexes: np.ndarray,
) -> dict:
    """Four inferential statistics, in the frozen within-draw order."""
    v = state[indexes]
    z = rv_formation[indexes]
    ordered = {
        "foundation_activity": spearman(v, activity[indexes]),
        "foundation_displacement": spearman(v, displacement[indexes]),
        "incremental_activity": partial_rho(v, activity[indexes], z),
        "incremental_displacement": partial_rho(v, displacement[indexes], z),
    }
    if tuple(ordered) != DRAW_STAT_ORDER:
        raise RuntimeError("inferential draw order drifted")
    return ordered


def bootstrap(
    state: np.ndarray,
    activity: np.ndarray,
    displacement: np.ndarray,
    rv_formation: np.ndarray,
    week_keys: list[tuple[int, int]],
    *,
    draws: int,
    seed: int,
) -> dict:
    weeks, _groups = _week_groups(week_keys)
    rng = np.random.default_rng(seed)
    columns = {name: np.empty(draws, dtype=np.float64) for name in DRAW_STAT_ORDER}
    n_weeks = len(weeks)
    for draw in range(draws):
        choice = rng.choice(n_weeks, size=n_weeks, replace=True)
        stats = one_draw_stats(state, activity, displacement, rv_formation, draw_indices(week_keys, choice))
        for name in DRAW_STAT_ORDER:
            columns[name][draw] = stats[name]
    return columns


def _cell(rho: float, samples: np.ndarray, n: int, weeks: int) -> dict:
    bounds = family_bounds(samples)
    clears = cell_clears(rho, bounds)
    return {
        "rho": None if not math.isfinite(rho) else float(rho),
        "interval": [bounds["lo"], bounds["hi"]],
        "valid_fraction": bounds["valid_fraction"],
        "interpretable": bounds["interpretable"],
        "abs_rho_meets_scale": bool(math.isfinite(rho) and abs(rho) >= K.PRACTICAL_ABS_RHO),
        "interval_excludes_zero": interval_excludes_zero(bounds),
        "clears": clears,
        "n": n,
        "iso_weeks": weeks,
    }


def apply_route(endpoints: dict[str, dict], *, information_limited_flag: bool) -> dict:
    return A2.assign_route(endpoints, information_limited=information_limited_flag)


def score_sample(sample: dict, *, draws: int, seed: int) -> dict:
    state = np.asarray(sample["v"], dtype=np.float64)
    activity = np.asarray(sample["activity"], dtype=np.float64)
    displacement = np.asarray(sample["displacement"], dtype=np.float64)
    rv_formation = np.asarray(sample["rv_formation"], dtype=np.float64)
    rv_prev = np.asarray(sample["rv_prev"], dtype=np.float64)
    year = np.asarray(sample["year"], dtype=np.int64)
    week_keys = [tuple(week) for week in sample["week_keys"]]
    n = int(state.shape[0])
    weeks = len(set(week_keys))
    limited = information_limited(n, weeks, state)
    columns = bootstrap(
        state, activity, displacement, rv_formation, week_keys, draws=draws, seed=seed,
    )
    foundation = {
        "activity": _cell(spearman(state, activity), columns["foundation_activity"], n, weeks),
        "displacement": _cell(spearman(state, displacement), columns["foundation_displacement"], n, weeks),
    }
    incremental = {
        "activity": _cell(
            partial_rho(state, activity, rv_formation), columns["incremental_activity"], n, weeks,
        ),
        "displacement": _cell(
            partial_rho(state, displacement, rv_formation), columns["incremental_displacement"], n, weeks,
        ),
    }
    years = {
        "activity": yearly_spearman(year, state, activity, min_n=K.MIN_YEAR_N),
        "displacement": yearly_spearman(year, state, displacement, min_n=K.MIN_YEAR_N),
    }
    unstable = {
        "activity": year_is_unstable(years["activity"]),
        "displacement": year_is_unstable(years["displacement"]),
    }
    placebo = {
        "activity": lag_placebo(state, activity),
        "displacement": lag_placebo(state, displacement),
    }
    endpoints = {}
    for name, key in ENDPOINT_KEYS:
        rho_f = foundation[key]["rho"]
        rho_l = placebo[key]
        endpoints[name] = {
            "foundation_clears": foundation[key]["clears"],
            "year_unstable": unstable[key],
            "incremental_formation_clears": incremental[key]["clears"],
            "foundation_abs": abs(rho_f) if rho_f is not None else float("nan"),
            "lag_placebo_abs": abs(rho_l) if math.isfinite(rho_l) else float("nan"),
            "foundation_rho": rho_f,
            "incremental_rho": incremental[key]["rho"],
            "lag_placebo_rho": None if not math.isfinite(rho_l) else float(rho_l),
        }
    decision = apply_route(endpoints, information_limited_flag=limited)
    routed_specific = {row["endpoint"]: row["current_state_specific"] for row in decision["endpoints"]}
    for name, _key in ENDPOINT_KEYS:
        own = A2.current_state_specific(endpoints[name])
        if name in routed_specific and routed_specific[name] != own:
            raise RuntimeError("specificity drifted from amendment A2")
        endpoints[name]["current_state_specific"] = own
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "exposure_class": "EXPOSED_SURFACE_DISCOVERY",
        "surface": K.SURFACE_ID,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "anchor": K.ANCHOR,
        "width": "W/P0",
        "horizon_bars": K.HORIZON_BARS,
        "incremental_covariate": A1.INCREMENTAL_COVARIATE,
        "n": n,
        "iso_weeks": weeks,
        "lag_placebo_n": n - 1,
        "boot_draws": draws,
        "boot_seed": seed,
        "family_quantiles": [K.FAMILY_ALPHA_QUANTILE, 1.0 - K.FAMILY_ALPHA_QUANTILE],
        "practical_abs_rho": K.PRACTICAL_ABS_RHO,
        "information_limited": limited,
        "foundation": foundation,
        "incremental_rv_formation": incremental,
        "years": years,
        "year_unstable": unstable,
        "lag_placebo": {
            key: {
                "rho": endpoints[name]["lag_placebo_rho"],
                "current_state_specific": endpoints[name]["current_state_specific"],
            }
            for name, key in ENDPOINT_KEYS
        },
        "rv_prev": {
            "role": A1.RV_PREV_ROLE,
            "route_input": False,
            "spearman_v": spearman(state, rv_prev),
            "partial_activity": partial_rho(state, activity, rv_prev),
            "partial_displacement": partial_rho(state, displacement, rv_prev),
        },
        "route_decision": decision,
        "route": decision["route"],
        "route_supporting_endpoints": decision["route_supporting_endpoints"],
        "incremental_qualified_but_not_specific_endpoints": decision[
            "incremental_qualified_but_not_specific_endpoints"
        ],
        "interpretation": INTERPRETATION[decision["route"]],
        "not_established": NOT_ESTABLISHED,
        "successor_started": False,
        "outcome_read": True,
        "future_association_read": True,
        "endpoints_reported_in_order": ["ACTIVITY", "DISPLACEMENT"],
    }


def eligible_forms(high, low, close, t0: int) -> list[dict]:
    """Analysis-sample indexes only. No future return is computed."""
    n_days = int(high.shape[0]) // K.BARS_PER_DAY
    rows = []
    for day in range(n_days):
        day_ms = t0 + day * PARENT.DAY_MS
        if day_ms < parent_census.EVENT_START_MS or day_ms >= parent_census.SURFACE_END_MS:
            continue
        form = day * K.BARS_PER_DAY
        geo = parent_census._geometry(high, low, close, form)
        if geo is None or not geo["usable"]:
            continue
        past_ok = census_mod._path_complete(close, form - K.FORMATION_BARS - 1, K.FORMATION_BARS + 1)
        future_ok = census_mod._path_complete(close, form + K.FORMATION_BARS - 1, K.HORIZON_BARS + 1)
        span_start, span_count = A1.formation_close_span(form)
        rv_ok = census_mod._path_complete(close, span_start, span_count)
        if not (past_ok and future_ok and rv_ok):
            continue
        stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=UTC)
        iso = stamp.isocalendar()
        rows.append({
            "form": form,
            "day_ms": day_ms,
            "year": stamp.year,
            "week": (int(iso.year), int(iso.week)),
            "high": float(geo["high"]),
            "low": float(geo["low"]),
            "p0": float(geo["p0"]),
        })
    return rows


def values_from_forms(close, rows: list[dict]) -> dict:
    v = []
    activity = []
    displacement = []
    rv_formation = []
    rv_prev = []
    year = []
    week_keys = []
    day_ms = []
    for row in rows:
        form = row["form"]
        p0 = row["p0"]
        v.append((row["high"] - row["low"]) / p0)
        future_returns = A1.log_returns(close, A1.future_return_pairs(form))
        activity.append(A1.realized_variation(future_returns))
        end_close = float(close[form + K.FORMATION_BARS + K.HORIZON_BARS - 1])
        displacement.append(abs(math.log(end_close / p0)))
        rv_formation.append(A1.realized_variation(A1.log_returns(close, A1.formation_return_pairs(form))))
        rv_prev.append(A1.realized_variation(A1.log_returns(close, A1.prev_hour_return_pairs(form))))
        year.append(row["year"])
        week_keys.append(row["week"])
        day_ms.append(row["day_ms"])
    return {
        "v": np.asarray(v, dtype=np.float64),
        "activity": np.asarray(activity, dtype=np.float64),
        "displacement": np.asarray(displacement, dtype=np.float64),
        "rv_formation": np.asarray(rv_formation, dtype=np.float64),
        "rv_prev": np.asarray(rv_prev, dtype=np.float64),
        "year": np.asarray(year, dtype=np.int64),
        "week_keys": week_keys,
        "day_ms": np.asarray(day_ms, dtype=np.int64),
    }


def _fmt(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "na"
    return f"{value:+.4f}"


def _interval(cell: dict) -> str:
    lo, hi = cell["interval"]
    if lo is None or hi is None:
        return "not interpretable"
    return f"[{lo:+.4f}, {hi:+.4f}]"


def render_markdown(payload: dict) -> str:
    lines = [
        "# FORMATION_WIDTH_REGIME_V1 — outcome read",
        "",
        f"`outcome_read = true`",
        f"`route = {payload['route']}`",
        "",
        payload["interpretation"],
        "",
        payload["not_established"],
        "",
        NO_SUCCESSOR,
        "",
        f"Surface `{payload['surface']}` `{payload['event_start']}` to `{payload['surface_end_exclusive']}` exclusive.",
        f"N {payload['n']}. ISO weeks {payload['iso_weeks']}. Seed {payload['boot_seed']}. Draws {payload['boot_draws']}.",
        f"Pre-outcome evaluator `{payload['pre_outcome_evaluator_commit']}`.",
        "",
        "## Foundation",
        "",
        "| endpoint | rho | family interval | clear |",
        "| --- | --- | --- | --- |",
    ]
    for name, key in ENDPOINT_KEYS:
        cell = payload["foundation"][key]
        lines.append(f"| {name} | {_fmt(cell['rho'])} | {_interval(cell)} | {str(cell['clears']).lower()} |")
    lines.extend(["", "## Years", ""])
    for name, key in ENDPOINT_KEYS:
        bits = [
            f"{year} {_fmt(row['rho'])} (n {row['n']})"
            for year, row in payload["years"][key].items()
        ]
        stable = "unstable" if payload["year_unstable"][key] else "stable"
        lines.append(f"- {name} foundation, {stable}: " + "; ".join(bits))
    lines.extend(["", "## Incremental given RV_FORMATION", "", "| endpoint | rho | family interval | clear |", "| --- | --- | --- | --- |"])
    for name, key in ENDPOINT_KEYS:
        cell = payload["incremental_rv_formation"][key]
        lines.append(f"| {name} | {_fmt(cell['rho'])} | {_interval(cell)} | {str(cell['clears']).lower()} |")
    prev = payload["rv_prev"]
    lines.extend([
        "",
        "## RV_PREV secondary context",
        "",
        f"Spearman(V, RV_PREV) {_fmt(prev['spearman_v'])}.",
        f"Partial ACTIVITY {_fmt(prev['partial_activity'])}. Partial DISPLACEMENT {_fmt(prev['partial_displacement'])}.",
        "These numbers are not route inputs.",
        "",
        "## Lag placebo",
        "",
    ])
    for name, key in ENDPOINT_KEYS:
        row = payload["lag_placebo"][key]
        lines.append(
            f"- {name}: rho {_fmt(row['rho'])}, current_state_specific {row['current_state_specific']}"
        )
    lines.extend([
        "",
        f"route_supporting_endpoints: {payload['route_supporting_endpoints']}",
        "incremental_qualified_but_not_specific_endpoints: "
        f"{payload['incremental_qualified_but_not_specific_endpoints']}",
        "",
    ])
    return "\n".join(lines)


def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def assert_frozen_texts() -> None:
    if _sha256(DESIGN_PATH) != DESIGN_SHA:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    if _sha256(A1_PATH) != A1_SHA:
        raise SystemExit("A1_HASH_MISMATCH")
    if _sha256(A2_PATH) != A2_SHA:
        raise SystemExit("A2_HASH_MISMATCH")


def assert_evaluator_matches_head() -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    package = Path(__file__).resolve().parent
    for path in sorted(package.glob("*.py")):
        rel = str(path.relative_to(ROOT))
        committed = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != hashlib.sha256(path.read_bytes()).hexdigest():
            raise SystemExit("EVALUATOR_DIFFERS_FROM_HEAD")
    return head


def write_outputs(payload: dict, manifest: dict) -> None:
    if OUT_JSON.exists() or OUT_MD.exists() or OUT_MANIFEST.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    OUT_JSON.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    OUT_MANIFEST.write_text(json.dumps(_json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if OUT_JSON.exists() or OUT_MD.exists() or OUT_MANIFEST.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    assert_frozen_texts()
    head = assert_evaluator_matches_head()
    from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

    bars = load_discovery_bars()
    if int(bars.t0) % PARENT.DAY_MS != 0:
        raise SystemExit("PANEL_T0_IS_NOT_UTC_MIDNIGHT")
    if int(bars.times[0]) < parent_census.EVENT_START_MS or int(bars.times[-1]) >= parent_census.SURFACE_END_MS:
        raise SystemExit("PANEL_LEAVES_THE_CONSUMED_SURFACE")
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    forms = eligible_forms(high, low, close, int(bars.t0))
    weeks = {row["week"] for row in forms}
    if len(forms) != EXPECTED_N or len(weeks) != EXPECTED_WEEKS:
        raise SystemExit("SAMPLE_DOES_NOT_MATCH_FROZEN_SUPPORT")
    payload = score_sample(values_from_forms(close, forms), draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
    payload["design_sha256"] = DESIGN_SHA
    payload["amendment_a1_sha256"] = A1_SHA
    payload["amendment_a2_sha256"] = A2_SHA
    payload["pre_outcome_evaluator_commit"] = head
    payload["evaluator_digest"] = census_mod.code_digest()
    payload["read_at"] = dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "unit": K.UNIT,
        "pre_outcome_evaluator_commit": head,
        "evaluator_digest": payload["evaluator_digest"],
        "design_sha256": DESIGN_SHA,
        "amendment_a1_sha256": A1_SHA,
        "amendment_a2_sha256": A2_SHA,
        "boot_seed": K.BOOT_SEED,
        "boot_draws": K.BOOT_DRAWS,
        "surface": K.SURFACE_ID,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "n": payload["n"],
        "iso_weeks": payload["iso_weeks"],
        "route": payload["route"],
        "read_at": payload["read_at"],
        "outcome_read": True,
    }
    write_outputs(payload, manifest)
    print(json.dumps({
        "route": payload["route"],
        "n": payload["n"],
        "iso_weeks": payload["iso_weeks"],
        "read_at": payload["read_at"],
        "pre_outcome_evaluator_commit": head,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
