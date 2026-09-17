"""MARKET-01_OI_EXPANSION_WEAK_CONTINUATION frozen-contract implementation.

In-memory scientific pipeline only. Bound CORE/OI snapshot evaluation is
refused. Does not ARM, execute, or inspect real MARKET outcomes.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.b2_03_impulse_morphology_lib import pre_vol_60 as b2_03_pre_vol_60
from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    namespace_seed,
    pcg64_generator,
)
from scripts.research.harness_synthetic_edge_calibration_v3_confirmatory import (
    optimal_stationary_block_length,
)
from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    B2_06_EXECUTION_AUTHORIZED,
    DEFAULT_V4,
    FROZEN_FREEZE_JSON_SHA256,
    FROZEN_FREEZE_MD_SHA256,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    MARKET_01_ARMED,
    MARKET_01_EXECUTION_AUTHORIZED,
    MARKET_01_TEST_CALIBRATED,
    OI_SNAPSHOT_ID,
    PRICE_DATASET_ID,
    PRICE_SNAPSHOT_ID,
    PROTECTED_OOS_AUTHORIZED,
    RESEARCH_ID,
    authenticate_arch_selector,
    authenticate_frozen_prereg_bytes,
    refuse_bound_execution,
    snapshot_is_bound,
)


BAR_MS = 60_000
FIVE_MS = 5 * BAR_MS
THIRTY_M_MS = 30 * BAR_MS
SIXTY_M_MS = 60 * BAR_MS
NINETY_M_MS = 90 * BAR_MS
EPISODE_MS = 120 * BAR_MS
CALENDAR_DAY_MS = 86_400_000
HIST_MS = 30 * CALENDAR_DAY_MS
OI_STALE_MS = 300_000

COMMON_START_MS = 1_598_918_400_000  # 2020-09-01T00:00:00Z
COMMON_END_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z

IMPULSE_P_MIN = 0.90
OI_P_STRICT = 0.75
CONTINUATION_MAX = 0.25
TERTILE_LOW = 1.0 / 3.0
TERTILE_HIGH = 2.0 / 3.0

TOTAL_MIN = 100
CAND_MIN = 30
BASE_MIN = 30
USABLE_STRATA_MIN = 3
STRATUM_GROUP_MIN = 5

BOOTSTRAP_B = 999
ALPHA = 0.05
SEED_MATERIAL = (
    "MARKET-01_OI_EXPANSION_WEAK_CONTINUATION|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999"
)
SEED_MATERIAL_SHA256 = "a960350293eacee83f5cfcb21e138f5f4dbbea1af4547d298e5a1da2ec571dbe"
MARKET_01_BOOTSTRAP_SEED = 12204813275361890024

CLASS_NOT_IDENTIFIABLE = "NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT"
CLASS_NO_EVIDENCE = "NO_EVIDENCE"
CLASS_DETECTED_NOT_ROBUST = "DETECTED_BUT_NOT_ROBUST"
CLASS_ROBUST_CANDIDATE = "ROBUST_CANDIDATE"

ERA_BOUNDS_MS = (
    ("ERA_1", 1_598_918_400_000, 1_609_459_200_000),
    ("ERA_2", 1_609_459_200_000, 1_640_995_200_000),
    ("ERA_3", 1_640_995_200_000, 1_672_531_200_000),
    ("ERA_4", 1_672_531_200_000, 1_704_067_200_000),
    ("ERA_5", 1_704_067_200_000, 1_735_689_600_000),
)

SYNTHETIC_SNAPSHOT = "SYNTHETIC_FIXTURE"


class Market01Error(RuntimeError):
    """Contract or construction failure."""


@dataclass(frozen=True)
class PriceView:
    open_time_ms: np.ndarray
    available_at_ms: np.ndarray
    close: np.ndarray
    snapshot_id: str = SYNTHETIC_SNAPSHOT


@dataclass(frozen=True)
class OiView:
    create_time_ms: np.ndarray
    available_at_ms: np.ndarray
    sum_open_interest: np.ndarray
    snapshot_id: str = SYNTHETIC_SNAPSHOT


@dataclass
class EpisodeRecord:
    impulse_end_t_ms: int
    impulse_start_ms: int
    decision_T_ms: int
    outcome_end_ms: int
    impulse_return: float | None = None
    D: int | None = None
    abs_impulse: float | None = None
    p_impulse: float | None = None
    qualifying_impulse: bool = False
    occupies_slot: bool = False
    oi_start: float | None = None
    oi_end: float | None = None
    delta_oi: float | None = None
    p_oi: float | None = None
    oi_expansion: bool = False
    state_return: float | None = None
    continuation_ratio: float | None = None
    weak_continuation: bool = False
    candidate: bool = False
    pre_vol_60: float | None = None
    impulse_mag_state: str | None = None
    trailing_vol_state: str | None = None
    stratum_id: str | None = None
    reversal_return: float | None = None
    confirmatory_eligible: bool = False
    exclusion_reason: str | None = None


def _require_finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def midrank_percentile(x: float, ref: np.ndarray) -> float | None:
    if not math.isfinite(x):
        return None
    finite = np.asarray(ref, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    n = int(finite.shape[0])
    if n < 1:
        return None
    n_lt = int(np.count_nonzero(finite < x))
    n_eq = int(np.count_nonzero(finite == x))
    return (n_lt + 0.5 * n_eq) / n


def tertile_state(p: float | None) -> str | None:
    if p is None or not math.isfinite(p):
        return None
    if p < TERTILE_LOW:
        return "LOW"
    if p < TERTILE_HIGH:
        return "MID"
    return "HIGH"


def stratum_id(mag: str, vol: str) -> str:
    return f"{mag}|{vol}"


def era_of_T(t_ms: int) -> str | None:
    for name, start, end in ERA_BOUNDS_MS:
        if start <= int(t_ms) < end:
            return name
    return None


def close_at(price: PriceView, clock_ms: int) -> float | None:
    """Close of the 1m bar whose bar_end_exclusive equals clock_ms."""
    open_t = int(clock_ms) - BAR_MS
    if open_t < 0:
        return None
    start = int(price.open_time_ms[0])
    delta = open_t - start
    if delta < 0 or delta % BAR_MS != 0:
        return None
    idx = delta // BAR_MS
    if idx < 0 or idx >= len(price.close):
        return None
    if int(price.open_time_ms[idx]) != open_t:
        return None
    if int(price.available_at_ms[idx]) != int(clock_ms):
        return None
    value = float(price.close[idx])
    if not _require_finite_positive(value):
        return None
    return value


def legal_oi_at(oi: OiView, clock_ms: int) -> float | None:
    """Latest native OI with available_at <= U and staleness <= 5m."""
    u = int(clock_ms)
    avail = np.asarray(oi.available_at_ms, dtype=np.int64)
    if avail.size == 0:
        return None
    idx = int(np.searchsorted(avail, u, side="right") - 1)
    if idx < 0:
        return None
    available_at = int(avail[idx])
    if available_at > u:
        return None
    if (u - available_at) > OI_STALE_MS:
        return None
    value = float(oi.sum_open_interest[idx])
    if not _require_finite_positive(value):
        return None
    return value


def pre_vol_60(price: PriceView, t_ms: int) -> float | None:
    try:
        value = b2_03_pre_vol_60(
            price.open_time_ms,
            price.available_at_ms,
            price.close,
            int(t_ms),
        )
    except Exception:
        return None
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def log_ratio(end: float, start: float) -> float | None:
    if not _require_finite_positive(end) or not _require_finite_positive(start):
        return None
    value = math.log(end / start)
    if not math.isfinite(value):
        return None
    return value


def _five_minute_range(start_ms: int, end_exclusive_ms: int) -> np.ndarray:
    start = ((int(start_ms) + FIVE_MS - 1) // FIVE_MS) * FIVE_MS
    end = int(end_exclusive_ms)
    if start >= end:
        return np.zeros(0, dtype=np.int64)
    return np.arange(start, end, FIVE_MS, dtype=np.int64)


def _impulse_return(price: PriceView, t_ms: int) -> float | None:
    end = close_at(price, t_ms)
    start = close_at(price, t_ms - THIRTY_M_MS)
    if end is None or start is None:
        return None
    return log_ratio(end, start)


def _abs_impulse_series(
    price: PriceView, taus: np.ndarray
) -> np.ndarray:
    out = np.full(taus.shape[0], np.nan, dtype=np.float64)
    for i, tau in enumerate(taus):
        ret = _impulse_return(price, int(tau))
        if ret is None:
            continue
        out[i] = abs(ret)
    return out


def _pre_vol_series(price: PriceView, taus: np.ndarray) -> np.ndarray:
    out = np.full(taus.shape[0], np.nan, dtype=np.float64)
    for i, tau in enumerate(taus):
        vol = pre_vol_60(price, int(tau))
        if vol is None:
            continue
        out[i] = vol
    return out


def _delta_oi_at(oi: OiView, tau_ms: int) -> float | None:
    end = legal_oi_at(oi, tau_ms)
    start = legal_oi_at(oi, tau_ms - THIRTY_M_MS)
    if end is None or start is None:
        return None
    return log_ratio(end, start)


def classify_qualifying_impulse(
    price: PriceView, t_ms: int
) -> tuple[bool, dict[str, Any]]:
    impulse_start = int(t_ms) - THIRTY_M_MS
    ret = _impulse_return(price, int(t_ms))
    info: dict[str, Any] = {
        "impulse_return": ret,
        "D": None,
        "abs_impulse": None,
        "p_impulse": None,
    }
    if ret is None or not math.isfinite(ret):
        return False, info
    if ret == 0.0:
        return False, info
    d = 1 if ret > 0.0 else -1
    abs_imp = abs(ret)
    hist_lo = impulse_start - HIST_MS
    taus = _five_minute_range(hist_lo, impulse_start)
    refs = _abs_impulse_series(price, taus)
    p = midrank_percentile(abs_imp, refs)
    info.update({"D": d, "abs_impulse": abs_imp, "p_impulse": p})
    if p is None:
        return False, info
    return bool(p >= IMPULSE_P_MIN), info


def classify_oi_expansion(
    oi: OiView, t_ms: int
) -> tuple[bool, dict[str, Any]]:
    state_start = int(t_ms)
    T = int(t_ms) + THIRTY_M_MS
    oi_start = legal_oi_at(oi, state_start)
    oi_end = legal_oi_at(oi, T)
    info: dict[str, Any] = {
        "oi_start": oi_start,
        "oi_end": oi_end,
        "delta_oi": None,
        "p_oi": None,
    }
    if oi_start is None or oi_end is None:
        return False, info
    delta = log_ratio(oi_end, oi_start)
    info["delta_oi"] = delta
    if delta is None:
        return False, info
    hist_lo = state_start - HIST_MS
    taus = _five_minute_range(hist_lo, state_start)
    refs = []
    for tau in taus:
        dref = _delta_oi_at(oi, int(tau))
        if dref is None:
            continue
        refs.append(dref)
    p = midrank_percentile(delta, np.asarray(refs, dtype=np.float64))
    info["p_oi"] = p
    if p is None:
        return False, info
    return bool(p > OI_P_STRICT), info


def classify_weak_continuation(
    price: PriceView, t_ms: int, d: int, abs_impulse: float
) -> tuple[bool, dict[str, Any]]:
    T = int(t_ms) + THIRTY_M_MS
    state_ret = log_ratio(close_at(price, T) or float("nan"), close_at(price, t_ms) or float("nan"))
    info: dict[str, Any] = {
        "state_return": state_ret,
        "continuation_ratio": None,
    }
    if state_ret is None or abs_impulse == 0.0 or not math.isfinite(abs_impulse):
        return False, info
    ratio = (d * state_ret) / abs_impulse
    info["continuation_ratio"] = ratio
    if not math.isfinite(ratio):
        return False, info
    return bool(ratio <= CONTINUATION_MAX), info


def assign_stratum(price: PriceView, t_ms: int, abs_impulse: float) -> dict[str, Any]:
    impulse_start = int(t_ms) - THIRTY_M_MS
    hist_lo = impulse_start - HIST_MS
    taus = _five_minute_range(hist_lo, impulse_start)
    mag_refs = _abs_impulse_series(price, taus)
    vol = pre_vol_60(price, int(t_ms))
    vol_refs = _pre_vol_series(price, taus)
    p_mag = midrank_percentile(abs_impulse, mag_refs)
    p_vol = None if vol is None else midrank_percentile(vol, vol_refs)
    mag_state = tertile_state(p_mag)
    vol_state = tertile_state(p_vol)
    sid = None
    if mag_state is not None and vol_state is not None:
        sid = stratum_id(mag_state, vol_state)
    return {
        "pre_vol_60": vol,
        "impulse_mag_state": mag_state,
        "trailing_vol_state": vol_state,
        "stratum_id": sid,
        "p_mag": p_mag,
        "p_vol": p_vol,
    }


def reversal_return(price: PriceView, t_ms: int, d: int) -> float | None:
    T = int(t_ms) + THIRTY_M_MS
    outcome_end = T + SIXTY_M_MS
    outcome = log_ratio(close_at(price, outcome_end) or float("nan"), close_at(price, T) or float("nan"))
    if outcome is None:
        return None
    value = -int(d) * outcome
    if not math.isfinite(value):
        return None
    return value


def _guard_views(price: PriceView, oi: OiView) -> None:
    authenticate_frozen_prereg_bytes()
    if snapshot_is_bound(price.snapshot_id) or snapshot_is_bound(oi.snapshot_id):
        refuse_bound_execution()
    if MARKET_01_EXECUTION_AUTHORIZED or MARKET_01_ARMED:
        refuse_bound_execution()


def construct_episodes(price: PriceView, oi: OiView) -> list[EpisodeRecord]:
    _guard_views(price, oi)
    if int(price.open_time_ms[0]) % BAR_MS != 0:
        raise Market01Error("price open_time_ms is not 1m aligned")
    episodes: list[EpisodeRecord] = []
    occupied_until_impulse_start = -1
    first_end = int(price.available_at_ms[0])
    last_end = int(price.available_at_ms[-1])
    t_lo = max(first_end, COMMON_START_MS + THIRTY_M_MS)
    t_hi = min(last_end, COMMON_END_MS - NINETY_M_MS)
    for t in _five_minute_range(t_lo, t_hi + 1):
        t = int(t)
        impulse_start = t - THIRTY_M_MS
        T = t + THIRTY_M_MS
        outcome_end = T + SIXTY_M_MS
        rec = EpisodeRecord(
            impulse_end_t_ms=t,
            impulse_start_ms=impulse_start,
            decision_T_ms=T,
            outcome_end_ms=outcome_end,
        )
        if impulse_start < COMMON_START_MS or outcome_end > COMMON_END_MS:
            rec.exclusion_reason = "not_completable_inside_common_period"
            episodes.append(rec)
            continue
        if impulse_start < occupied_until_impulse_start:
            rec.exclusion_reason = "overlap_skip"
            episodes.append(rec)
            continue
        ok, info = classify_qualifying_impulse(price, t)
        rec.impulse_return = info["impulse_return"]
        rec.D = info["D"]
        rec.abs_impulse = info["abs_impulse"]
        rec.p_impulse = info["p_impulse"]
        rec.qualifying_impulse = ok
        if not ok:
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        rec.occupies_slot = True
        occupied_until_impulse_start = impulse_start + EPISODE_MS
        oi_ok, oi_info = classify_oi_expansion(oi, t)
        rec.oi_start = oi_info["oi_start"]
        rec.oi_end = oi_info["oi_end"]
        rec.delta_oi = oi_info["delta_oi"]
        rec.p_oi = oi_info["p_oi"]
        rec.oi_expansion = oi_ok
        if rec.oi_start is None or rec.oi_end is None or rec.delta_oi is None or rec.p_oi is None:
            rec.exclusion_reason = "missing_or_invalid_oi"
            episodes.append(rec)
            continue
        weak_ok, weak_info = classify_weak_continuation(
            price, t, int(rec.D), float(rec.abs_impulse)
        )
        rec.state_return = weak_info["state_return"]
        rec.continuation_ratio = weak_info["continuation_ratio"]
        rec.weak_continuation = weak_ok
        if rec.state_return is None or rec.continuation_ratio is None:
            rec.exclusion_reason = "missing_state_return"
            episodes.append(rec)
            continue
        rec.candidate = bool(
            rec.qualifying_impulse and rec.oi_expansion and rec.weak_continuation
        )
        strat = assign_stratum(price, t, float(rec.abs_impulse))
        rec.pre_vol_60 = strat["pre_vol_60"]
        rec.impulse_mag_state = strat["impulse_mag_state"]
        rec.trailing_vol_state = strat["trailing_vol_state"]
        rec.stratum_id = strat["stratum_id"]
        if rec.stratum_id is None:
            rec.exclusion_reason = "stratum_unavailable"
            episodes.append(rec)
            continue
        rev = reversal_return(price, t, int(rec.D))
        rec.reversal_return = rev
        if rev is None:
            rec.exclusion_reason = "missing_outcome"
            episodes.append(rec)
            continue
        rec.confirmatory_eligible = True
        episodes.append(rec)
    return episodes


def exclusion_counts(episodes: Sequence[EpisodeRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in episodes:
        key = rec.exclusion_reason or (
            "confirmatory_eligible" if rec.confirmatory_eligible else "unclassified"
        )
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def confirmatory_rows(episodes: Sequence[EpisodeRecord]) -> list[dict[str, Any]]:
    rows = []
    for rec in episodes:
        if not rec.confirmatory_eligible or rec.stratum_id is None:
            continue
        if rec.reversal_return is None or rec.D is None:
            continue
        rows.append(
            {
                "impulse_end_t_ms": rec.impulse_end_t_ms,
                "impulse_start_ms": rec.impulse_start_ms,
                "decision_T_ms": rec.decision_T_ms,
                "reversal_return": float(rec.reversal_return),
                "candidate_indicator": 1 if rec.candidate else 0,
                "stratum_id": rec.stratum_id,
            }
        )
    rows.sort(key=lambda r: (int(r["decision_T_ms"]), int(r["impulse_start_ms"])))
    return rows


def usable_strata(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    cand: dict[str, int] = {}
    base: dict[str, int] = {}
    for row in rows:
        sid = str(row["stratum_id"])
        if int(row["candidate_indicator"]) == 1:
            cand[sid] = cand.get(sid, 0) + 1
        else:
            base[sid] = base.get(sid, 0) + 1
    usable = [
        sid
        for sid in sorted(set(cand) | set(base))
        if cand.get(sid, 0) >= STRATUM_GROUP_MIN and base.get(sid, 0) >= STRATUM_GROUP_MIN
    ]
    return usable


def support_gate(rows: Sequence[Mapping[str, Any]], usable: Sequence[str]) -> dict[str, Any]:
    usable_set = set(usable)
    primary = [r for r in rows if str(r["stratum_id"]) in usable_set]
    n_total = len(primary)
    n_cand = sum(int(r["candidate_indicator"]) == 1 for r in primary)
    n_base = n_total - n_cand
    ok = (
        n_total >= TOTAL_MIN
        and n_cand >= CAND_MIN
        and n_base >= BASE_MIN
        and len(usable) >= USABLE_STRATA_MIN
    )
    return {
        "ok": ok,
        "TOTAL_ELIGIBLE_EPISODES": n_total,
        "CANDIDATE_EPISODES": n_cand,
        "BASELINE_EPISODES": n_base,
        "USABLE_STRATA": len(usable),
        "usable_stratum_ids": list(usable),
        "primary_rows": primary,
    }


def design_matrix(
    rows: Sequence[Mapping[str, Any]], usable: Sequence[str]
) -> tuple[np.ndarray, np.ndarray]:
    k = len(usable)
    n = len(rows)
    index = {sid: i for i, sid in enumerate(usable)}
    x = np.zeros((n, k + 1), dtype=np.float64)
    y = np.empty(n, dtype=np.float64)
    for i, row in enumerate(rows):
        x[i, index[str(row["stratum_id"])]] = 1.0
        x[i, -1] = float(row["candidate_indicator"])
        y[i] = float(row["reversal_return"])
    return x, y


def fit_stratified_ols(
    rows: Sequence[Mapping[str, Any]], usable: Sequence[str]
) -> dict[str, Any]:
    if not rows or not usable:
        return {"ok": False, "reason": "empty_design"}
    x, y = design_matrix(rows, usable)
    xtx = x.T @ x
    xty = x.T @ y
    ncols = int(x.shape[1])
    rank = int(np.linalg.matrix_rank(xtx))
    if rank < ncols:
        return {"ok": False, "reason": "rank_deficient", "rank": rank, "ncols": ncols}
    try:
        beta = np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        return {"ok": False, "reason": "solve_failed", "rank": rank, "ncols": ncols}
    if not np.all(np.isfinite(beta)):
        return {"ok": False, "reason": "nonfinite_beta", "rank": rank, "ncols": ncols}
    return {
        "ok": True,
        "beta": beta,
        "beta_candidate": float(beta[-1]),
        "rank": rank,
        "ncols": ncols,
        "X": x,
        "y": y,
        "usable": list(usable),
    }


def frisch_waugh_influence(
    rows: Sequence[Mapping[str, Any]],
    usable: Sequence[str],
    beta_hat: float,
) -> np.ndarray:
    x, y = design_matrix(rows, usable)
    s = x[:, :-1]
    cand = x[:, -1]
    x_tilde = cand.copy()
    y_tilde = y.copy()
    for j in range(s.shape[1]):
        mask = s[:, j] == 1.0
        if not np.any(mask):
            continue
        x_tilde[mask] -= float(x_tilde[mask].mean())
        y_tilde[mask] -= float(y_tilde[mask].mean())
    return x_tilde * (y_tilde - x_tilde * float(beta_hat))


def _draw_indices(n: int, p_geom: float, rng: np.random.Generator) -> np.ndarray:
    picked: list[int] = []
    while len(picked) < n:
        start = int(rng.integers(0, n))
        length = int(rng.geometric(p_geom))
        for j in range(length):
            picked.append((start + j) % n)
            if len(picked) >= n:
                break
    return np.asarray(picked[:n], dtype=np.int64)


def one_sided_p(t_star: np.ndarray, t_obs: float) -> float:
    return (1.0 + float(np.sum(t_star >= t_obs))) / (BOOTSTRAP_B + 1.0)


def run_stationary_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    usable: Sequence[str],
    beta_hat: float,
) -> dict[str, Any]:
    selector = authenticate_arch_selector()
    z = frisch_waugh_influence(rows, usable, beta_hat)
    b_hat = float(optimal_stationary_block_length(z))
    n = len(rows)
    if not math.isfinite(b_hat) or b_hat <= 0.0:
        return {"ok": False, "reason": "invalid_b_hat", "b_hat": b_hat, "selector": selector}
    clamped = min(max(b_hat, 1.0), float(n))
    p_geom = 1.0 / round(clamped)
    rng = pcg64_generator(
        namespace_seed(MARKET_01_BOOTSTRAP_SEED, "BOOTSTRAP", "PRIMARY_BETA_CANDIDATE")
    )
    beta_star = np.empty(BOOTSTRAP_B, dtype=np.float64)
    for b in range(BOOTSTRAP_B):
        idx = _draw_indices(n, p_geom, rng)
        resampled = [rows[int(i)] for i in idx]
        fit = fit_stratified_ols(resampled, usable)
        if not fit["ok"]:
            return {
                "ok": False,
                "reason": f"replicate_not_identifiable:{b}",
                "b_hat": b_hat,
                "selector": selector,
            }
        beta_star[b] = float(fit["beta_candidate"])
        if not math.isfinite(beta_star[b]):
            return {
                "ok": False,
                "reason": f"replicate_nonfinite:{b}",
                "b_hat": b_hat,
                "selector": selector,
            }
    se_hat = float(np.std(beta_star, ddof=1))
    if not math.isfinite(se_hat) or se_hat <= 0.0:
        return {"ok": False, "reason": "invalid_se_hat", "se_hat": se_hat, "selector": selector}
    t_obs = float(beta_hat) / se_hat
    t_star = (beta_star - float(beta_hat)) / se_hat
    p = one_sided_p(t_star, t_obs)
    return {
        "ok": True,
        "b_hat": b_hat,
        "p_geom": p_geom,
        "se_hat": se_hat,
        "t_obs": t_obs,
        "p_one_sided": p,
        "selector": selector,
        "B": BOOTSTRAP_B,
        "seed_material": SEED_MATERIAL,
        "seed_material_sha256": SEED_MATERIAL_SHA256,
        "MARKET_01_BOOTSTRAP_SEED": MARKET_01_BOOTSTRAP_SEED,
    }


def loeo_sign_stable(primary_rows: Sequence[Mapping[str, Any]], usable: Sequence[str]) -> dict[str, Any]:
    betas: dict[str, float | None] = {}
    stable = True
    reasons: dict[str, str] = {}
    for name, start, end in ERA_BOUNDS_MS:
        remain = [
            r for r in primary_rows if not (start <= int(r["decision_T_ms"]) < end)
        ]
        n_total = len(remain)
        n_cand = sum(int(r["candidate_indicator"]) == 1 for r in remain)
        n_base = n_total - n_cand
        failed_support = (
            n_total < TOTAL_MIN
            or n_cand < CAND_MIN
            or n_base < BASE_MIN
        )
        stratum_fail = False
        for sid in usable:
            c = sum(
                1
                for r in remain
                if str(r["stratum_id"]) == sid and int(r["candidate_indicator"]) == 1
            )
            b = sum(
                1
                for r in remain
                if str(r["stratum_id"]) == sid and int(r["candidate_indicator"]) == 0
            )
            if c < STRATUM_GROUP_MIN or b < STRATUM_GROUP_MIN:
                stratum_fail = True
                break
        if failed_support or stratum_fail:
            betas[name] = None
            stable = False
            reasons[name] = "insufficient_support"
            continue
        fit = fit_stratified_ols(remain, usable)
        if not fit["ok"]:
            betas[name] = None
            stable = False
            reasons[name] = str(fit.get("reason"))
            continue
        beta = float(fit["beta_candidate"])
        betas[name] = beta
        if not (math.isfinite(beta) and beta > 0.0):
            stable = False
            reasons[name] = "nonpositive_or_nonfinite"
    return {
        "ROBUSTNESS_SIGN_STABLE": bool(stable),
        "beta_candidate_LOEO": betas,
        "reasons": reasons,
    }


def concentration(primary_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cands = [r for r in primary_rows if int(r["candidate_indicator"]) == 1]
    n = len(cands)
    shares: dict[str, float] = {}
    if n == 0:
        return {
            "ROBUSTNESS_CONCENTRATION_OK": False,
            "candidate_share": shares,
            "max_candidate_share": None,
        }
    for name, start, end in ERA_BOUNDS_MS:
        k = sum(1 for r in cands if start <= int(r["decision_T_ms"]) < end)
        shares[name] = k / n
    max_share = max(shares.values())
    return {
        "ROBUSTNESS_CONCENTRATION_OK": bool(max_share <= 0.50),
        "candidate_share": shares,
        "max_candidate_share": max_share,
    }


def final_classification(
    *,
    identifiable: bool,
    beta_hat: float | None,
    p_one_sided: float | None,
    detected: bool,
    robustness_pass: bool | None,
) -> str:
    if not identifiable:
        return CLASS_NOT_IDENTIFIABLE
    if beta_hat is None or p_one_sided is None:
        return CLASS_NOT_IDENTIFIABLE
    if (beta_hat <= 0.0) or (p_one_sided > ALPHA):
        return CLASS_NO_EVIDENCE
    if detected and robustness_pass is False:
        return CLASS_DETECTED_NOT_ROBUST
    if detected and robustness_pass is True:
        return CLASS_ROBUST_CANDIDATE
    return CLASS_NO_EVIDENCE


def evaluate_from_confirmatory_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    authenticate: bool = True,
) -> dict[str, Any]:
    if authenticate:
        authenticate_frozen_prereg_bytes()
    usable = usable_strata(rows)
    support = support_gate(rows, usable)
    diagnostics = {
        "stratum_counts": _stratum_counts(rows),
        "non_usable_strata": [
            sid for sid in sorted({str(r["stratum_id"]) for r in rows}) if sid not in set(usable)
        ],
    }
    if not support["ok"]:
        return _result_payload(
            identifiable=False,
            support=support,
            diagnostics=diagnostics,
            fit=None,
            bootstrap=None,
            detected=False,
            robustness=None,
            classification=CLASS_NOT_IDENTIFIABLE,
        )
    fit = fit_stratified_ols(support["primary_rows"], usable)
    if not fit["ok"]:
        return _result_payload(
            identifiable=False,
            support=support,
            diagnostics=diagnostics,
            fit=fit,
            bootstrap=None,
            detected=False,
            robustness=None,
            classification=CLASS_NOT_IDENTIFIABLE,
        )
    boot = run_stationary_bootstrap(support["primary_rows"], usable, float(fit["beta_candidate"]))
    if not boot["ok"]:
        return _result_payload(
            identifiable=False,
            support=support,
            diagnostics=diagnostics,
            fit=fit,
            bootstrap=boot,
            detected=False,
            robustness=None,
            classification=CLASS_NOT_IDENTIFIABLE,
        )
    beta_hat = float(fit["beta_candidate"])
    p = float(boot["p_one_sided"])
    detected = bool(beta_hat > 0.0 and p <= ALPHA)
    robustness = None
    robustness_pass = None
    if detected:
        sign = loeo_sign_stable(support["primary_rows"], usable)
        conc = concentration(support["primary_rows"])
        robustness_pass = bool(sign["ROBUSTNESS_SIGN_STABLE"] and conc["ROBUSTNESS_CONCENTRATION_OK"])
        robustness = {**sign, **conc, "ROBUSTNESS_PASS": robustness_pass}
    classification = final_classification(
        identifiable=True,
        beta_hat=beta_hat,
        p_one_sided=p,
        detected=detected,
        robustness_pass=robustness_pass,
    )
    return _result_payload(
        identifiable=True,
        support=support,
        diagnostics=diagnostics,
        fit=fit,
        bootstrap=boot,
        detected=detected,
        robustness=robustness,
        classification=classification,
    )


def evaluate_market_01(price: PriceView, oi: OiView) -> dict[str, Any]:
    episodes = construct_episodes(price, oi)
    rows = confirmatory_rows(episodes)
    result = evaluate_from_confirmatory_rows(rows, authenticate=False)
    result["episode_diagnostics"] = {
        "n_records_seen": len(episodes),
        "n_occupying_qualifying_impulses": sum(1 for e in episodes if e.occupies_slot),
        "n_confirmatory_eligible": sum(1 for e in episodes if e.confirmatory_eligible),
        "exclusion_counts": exclusion_counts(episodes),
    }
    return result


def evaluate_bound_market_01(*_args: Any, **_kwargs: Any) -> None:
    refuse_bound_execution()


def _stratum_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        sid = str(row["stratum_id"])
        slot = out.setdefault(sid, {"candidate": 0, "baseline": 0})
        if int(row["candidate_indicator"]) == 1:
            slot["candidate"] += 1
        else:
            slot["baseline"] += 1
    return dict(sorted(out.items()))


def _strip_arrays(fit: dict[str, Any] | None) -> dict[str, Any] | None:
    if fit is None:
        return None
    return {
        k: v
        for k, v in fit.items()
        if k not in {"X", "y", "beta"}
    }


def _result_payload(
    *,
    identifiable: bool,
    support: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    fit: dict[str, Any] | None,
    bootstrap: dict[str, Any] | None,
    detected: bool,
    robustness: Mapping[str, Any] | None,
    classification: str,
) -> dict[str, Any]:
    support_public = {
        k: v for k, v in support.items() if k != "primary_rows"
    }
    payload = {
        "research_id": RESEARCH_ID,
        "status": "IMPLEMENTED_NOT_ARMED",
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "freeze_md_sha256": FROZEN_FREEZE_MD_SHA256,
        "freeze_json_sha256": FROZEN_FREEZE_JSON_SHA256,
        "implementation_commit": "UNSET_UNTIL_CANONICAL_EXECUTION",
        "implementation_tree": "UNSET_UNTIL_CANONICAL_EXECUTION",
        "price_dataset_id": PRICE_DATASET_ID,
        "price_snapshot_id": PRICE_SNAPSHOT_ID,
        "oi_snapshot_id": OI_SNAPSHOT_ID,
        "common_start_inclusive": "2020-09-01T00:00:00Z",
        "common_end_exclusive": "2025-01-01T00:00:00Z",
        "identifiable": identifiable,
        "support": support_public,
        "diagnostics": diagnostics,
        "beta_candidate": None if fit is None or not fit.get("ok") else float(fit["beta_candidate"]),
        "bootstrap": None
        if bootstrap is None
        else {k: v for k, v in bootstrap.items() if k not in {"selector"} | set()},
        "bootstrap_selector": None if bootstrap is None else bootstrap.get("selector"),
        "detected": bool(detected),
        "robustness": None if robustness is None else dict(robustness),
        "final_classification": classification,
        "MARKET_01_TEST_CALIBRATED": MARKET_01_TEST_CALIBRATED,
        "MARKET_01_ARMED": MARKET_01_ARMED,
        "MARKET_01_EXECUTION_AUTHORIZED": MARKET_01_EXECUTION_AUTHORIZED,
        "PROTECTED_OOS_AUTHORIZED": PROTECTED_OOS_AUTHORIZED,
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": B2_06_EXECUTION_AUTHORIZED,
        "DEFAULT_V4": DEFAULT_V4,
        "v3_reused_as_market_01_test": False,
        "fit_ok": False if fit is None else bool(fit.get("ok")),
        "fit_detail": _strip_arrays(fit),
    }
    if bootstrap and bootstrap.get("ok"):
        payload["se_hat"] = bootstrap["se_hat"]
        payload["p_one_sided"] = bootstrap["p_one_sided"]
        payload["b_hat"] = bootstrap["b_hat"]
        payload["t_obs"] = bootstrap["t_obs"]
    else:
        payload["se_hat"] = None
        payload["p_one_sided"] = None
        payload["b_hat"] = None
        payload["t_obs"] = None
    return payload


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def dumps_result(result: Mapping[str, Any]) -> str:
    return json.dumps(_jsonable(result), sort_keys=True, separators=(",", ":"), allow_nan=False)
