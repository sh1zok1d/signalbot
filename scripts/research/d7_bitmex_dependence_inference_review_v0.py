"""D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.

Outcome-blind confirmation-inference design. Synthetic targets only.
Does not construct NEXT_HOUR_HIGH_IMPACT_STATE on real BitMEX rows,
does not pair D7 states, and does not assign a replication class.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.d7_bitmex_support_and_power_v0 import (
    BINANCE_DELTA_D7,
    BINANCE_MU_D7_CONTROL,
    BINANCE_MU_D7_RULE,
    HOUR_MS,
    canonical_json,
    wilson_score_interval,
)
from scripts.research.discovery_sprint_02_impl import (
    D7_PRACTICAL_GATE,
    D7_TEMPORAL_YEARS_REQUIRED,
    MIN_D7_STATE_PER_YEAR,
    N_RV_BUCKETS,
    PERCENTILE_METHOD,
    RV_CUTS,
    TRAILING_WINDOW,
    percentile,
)

UNIT = "D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0"

# Reviewed calibration seed. The amendment does not reuse it.
REVIEWED_CALIBRATION_SEED = 20260930181
# Frozen before the amendment rerun. Not chosen from amendment outputs.
AMENDMENT_MASTER_SEED = 20260930211
MASTER_SEED = AMENDMENT_MASTER_SEED
ALPHA = 0.05
# 20% relative inflation above nominal alpha, fixed before the rerun.
# 1.2 * 0.05 = 0.06. Stored as the decimal ceiling, not a post-hoc fit.
TYPE_I_RELATIVE_INFLATION = 0.20
TYPE_I_CEILING = 0.06
WILSON_CONFIDENCE_LEVEL = 0.95
Z_ONESIDED_95 = 1.6448536269514722
N_OUTER = 5000
N_BOOT_OUTER = 5000
N_BOOT_INNER = 399
GENERATION_CHUNK = 500
PRACTICAL_THRESHOLD = float(D7_PRACTICAL_GATE)
# Binance discovery required 3 of 5. The BitMEX confirmation amendment
# uses a separate count: 2 of the 3 full years.
TEMPORAL_POSITIVE_YEARS_REQUIRED = 2
DESIGN_YEARS = (2016, 2017, 2018, 2019)
TEMPORAL_GATE_YEARS = (2017, 2018, 2019)
DIAGNOSTIC_YEAR = 2016
PARTIAL_YEAR_TREATMENT = "DIAGNOSTIC_ONLY_EXCLUDED_FROM_GATE"
# Same floor the frozen discovery gate uses for a year of D7 states.
# Applied to each arm of an RV x qrel cell. Not fit to BitMEX cell counts.
MIN_CELL_ARM = int(MIN_D7_STATE_PER_YEAR)
QREL_FINE_BINS = (0, 1, 2, 3)
QREL_COARSE_GROUPS = ((0, 1), (2, 3))

# Bandwidths are valid-hour steps. 721 covers the score overlap of the
# 720-hour window plus the one-hour target shift. 720 is one step short
# and is sensitivity only; it cannot be selected as primary.
NW_LAG_PRIMARY = 721
NW_LAG_SENSITIVITY = 720
BLOCK_LENGTH = 1440
MIN_EFFECTIVE_BLOCKS = 20

# Latent-Markov parameters. Not estimated from BitMEX targets.
PHI_MODERATE = 0.50
PHI_STRONG = 0.90
REGIME_MEAN_HOURS = 720
REGIME_P_LOW = 0.02
REGIME_P_HIGH = 2.0 * BINANCE_MU_D7_CONTROL - REGIME_P_LOW
YEAR_BASE_RATE = {2016: 0.06, 2017: 0.11, 2018: 0.14, 2019: 0.07}

# Type-I rule, frozen before the amendment rerun.
# Nominal alpha is 0.05. The tolerance is 20% relative inflation, so the
# ceiling is 0.06. A regime passes only when the Wilson 95% upper bound
# is at most that ceiling. The ceiling is not taken from a previous
# synthetic rejection rate.
TYPE_I_RULE = (
    "For every predeclared null regime, the Wilson 95% upper bound of the "
    "one-sided rejection rate must be <= 0.06. "
    "TYPE_I_CEILING = 1.2 * alpha, with alpha = 0.05. "
    "The point estimate and the Wilson lower bound are not the rule."
)

# Power rule is a new confirmation-design choice. The old IID power is not the bar.
BASE_POWER_REGIME = "NULL_1_MARKOV_MODERATE"
STRESS_POWER_REGIMES = (
    "NULL_2_MARKOV_STRONG",
    "NULL_3_LATENT_30D",
    "NULL_4_YEAR_HETERO",
)
BASE_POWER_MIN = 0.80
STRESS_POWER_MIN = 0.50
POWER_RULE = (
    "NEW_CONFIRMATION_DESIGN_CHOICE: joint confirmation power "
    "(statistical AND practical AND temporal) at the full frozen delta "
    "has point estimate >= 0.80 under NULL_1_MARKOV_MODERATE, and "
    "point estimate >= 0.50 under each of NULL_2_MARKOV_STRONG, "
    "NULL_3_LATENT_30D, and NULL_4_YEAR_HETERO. "
    "IID power is reported and is not the acceptance bar. "
    "75% and 50% effects are reported and are not substituted for the full-effect bar."
)

METHOD_NW = "EXACT_DELTA_NW_BARTLETT_LAG_721"
METHOD_NW_SHORT = "EXACT_DELTA_NW_BARTLETT_LAG_720"
METHOD_BOOT = "EXACT_DELTA_NONOVERLAPPING_BLOCK_BOOTSTRAP"
METHOD_SHIFT = "CIRCULAR_SHIFT"
PRIMARY_RANK = (METHOD_NW, METHOD_BOOT)
SELECTABLE_PRIMARY = frozenset(PRIMARY_RANK)
# Fixed after the completed outcome-blind calibration. Confirmation may
# not walk PRIMARY_RANK again.
FROZEN_CONFIRMATION_METHOD = METHOD_NW

NULL_REGIMES = (
    "NULL_0_IID",
    "NULL_1_MARKOV_MODERATE",
    "NULL_2_MARKOV_STRONG",
    "NULL_3_LATENT_30D",
    "NULL_4_YEAR_HETERO",
)
EFFECT_FRACTIONS = (1.0, 0.75, 0.5)


class DesignError(RuntimeError):
    pass


def norm_cdf(x: np.ndarray) -> np.ndarray:
    """Standard normal CDF via the Abramowitz-Stegun erf approximation."""

    arr = np.asarray(x, dtype=np.float64)
    sign = np.sign(arr)
    ax = np.abs(arr) / math.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * ax)
    poly = (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
    erf = sign * (1.0 - poly * np.exp(-ax * ax))
    erf = np.where(arr == 0.0, 0.0, erf)
    return 0.5 * (1.0 + erf)


def contrast_scale(candidate_n: Sequence[int], eligible_n: Sequence[int]) -> float:
    """c such that a common within-stratum mean gap d produces delta = c * d."""

    k_total = int(sum(int(k) for k in candidate_n))
    if k_total <= 0:
        raise DesignError("NO_CANDIDATES")
    scale = 0.0
    for k_raw, n_raw in zip(candidate_n, eligible_n):
        k = int(k_raw)
        n = int(n_raw)
        if k == 0:
            continue
        if n < k:
            raise DesignError("STRATUM_SHAPE")
        scale += (k / float(k_total)) * (1.0 - k / float(n))
    return float(scale)


def stratum_weights(k: int, n: int, k_total: int) -> tuple[float, float]:
    """Weights on a candidate hour and a non-candidate eligible hour."""

    if k_total <= 0 or n <= 0 or k > n:
        raise DesignError("WEIGHT_SHAPE")
    pi = k / float(n) if k else 0.0
    if k == 0:
        return 0.0, 0.0
    return (1.0 - pi) / float(k_total), -pi / float(k_total)


def delta_from_means(
    candidate_n: Sequence[int],
    mean_candidate: Sequence[float],
    mean_pool: Sequence[float],
) -> float:
    k_total = float(sum(int(k) for k in candidate_n))
    if k_total <= 0:
        raise DesignError("NO_CANDIDATES")
    acc = 0.0
    for k_raw, mu_c, mu_p in zip(candidate_n, mean_candidate, mean_pool):
        k = int(k_raw)
        if k == 0:
            continue
        acc += (k / k_total) * (float(mu_c) - float(mu_p))
    return float(acc)


def sum_autocovariance(v: np.ndarray, max_lag: int) -> np.ndarray:
    """Linear sum products gamma[h] = sum_t v_t v_{t+h}.

    v is (n,) or (r, n). Circular wrap is padded out.
    """

    single = v.ndim == 1
    if single:
        v = v[None, :]
    _r, n = v.shape
    nfft = int(n + max_lag)
    spec = np.fft.rfft(v, n=nfft, axis=1)
    ac = np.fft.irfft(spec * np.conjugate(spec), n=nfft, axis=1)[:, : max_lag + 1]
    out = np.real(ac)
    return out[0] if single else out


def bartlett_lrv(gamma: np.ndarray, lag: int) -> np.ndarray:
    """gamma[..., h] are sum-autocovariances. Returns LRV of the sum."""

    if gamma.shape[-1] < lag + 1:
        raise DesignError("GAMMA_SHORT")
    h = np.arange(lag + 1, dtype=np.float64)
    kern = np.ones(lag + 1, dtype=np.float64)
    kern[1:] = 1.0 - h[1:] / float(lag + 1)
    lrv = kern[0] * gamma[..., 0] + 2.0 * np.sum(kern[1:] * gamma[..., 1 : lag + 1], axis=-1)
    return lrv


def nw_reject(delta: np.ndarray, lrv: np.ndarray) -> np.ndarray:
    se = np.sqrt(np.maximum(lrv, 0.0))
    stat = np.zeros(delta.shape, dtype=bool)
    ok = lrv > 0.0
    stat[ok] = (delta[ok] / se[ok]) > Z_ONESIDED_95
    return stat


def wilson_upper_accepts(rejections: int, n: int) -> bool:
    """Accept only when the Wilson 95% upper bound is within the ceiling."""

    _lo, hi = wilson_score_interval(int(rejections), int(n))
    return bool(hi <= TYPE_I_CEILING)


def type_i_passes(by_regime: Mapping[str, Mapping[str, Any]]) -> bool:
    if set(by_regime) != set(NULL_REGIMES):
        raise DesignError("TYPE_I_REGIME_SET")
    return all(bool(by_regime[name]["accepted"]) for name in NULL_REGIMES)


def choose_primary_method(type_i_by_method: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Return NW721 when it passes the amended type-I rule. Nothing else.

    The block bootstrap, lag 720, and circular shift are not selectable.
    Power is not an input.
    """

    block = type_i_by_method.get(METHOD_NW)
    if block is None or block.get("support_eligible") is False:
        return None
    if type_i_passes(block["regimes"]):
        return METHOD_NW
    return None


def temporal_gate_passes(year_positive: Mapping[int, bool]) -> bool:
    """2 of 3 full years. 2016 is ignored even if the caller passes it."""

    count = 0
    for year in TEMPORAL_GATE_YEARS:
        if year not in year_positive:
            raise DesignError(f"TEMPORAL_YEAR_MISSING:{year}")
        count += int(bool(year_positive[year]))
    return count >= TEMPORAL_POSITIVE_YEARS_REQUIRED


def classify_inference_sensitivity(primary_pass: bool, bootstrap_pass: bool) -> dict[str, Any]:
    """Bootstrap disagreement flags sensitivity and does not flip the primary call."""

    primary = "PASS" if bool(primary_pass) else "FAIL"
    bootstrap = "PASS" if bool(bootstrap_pass) else "FAIL"
    return {
        "PRIMARY_INFERENCE_RESULT": primary,
        "BLOCK_BOOTSTRAP_SENSITIVITY_RESULT": bootstrap,
        "INFERENCE_SENSITIVE": bool(primary_pass) != bool(bootstrap_pass),
        "PRIMARY_DECISION": primary,
    }


def joint_power_passes(power_by_regime: Mapping[str, Mapping[str, float]]) -> bool:
    base = float(power_by_regime[BASE_POWER_REGIME]["joint_full"])
    if base < BASE_POWER_MIN:
        return False
    for name in STRESS_POWER_REGIMES:
        if float(power_by_regime[name]["joint_full"]) < STRESS_POWER_MIN:
            return False
    return True


def feasibility_decision(*, primary: str | None, power_ok: bool, any_support_eligible: bool) -> str:
    if not any_support_eligible:
        return "INFERENCE_SUPPORT_INSUFFICIENT"
    if primary is None:
        return "NO_VALID_EQUIVALENT_INFERENCE_DESIGN"
    if not power_ok:
        return "DEPENDENCE_ROBUST_POWER_INSUFFICIENT"
    return "DEPENDENCE_VALID_DESIGN_READY_FOR_PREREG"


def confirmation_estimator(requested: str | None = None) -> str:
    """The only estimator a later confirmation unit may apply."""

    if requested not in (None, FROZEN_CONFIRMATION_METHOD):
        raise DesignError("ALTERNATE_PRIMARY_NOT_SELECTABLE")
    return FROZEN_CONFIRMATION_METHOD


def final_pass_rule_text() -> dict[str, str]:
    method = confirmation_estimator()
    return {
        "STATISTICAL_GATE": (
            "One-sided level 0.05 test of H0: delta <= 0 on the exact frozen "
            f"pool-adjusted contrast, using {method} only. Bartlett kernel, "
            "fixed lag 721 valid hours, normal critical value "
            f"{Z_ONESIDED_95}. Reject only when the long-run variance is "
            "positive and delta_hat / se exceeds that critical value. "
            "Lag 720, the block bootstrap, and circular shift are not "
            "selectable at confirmation."
        ),
        "PRACTICAL_GATE": "delta_hat >= 0.05",
        "TEMPORAL_GATE": (
            "PASS if year-level delta_hat > 0 in at least 2 of the 3 full "
            "calendar years 2017, 2018, and 2019. 2016 is diagnostic only "
            "and does not enter the numerator or the denominator. A full "
            "year with no candidates would not count as positive."
        ),
        "INTEGRITY_GATE": (
            "Canonical D7_BITMEX_ACTIVITY_V0 gzip hash, frozen selector digest, "
            "and unchanged D2 gzip all match the support-unit pin; no Binance "
            "2025/2026 input is read; the estimator uses only the predeclared "
            "weights, Bartlett kernel, and lag 721."
        ),
        "D7_BITMEX_REPLICATION_SUPPORTED_IFF": (
            "STATISTICAL_GATE AND PRACTICAL_GATE AND TEMPORAL_GATE AND "
            "INTEGRITY_GATE. This unit does not evaluate that conjunction "
            "on real BitMEX targets."
        ),
    }


@dataclass
class Stratum:
    year: int
    bucket: int
    cand_idx: np.ndarray
    pool_idx: np.ndarray

    @property
    def k(self) -> int:
        return int(self.cand_idx.size)

    @property
    def n(self) -> int:
        return int(self.pool_idx.size)


@dataclass
class Segment:
    start: int
    stop: int
    slots: list[tuple[int, int]]


@dataclass
class PredictorDesign:
    """Predictor geometry only. No target values."""

    year: np.ndarray
    in_contrast: np.ndarray
    candidate: np.ndarray
    weights: np.ndarray
    strata: list[Stratum]
    segments: list[Segment]
    gap_breaks: tuple[int, ...]
    k_total: int
    scale_c: float
    k_year: dict[int, int]
    effective_blocks: int


def build_predictor_design(
    hour_start_ms: np.ndarray,
    year: np.ndarray,
    rv_bucket: np.ndarray,
    state_at_t: Sequence[bool | None],
    state_defined: np.ndarray,
) -> PredictorDesign:
    """Build weights from D7_STATE_t only. Does not read a t+1 boolean."""

    from scripts.research.d7_bitmex_support_and_power_v0 import structural_target_eligible

    n = int(hour_start_ms.size)
    if len(state_at_t) != n:
        raise DesignError("STATE_LENGTH")
    eligible = structural_target_eligible(hour_start_ms, state_defined)
    in_contrast = eligible & (rv_bucket >= 0)
    candidate = np.zeros(n, dtype=bool)
    for i in range(n):
        # Same-index state only. The next index is intentionally not read.
        candidate[i] = bool(state_at_t[i] is True) and bool(in_contrast[i])
    groups: dict[tuple[int, int], list[list[int]]] = {}
    for i in range(n):
        if not bool(in_contrast[i]):
            continue
        key = (int(year[i]), int(rv_bucket[i]))
        slot = groups.setdefault(key, [[], []])
        slot[1].append(i)
        if bool(candidate[i]):
            slot[0].append(i)
    strata: list[Stratum] = []
    for key in sorted(groups):
        cand_idx = np.asarray(groups[key][0], dtype=np.int64)
        pool_idx = np.asarray(groups[key][1], dtype=np.int64)
        strata.append(Stratum(key[0], key[1], cand_idx, pool_idx))
    k_total = int(sum(s.k for s in strata))
    scale = contrast_scale([s.k for s in strata], [s.n for s in strata])
    weights = np.zeros(n, dtype=np.float64)
    k_year = {y: 0 for y in DESIGN_YEARS}
    for s in strata:
        w_c, w_n = stratum_weights(s.k, s.n, k_total)
        if s.k:
            weights[s.cand_idx] = w_c
            non = np.setdiff1d(s.pool_idx, s.cand_idx, assume_unique=False)
            weights[non] = w_n
        k_year[s.year] = k_year.get(s.year, 0) + s.k
    segments, breaks = _segments(hour_start_ms, year)
    n_blocks = sum(len(seg.slots) for seg in segments)
    return PredictorDesign(
        year=np.asarray(year, dtype=np.int64),
        in_contrast=in_contrast,
        candidate=candidate,
        weights=weights,
        strata=strata,
        segments=segments,
        gap_breaks=breaks,
        k_total=k_total,
        scale_c=scale,
        k_year={int(k): int(v) for k, v in k_year.items()},
        effective_blocks=int(n_blocks),
    )


def _segments(hour_start_ms: np.ndarray, year: np.ndarray) -> tuple[list[Segment], tuple[int, ...]]:
    n = int(hour_start_ms.size)
    cuts = [0]
    gap_breaks: list[int] = []
    for i in range(1, n):
        gap = int(hour_start_ms[i]) - int(hour_start_ms[i - 1]) != HOUR_MS
        year_break = int(year[i]) != int(year[i - 1])
        if gap:
            gap_breaks.append(i)
        if gap or year_break:
            cuts.append(i)
    cuts.append(n)
    segments: list[Segment] = []
    for a, b in zip(cuts, cuts[1:]):
        if b <= a:
            continue
        slots: list[tuple[int, int]] = []
        cursor = a
        while cursor < b:
            nxt = min(cursor + BLOCK_LENGTH, b)
            slots.append((cursor, nxt))
            cursor = nxt
        segments.append(Segment(a, b, slots))
    return segments, tuple(gap_breaks)


def deltas_from_targets(y: np.ndarray, design: PredictorDesign) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Exact frozen contrast. y is (r, n) synthetic 0/1 targets."""

    r = int(y.shape[0])
    delta = np.zeros(r, dtype=np.float64)
    yearly = {year: np.zeros(r, dtype=np.float64) for year in DESIGN_YEARS}
    for s in design.strata:
        if s.k == 0:
            continue
        mean_c = y[:, s.cand_idx].mean(axis=1)
        mean_p = y[:, s.pool_idx].mean(axis=1)
        diff = mean_c - mean_p
        delta += (s.k / float(design.k_total)) * diff
        ky = design.k_year[s.year]
        yearly[s.year] += (s.k / float(ky)) * diff
    return delta, yearly


def score_matrix(y: np.ndarray, design: PredictorDesign) -> np.ndarray:
    """Restricted scores w_t * (Y_t - stratum pool mean). Shape (r, n)."""

    r, n = y.shape
    mu = np.zeros((r, n), dtype=np.float64)
    y64 = np.asarray(y, dtype=np.float64)
    for s in design.strata:
        if s.n == 0:
            continue
        mean_p = y64[:, s.pool_idx].mean(axis=1)
        mu[:, s.pool_idx] = mean_p[:, None]
    return (y64 - mu) * design.weights


def hac_reject(y: np.ndarray, design: PredictorDesign, lag: int) -> tuple[np.ndarray, np.ndarray]:
    delta, _yearly = deltas_from_targets(y, design)
    scores = score_matrix(y, design)
    gamma = sum_autocovariance(scores, lag)
    lrv = bartlett_lrv(gamma, lag)
    return delta, nw_reject(delta, lrv)


def _circular_lag_dots(w: np.ndarray, e: np.ndarray) -> np.ndarray:
    n = int(w.size)
    corr = np.fft.irfft(np.fft.rfft(w) * np.conjugate(np.fft.rfft(e)), n=n)
    return np.real(corr)


def bootstrap_null_deltas(
    y_row: np.ndarray,
    design: PredictorDesign,
    rng: np.random.Generator,
    n_inner: int,
) -> np.ndarray:
    """Residual block bootstrap with the null delta=0 imposed inside each segment."""

    y = np.asarray(y_row, dtype=np.float64)
    mu = np.zeros(y.size, dtype=np.float64)
    for s in design.strata:
        if s.n == 0:
            continue
        mu[s.pool_idx] = float(y[s.pool_idx].mean())
    e = y - mu
    acc = np.zeros(n_inner, dtype=np.float64)
    for seg in design.segments:
        if len(seg.slots) == 1:
            w = design.weights[seg.start : seg.stop]
            corr = _circular_lag_dots(w, e[seg.start : seg.stop])
            picks = rng.integers(0, corr.size, size=n_inner)
            acc += corr[picks]
            continue
        sources = seg.slots
        # Group slots by length so dots line up.
        by_len: dict[int, list[int]] = {}
        for j, (a, b) in enumerate(sources):
            by_len.setdefault(b - a, []).append(j)
        for _length, js in by_len.items():
            if len(js) == 1:
                a, b = sources[js[0]]
                corr = _circular_lag_dots(design.weights[a:b], e[a:b])
                picks = rng.integers(0, corr.size, size=n_inner)
                acc += corr[picks]
                continue
            w_mat = np.stack([design.weights[sources[j][0] : sources[j][1]] for j in js])
            e_mat = np.stack([e[sources[j][0] : sources[j][1]] for j in js])
            dots = e_mat @ w_mat.T
            picks = rng.integers(0, len(js), size=(n_inner, len(js)))
            acc += dots[picks, np.arange(len(js))].sum(axis=1)
    return acc


def bootstrap_reject_row(
    y_row: np.ndarray,
    design: PredictorDesign,
    rng: np.random.Generator,
) -> tuple[float, bool]:
    delta = float(deltas_from_targets(y_row[None, :], design)[0][0])
    null = bootstrap_null_deltas(y_row, design, rng, N_BOOT_INNER)
    cut = float(np.percentile(null, 95.0, method=PERCENTILE_METHOD))
    return delta, bool(delta > cut and delta > 0.0)


def _rng(label: str, seed: int = AMENDMENT_MASTER_SEED) -> np.random.Generator:
    digest = np.frombuffer(f"{seed}:{label}".encode("utf-8"), dtype=np.uint8)
    mix = int(np.uint32(np.sum(digest.astype(np.uint64) * np.arange(1, digest.size + 1))))
    return np.random.Generator(np.random.PCG64([seed, mix]))


def probability_grid(
    design: PredictorDesign,
    regime: str,
    fraction: float,
    rng: np.random.Generator,
    n_rep: int,
) -> np.ndarray:
    """Conditional target probabilities. Shape (n_rep, n). No real outcomes."""

    n = int(design.weights.size)
    d_gap = float(fraction) * float(BINANCE_DELTA_D7) / float(design.scale_c)
    x = design.candidate.astype(np.float64)
    if regime == "NULL_0_IID":
        base = np.full((n_rep, n), BINANCE_MU_D7_CONTROL, dtype=np.float64)
    elif regime in {"NULL_1_MARKOV_MODERATE", "NULL_2_MARKOV_STRONG"}:
        base = np.full((n_rep, n), BINANCE_MU_D7_CONTROL, dtype=np.float64)
    elif regime == "NULL_3_LATENT_30D":
        base = _regime_base(design, rng, n_rep)
    elif regime == "NULL_4_YEAR_HETERO":
        base = np.empty((n_rep, n), dtype=np.float64)
        for year, rate in YEAR_BASE_RATE.items():
            base[:, design.year == int(year)] = float(rate)
    else:
        raise DesignError(f"REGIME:{regime}")
    return np.clip(base + d_gap * x, 1e-6, 1.0 - 1e-6)


def _regime_base(design: PredictorDesign, rng: np.random.Generator, n_rep: int) -> np.ndarray:
    n = int(design.weights.size)
    p_stay = 1.0 - 1.0 / float(REGIME_MEAN_HOURS)
    reg = np.zeros((n_rep, n), dtype=np.int8)
    reg[:, 0] = rng.integers(0, 2, size=n_rep)
    draws = rng.random((n_rep, n))
    breaks = set(design.gap_breaks)
    for t in range(1, n):
        if t in breaks:
            reg[:, t] = rng.integers(0, 2, size=n_rep)
            continue
        reg[:, t] = reg[:, t - 1]
        flip = draws[:, t] >= p_stay
        reg[flip, t] = 1 - reg[flip, t]
    base = np.where(reg == 1, REGIME_P_HIGH, REGIME_P_LOW).astype(np.float64)
    return base


def latent_uniforms(
    design: PredictorDesign,
    regime: str,
    rng: np.random.Generator,
    n_rep: int,
) -> np.ndarray:
    n = int(design.weights.size)
    if regime in {"NULL_0_IID", "NULL_3_LATENT_30D"}:
        return rng.random((n_rep, n))
    phi = PHI_MODERATE if regime in {"NULL_1_MARKOV_MODERATE", "NULL_4_YEAR_HETERO"} else PHI_STRONG
    innov = rng.standard_normal((n_rep, n))
    eps = np.empty((n_rep, n), dtype=np.float64)
    scale = math.sqrt(1.0 - phi * phi)
    breaks = set(design.gap_breaks)
    eps[:, 0] = innov[:, 0]
    for t in range(1, n):
        if t in breaks:
            eps[:, t] = innov[:, t]
        else:
            eps[:, t] = phi * eps[:, t - 1] + scale * innov[:, t]
    return norm_cdf(eps)


def draw_targets(
    design: PredictorDesign,
    regime: str,
    fraction: float,
    rng: np.random.Generator,
    n_rep: int,
) -> np.ndarray:
    probs = probability_grid(design, regime, fraction, rng, n_rep)
    uniforms = latent_uniforms(design, regime, rng, n_rep)
    return (uniforms <= probs).astype(np.float64)


def evaluate_hac_chunk(y: np.ndarray, design: PredictorDesign) -> dict[str, np.ndarray]:
    delta, yearly = deltas_from_targets(y, design)
    practical = delta >= PRACTICAL_THRESHOLD
    positive = np.zeros(delta.shape, dtype=np.int64)
    for year in TEMPORAL_GATE_YEARS:
        positive += (yearly[year] > 0.0).astype(np.int64)
    temporal = positive >= TEMPORAL_POSITIVE_YEARS_REQUIRED
    scores = score_matrix(y, design)
    gamma = sum_autocovariance(scores, NW_LAG_PRIMARY)
    out: dict[str, np.ndarray] = {
        "delta": delta,
        "practical": practical,
        "temporal": temporal,
    }
    for lag, name in ((NW_LAG_PRIMARY, METHOD_NW), (NW_LAG_SENSITIVITY, METHOD_NW_SHORT)):
        stat = nw_reject(delta, bartlett_lrv(gamma, lag))
        out[f"stat_{name}"] = stat
        out[f"joint_{name}"] = stat & practical & temporal
    return out


def accumulate_bool(store: dict[str, int], key: str, mask: np.ndarray) -> None:
    store[key] = int(store.get(key, 0) + int(np.count_nonzero(mask)))


def run_hac_study(design: PredictorDesign) -> dict[str, Any]:
    type_i: dict[str, dict[str, Any]] = {METHOD_NW: {}, METHOD_NW_SHORT: {}}
    for regime in NULL_REGIMES:
        rng = _rng(f"amend-null-nw:{regime}")
        counts = {METHOD_NW: 0, METHOD_NW_SHORT: 0}
        done = 0
        while done < N_OUTER:
            take = min(GENERATION_CHUNK, N_OUTER - done)
            y = draw_targets(design, regime, 0.0, rng, take)
            ev = evaluate_hac_chunk(y, design)
            counts[METHOD_NW] += int(np.count_nonzero(ev[f"stat_{METHOD_NW}"]))
            counts[METHOD_NW_SHORT] += int(np.count_nonzero(ev[f"stat_{METHOD_NW_SHORT}"]))
            done += take
            print(f"type1 {regime} {done}/{N_OUTER}", flush=True)
        for method in (METHOD_NW, METHOD_NW_SHORT):
            lo, hi = wilson_score_interval(counts[method], N_OUTER)
            type_i[method][regime] = _rate_row(counts[method], N_OUTER, lo, hi)
    power: dict[str, dict[str, Any]] = {METHOD_NW: {}, METHOD_NW_SHORT: {}}
    for regime in NULL_REGIMES:
        power[METHOD_NW][regime] = {}
        power[METHOD_NW_SHORT][regime] = {}
        for fraction in EFFECT_FRACTIONS:
            label = _fraction_label(fraction)
            rng = _rng(f"amend-power-nw:{regime}:{label}")
            joint = {METHOD_NW: 0, METHOD_NW_SHORT: 0}
            stat = {METHOD_NW: 0, METHOD_NW_SHORT: 0}
            practical = 0
            temporal = 0
            done = 0
            while done < N_OUTER:
                take = min(GENERATION_CHUNK, N_OUTER - done)
                y = draw_targets(design, regime, fraction, rng, take)
                ev = evaluate_hac_chunk(y, design)
                practical += int(np.count_nonzero(ev["practical"]))
                temporal += int(np.count_nonzero(ev["temporal"]))
                for method in (METHOD_NW, METHOD_NW_SHORT):
                    stat[method] += int(np.count_nonzero(ev[f"stat_{method}"]))
                    joint[method] += int(np.count_nonzero(ev[f"joint_{method}"]))
                done += take
                print(f"power {regime} {label} {done}/{N_OUTER}", flush=True)
            for method in (METHOD_NW, METHOD_NW_SHORT):
                power[method][regime][label] = _power_row(
                    joint[method], stat[method], practical, temporal, N_OUTER
                )
    return {"type_i": type_i, "power": power}


def run_bootstrap_study(design: PredictorDesign) -> dict[str, Any]:
    """Null calibration only. The bootstrap is not a confirmation gate."""

    if design.effective_blocks < MIN_EFFECTIVE_BLOCKS:
        return {"support_eligible": False, "effective_blocks": design.effective_blocks}
    type_i: dict[str, Any] = {}
    for regime in NULL_REGIMES:
        rng = _rng(f"amend-null-boot:{regime}")
        y = _draw_all(design, regime, 0.0, rng, N_BOOT_OUTER)
        rejects = 0
        for i in range(N_BOOT_OUTER):
            _delta, hit = bootstrap_reject_row(y[i], design, rng)
            rejects += int(hit)
            if (i + 1) % 250 == 0:
                print(f"boot-type1 {regime} {i + 1}/{N_BOOT_OUTER}", flush=True)
        lo, hi = wilson_score_interval(rejects, N_BOOT_OUTER)
        type_i[regime] = _rate_row(rejects, N_BOOT_OUTER, lo, hi)
    return {
        "support_eligible": True,
        "effective_blocks": design.effective_blocks,
        "type_i": type_i,
        "ROLE": "SENSITIVITY_ONLY",
    }


def _draw_all(
    design: PredictorDesign,
    regime: str,
    fraction: float,
    rng: np.random.Generator,
    n_rep: int,
) -> np.ndarray:
    rows = []
    done = 0
    while done < n_rep:
        take = min(GENERATION_CHUNK, n_rep - done)
        rows.append(draw_targets(design, regime, fraction, rng, take))
        done += take
    return np.concatenate(rows, axis=0)


def _rate_row(rejections: int, n: int, lo: float, hi: float) -> dict[str, Any]:
    return {
        "rejections": int(rejections),
        "n": int(n),
        "rate": rejections / float(n),
        "wilson_95": [float(lo), float(hi)],
        "accepted": bool(hi <= TYPE_I_CEILING),
    }


def _power_row(joint: int, stat: int, practical: int, temporal: int, n: int) -> dict[str, Any]:
    j_lo, j_hi = wilson_score_interval(joint, n)
    return {
        "joint": joint / float(n),
        "joint_wilson_95": [j_lo, j_hi],
        "joint_rejections": int(joint),
        "statistical": stat / float(n),
        "practical": practical / float(n),
        "temporal": temporal / float(n),
        "n": int(n),
    }


def _fraction_label(fraction: float) -> str:
    return {1.0: "full", 0.75: "75pct", 0.5: "50pct"}[float(fraction)]


def assemble_decision(hac: Mapping[str, Any], boot: Mapping[str, Any]) -> dict[str, Any]:
    type_i_by_method: dict[str, Any] = {}
    type_i_by_method[METHOD_NW] = {
        "support_eligible": True,
        "regimes": hac["type_i"][METHOD_NW],
    }
    boot_ok = bool(boot.get("support_eligible"))
    if boot_ok:
        type_i_by_method[METHOD_BOOT] = {
            "support_eligible": True,
            "regimes": boot["type_i"],
        }
    else:
        type_i_by_method[METHOD_BOOT] = {"support_eligible": False, "regimes": {}}
    primary = choose_primary_method(
        {
            METHOD_NW: type_i_by_method[METHOD_NW],
            **(
                {METHOD_BOOT: type_i_by_method[METHOD_BOOT]}
                if boot_ok
                else {METHOD_BOOT: {"support_eligible": False}}
            ),
        }
    )
    power_view: dict[str, dict[str, float]] = {}
    power_source = hac["power"][METHOD_NW] if primary == METHOD_NW else None
    power_ok = False
    if power_source is not None:
        for regime in NULL_REGIMES:
            power_view[regime] = {"joint_full": float(power_source[regime]["full"]["joint"])}
        power_ok = joint_power_passes(power_view)
    decision = feasibility_decision(
        primary=primary,
        power_ok=power_ok,
        any_support_eligible=True,
    )
    return {
        "primary": primary,
        "power_ok": power_ok,
        "decision": decision,
        "power_view": power_view,
    }


def public_power_fields(power_source: Mapping[str, Any] | None) -> dict[str, Any]:
    if power_source is None:
        return {
            "POWER_FULL_EFFECT": None,
            "POWER_75PCT_EFFECT": None,
            "POWER_50PCT_EFFECT": None,
        }
    base = power_source[BASE_POWER_REGIME]
    return {
        "POWER_FULL_EFFECT": base["full"]["joint"],
        "POWER_FULL_EFFECT_95CI": base["full"]["joint_wilson_95"],
        "POWER_75PCT_EFFECT": base["75pct"]["joint"],
        "POWER_75PCT_EFFECT_95CI": base["75pct"]["joint_wilson_95"],
        "POWER_50PCT_EFFECT": base["50pct"]["joint"],
        "POWER_50PCT_EFFECT_95CI": base["50pct"]["joint_wilson_95"],
    }


def _calibration_lines(payload: Mapping[str, Any]) -> list[str]:
    """Render frozen calibration counts. Does not recompute them."""

    lines = [
        "## Calibration",
        "",
        "One-sided rejection rate at alpha 0.05. A regime is accepted when",
        "the Wilson 95% upper bound is at most 0.06. The point estimate and",
        "the lower bound are not the rule. Lag 720 is reported and is not",
        "selectable. The block bootstrap is a sensitivity calibration, not",
        "a second gate.",
        "",
        "### Type I",
        "",
    ]
    type_i = payload["TYPE_I_RESULTS"]
    for method in (METHOD_NW, METHOD_NW_SHORT, METHOD_BOOT):
        block = type_i[method]
        lines.append(f"`{method}`")
        lines.append("")
        for regime in NULL_REGIMES:
            cell = block[regime]
            lo, hi = cell["wilson_95"]
            lines.append(
                f"- {regime}: {cell['rejections']}/{cell['n']} = {cell['rate']}, "
                f"Wilson [{lo}, {hi}], accepted={str(bool(cell['accepted'])).lower()}"
            )
        lines.append("")
    shift = type_i[METHOD_SHIFT]
    lines.append(f"`{METHOD_SHIFT}`: {shift['STATUS']}. {shift['REASON']}")
    lines.append("")
    lines.append("### Joint power")
    lines.append("")
    lines.append(
        "Joint means the statistical gate, the practical gate, and the"
    )
    lines.append(
        "temporal gate all pass. At half the frozen delta the within-stratum"
    )
    lines.append(
        "gap maps to a contrast near 0.045, below 0.05, so the practical gate"
    )
    lines.append(
        "binds and the joint rate equals the practical rate. That 50% rate is"
    )
    lines.append("reported. It is not the acceptance bar.")
    lines.append("")
    power = payload["POWER_BY_METHOD"]
    labels = {
        METHOD_NW: "primary",
        METHOD_NW_SHORT: "sensitivity, not selectable",
        METHOD_BOOT: "sensitivity only, not a gate",
    }
    for method, label in labels.items():
        block = power[method]
        if isinstance(block, Mapping) and block.get("ROLE") == "SENSITIVITY_ONLY":
            lines.append(f"`{method}` ({label})")
            lines.append("")
            lines.append(str(block.get("NOTE")))
            lines.append("")
            continue
        regimes = block["regimes"] if isinstance(block, Mapping) and "regimes" in block else block
        lines.append(f"`{method}` ({label})")
        lines.append("")
        for regime in NULL_REGIMES:
            cell = regimes[regime]
            bits = [
                f"{key} joint {cell[key]['joint']}"
                for key in ("full", "75pct", "50pct")
            ]
            lines.append(f"- {regime}: " + "; ".join(bits))
        lines.append("")
    return lines


def _support_lines(payload: Mapping[str, Any]) -> list[str]:
    table = payload["RV_QREL_SUPPORT"]
    lines = [
        f"STATUS = {table['STATUS']}",
        "",
        "Fine cells:",
        "",
    ]
    for cell in table["FINE_CELLS"]:
        lines.append(
            f"- RV {cell['rv_bucket']} qrel {cell['qrel_bucket']}: "
            f"n={cell['n']} candidates={cell['candidates']} "
            f"controls={cell['controls']} "
            f"candidate_share={cell['candidate_share']} "
            f"control_share={cell['control_share']} "
            f"arm_support_ok={str(bool(cell['arm_support_ok'])).lower()}"
        )
    lines.append("")
    coarse = table.get("COARSE_CELLS")
    if coarse:
        lines.append("Coarse cells:")
        lines.append("")
        for cell in coarse:
            lines.append(
                f"- RV {cell['rv_bucket']} qrel {cell['qrel_bucket']}: "
                f"n={cell['n']} candidates={cell['candidates']} "
                f"controls={cell['controls']} "
                f"candidate_share={cell['candidate_share']} "
                f"control_share={cell['control_share']} "
                f"arm_support_ok={str(bool(cell['arm_support_ok'])).lower()}"
            )
        lines.append("")
    return lines


def render_markdown(payload: Mapping[str, Any]) -> str:
    gates = payload["FINAL_PASS_RULE"]
    power = payload["POWER_FIELDS"]
    lines = [
        "# D7 BitMEX dependence inference review V0",
        "",
        f"**Unit:** `{UNIT}`",
        "",
        "Outcome-blind statistical design. Real BitMEX t+1 targets are not",
        "constructed. No replication class is assigned. No confirmation",
        "preregistration and no execution permit.",
        "",
        "## Estimand",
        "",
        "The market claim is unchanged. For target-eligible hours, let",
        "`Y_t` be the next completed hour's D7 state and let `X_t` be",
        "`D7_STATE_t`. Strata are calendar year × RV bucket. With `K_s`",
        "candidates and `N_s` eligible hours in stratum `s`, and `K = sum K_s`,",
        "",
        "`delta = sum_s (K_s / K) (mean(Y | X=1, s) - mean(Y | eligible, s))`.",
        "",
        "That is the expectation of the frozen rate-matched contrast, because",
        "a rate-matched draw in stratum `s` has mean equal to the eligible-pool",
        "mean. It equals `sum_s (K_s / K) (1 - K_s/N_s) (mean_1 - mean_0)`.",
        "The ordinary stratum-fixed-effect slope is `delta / c` with",
        f"`c = {payload['CONTRAST_SCALE_C']}`, so the slope is not the frozen",
        "delta. The practical gate stays on `delta`, which keeps the 0.05",
        "threshold on the same magnitude as discovery.",
        "",
        "Inference is separate from this estimand. Replacing the exchangeable",
        "Monte Carlo changes the reference distribution, not the claim.",
        "",
        "## Why the exchangeable null is invalid",
        "",
        "The frozen null draws `K_s` eligible hours without replacement inside",
        "each stratum and treats those hours as exchangeable. The contrast is",
        "the linear statistic `delta = sum_t w_t Y_t`, with weights that sum",
        "to zero inside each stratum: positive on candidates and negative on",
        "other eligible hours. Exchangeability supplies every covariance term",
        "`Cov(Y_t, Y_{t+h})` for `h ≠ 0` as if the candidate set were a random",
        "subset. It is not. The 720-hour QREL median, the 720-hour impact P90,",
        "and the 720-hour RV quantiles make nearby hours share threshold",
        "inputs. The target is the next hour, so the score at `t` uses states",
        "at `t` and `t+1`. Those scores still share a construction input at",
        "valid-hour separation 721, and the overlap is gone at separation 722.",
        "Positive serial correlation then inflates `Var(sum w_t Y_t)` relative",
        "to the exchangeable formula, and the old 95th percentile is too small.",
        "This is a structural statement. No BitMEX state adjacency was measured.",
        "",
        "## Designs reviewed",
        "",
        "A. Exact-delta Newey-West, Bartlett kernel, fixed lag 721 valid hours.",
        "Estimand is `delta`. Year × RV bucket adjustment is the weight",
        "construction. Lag 721 is the construction cutoff, not a residual lag.",
        "Lag 720 leaves the last overlapping score lag uncovered and is not",
        "selectable. Normal critical value `1.6448536269514722`. Finite-sample",
        "risk: `L/T` is about 0.02, so fixed-b distortion is possible; the",
        "null battery is the check. No automatic lag picker.",
        "",
        "B. Non-overlapping block bootstrap of residuals, block length 1440",
        "valid hours, resampled with replacement inside year segments and",
        "inside the December 2016 gap split. Stratum means are added back, so",
        "the bootstrap imposes `delta = 0` while keeping within-block serial",
        "structure and the RV-bucket adjustment. A segment that is a single",
        "block uses a circular residual shift inside that segment only, so",
        "the short post-gap piece is still randomized. This is not a test",
        "against other lags of the original contrast.",
        "",
        "C. Circular shift of the target across lags. Rejecting when the",
        "next-hour alignment is extreme among alignments changes the null",
        "into 'lag 1 is unusual relative to other lags'. Status:",
        "`NOT_EQUIVALENT`. It is not a primary method and it is not selectable",
        "at execution.",
        "",
        "## Calibration rules",
        "",
        TYPE_I_RULE,
        "",
        POWER_RULE,
        "",
        "## Gates",
        "",
        f"STATISTICAL_GATE = {gates['STATISTICAL_GATE']}",
        "",
        f"PRACTICAL_GATE = {gates['PRACTICAL_GATE']}",
        "",
        f"TEMPORAL_GATE = {gates['TEMPORAL_GATE']}",
        "",
        f"INTEGRITY_GATE = {gates['INTEGRITY_GATE']}",
        "",
        "The Binance temporal gate remains `D7_TEMPORAL_YEARS_REQUIRED = 3`",
        "positive year-level contrasts on `(2020, 2021, 2022, 2023, 2024)`.",
        "That discovery rule is unchanged. The BitMEX confirmation amendment",
        "uses a different surface: PASS if the sign is positive in at least",
        "2 of the 3 full years 2017, 2018, and 2019. The gate exists to stop",
        "one historical period from carrying the result. It does not require",
        "the effect in every year. With three full years, 2 of 3 is a",
        "symmetric majority. 2016 is a partial post-listing year. Its",
        "year-level sign is recorded as a diagnostic and is excluded from",
        "both the numerator and the denominator.",
        "",
        "The block bootstrap does not enter the confirmation conjunction.",
        "If the primary call and the bootstrap call disagree,",
        "`INFERENCE_SENSITIVE` is true. Agreement adds no flag. The flag",
        "does not turn a primary PASS into a FAIL or a primary FAIL into a",
        "PASS, and it is not combined with the primary call by AND or OR.",
        "",
        "## RV x qrel support",
        "",
        "Each fine cell is one RV quartile crossed with one trailing qrel",
        f"quartile. A cell is supported when both arms have at least {MIN_CELL_ARM}",
        "hours. That floor is the frozen `MIN_D7_STATE_PER_YEAR`. If any fine",
        "cell fails, qrel is coarsened once, by merging bins (0, 1) and bins",
        "(2, 3). RV bins stay at four. No other merge is allowed. If the",
        "coarse grid still fails, the decomposition is `NOT_SUPPORTED` and",
        "no effect is reported for it.",
        "",
        *_support_lines(payload),
        *_calibration_lines(payload),
        "## Results",
        "",
        "```",
        f"OLD_EXCHANGEABLE_NULL_STATUS = {payload['OLD_EXCHANGEABLE_NULL_STATUS']}",
        f"PRIMARY_INFERENCE_METHOD = {payload['PRIMARY_INFERENCE_METHOD']}",
        f"DECISION = {payload['DECISION']}",
        f"NEXT_UNIT = {payload['NEXT_UNIT']}",
        f"POWER_FULL_EFFECT = {power.get('POWER_FULL_EFFECT')}",
        f"POWER_75PCT_EFFECT = {power.get('POWER_75PCT_EFFECT')}",
        f"POWER_50PCT_EFFECT = {power.get('POWER_50PCT_EFFECT')}",
        "D7_BITMEX_PRIMARY_TARGET_OPENED = false",
        "D7_BITMEX_EFFECT_COMPUTED = false",
        "D7_PRIMARY_EFFECT_COMPUTED = false",
        "D7_AMENDMENT_OUTCOME_BLIND = true",
        "D7_BITMEX_REPLICATION_CLASS_ASSIGNED = false",
        "BINANCE_2025_OPENED = false",
        "BINANCE_2026_OPENED = false",
        f"PRIMARY_INFERENCE_RESULT = {payload['PRIMARY_INFERENCE_RESULT']}",
        f"BLOCK_BOOTSTRAP_SENSITIVITY_RESULT = {payload['BLOCK_BOOTSTRAP_SENSITIVITY_RESULT']}",
        f"INFERENCE_SENSITIVE = {payload['INFERENCE_SENSITIVE']}",
        f"RV_QREL_DECOMPOSITION = {payload['RV_QREL_SUPPORT']['STATUS']}",
        "```",
        "",
        payload["DECISION_NOTE"],
        "",
        (
            "Block-bootstrap null calibration is "
            f"{payload['BLOCK_BOOTSTRAP_SENSITIVITY_CALIBRATION']}. "
            "A FAIL means the bootstrap is not an interpretable sensitivity "
            "check. It does not change the primary call."
        ),
        "",
        "This unit does not classify scientific truth.",
        "",
    ]
    return "\n".join(lines)


def assert_public_closed(payload: Mapping[str, Any]) -> None:
    blob = canonical_json(payload)
    for token in ("hour_start_ms", "autocorrelation", "run_length", "next_d7", "REPLICATED"):
        if token in blob:
            raise DesignError(f"PUBLIC_LEAK:{token}")
    if payload["D7_BITMEX_PRIMARY_TARGET_OPENED"] is not False:
        raise DesignError("TARGET_OPENED")
    if payload["D7_BITMEX_EFFECT_COMPUTED"] is not False:
        raise DesignError("EFFECT_COMPUTED")
    if payload["D7_PRIMARY_EFFECT_COMPUTED"] is not False:
        raise DesignError("PRIMARY_EFFECT_COMPUTED")
    if payload["D7_AMENDMENT_OUTCOME_BLIND"] is not True:
        raise DesignError("AMENDMENT_NOT_BLIND")
    if payload["D7_BITMEX_REPLICATION_CLASS_ASSIGNED"] is not False:
        raise DesignError("CLASS_ASSIGNED")


def qrel_bucket_from_trailing(qrel: float, trailing: Sequence[float]) -> int:
    """Same cuts and assignment as RV_BUCKET, applied to trailing qrel."""

    if len(trailing) < TRAILING_WINDOW:
        raise DesignError("QREL_BUCKET_SHORT_WINDOW")
    p25 = percentile(trailing, RV_CUTS[0])
    p50 = percentile(trailing, RV_CUTS[1])
    p75 = percentile(trailing, RV_CUTS[2])
    if qrel <= p25:
        return 0
    if qrel <= p50:
        return 1
    if qrel <= p75:
        return 2
    return 3


def assign_qrel_buckets(qrel_values: Sequence[float | None]) -> np.ndarray:
    """Trailing qrel quartile. Current value is excluded. -1 if undefined."""

    valid: list[float] = []
    out = np.full(len(qrel_values), -1, dtype=np.int64)
    for i, raw in enumerate(qrel_values):
        if raw is not None and math.isfinite(float(raw)) and len(valid) >= TRAILING_WINDOW:
            out[i] = qrel_bucket_from_trailing(float(raw), valid[-TRAILING_WINDOW:])
        if raw is not None and math.isfinite(float(raw)):
            valid.append(float(raw))
    return out


def _arm_cell(rv_bucket: int, qrel_label: str, candidates: int, controls: int) -> dict[str, Any]:
    n = int(candidates) + int(controls)
    return {
        "rv_bucket": int(rv_bucket),
        "qrel_bucket": qrel_label,
        "n": n,
        "candidates": int(candidates),
        "controls": int(controls),
        "candidate_share": None if n == 0 else candidates / float(n),
        "control_share": None if n == 0 else controls / float(n),
        "arm_support_ok": int(candidates) >= MIN_CELL_ARM and int(controls) >= MIN_CELL_ARM,
    }


def _count_cells(
    rv: np.ndarray,
    qrel: np.ndarray,
    candidate: np.ndarray,
    mask: np.ndarray,
    groups: Sequence[tuple[str, tuple[int, ...]]],
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for rv_id in range(int(N_RV_BUCKETS)):
        for label, members in groups:
            sel = mask & (rv == int(rv_id)) & np.isin(qrel, np.asarray(members, dtype=np.int64))
            cand_n = int(np.count_nonzero(sel & candidate))
            ctrl_n = int(np.count_nonzero(sel & ~candidate))
            cells.append(_arm_cell(rv_id, label, cand_n, ctrl_n))
    return cells


def rv_qrel_support_from_buckets(
    rv_bucket: np.ndarray,
    qrel_bucket: np.ndarray,
    is_candidate: np.ndarray,
    in_contrast: np.ndarray,
) -> dict[str, Any]:
    """Covariate overlap only. Arguments are buckets, the candidate bit, and the mask."""

    rv = np.asarray(rv_bucket, dtype=np.int64)
    qrel = np.asarray(qrel_bucket, dtype=np.int64)
    candidate = np.asarray(is_candidate, dtype=bool)
    mask = np.asarray(in_contrast, dtype=bool) & (qrel >= 0) & (rv >= 0)
    undefined = int(np.count_nonzero(np.asarray(in_contrast, dtype=bool) & (qrel < 0)))
    fine_groups = [(str(b), (b,)) for b in QREL_FINE_BINS]
    coarse_groups = [(f"{a}+{b}", (a, b)) for a, b in QREL_COARSE_GROUPS]
    fine = _count_cells(rv, qrel, candidate, mask, fine_groups)
    fine_ok = all(bool(cell["arm_support_ok"]) for cell in fine)
    coarse = _count_cells(rv, qrel, candidate, mask, coarse_groups)
    coarse_ok = all(bool(cell["arm_support_ok"]) for cell in coarse)
    if fine_ok:
        status = "SUPPORTED"
    elif coarse_ok:
        status = "SUPPORTED_AFTER_COARSENING"
    else:
        status = "NOT_SUPPORTED"
    return {
        "MINIMUM_ARM_COUNT": MIN_CELL_ARM,
        "MINIMUM_ARM_SOURCE": "MIN_D7_STATE_PER_YEAR",
        "COARSENING_RULE": (
            "If any fine RV x qrel cell has fewer than 50 candidates or fewer "
            "than 50 controls, merge qrel bins (0, 1) and (2, 3) once. "
            "RV bins stay unmerged. No further bin search."
        ),
        "STATUS": status,
        "UNDEFINED_QREL_IN_CONTRAST": undefined,
        "FINE_CELLS": fine,
        "COARSE_CELLS": coarse,
    }


def load_real_predictor_design():
    """Load predictor geometry. Does not form a real t+1 target."""

    from pathlib import Path
    import json

    from scripts.research.d7_bitmex_support_and_power_v0 import (
        aggregate_completed_hours,
        build_predictor_frame,
        repo_root,
        support_from_frame,
        verify_data_identity,
    )

    root = repo_root()
    identity = verify_data_identity(root)
    bars = identity.pop("bars")
    hours = aggregate_completed_hours(bars)
    frame = build_predictor_frame(hours)
    support = support_from_frame(frame)
    pinned = json.loads(
        (root / "docs/research/D7_BITMEX_SUPPORT_AND_POWER_V0.json").read_text(encoding="utf-8")
    )
    if support["SELECTOR_DIGEST"] != pinned["SELECTOR_DIGEST"]:
        raise DesignError("SELECTOR_DIGEST_MISMATCH")
    if int(support["STATE_N"]) != int(pinned["STATE_N"]):
        raise DesignError("STATE_N_MISMATCH")
    design = build_predictor_design(
        frame.hour_start_ms,
        frame.year,
        frame.rv_bucket,
        frame.state,
        frame.state_defined,
    )
    qrel_bucket = assign_qrel_buckets(frame.qrel_1h)
    is_candidate = np.array([value is True for value in frame.state], dtype=bool)
    support_table = rv_qrel_support_from_buckets(
        frame.rv_bucket,
        qrel_bucket,
        is_candidate,
        design.in_contrast,
    )
    # Drop the state sequence before any synthetic target is drawn.
    del frame
    return design, support_table, {
        "DATA_IDENTITY_STATUS": identity["DATA_IDENTITY_STATUS"],
        "SELECTOR_DIGEST": support["SELECTOR_DIGEST"],
        "STATE_N": support["STATE_N"],
        "SELECTOR_N": support["SELECTOR_N"],
        "CANONICAL_GZ_SHA256": identity["CANONICAL_GZ_SHA256"],
        "D2_CANONICAL_MODIFIED": False,
    }


def build_payload(
    design: PredictorDesign,
    pin: Mapping[str, Any],
    hac: Mapping[str, Any],
    boot: Mapping[str, Any],
    support_table: Mapping[str, Any],
) -> dict[str, Any]:
    decision_bits = assemble_decision(hac, boot)
    primary = decision_bits["primary"]
    if primary not in (None, confirmation_estimator()):
        raise DesignError("PRIMARY_NOT_FROZEN")
    if primary == METHOD_NW:
        power_source = hac["power"][METHOD_NW]
    else:
        power_source = None
    decision = decision_bits["decision"]
    next_unit = (
        "D7_BITMEX_CONFIRMATION_PREREG_FREEZE"
        if decision == "DEPENDENCE_VALID_DESIGN_READY_FOR_PREREG"
        else "NONE"
    )
    blockers: list[str] = []
    if decision == "NO_VALID_EQUIVALENT_INFERENCE_DESIGN":
        blockers.append(
            "Primary NW721 did not keep every null regime inside the Wilson "
            "95% upper bound of 0.06. The block bootstrap was not promoted."
        )
    elif decision == "DEPENDENCE_ROBUST_POWER_INSUFFICIENT":
        blockers.append(
            "The type-I-valid primary method missed the predeclared "
            "dependence-aware power bar."
        )
    elif decision == "INFERENCE_SUPPORT_INSUFFICIENT":
        blockers.append("No equivalent method met the support minimum.")
    note = _decision_note(decision, primary, decision_bits["power_view"])
    payload: dict[str, Any] = {
        "UNIT": UNIT,
        "OLD_EXCHANGEABLE_NULL_STATUS": "INVALID_UNDER_SERIAL_DEPENDENCE",
        "PRIMARY_ESTIMAND": (
            "delta = sum_s (K_s/K) * (mean(Y|X=1,s) - mean(Y|eligible,s))"
        ),
        "PRIMARY_INFERENCE_METHOD": confirmation_estimator(),
        "DEPENDENCE_PARAMETERS": {
            "NW_LAG_PRIMARY": NW_LAG_PRIMARY,
            "NW_LAG_SENSITIVITY_NOT_SELECTABLE": NW_LAG_SENSITIVITY,
            "BLOCK_LENGTH": BLOCK_LENGTH,
            "MIN_EFFECTIVE_BLOCKS": MIN_EFFECTIVE_BLOCKS,
            "EFFECTIVE_BLOCKS": design.effective_blocks,
            "PHI_MODERATE": PHI_MODERATE,
            "PHI_STRONG": PHI_STRONG,
            "REGIME_MEAN_HOURS": REGIME_MEAN_HOURS,
            "REGIME_P_LOW": REGIME_P_LOW,
            "REGIME_P_HIGH": REGIME_P_HIGH,
            "YEAR_BASE_RATE": {str(k): v for k, v in YEAR_BASE_RATE.items()},
            "P0": BINANCE_MU_D7_CONTROL,
            "PLANNING_DELTA": BINANCE_DELTA_D7,
            "PLANNING_MU_RULE": BINANCE_MU_D7_RULE,
        },
        "ALPHA": ALPHA,
        "CONTRAST_SCALE_C": design.scale_c,
        "WITHIN_STRATUM_GAP_FOR_FULL_DELTA": BINANCE_DELTA_D7 / design.scale_c,
        "TYPE_I_ACCEPTANCE_RULE": TYPE_I_RULE,
        "TYPE_I_RESULTS": {
            METHOD_NW: hac["type_i"][METHOD_NW],
            METHOD_NW_SHORT: hac["type_i"][METHOD_NW_SHORT],
            METHOD_BOOT: boot.get("type_i"),
            METHOD_SHIFT: {
                "STATUS": "NOT_EQUIVALENT",
                "REASON": (
                    "A circular-shift reference distribution tests whether the "
                    "next-hour alignment is unusual among alignments."
                ),
            },
        },
        "POWER_FIELDS": public_power_fields(power_source),
        "POWER_BY_METHOD": {
            METHOD_NW: hac["power"][METHOD_NW],
            METHOD_NW_SHORT: {
                "ROLE": "SENSITIVITY_NOT_SELECTABLE",
                "regimes": hac["power"][METHOD_NW_SHORT],
            },
            METHOD_BOOT: {
                "ROLE": "SENSITIVITY_ONLY",
                "NOTE": (
                    "Null calibration is under type I. Bootstrap power is not "
                    "a gate and was not recomputed."
                ),
            },
        },
        "DEPENDENCE_POWER_SCENARIOS": NULL_REGIMES,
        "POWER_ACCEPTANCE_RULE": POWER_RULE,
        "BASE_POWER_REGIME": BASE_POWER_REGIME,
        "CONFIRMATION_STATISTICAL_GATE": final_pass_rule_text()["STATISTICAL_GATE"],
        "CONFIRMATION_PRACTICAL_GATE": final_pass_rule_text()["PRACTICAL_GATE"],
        "CONFIRMATION_TEMPORAL_GATE": final_pass_rule_text()["TEMPORAL_GATE"],
        "CONFIRMATION_INTEGRITY_GATE": final_pass_rule_text()["INTEGRITY_GATE"],
        "FINAL_PASS_RULE": final_pass_rule_text(),
        "BITMEX_2016_PARTIAL_YEAR_TREATMENT": PARTIAL_YEAR_TREATMENT,
        "TEMPORAL_GATE_YEARS": list(TEMPORAL_GATE_YEARS),
        "TYPE_I_CEILING": TYPE_I_CEILING,
        "TYPE_I_RELATIVE_INFLATION": TYPE_I_RELATIVE_INFLATION,
        "WILSON_CONFIDENCE_LEVEL": WILSON_CONFIDENCE_LEVEL,
        "AMENDMENT_MASTER_SEED": AMENDMENT_MASTER_SEED,
        "REVIEWED_CALIBRATION_SEED": REVIEWED_CALIBRATION_SEED,
        "AMENDMENT_SEED_TABLE": {
            "master": AMENDMENT_MASTER_SEED,
            "nw_null_label": "amend-null-nw:{regime}",
            "nw_power_label": "amend-power-nw:{regime}:{fraction}",
            "boot_null_label": "amend-null-boot:{regime}",
            "generator": "PCG64([master, mix(label)])",
            "n_nw_null": N_OUTER,
            "n_nw_power": N_OUTER,
            "n_boot_null": N_BOOT_OUTER,
            "regimes": list(NULL_REGIMES),
        },
        "BLOCK_BOOTSTRAP_ROLE": "SENSITIVITY_ONLY",
        "PRIMARY_INFERENCE_RESULT": "NOT_EVALUATED_TARGET_UNOPENED",
        "BLOCK_BOOTSTRAP_SENSITIVITY_RESULT": "NOT_EVALUATED_TARGET_UNOPENED",
        "INFERENCE_SENSITIVE": None,
        "BLOCK_BOOTSTRAP_SENSITIVITY_CALIBRATION": (
            "PASS" if boot.get("type_i") and type_i_passes(boot["type_i"]) else "FAIL"
        ),
        "RV_QREL_SUPPORT": dict(support_table),
        "DESIGN_EQUIVALENCE_STATUS": (
            "ESTIMAND_EQUIVALENT_INFERENCE_REPLACED"
            if primary is not None
            else "NO_CALIBRATED_EQUIVALENT_PROCEDURE"
        ),
        "PRIMARY_ASSUMPTIONS": _assumptions(primary),
        "CIRCULAR_SHIFT_STATUS": "NOT_EQUIVALENT",
        "BOOTSTRAP_SUPPORT": {
            "support_eligible": boot.get("support_eligible"),
            "effective_blocks": design.effective_blocks,
            "min_effective_blocks": MIN_EFFECTIVE_BLOCKS,
        },
        "PIN": dict(pin),
        "DECISION": decision,
        "PRIMARY_BLOCKERS": blockers,
        "DECISION_NOTE": note,
        "NEXT_UNIT": next_unit,
        "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
        "D7_BITMEX_EFFECT_COMPUTED": False,
        "D7_PRIMARY_EFFECT_COMPUTED": False,
        "D7_AMENDMENT_OUTCOME_BLIND": True,
        "D7_BITMEX_REPLICATION_CLASS_ASSIGNED": False,
        "BINANCE_2025_OPENED": False,
        "BINANCE_2026_OPENED": False,
        "CONFIRMATION_PREREG_CREATED": False,
        "EXECUTION_PERMIT_CREATED": False,
        "CONFIRMATION_EXECUTED": False,
        "MASTER_SEED": MASTER_SEED,
        "N_OUTER_HAC": N_OUTER,
        "N_OUTER_BOOT": N_BOOT_OUTER,
        "N_INNER_BOOT": N_BOOT_INNER,
    }
    assert_public_closed(payload)
    return payload


def _assumptions(primary: str | None) -> list[str]:
    common = [
        "Weights are fixed from the predictor and the stratum counts.",
        "The scientific contrast remains the frozen pool-adjusted delta.",
        "Synthetic nulls are independent of the real target, which is unopened.",
        "Lag and block length were fixed from the 720-hour construction and the 30-day stress, not from residuals.",
    ]
    if primary == METHOD_NW:
        common.append(
            "Bartlett Newey-West at lag 721 with a normal one-sided critical value is an adequate reference for this sample size."
        )
    elif primary == METHOD_BOOT:
        common.append(
            "Non-overlapping 1440-hour residual blocks, split on years and the structural gap, approximate the null distribution of delta."
        )
    return common


def _decision_note(decision: str, primary: str | None, power_view: Mapping[str, Any]) -> str:
    if decision == "DEPENDENCE_VALID_DESIGN_READY_FOR_PREREG":
        return (
            f"Primary method `{primary}` passed the type-I rule on every null "
            "regime and the predeclared dependence-aware power rule. The next "
            "unit may freeze the preregistration. It may not open the target "
            "inside that freeze."
        )
    if decision == "DEPENDENCE_ROBUST_POWER_INSUFFICIENT":
        return (
            f"Primary method `{primary}` passed type I and failed the power rule. "
            f"Full-effect joint power by regime: {dict(power_view)}."
        )
    if decision == "NO_VALID_EQUIVALENT_INFERENCE_DESIGN":
        return (
            "Primary NW721 did not keep every null regime's Wilson 95% upper "
            "bound at or below 0.06. The block bootstrap is not a fallback gate. "
            "No confirmation preregistration is authorized."
        )
    return "No equivalent procedure met the support minimum."


def write_artifacts(payload: Mapping[str, Any]) -> None:
    from scripts.research.d7_bitmex_support_and_power_v0 import repo_root

    root = repo_root()
    json_path = root / "docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.json"
    md_path = root / "docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.md"
    json_path.write_text(canonical_json(payload), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def main() -> None:
    if int(D7_TEMPORAL_YEARS_REQUIRED) != 3:
        raise DesignError("TEMPORAL_COUNT_CHANGED")
    if TEMPORAL_POSITIVE_YEARS_REQUIRED != 2 or TEMPORAL_GATE_YEARS != (2017, 2018, 2019):
        raise DesignError("TEMPORAL_AMENDMENT")
    if TYPE_I_CEILING != 0.06 or ALPHA != 0.05:
        raise DesignError("TYPE_I_CEILING")
    if AMENDMENT_MASTER_SEED == REVIEWED_CALIBRATION_SEED:
        raise DesignError("SEED_REUSED")
    if N_OUTER < 5000 or N_BOOT_OUTER < 5000:
        raise DesignError("SIMULATION_COUNT")
    if not math.isclose(REGIME_P_HIGH * 0.5 + REGIME_P_LOW * 0.5, BINANCE_MU_D7_CONTROL):
        raise DesignError("REGIME_MEAN")
    design, support_table, pin = load_real_predictor_design()
    print(
        f"design K={design.k_total} c={design.scale_c:.6f} blocks={design.effective_blocks}",
        flush=True,
    )
    hac = run_hac_study(design)
    boot = run_bootstrap_study(design)
    payload = build_payload(design, pin, hac, boot, support_table)
    write_artifacts(payload)
    print(canonical_json({
        "DECISION": payload["DECISION"],
        "PRIMARY": payload["PRIMARY_INFERENCE_METHOD"],
        "NEXT_UNIT": payload["NEXT_UNIT"],
        "POWER_FULL_EFFECT": payload["POWER_FIELDS"]["POWER_FULL_EFFECT"],
        "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
    }))


if __name__ == "__main__":
    main()
