"""MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION outcome-blind implementation.

This is not MARKET-01. MARKET-01 asked whether joint OI-expansion and
weak continuation predicted later *reversal*. MARKET-02 asks, *conditional
on a qualifying impulse and OI expansion*, whether price confirmation
versus weak/non-confirmation separates later *continuation*.

PRIMARY POPULATION:
    QUALIFYING_IMPULSE AND OI_EXPANSION
WITHIN THAT POPULATION:
    candidate = continuation_ratio > 0.25
    baseline  = continuation_ratio <= 0.25
OUTCOME:
    continuation_return = D * ln(close(T+60m) / close(T))

Non-OI-expansion occupying episodes are outside the primary population.
They are not MARKET-02 baselines.

In-memory scientific pipeline only. Bound CORE/OI snapshot evaluation is
refused because MARKET-02 is not armed. Does not ARM, execute, or inspect
real MARKET-02 outcomes. Does not load CORE/OI from disk.

Construction uses MARKET-01's proven fast precompute primitives
(`_close_1m_clock`, rolling OI/PRE_VOL arrays). It does not delegate
scientific episode identity to MARKET-01 `construct_episodes` /
`EpisodeRecord`.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    namespace_seed,
    pcg64_generator,
)
from scripts.research.harness_synthetic_edge_calibration_v3_confirmatory import (
    optimal_stationary_block_length,
)
from scripts.research.market_01_episode_construction_fast import (
    _at,
    _close_1m_clock,
    _contiguous_1m,
    _legal_oi_vector,
    _log_ratio_arr,
    _logret_1m,
    _pre_vol_on_clocks,
    _slice_or_empty,
)
from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    authenticate_arch_selector,
    snapshot_is_bound,
)
from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    BAR_MS,
    COMMON_END_MS,
    COMMON_START_MS,
    EPISODE_MS,
    FIVE_MS,
    HIST_MS,
    NINETY_M_MS,
    SIXTY_M_MS,
    SYNTHETIC_SNAPSHOT,
    THIRTY_M_MS,
    OiView,
    PriceView,
    _five_minute_range,
    assign_stratum,
    classify_oi_expansion,
    classify_qualifying_impulse,
    close_at,
    log_ratio,
    midrank_percentile,
    stratum_id,
    tertile_state,
)


RESEARCH_ID = "MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION"
PREREG_MD_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json"
FROZEN_PREREG_MD_SHA256 = (
    "4f19fd27435adddf4cc7e3c5568a8e316d8865b64468cdc30a9fd3918ffc3275"
)
FROZEN_PREREG_JSON_SHA256 = (
    "ffc11ffd0f9d76ca12542ce45f466a6a7f9c651f1a030168a1617af2caa545a7"
)

REQUIRED_NUMPY = "2.1.3"

# Frozen prospective definitions (same numeric cuts as MARKET-01 impulse/OI,
# different confirmation/outcome/population identity).
IMPULSE_P_MIN = 0.90
OI_P_STRICT = 0.75
CONFIRMATION_CUT = 0.25

TOTAL_MIN = 100
CAND_MIN = 30
BASE_MIN = 30
USABLE_STRATA_MIN = 3
STRATUM_GROUP_MIN = 5

BOOTSTRAP_B = 999
ALPHA = 0.05
SEED_MATERIAL = (
    "MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999"
)
SEED_MATERIAL_SHA256 = (
    "19b71ee831e69f273338ef94e65ff4cc339eb6d8054c365fd160c7769955558f"
)
# MD scientific authority. JSON twin stores 1852983754304692000 from IEEE/JSON
# number precision loss; JSON never overrides this MD seed.
MARKET_02_BOOTSTRAP_SEED = 1852983754304692007
BOOTSTRAP_NAMESPACE = "BOOTSTRAP"
BOOTSTRAP_CONTEXT = "PRIMARY_BETA_CONFIRMATION"

CLASS_NOT_IDENTIFIABLE = "NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT"
CLASS_NO_EVIDENCE = "NO_EVIDENCE"
CLASS_ROBUST = "EVIDENCE_WITH_PROSPECTIVE_ROBUSTNESS"
CLASS_FRAGILE = "EVIDENCE_FRAGILE_NONSTATIONARITY"

MARKET_02_TEST_CALIBRATED = False
MARKET_02_ARMED = False
MARKET_02_EXECUTED = False
PROTECTED_OOS_AUTHORIZED = False
B2_06_EXECUTION_AUTHORIZED = False
DEFAULT_V4 = False
V3_REUSED_AS_MARKET_02_TEST = False

PRICE_DATASET_ID = "CORE_BTC_BINANCE_V0"
PRICE_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
OI_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"

ERA_BOUNDS_MS = (
    ("ERA_1", 1_598_918_400_000, 1_609_459_200_000),
    ("ERA_2", 1_609_459_200_000, 1_640_995_200_000),
    ("ERA_3", 1_640_995_200_000, 1_672_531_200_000),
    ("ERA_4", 1_672_531_200_000, 1_704_067_200_000),
    ("ERA_5", 1_704_067_200_000, 1_735_689_600_000),
)


class Market02Error(RuntimeError):
    """Contract or construction failure."""


class Market02NotArmed(RuntimeError):
    def __init__(self, message: str = "MARKET_02_NOT_ARMED") -> None:
        super().__init__(message)


@dataclass
class EpisodeRecord:
    """MARKET-02 episode identity. Not MARKET-01 EpisodeRecord.

    Scientific fields are confirmation / continuation, not
    weak_continuation / reversal_return.
    """

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
    primary_population: bool = False
    state_return: float | None = None
    continuation_ratio: float | None = None
    price_confirmation: bool = False
    weak_or_nonconfirmation: bool = False
    candidate: bool = False
    pre_vol_60: float | None = None
    impulse_mag_state: str | None = None
    trailing_vol_state: str | None = None
    stratum_id: str | None = None
    continuation_return: float | None = None
    confirmatory_eligible: bool = False
    exclusion_reason: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authenticate_frozen_prereg_bytes() -> None:
    """Authenticate frozen MARKET-02 prereg bytes. MD is scientific authority."""
    root = _repo_root()
    md = sha256_file(root / PREREG_MD_REL)
    js = sha256_file(root / PREREG_JSON_REL)
    if md != FROZEN_PREREG_MD_SHA256:
        raise Market02Error("MARKET_02_PREREG_MD_BYTE_IDENTITY_MISMATCH")
    if js != FROZEN_PREREG_JSON_SHA256:
        raise Market02Error("MARKET_02_PREREG_JSON_BYTE_IDENTITY_MISMATCH")


def _require_numpy_2_1_3() -> None:
    version = str(np.__version__)
    if version != REQUIRED_NUMPY:
        raise Market02Error(f"numpy_version_mismatch:{version!r}")


def _guard_views(price: PriceView, oi: OiView) -> None:
    authenticate_frozen_prereg_bytes()
    if snapshot_is_bound(price.snapshot_id) or snapshot_is_bound(oi.snapshot_id):
        raise Market02NotArmed("MARKET_02_NOT_ARMED")


def classify_price_confirmation(
    price: PriceView, t_ms: int, d: int, abs_impulse: float
) -> tuple[bool, dict[str, Any]]:
    """PRICE_CONFIRMATION iff continuation_ratio > 0.25.

    The equality boundary is WEAK_OR_NONCONFIRMATION (baseline), the exact
    complement of MARKET-01 WEAK_CONTINUATION <= 0.25.
    """
    T = int(t_ms) + THIRTY_M_MS
    state_ret = log_ratio(
        close_at(price, T) or float("nan"), close_at(price, t_ms) or float("nan")
    )
    info: dict[str, Any] = {
        "state_return": state_ret,
        "continuation_ratio": None,
        "price_confirmation": False,
        "weak_or_nonconfirmation": False,
    }
    if state_ret is None or abs_impulse == 0.0 or not math.isfinite(abs_impulse):
        return False, info
    ratio = (int(d) * state_ret) / abs_impulse
    info["continuation_ratio"] = ratio
    if not math.isfinite(ratio):
        return False, info
    confirmed = bool(ratio > CONFIRMATION_CUT)
    info["price_confirmation"] = confirmed
    info["weak_or_nonconfirmation"] = bool(ratio <= CONFIRMATION_CUT)
    return confirmed, info


def continuation_return(price: PriceView, t_ms: int, d: int) -> float | None:
    """D * ln(close(T+60m)/close(T)). Not MARKET-01's -D reversal sign."""
    T = int(t_ms) + THIRTY_M_MS
    outcome_end = T + SIXTY_M_MS
    outcome = log_ratio(
        close_at(price, outcome_end) or float("nan"),
        close_at(price, T) or float("nan"),
    )
    if outcome is None:
        return None
    value = int(d) * outcome
    if not math.isfinite(value):
        return None
    return value


def _apply_confirmation(
    rec: EpisodeRecord, price: PriceView
) -> str | None:
    confirmed, info = classify_price_confirmation(
        price, rec.impulse_end_t_ms, int(rec.D), float(rec.abs_impulse)
    )
    rec.state_return = info["state_return"]
    rec.continuation_ratio = info["continuation_ratio"]
    rec.price_confirmation = bool(info["price_confirmation"])
    rec.weak_or_nonconfirmation = bool(info["weak_or_nonconfirmation"])
    if rec.state_return is None or rec.continuation_ratio is None:
        return "missing_state_return"
    rec.candidate = bool(
        rec.qualifying_impulse and rec.oi_expansion and confirmed
    )
    return None


def _apply_stratum(rec: EpisodeRecord, price: PriceView) -> str | None:
    strat = assign_stratum(price, rec.impulse_end_t_ms, float(rec.abs_impulse))
    rec.pre_vol_60 = strat["pre_vol_60"]
    rec.impulse_mag_state = strat["impulse_mag_state"]
    rec.trailing_vol_state = strat["trailing_vol_state"]
    rec.stratum_id = strat["stratum_id"]
    if rec.stratum_id is None:
        return "stratum_unavailable"
    return None


def _apply_outcome(rec: EpisodeRecord, price: PriceView) -> str | None:
    cont = continuation_return(price, rec.impulse_end_t_ms, int(rec.D))
    rec.continuation_return = cont
    if cont is None:
        return "missing_outcome"
    rec.confirmatory_eligible = True
    return None


def _construct_episodes_scalar(price: PriceView, oi: OiView) -> list[EpisodeRecord]:
    """Correctness fallback when 1m bars are not a contiguous grid.

    MARKET-02 semantics only. Does not call MARKET-01 construct_episodes.
    """
    if int(price.open_time_ms[0]) % BAR_MS != 0:
        raise Market02Error("price open_time_ms is not 1m aligned")
    episodes: list[EpisodeRecord] = []
    occupied_until_impulse_start = -1
    first_end = int(price.available_at_ms[0])
    last_end = int(price.available_at_ms[-1])
    t_lo = max(first_end, COMMON_START_MS + THIRTY_M_MS)
    t_hi = min(last_end, COMMON_END_MS - NINETY_M_MS)
    for t in _five_minute_range(t_lo, t_hi + 1):
        t = int(t)
        rec = _new_record(t)
        reason = _occupancy_gate(rec, occupied_until_impulse_start)
        if reason is not None:
            rec.exclusion_reason = reason
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
        occupied_until_impulse_start = rec.impulse_start_ms + EPISODE_MS
        oi_ok, oi_info = classify_oi_expansion(oi, t)
        rec.oi_start = oi_info["oi_start"]
        rec.oi_end = oi_info["oi_end"]
        rec.delta_oi = oi_info["delta_oi"]
        rec.p_oi = oi_info["p_oi"]
        rec.oi_expansion = oi_ok
        if (
            rec.oi_start is None
            or rec.oi_end is None
            or rec.delta_oi is None
            or rec.p_oi is None
        ):
            rec.exclusion_reason = "missing_or_invalid_oi"
            episodes.append(rec)
            continue
        if not rec.oi_expansion:
            rec.exclusion_reason = "not_oi_expansion"
            episodes.append(rec)
            continue
        rec.primary_population = True
        reason = _apply_confirmation(rec, price)
        if reason is not None:
            rec.exclusion_reason = reason
            episodes.append(rec)
            continue
        reason = _apply_stratum(rec, price)
        if reason is not None:
            rec.exclusion_reason = reason
            episodes.append(rec)
            continue
        reason = _apply_outcome(rec, price)
        if reason is not None:
            rec.exclusion_reason = reason
            episodes.append(rec)
            continue
        episodes.append(rec)
    return episodes


def _new_record(t: int) -> EpisodeRecord:
    impulse_start = t - THIRTY_M_MS
    T = t + THIRTY_M_MS
    outcome_end = T + SIXTY_M_MS
    return EpisodeRecord(
        impulse_end_t_ms=t,
        impulse_start_ms=impulse_start,
        decision_T_ms=T,
        outcome_end_ms=outcome_end,
    )


def _occupancy_gate(rec: EpisodeRecord, occupied_until_impulse_start: int) -> str | None:
    if rec.impulse_start_ms < COMMON_START_MS or rec.outcome_end_ms > COMMON_END_MS:
        return "not_completable_inside_common_period"
    if rec.impulse_start_ms < occupied_until_impulse_start:
        return "overlap_skip"
    return None


def _construct_episodes_precomputed(price: PriceView, oi: OiView) -> list[EpisodeRecord]:
    """Fast MARKET-02 construction via precomputed rolling arrays."""
    first_end = int(price.available_at_ms[0])
    last_end = int(price.available_at_ms[-1])
    t_lo = max(first_end, COMMON_START_MS + THIRTY_M_MS)
    t_hi = min(last_end, COMMON_END_MS - NINETY_M_MS)
    eval_ts = _five_minute_range(t_lo, t_hi + 1)
    if eval_ts.size == 0:
        return []

    hist_need = int(eval_ts[0]) - THIRTY_M_MS - HIST_MS
    series_lo = min(first_end, hist_need)
    series_hi = int(eval_ts[-1]) + THIRTY_M_MS + SIXTY_M_MS
    clocks5 = _five_minute_range(series_lo, series_hi + 1)
    if clocks5.size == 0:
        return _construct_episodes_scalar(price, oi)
    grid0 = int(clocks5[0])
    n5 = int(clocks5.shape[0])

    def idx5(clock: int) -> int:
        return (int(clock) - grid0) // FIVE_MS

    close5 = _close_1m_clock(price, clocks5)
    close5_lag = _close_1m_clock(price, clocks5 - THIRTY_M_MS)
    signed_imp = _log_ratio_arr(close5, close5_lag)
    abs_imp = np.abs(signed_imp)

    oi5 = _legal_oi_vector(oi, clocks5)
    oi5_lag = _legal_oi_vector(oi, clocks5 - THIRTY_M_MS)
    delta_oi = _log_ratio_arr(oi5, oi5_lag)

    logret = _logret_1m(price)
    vol5 = _pre_vol_on_clocks(price, clocks5, logret)

    episodes: list[EpisodeRecord] = []
    occupied_until_impulse_start = -1
    for t in eval_ts:
        t = int(t)
        rec = _new_record(t)
        reason = _occupancy_gate(rec, occupied_until_impulse_start)
        if reason is not None:
            rec.exclusion_reason = reason
            episodes.append(rec)
            continue
        i_t = idx5(t)
        if i_t < 0 or i_t >= n5:
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        ret_raw = signed_imp[i_t]
        if not math.isfinite(float(ret_raw)):
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        ret = float(ret_raw)
        if ret == 0.0:
            rec.impulse_return = 0.0
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        d = 1 if ret > 0.0 else -1
        abs_i = abs(ret)
        i_imp_start = idx5(rec.impulse_start_ms)
        i_imp_hist_lo = idx5(rec.impulse_start_ms - HIST_MS)
        mag_refs = _slice_or_empty(abs_imp, i_imp_hist_lo, i_imp_start)
        p_imp = midrank_percentile(abs_i, mag_refs)
        rec.impulse_return = ret
        rec.D = d
        rec.abs_impulse = abs_i
        rec.p_impulse = p_imp
        rec.qualifying_impulse = bool(p_imp is not None and p_imp >= IMPULSE_P_MIN)
        if not rec.qualifying_impulse:
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        rec.occupies_slot = True
        occupied_until_impulse_start = rec.impulse_start_ms + EPISODE_MS

        i_state = i_t
        i_T = idx5(rec.decision_T_ms)
        oi_start_raw = _at(oi5, i_state)
        oi_end_raw = _at(oi5, i_T)
        oi_start = oi_start_raw if math.isfinite(oi_start_raw) else None
        oi_end = oi_end_raw if math.isfinite(oi_end_raw) else None
        rec.oi_start = oi_start
        rec.oi_end = oi_end
        delta = None
        if oi_start is not None and oi_end is not None:
            delta = log_ratio(oi_end, oi_start)
        rec.delta_oi = delta
        p_oi = None
        if delta is not None:
            i_oi_hist_lo = idx5(t - HIST_MS)
            d_refs = _slice_or_empty(delta_oi, i_oi_hist_lo, i_state)
            p_oi = midrank_percentile(float(delta), d_refs)
        rec.p_oi = p_oi
        rec.oi_expansion = bool(p_oi is not None and p_oi > OI_P_STRICT)
        if rec.oi_start is None or rec.oi_end is None or rec.delta_oi is None or rec.p_oi is None:
            rec.exclusion_reason = "missing_or_invalid_oi"
            episodes.append(rec)
            continue
        if not rec.oi_expansion:
            rec.exclusion_reason = "not_oi_expansion"
            episodes.append(rec)
            continue
        rec.primary_population = True

        close_T = _at(close5, i_T)
        close_t = _at(close5, i_t)
        state_ret = log_ratio(
            close_T if math.isfinite(close_T) else float("nan"),
            close_t if math.isfinite(close_t) else float("nan"),
        )
        rec.state_return = state_ret
        if state_ret is None or abs_i == 0.0 or not math.isfinite(abs_i):
            rec.exclusion_reason = "missing_state_return"
            episodes.append(rec)
            continue
        ratio = (d * state_ret) / abs_i
        rec.continuation_ratio = ratio
        if not math.isfinite(ratio):
            rec.exclusion_reason = "missing_state_return"
            episodes.append(rec)
            continue
        rec.price_confirmation = bool(ratio > CONFIRMATION_CUT)
        rec.weak_or_nonconfirmation = bool(ratio <= CONFIRMATION_CUT)
        rec.candidate = bool(
            rec.qualifying_impulse and rec.oi_expansion and rec.price_confirmation
        )

        vol_raw = _at(vol5, i_t)
        vol = vol_raw if math.isfinite(vol_raw) else None
        rec.pre_vol_60 = vol
        p_mag = midrank_percentile(abs_i, mag_refs)
        vol_refs = _slice_or_empty(vol5, i_imp_hist_lo, i_imp_start)
        p_vol = None if vol is None else midrank_percentile(vol, vol_refs)
        mag_state = tertile_state(p_mag)
        vol_state = tertile_state(p_vol)
        sid = None
        if mag_state is not None and vol_state is not None:
            sid = stratum_id(mag_state, vol_state)
        rec.impulse_mag_state = mag_state
        rec.trailing_vol_state = vol_state
        rec.stratum_id = sid
        if rec.stratum_id is None:
            rec.exclusion_reason = "stratum_unavailable"
            episodes.append(rec)
            continue

        i_out = idx5(rec.outcome_end_ms)
        close_out = _at(close5, i_out)
        outcome = log_ratio(
            close_out if math.isfinite(close_out) else float("nan"),
            close_T if math.isfinite(close_T) else float("nan"),
        )
        if outcome is None:
            rec.exclusion_reason = "missing_outcome"
            episodes.append(rec)
            continue
        cont = int(d) * outcome
        if not math.isfinite(cont):
            rec.exclusion_reason = "missing_outcome"
            episodes.append(rec)
            continue
        rec.continuation_return = cont
        rec.confirmatory_eligible = True
        episodes.append(rec)
    return episodes


def construct_episodes(price: PriceView, oi: OiView) -> list[EpisodeRecord]:
    """MARKET-02 episode construction. Fast precompute when 1m is contiguous."""
    _guard_views(price, oi)
    if int(price.open_time_ms[0]) % BAR_MS != 0:
        raise Market02Error("price open_time_ms is not 1m aligned")
    if _contiguous_1m(price):
        return _construct_episodes_precomputed(price, oi)
    return _construct_episodes_scalar(price, oi)


def exclusion_counts(episodes: Sequence[EpisodeRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in episodes:
        key = rec.exclusion_reason or (
            "confirmatory_eligible" if rec.confirmatory_eligible else "unclassified"
        )
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def confirmatory_rows(episodes: Sequence[EpisodeRecord]) -> list[dict[str, Any]]:
    """Primary-population rows only (QUALIFYING_IMPULSE AND OI_EXPANSION)."""
    rows = []
    for rec in episodes:
        if not rec.confirmatory_eligible or rec.stratum_id is None:
            continue
        if not rec.primary_population or not rec.oi_expansion:
            continue
        if rec.continuation_return is None or rec.D is None:
            continue
        rows.append(
            {
                "impulse_end_t_ms": rec.impulse_end_t_ms,
                "impulse_start_ms": rec.impulse_start_ms,
                "decision_T_ms": rec.decision_T_ms,
                "continuation_return": float(rec.continuation_return),
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
    usable_lex = list(usable)
    k = len(usable_lex)
    n = len(rows)
    index = {sid: i for i, sid in enumerate(usable_lex)}
    x = np.zeros((n, k + 1), dtype=np.float64)
    y = np.empty(n, dtype=np.float64)
    for i, row in enumerate(rows):
        x[i, index[str(row["stratum_id"])]] = 1.0
        x[i, -1] = float(row["candidate_indicator"])
        y[i] = float(row["continuation_return"])
    return x, y


def fit_stratified_ols(
    rows: Sequence[Mapping[str, Any]], usable: Sequence[str]
) -> dict[str, Any]:
    _require_numpy_2_1_3()
    if not rows or not usable:
        return {"ok": False, "reason": "empty_design"}
    x, y = design_matrix(rows, usable)
    xtx = x.T @ x
    xty = x.T @ y
    ncols = int(x.shape[1])
    rank = int(np.linalg.matrix_rank(xtx))
    if rank != ncols:
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
        "beta_confirmation": float(beta[-1]),
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
        namespace_seed(MARKET_02_BOOTSTRAP_SEED, BOOTSTRAP_NAMESPACE, BOOTSTRAP_CONTEXT)
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
        beta_star[b] = float(fit["beta_confirmation"])
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
        "MARKET_02_BOOTSTRAP_SEED": MARKET_02_BOOTSTRAP_SEED,
        "namespace": [BOOTSTRAP_NAMESPACE, BOOTSTRAP_CONTEXT],
    }


def loeo_sign_stable(primary_rows: Sequence[Mapping[str, Any]], usable: Sequence[str]) -> dict[str, Any]:
    """Leave-one-era-out. Primary usable-stratum columns stay fixed."""
    betas: dict[str, float | None] = {}
    stable = True
    reasons: dict[str, str] = {}
    fixed_usable = list(usable)
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
        for sid in fixed_usable:
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
        fit = fit_stratified_ols(remain, fixed_usable)
        if not fit["ok"]:
            betas[name] = None
            stable = False
            reasons[name] = str(fit.get("reason"))
            continue
        beta = float(fit["beta_confirmation"])
        betas[name] = beta
        if not (math.isfinite(beta) and beta > 0.0):
            stable = False
            reasons[name] = "nonpositive_or_nonfinite"
    return {
        "ROBUSTNESS_SIGN_STABLE": bool(stable),
        "beta_confirmation_LOEO": betas,
        "usable_stratum_ids_fixed": list(fixed_usable),
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


def detected_rule(beta_hat: float, p_one_sided: float) -> bool:
    return bool(beta_hat > 0.0 and p_one_sided <= ALPHA)


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
    if not detected:
        return CLASS_NO_EVIDENCE
    if robustness_pass is True:
        return CLASS_ROBUST
    if robustness_pass is False:
        return CLASS_FRAGILE
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
        "primary_population": "QUALIFYING_IMPULSE AND OI_EXPANSION",
        "candidate_rule": "continuation_ratio > 0.25",
        "baseline_rule": "continuation_ratio <= 0.25",
        "outcome": "continuation_return = D * ln(close(T+60m)/close(T))",
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
    boot = run_stationary_bootstrap(
        support["primary_rows"], usable, float(fit["beta_confirmation"])
    )
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
    beta_hat = float(fit["beta_confirmation"])
    p = float(boot["p_one_sided"])
    detected = detected_rule(beta_hat, p)
    robustness = None
    robustness_pass = None
    if detected:
        sign = loeo_sign_stable(support["primary_rows"], usable)
        conc = concentration(support["primary_rows"])
        robustness_pass = bool(
            sign["ROBUSTNESS_SIGN_STABLE"] and conc["ROBUSTNESS_CONCENTRATION_OK"]
        )
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


def evaluate_market_02(price: PriceView, oi: OiView) -> dict[str, Any]:
    episodes = construct_episodes(price, oi)
    rows = confirmatory_rows(episodes)
    result = evaluate_from_confirmatory_rows(rows, authenticate=False)
    result["episode_diagnostics"] = {
        "n_records_seen": len(episodes),
        "n_occupying_qualifying_impulses": sum(1 for e in episodes if e.occupies_slot),
        "n_primary_population": sum(1 for e in episodes if e.primary_population),
        "n_confirmatory_eligible": sum(1 for e in episodes if e.confirmatory_eligible),
        "exclusion_counts": exclusion_counts(episodes),
    }
    return result


def evaluate_bound_market_02(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Bound CORE/OI evaluation is refused: MARKET-02 is not armed."""
    raise Market02NotArmed("MARKET_02_NOT_ARMED")


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
    return {k: v for k, v in fit.items() if k not in {"X", "y", "beta"}}


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
    support_public = {k: v for k, v in support.items() if k != "primary_rows"}
    payload = {
        "research_id": RESEARCH_ID,
        "status": "IMPLEMENTED_NOT_ARMED",
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "implementation_frozen": False,
        "armed": False,
        "executed": False,
        "price_dataset_id": PRICE_DATASET_ID,
        "price_snapshot_id": PRICE_SNAPSHOT_ID,
        "oi_snapshot_id": OI_SNAPSHOT_ID,
        "common_start_inclusive": "2020-09-01T00:00:00Z",
        "common_end_exclusive": "2025-01-01T00:00:00Z",
        "identifiable": identifiable,
        "support": support_public,
        "diagnostics": diagnostics,
        "beta_confirmation": None
        if fit is None or not fit.get("ok")
        else float(fit["beta_confirmation"]),
        "bootstrap": None if bootstrap is None else dict(bootstrap),
        "detected": bool(detected),
        "robustness": None if robustness is None else dict(robustness),
        "final_classification": classification,
        "MARKET_02_TEST_CALIBRATED": MARKET_02_TEST_CALIBRATED,
        "MARKET_02_ARMED": MARKET_02_ARMED,
        "MARKET_02_EXECUTED": MARKET_02_EXECUTED,
        "PROTECTED_OOS_AUTHORIZED": PROTECTED_OOS_AUTHORIZED,
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": B2_06_EXECUTION_AUTHORIZED,
        "DEFAULT_V4": DEFAULT_V4,
        "v3_reused_as_market_02_test": V3_REUSED_AS_MARKET_02_TEST,
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
