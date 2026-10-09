"""One outcome read of the frozen Bybit formation-width activity cell.

Owner go 2026-10-09: one read of partial Spearman of V with ACTIVITY given
RV_FORMATION on the pinned Bybit series. A second official run returns
REFUSING_RERUN before loading the panel. The route function is the confirmation
design's order, with the Bybit stability date. This module does not define a
new route.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.formation_width_activity_confirmation_v1 import constants as CONF
from scripts.research.formation_width_regime_v1 import amendment_a1 as A1

from . import constants as K
from . import support

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_DESIGN.md"
SUPPORT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_SUPPORT.json"
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_RESULT.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_RESULT.md"
OUT_MANIFEST = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_EVALUATOR_MANIFEST.json"
UTC = dt.timezone.utc

DESIGN_SHA = "83e5a84de4606ec96ed1605690c2ba708970473c0626ca23b766d05a7ac4c642"
SUPPORT_SHA = "69bbe8384e9f1a029d700d306471ef70cd270ea97373404ea9991df1fb1d3118"
EXPECTED_N = 1613
EXPECTED_WEEKS = 240
QUANTILE_HI = CONF.BOOT_QUANTILE_HI
MIN_VALID_FRACTION = CONF.MIN_VALID_FRACTION
MIN_LAG_PAIRS = CONF.MIN_LAG_PAIRS

ROUTE_CONFIRMED = CONF.ROUTE_CONFIRMED
ROUTE_BELOW = CONF.ROUTE_BELOW
ROUTE_NO = CONF.ROUTE_NO
ROUTE_UNSTABLE = CONF.ROUTE_UNSTABLE
ROUTE_WEAK = CONF.ROUTE_WEAK
REASON_SPECIFICITY = "LAG_PLACEBO_SPECIFICITY_NOT_SATISFIED"

# Atlas CONFIRMED means an independent-surface confirmation. This calendar is
# the discovery calendar, so a passing route stays a replication candidate.
ATLAS_STATE = {
    ROUTE_CONFIRMED: "LIVE_SIGNAL",
    ROUTE_BELOW: "CLOSED_ON_SURFACE",
    ROUTE_UNSTABLE: "CLOSED_ON_SURFACE",
    ROUTE_NO: "CLOSED_ON_SURFACE",
    ROUTE_WEAK: "INFORMATIONALLY_WEAK",
}

PASS_TEXT = (
    "On the exposed cross-venue Bybit BTCUSDT linear perpetual surface for 2020-2024, "
    "the exact incremental relation repeated: formation width had a positive association "
    "with next-hour activity beyond RV_FORMATION, with a point at least +0.10 and a "
    "positive one-sided lower bound."
)
FAIL_TEXT = (
    "The exact claim did not receive cross-venue support on Bybit under the frozen confirmation rule."
)
NOT_ESTABLISHED = (
    "Cross-venue replication support on this exposed same-calendar tape is L2 historical "
    "evidence when the route passes. It is not a time-disjoint confirmation, not L3, not a "
    "forecast, not a live probability, not an edge, not a causal claim, and not a product signal. "
    "The Binance discovery result is not rewritten."
)

assert K.BOOT_SEED == 20261108
assert K.BOOT_DRAWS == 2000
assert K.BOOT_QUANTILE_LO == 0.05
assert QUANTILE_HI == 0.95
assert MIN_VALID_FRACTION == 0.90
assert MIN_LAG_PAIRS == 100
assert K.PRACTICAL_RHO == 0.10
assert K.STABILITY_SPLIT == "2022-08-17"
assert K.EXPOSURE_CLASS == "SAME_CALENDAR_CROSS_VENUE_EXPOSED_REPLICATION"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def partial_rho(v: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    got = A1.partial_spearman(v, y, z)
    if got["degenerate"] or got["rho"] is None:
        return float("nan")
    return float(got["rho"])


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    values_x = np.asarray(x, dtype=np.float64)
    values_y = np.asarray(y, dtype=np.float64)
    if len(values_x) < 3 or len(values_x) != len(values_y):
        return float("nan")
    left = A1.average_ranks(values_x)
    right = A1.average_ranks(values_y)
    left = left - float(left.mean())
    right = right - float(right.mean())
    denom = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
    if denom == 0.0 or not math.isfinite(denom):
        return float("nan")
    return float(np.dot(left, right) / denom)


def decision_bounds(samples: np.ndarray) -> dict:
    column = np.asarray(samples, dtype=np.float64)
    finite = column[np.isfinite(column)]
    fraction = float(len(finite) / len(column)) if len(column) else 0.0
    valid_draws = int(len(finite))
    if fraction < MIN_VALID_FRACTION or valid_draws == 0:
        return {
            "lo": None,
            "hi": None,
            "valid_fraction": fraction,
            "valid_draws": valid_draws,
            "interpretable": False,
        }
    lo, hi = np.quantile(finite, [K.BOOT_QUANTILE_LO, QUANTILE_HI], method="linear")
    return {
        "lo": float(lo),
        "hi": float(hi),
        "valid_fraction": fraction,
        "valid_draws": valid_draws,
        "interpretable": True,
    }


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


def bootstrap_partial(
    state: np.ndarray,
    activity: np.ndarray,
    rv_formation: np.ndarray,
    week_keys: list[tuple[int, int]],
    *,
    draws: int,
    seed: int,
) -> np.ndarray:
    """ISO-week resample. Each draw recomputes ranks and scores only the partial cell."""
    weeks, _groups = _week_groups(week_keys)
    rng = np.random.default_rng(seed)
    out = np.empty(draws, dtype=np.float64)
    n_weeks = len(weeks)
    for draw in range(draws):
        choice = rng.choice(n_weeks, size=n_weeks, replace=True)
        indexes = draw_indices(week_keys, choice)
        out[draw] = partial_rho(state[indexes], activity[indexes], rv_formation[indexes])
    return out


def half_partial(state, activity, rv_formation, mask: np.ndarray) -> dict:
    n = int(np.count_nonzero(mask))
    if n < 3:
        return {"n": n, "rho": None}
    rho = partial_rho(state[mask], activity[mask], rv_formation[mask])
    if not math.isfinite(rho):
        return {"n": n, "rho": None}
    return {"n": n, "rho": float(rho)}


def stability_fails(first: dict, second: dict) -> bool:
    """Opposite signs on two halves that each have the frozen minimum N. Zero is not a sign."""
    if first["n"] < K.MIN_HALF_N or second["n"] < K.MIN_HALF_N:
        return False
    left = first["rho"]
    right = second["rho"]
    if left is None or right is None:
        return False
    if left == 0.0 or right == 0.0:
        return False
    return (left > 0.0) != (right > 0.0)


def lag_partial(state, activity, rv_formation) -> tuple[float, int]:
    """Today's V with the previous analysis row's ACTIVITY, given today's RV_FORMATION."""
    n_pairs = int(len(state) - 1)
    if n_pairs < 3:
        return float("nan"), n_pairs
    rho = partial_rho(state[1:], activity[:-1], rv_formation[1:])
    return rho, n_pairs


def specificity_passes(rho: float, lag_rho: float, lag_n: int) -> bool:
    if lag_n < MIN_LAG_PAIRS:
        return False
    if not math.isfinite(rho) or not math.isfinite(lag_rho):
        return False
    return abs(lag_rho) < abs(rho)


def assign_route(
    *,
    information_floor_failed: bool,
    interpretable: bool,
    rho: float,
    lower: float | None,
    stability_failed: bool,
    specific: bool,
) -> dict:
    """Confirmation-design order. The first match wins. Reasons are not new routes."""
    if information_floor_failed:
        return {"route": ROUTE_WEAK, "reason": None}
    positive = math.isfinite(rho) and rho > 0.0
    bound_above_zero = lower is not None and math.isfinite(lower) and lower > 0.0
    if not interpretable or not positive or not bound_above_zero:
        reason = None if interpretable else "NOT_INTERPRETABLE"
        if interpretable:
            reason = "SIGN_OR_BOUND_FAILS"
        return {"route": ROUTE_NO, "reason": reason}
    if rho < K.PRACTICAL_RHO:
        return {"route": ROUTE_BELOW, "reason": None}
    if stability_failed:
        return {"route": ROUTE_UNSTABLE, "reason": None}
    if not specific:
        return {"route": ROUTE_NO, "reason": REASON_SPECIFICITY}
    return {"route": ROUTE_CONFIRMED, "reason": None}


def selected_rows(collected: dict) -> list[dict]:
    return [row for row in collected["rows"] if row["in_sample"]]


def form_index(day_ms: int) -> int:
    day = (int(day_ms) - support.GRID_START_MS) // K.DAY_MS
    return int(day) * K.BARS_PER_DAY


def values_from_rows(close: np.ndarray, rows: list[dict]) -> dict:
    v = []
    activity = []
    rv_formation = []
    week_keys = []
    first_half = []
    for row in rows:
        form = form_index(row["day_ms"])
        v.append(float(row["relative_width"]))
        activity.append(A1.realized_variation(A1.log_returns(close, A1.future_return_pairs(form))))
        rv_formation.append(A1.realized_variation(A1.log_returns(close, A1.formation_return_pairs(form))))
        week_keys.append((int(row["iso_year"]), int(row["iso_week"])))
        first_half.append(bool(row["first_half"]))
    return {
        "v": np.asarray(v, dtype=np.float64),
        "activity": np.asarray(activity, dtype=np.float64),
        "rv_formation": np.asarray(rv_formation, dtype=np.float64),
        "week_keys": week_keys,
        "first_half": np.asarray(first_half, dtype=bool),
    }


def score_sample(
    sample: dict,
    *,
    draws: int,
    seed: int,
    information_floor_failed: bool,
) -> dict:
    state = np.asarray(sample["v"], dtype=np.float64)
    activity = np.asarray(sample["activity"], dtype=np.float64)
    rv_formation = np.asarray(sample["rv_formation"], dtype=np.float64)
    week_keys = [tuple(week) for week in sample["week_keys"]]
    first_mask = np.asarray(sample["first_half"], dtype=bool)
    n = int(state.shape[0])
    weeks = len(set(week_keys))
    rho = partial_rho(state, activity, rv_formation)
    draws_out = bootstrap_partial(
        state, activity, rv_formation, week_keys, draws=draws, seed=seed,
    )
    bounds = decision_bounds(draws_out)
    first = half_partial(state, activity, rv_formation, first_mask)
    second = half_partial(state, activity, rv_formation, ~first_mask)
    unstable = stability_fails(first, second)
    lag_rho, lag_n = lag_partial(state, activity, rv_formation)
    specific = specificity_passes(rho, lag_rho, lag_n)
    decision = assign_route(
        information_floor_failed=information_floor_failed,
        interpretable=bool(bounds["interpretable"]),
        rho=rho,
        lower=bounds["lo"],
        stability_failed=unstable,
        specific=specific,
    )
    route = decision["route"]
    return {
        "unit": K.UNIT,
        "mode": "ONE_OUTCOME_READ",
        "exposure_class": K.EXPOSURE_CLASS,
        "claim_ceiling": K.CLAIM_CEILING,
        "time_disjoint_from_discovery": False,
        "pristine": False,
        "surface": K.DATASET_ID,
        "series": K.SERIES_NAME,
        "canonical_sha256": K.CANONICAL_SHA256,
        "venue": K.VENUE,
        "instrument": K.INSTRUMENT,
        "contract_type": K.CONTRACT_TYPE,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "anchor": K.ANCHOR,
        "state": K.STATE,
        "endpoint_name": K.ENDPOINT,
        "incremental_covariate": K.INCREMENTAL_COVARIATE,
        "n": n,
        "iso_weeks": weeks,
        "boot_draws": draws,
        "boot_seed": seed,
        "boot_quantile_lo": K.BOOT_QUANTILE_LO,
        "boot_quantile_hi": QUANTILE_HI,
        "min_valid_fraction": MIN_VALID_FRACTION,
        "practical_rho": K.PRACTICAL_RHO,
        "primary": {
            "rho": None if not math.isfinite(rho) else float(rho),
            "lower": bounds["lo"],
            "upper": bounds["hi"],
            "valid_fraction": bounds["valid_fraction"],
            "valid_draws": bounds["valid_draws"],
            "interpretable": bounds["interpretable"],
            "practical_bar_met": bool(math.isfinite(rho) and rho >= K.PRACTICAL_RHO),
            "lower_bound_above_zero": bool(bounds["lo"] is not None and bounds["lo"] > 0.0),
        },
        "context": {
            "route_input": False,
            "spearman_v_endpoint": None if not math.isfinite(spearman(state, activity)) else float(spearman(state, activity)),
            "spearman_v_covariate": None if not math.isfinite(spearman(state, rv_formation)) else float(spearman(state, rv_formation)),
        },
        "stability": {
            "split": K.STABILITY_SPLIT,
            "rule": "OPPOSITE_SIGNS_WHEN_BOTH_HALVES_MEET_MIN_N",
            "first_half": first,
            "second_half": second,
            "fails": unstable,
        },
        "lag_placebo": {
            "rho": None if not math.isfinite(lag_rho) else float(lag_rho),
            "n": lag_n,
            "min_pairs": MIN_LAG_PAIRS,
            "current_state_specific": specific,
        },
        "route": route,
        "route_reason": decision["reason"],
        "atlas_state": ATLAS_STATE[route],
        "interpretation": PASS_TEXT if route == ROUTE_CONFIRMED else FAIL_TEXT,
        "not_established": NOT_ESTABLISHED,
        "outcome_read": True,
        "future_association_read": True,
        "bitmex_in_unit": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
        "prospective_opened": False,
        "forecast_changed": False,
        "discovery_result_sha256": K.DISCOVERY_RESULT_SHA256,
        "successor_started": False,
    }


def _fmt(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "na"
    return f"{value:+.6f}"


def render_markdown(payload: dict) -> str:
    primary = payload["primary"]
    stability = payload["stability"]
    lag = payload["lag_placebo"]
    context = payload["context"]
    lines = [
        f"# {K.UNIT} — one outcome read",
        "",
        "`outcome_read = true`",
        "`future_association_read = true`",
        f"`route = {payload['route']}`",
        f"`exposure_class = {payload['exposure_class']}`",
        f"`claim_ceiling = {payload['claim_ceiling']}`",
        "",
        payload["interpretation"],
        "",
        payload["not_established"],
        "",
        "No successor is started. BitMEX, 2025/2026, E1, a prospective panel, the product, and the forecast are outside this read.",
        "",
        f"Surface `{payload['surface']}` `{payload['series']}` SHA256 `{payload['canonical_sha256']}`.",
        f"Events `{payload['event_start']}` to `{payload['surface_end_exclusive']}` exclusive.",
        f"N {payload['n']}. ISO weeks {payload['iso_weeks']}. Seed {payload['boot_seed']}. Draws {payload['boot_draws']}.",
        f"Read `{payload['read_at']}`. Pre-outcome evaluator `{payload['pre_outcome_evaluator_commit']}`.",
        f"Evaluator digest `{payload['evaluator_digest']}`.",
        "",
        "## Primary cell",
        "",
        f"- partial Spearman: {_fmt(primary['rho'])}",
        f"- one-sided lower bound: {_fmt(primary['lower'])}",
        f"- descriptive upper quantile: {_fmt(primary['upper'])}",
        f"- valid draws: {primary['valid_draws']} / {payload['boot_draws']}",
        f"- valid fraction: {primary['valid_fraction']}",
        f"- interpretable: {str(primary['interpretable']).lower()}",
        f"- practical bar +0.10 met: {str(primary['practical_bar_met']).lower()}",
        f"- lower bound above 0: {str(primary['lower_bound_above_zero']).lower()}",
        "",
        "## Context, not a route input",
        "",
        f"- Spearman(V, endpoint): {_fmt(context['spearman_v_endpoint'])}",
        f"- Spearman(V, covariate): {_fmt(context['spearman_v_covariate'])}",
        "",
        "## Stability",
        "",
        f"- split: {stability['split']}",
        f"- first half: {_fmt(stability['first_half']['rho'])} (n {stability['first_half']['n']})",
        f"- second half: {_fmt(stability['second_half']['rho'])} (n {stability['second_half']['n']})",
        f"- fails: {str(stability['fails']).lower()}",
        "",
        "## Lag placebo",
        "",
        f"- partial rho: {_fmt(lag['rho'])}",
        f"- pairs: {lag['n']}",
        f"- current_state_specific: {str(lag['current_state_specific']).lower()}",
        "",
        f"Route reason: {payload['route_reason']}.",
        "",
    ]
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
    if isinstance(value, np.integer):
        value = int(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def assert_frozen_texts() -> None:
    if _sha256(DESIGN_PATH) != DESIGN_SHA:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    if _sha256(SUPPORT_JSON) != SUPPORT_SHA:
        raise SystemExit("SUPPORT_HASH_MISMATCH")
    payload = json.loads(SUPPORT_JSON.read_text(encoding="utf-8"))
    if payload.get("pre_outcome_route") != K.ROUTE_ADEQUATE:
        raise SystemExit("SUPPORT_ROUTE_DOES_NOT_AUTHORIZE_THE_READ")
    if payload.get("outcome_read") is not False or payload.get("future_association_read") is not False:
        raise SystemExit("SUPPORT_ALREADY_MARKED_AN_OUTCOME")
    if payload["counts"]["analysis_sample"] != EXPECTED_N or payload["analysis_iso_weeks"] != EXPECTED_WEEKS:
        raise SystemExit("SUPPORT_COUNTS_DRIFTED")


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
    _high, _low, close, provenance = support.load_ohlc()
    if provenance["canonical_sha256"] != K.CANONICAL_SHA256:
        raise SystemExit("CANONICAL_SHA_MISMATCH")
    rows = selected_rows(support.collect(_high, _low, close))
    weeks = {(int(row["iso_year"]), int(row["iso_week"])) for row in rows}
    if len(rows) != EXPECTED_N or len(weeks) != EXPECTED_WEEKS:
        raise SystemExit("SAMPLE_DOES_NOT_MATCH_FROZEN_SUPPORT")
    payload = score_sample(
        values_from_rows(close, rows),
        draws=K.BOOT_DRAWS,
        seed=K.BOOT_SEED,
        information_floor_failed=False,
    )
    if payload["n"] != EXPECTED_N or payload["iso_weeks"] != EXPECTED_WEEKS:
        raise SystemExit("SCORED_SAMPLE_DRIFTED")
    payload["design_sha256"] = DESIGN_SHA
    payload["support_sha256"] = SUPPORT_SHA
    payload["pre_outcome_evaluator_commit"] = head
    payload["evaluator_digest"] = support.code_digest()
    payload["read_at"] = dt.datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "unit": K.UNIT,
        "outcome_read": True,
        "future_association_read": True,
        "pre_outcome_evaluator_commit": head,
        "evaluator_digest": payload["evaluator_digest"],
        "design_sha256": DESIGN_SHA,
        "support_sha256": SUPPORT_SHA,
        "canonical_sha256": K.CANONICAL_SHA256,
        "surface": K.DATASET_ID,
        "series": K.SERIES_NAME,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "exposure_class": K.EXPOSURE_CLASS,
        "n": payload["n"],
        "iso_weeks": payload["iso_weeks"],
        "boot_seed": K.BOOT_SEED,
        "boot_draws": K.BOOT_DRAWS,
        "primary_rho": payload["primary"]["rho"],
        "lower": payload["primary"]["lower"],
        "upper": payload["primary"]["upper"],
        "valid_draws": payload["primary"]["valid_draws"],
        "practical_bar_met": payload["primary"]["practical_bar_met"],
        "first_half_rho": payload["stability"]["first_half"]["rho"],
        "second_half_rho": payload["stability"]["second_half"]["rho"],
        "stability_fails": payload["stability"]["fails"],
        "lag_placebo_rho": payload["lag_placebo"]["rho"],
        "current_state_specific": payload["lag_placebo"]["current_state_specific"],
        "route": payload["route"],
        "route_reason": payload["route_reason"],
        "atlas_state": payload["atlas_state"],
        "read_at": payload["read_at"],
        "bitmex_in_unit": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
        "prospective_opened": False,
        "forecast_changed": False,
    }
    write_outputs(payload, manifest)
    print(json.dumps({
        "route": payload["route"],
        "n": payload["n"],
        "iso_weeks": payload["iso_weeks"],
        "read_at": payload["read_at"],
        "pre_outcome_evaluator_commit": head,
        "primary_rho": payload["primary"]["rho"],
        "lower": payload["primary"]["lower"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
