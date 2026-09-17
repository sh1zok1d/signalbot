"""V3 confirmatory calibration -- literal implementation of the frozen prereg.

Authority (binding, not chosen here):
``docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md`` / ``.json``
at commit ``543687fe79ba2e6254e879b0574e58a1909c15fe``, frozen by
``HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.md`` / ``.json`` at
commit ``fd21ed7f8cf8279d367d7a7cf3f1740398d73883``.

This module implements one frozen claim (the F03 oracle candidate) against
one frozen per-world confirmatory decision. It does not execute the
canonical 400-world-per-cell acceptance grid, create a reservation, or mint
a RESULT -- ``aggregate_verdict`` is provided as pure, unexecuted machinery
for that later, separately-authorized unit.

Frozen primitives reused unmodified from
``harness_synthetic_edge_calibration_v1_lib.py`` (SHA256
``12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51``, not
edited by this module): ``simulate_dgp``, ``world_identity``, ``world_seed``,
``pcg64_generator``, ``candidate_features``, ``expanding_era_predictions``,
``era_slices``, ``scored_mask``, ``ae_metrics``, ``IncompleteWorld``, and
constants ``SCORED_ERAS``/``ERA_NAMES``. RNG for the new
``"V3_CONFIRMATORY"`` namespace comes only from
``harness_synthetic_edge_calibration_v3_rng.py`` (``v3_namespace_seed``);
``harness_synthetic_edge_calibration_v1_lib.py``'s own ``NAMESPACES``
allowlist and ``namespace_seed()`` are never touched.

``era_blocks``/``resample_era_rows`` (V1's fixed non-overlapping block
partition) are not used: the frozen stationary-bootstrap algorithm (prereg
section 7) draws blocks at arbitrary, uniformly-random start positions with
geometric lengths, which a fixed partition cannot represent. ``ae_metrics``
is used only for its finite-computation guard and its
``RELATIVE_MAE_IMPROVEMENT`` output, reused as the required non-authoritative
materiality diagnostic (prereg section 12); it does not feed the primary
squared-error estimand.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    ERA_NAMES,
    SCORED_ERAS,
    IncompleteWorld,
    ae_metrics,
    candidate_features,
    era_slices,
    expanding_era_predictions,
    pcg64_generator,
    scored_mask,
    simulate_dgp,
    world_identity,
    world_seed,
)
from scripts.research.harness_synthetic_edge_calibration_v3_rng import (
    v3_namespace_seed,
)

# =============================================================================
# Frozen constants (bound by the prereg; not chosen here).
# =============================================================================

V3_CANDIDATE_FEATURE_ID = "F03"
V3_STATIONARY_BOOTSTRAP_REPLICATES = 999  # prereg section 7 (B)
V3_ALPHA_ONE_SIDED = 0.05
V3_SUPPORT_COUNT_MIN = 50
V3_SE_DDOF = 1  # Amendment 001

V3_WORLD_INDEX_START = 10000
V3_WORLD_INDEX_END = 10399  # inclusive
V3_FRESH_WORLD_COUNT_PER_SCENARIO = 400
V3_PRIMARY_SCENARIOS = ("EASY", "MODERATE", "NULL", "NONSTATIONARY_TRAP")

V3_WILSON_Z_ONE_SIDED = 1.6448536269514722

V3_AGGREGATE_TARGETS: dict[str, dict[str, Any]] = {
    "EASY": {"kind": "power_min", "value": 0.90},
    "MODERATE": {"kind": "power_min", "value": 0.70},
    "NULL": {"kind": "fpr_max", "value": 0.05},
    "NONSTATIONARY_TRAP": {"kind": "detect_max", "value": 0.20},
}

VALIDITY_CHRONOLOGY = "CHRONOLOGY"
VALIDITY_SUPPORT = "SUPPORT_VALIDITY"
VALIDITY_IDENTIFIABILITY = "IDENTIFIABILITY_AND_RESAMPLING_VALIDITY"
VALIDITY_GUARDS = (VALIDITY_CHRONOLOGY, VALIDITY_SUPPORT, VALIDITY_IDENTIFIABILITY)


class V3WorldInvalid(RuntimeError):
    """A V3 world failed one of the three frozen per-world validity guards."""

    def __init__(self, guard: str, reason: str) -> None:
        if guard not in VALIDITY_GUARDS:
            raise ValueError(f"unknown validity guard {guard!r}")
        super().__init__(f"{guard}: {reason}")
        self.guard = guard
        self.reason = reason


def is_fresh_v3_world_index(world_index: int) -> bool:
    """True iff ``world_index`` is inside the frozen canonical acceptance range.

    Diagnostic/guard helper only -- this module does not refuse to evaluate a
    canonical index (it must be able to, once ARMed); it is used by tests to
    assert their own disposable identities never collide with it.
    """
    return V3_WORLD_INDEX_START <= world_index <= V3_WORLD_INDEX_END


# =============================================================================
# Section 5: loss, Clark-West adjustment, estimand.
# =============================================================================


@dataclass(frozen=True)
class ScoredDifferential:
    d: np.ndarray  # raw squared-error differential, diagnostic only
    d_star: np.ndarray  # Clark-West-adjusted differential, primary
    support: np.ndarray  # S_t on scored rows, float64 {0,1}
    era_index: np.ndarray  # 0..3 for E2..E5, aligned to scored rows


def _candidate_predictions(
    world: Mapping[str, np.ndarray], feature_id: str, n_rows: int
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    feats = candidate_features(world)
    feature = feats[feature_id]
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    preds = expanding_era_predictions(y, x1, x2, feature, n_rows)
    return y, preds


def _scored_differential(
    world: Mapping[str, np.ndarray], y: np.ndarray, preds: Mapping[str, np.ndarray], n_rows: int
) -> ScoredDifferential:
    mask = scored_mask(n_rows)
    base = np.asarray(preds["BASE_PRED"], dtype=np.float64)
    cand = np.asarray(preds["CAND_PRED"], dtype=np.float64)
    y_s = y[mask]
    base_s = base[mask]
    cand_s = cand[mask]
    if not (np.all(np.isfinite(base_s)) and np.all(np.isfinite(cand_s))):
        raise V3WorldInvalid(VALIDITY_IDENTIFIABILITY, "non-finite BASE_PRED/CAND_PRED on scored rows")

    e_base = y_s - base_s
    e_cand = y_s - cand_s
    d = e_base**2 - e_cand**2  # diagnostic only, prereg section 5
    adj_term = (base_s - cand_s) ** 2  # (yhat_B,t - yhat_C,t)^2
    d_star = e_base**2 - (e_cand**2 - adj_term)  # Clark-West-adjusted, primary
    if not (np.all(np.isfinite(d)) and np.all(np.isfinite(d_star))):
        raise V3WorldInvalid(VALIDITY_IDENTIFIABILITY, "non-finite loss differential")

    s = np.asarray(world["S"], dtype=np.float64)[mask]

    era_index = np.zeros(mask.sum(), dtype=np.int64)
    width = n_rows // 5
    for era_i, era_name in enumerate(SCORED_ERAS):
        start = era_i * width
        era_index[start : start + width] = era_i

    return ScoredDifferential(d=d, d_star=d_star, support=s, era_index=era_index)


def compute_theta_hat(support: np.ndarray, d_star: np.ndarray) -> float:
    """theta_hat = sum_t(S_t * d*_t) / sum_t(S_t), prereg section 5."""
    denom = float(np.sum(support))
    if denom <= 0:
        raise V3WorldInvalid(VALIDITY_SUPPORT, "support_count is zero")
    return float(np.sum(support * d_star) / denom)


# =============================================================================
# Section 6: support validity / effective_N (Geyer paired-lag truncation,
# the "EFFECTIVE_SUPPORT_N" formula already frozen in
# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json's metrics block:
# "N_positive/(1+2*sum rho_k); rho pairs included only while adjacent pair
# sum remains positive; first nonpositive pair and later lags excluded; if
# none then all estimable positive-pair lags; cap [1,N_positive]").
# =============================================================================


def _biased_autocorrelations(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    eps = x - x.mean()
    gamma0 = float(eps @ eps) / n
    if not math.isfinite(gamma0) or gamma0 <= 0:
        return np.array([], dtype=np.float64)
    max_lag = n - 1
    rhos = np.empty(max_lag, dtype=np.float64)
    for k in range(1, max_lag + 1):
        gamma_k = float(eps[k:] @ eps[: n - k]) / n
        rhos[k - 1] = gamma_k / gamma0
    return rhos


def effective_support_n(support: np.ndarray, support_count: int) -> float | None:
    """Geyer-style initial-positive-pair-sequence effective sample size.

    Diagnostic and range-validity only (prereg section 6): never a
    confirmatory power veto. Returns None if it cannot be computed.
    """
    rhos = _biased_autocorrelations(support)
    total = 0.0
    k = 0
    while k + 1 < rhos.shape[0]:
        pair_sum = float(rhos[k] + rhos[k + 1])
        if not math.isfinite(pair_sum) or pair_sum <= 0:
            break
        total += pair_sum
        k += 2
    denom = 1.0 + 2.0 * total
    if not math.isfinite(denom) or denom <= 0:
        return None
    raw = support_count / denom
    if not math.isfinite(raw):
        return None
    return float(min(max(raw, 1.0), support_count))


# =============================================================================
# Section 7: block-length selector -- literal port of arch==8.0.0
# arch.bootstrap.base._single_optimal_block's stationary-bootstrap branch
# (b_sb / d_sb / c=2 only; the circular-bootstrap branch is not computed).
# =============================================================================


def optimal_stationary_block_length(x: np.ndarray) -> float:
    """b_hat_SB per prereg section 7. NaN on any degenerate condition;
    callers must treat non-finite/<=0 output as world INVALID."""
    x = np.asarray(x, dtype=np.float64)
    nobs = x.shape[0]
    if nobs <= 1:
        return float("nan")
    with np.errstate(divide="ignore", invalid="ignore"):
        eps = x - x.mean(0)
        try:
            log10_nobs = math.log10(nobs)
        except ValueError:
            return float("nan")
        b_max = math.ceil(min(3.0 * math.sqrt(nobs), nobs / 3.0))
        kn = max(5, int(log10_nobs))
        m_max = int(math.ceil(math.sqrt(nobs))) + kn
        cv = 2.0 * math.sqrt(log10_nobs / nobs)

        acv = np.zeros(m_max + 1, dtype=np.float64)
        abs_acorr = np.zeros(m_max + 1, dtype=np.float64)
        opt_m: int | None = None
        for i in range(m_max + 1):
            v1 = eps[i + 1 :] @ eps[i + 1 :]
            v2 = eps[: -(i + 1)] @ eps[: -(i + 1)]
            cross_prod = eps[i:] @ eps[: nobs - i]
            acv[i] = cross_prod / nobs
            abs_acorr[i] = np.abs(cross_prod) / np.sqrt(v1 * v2)
            if i >= kn:
                window = abs_acorr[i - kn : i]
                if opt_m is None and np.all(np.isfinite(window)) and np.all(window < cv):
                    opt_m = i - kn
        m = 2 * max(opt_m, 1) if opt_m is not None else m_max
        m = min(m, m_max)
        if m < 1:
            return float("nan")

        g = 0.0
        lr_acv = acv[0]
        for k in range(1, m + 1):
            lam = 1.0 if (k / m) <= 0.5 else 2.0 * (1.0 - k / m)
            g += 2.0 * lam * k * acv[k]
            lr_acv += 2.0 * lam * acv[k]

        d_sb = 2.0 * lr_acv**2
        if not math.isfinite(d_sb) or d_sb <= 0:
            return float("nan")
        b_sb = ((2.0 * g**2) / d_sb) ** (1.0 / 3.0) * nobs ** (1.0 / 3.0)
        if not math.isfinite(b_sb) or b_sb <= 0:
            return float("nan")
        return float(min(b_sb, b_max))


def block_continuation_probability(b_hat: float, n_e: int) -> float:
    """p = 1 / round(clamp(b_hat, 1, n_e)) -- the per-era clamp, distinct
    from optimal_stationary_block_length's own internal b_max cap."""
    clamped = min(max(b_hat, 1.0), float(n_e))
    return 1.0 / round(clamped)


# =============================================================================
# Section 7: full-time-axis joint stationary bootstrap.
# =============================================================================


def _draw_era_block_indices(
    n_e: int, p: float, rng: np.random.Generator
) -> np.ndarray:
    """One replicate's resampled row indices (0..n_e-1) for one era, drawn by
    stationary-bootstrap blocks with circular wrap WITHIN this era only."""
    picked: list[int] = []
    while len(picked) < n_e:
        start = int(rng.integers(0, n_e))
        length = int(rng.geometric(p))
        for j in range(length):
            picked.append((start + j) % n_e)
            if len(picked) >= n_e:
                break
    return np.asarray(picked[:n_e], dtype=np.int64)


@dataclass(frozen=True)
class BootstrapEvidence:
    b_hat: float
    theta_star: np.ndarray  # length V3_STATIONARY_BOOTSTRAP_REPLICATES
    se_hat: float
    t_obs: float
    t_star: np.ndarray
    p_one_sided: float


def run_stationary_bootstrap(
    diff: ScoredDifferential,
    theta_hat: float,
    *,
    world_seed_int: int,
    feature_id: str,
    replicates: int = V3_STATIONARY_BOOTSTRAP_REPLICATES,
) -> BootstrapEvidence:
    n_scored = diff.d_star.shape[0]
    n_eras = len(SCORED_ERAS)
    if n_scored % n_eras != 0:
        raise V3WorldInvalid(VALIDITY_IDENTIFIABILITY, "scored rows not divisible into equal eras")
    width = n_scored // n_eras

    z_t = diff.support * (diff.d_star - theta_hat)  # full time axis, S=0 rows are zero
    b_hat = optimal_stationary_block_length(z_t)
    if not math.isfinite(b_hat) or b_hat <= 0:
        raise V3WorldInvalid(VALIDITY_IDENTIFIABILITY, f"block-length selector returned invalid b_hat={b_hat!r}")

    era_d_star = [diff.d_star[i * width : (i + 1) * width] for i in range(n_eras)]
    era_support = [diff.support[i * width : (i + 1) * width] for i in range(n_eras)]
    era_p = [block_continuation_probability(b_hat, width) for _ in range(n_eras)]

    rng = pcg64_generator(v3_namespace_seed(world_seed_int, feature_id))

    theta_star = np.empty(replicates, dtype=np.float64)
    for b in range(replicates):
        support_sum = 0.0
        numer_sum = 0.0
        for era_i in range(n_eras):
            idx = _draw_era_block_indices(width, era_p[era_i], rng)
            support_sum += float(np.sum(era_support[era_i][idx]))
            numer_sum += float(np.sum(era_support[era_i][idx] * era_d_star[era_i][idx]))
        if support_sum <= 0:
            raise V3WorldInvalid(
                VALIDITY_IDENTIFIABILITY, f"bootstrap replicate {b} has zero resampled support"
            )
        theta_star[b] = numer_sum / support_sum

    se_hat = float(np.std(theta_star, ddof=V3_SE_DDOF))
    if not math.isfinite(se_hat) or se_hat <= 0:
        raise V3WorldInvalid(VALIDITY_IDENTIFIABILITY, f"SE_hat is degenerate ({se_hat!r})")

    t_obs = theta_hat / se_hat
    t_star = (theta_star - theta_hat) / se_hat
    p_one_sided = (1.0 + float(np.sum(t_star >= t_obs))) / (replicates + 1.0)

    return BootstrapEvidence(
        b_hat=b_hat,
        theta_star=theta_star,
        se_hat=se_hat,
        t_obs=t_obs,
        t_star=t_star,
        p_one_sided=p_one_sided,
    )


# =============================================================================
# Per-world evaluation and record.
# =============================================================================


@dataclass(frozen=True)
class V3WorldRecord:
    scenario: str
    n_rows: int
    world_index: int
    world_id: str
    feature_id: str
    world_valid: bool
    validity_guard_failed: str | None = None
    validity_reason: str | None = None

    support_count: int | None = None
    support_fraction: float | None = None
    support_run_count: int | None = None
    effective_n: float | None = None

    theta_hat: float | None = None
    unconditional_effect: float | None = None
    era_effects: dict[str, float] = field(default_factory=dict)

    b_hat: float | None = None
    se_hat: float | None = None
    t_obs: float | None = None
    p_one_sided: float | None = None

    relative_mae_improvement: float | None = None

    detected: bool | None = None


def _support_runs(support: np.ndarray) -> int:
    s = support.astype(np.int64)
    if s.shape[0] == 0:
        return 0
    diffs = np.diff(s)
    runs = int(np.sum(diffs == 1))
    if s[0] == 1:
        runs += 1
    return runs


def evaluate_v3_world(
    scenario_id: str,
    n_rows: int,
    world_index: int,
    *,
    feature_id: str = V3_CANDIDATE_FEATURE_ID,
) -> V3WorldRecord:
    """One full frozen V3 confirmatory evaluation for one world.

    Never raises for a scientifically-invalid world: returns a record with
    ``world_valid=False`` and the failing guard/reason instead, matching
    existing project convention (WORLD_INVALID stays in the denominator).
    """
    expected_id = world_identity(scenario_id, n_rows, world_index)
    try:
        world = simulate_dgp(scenario_id=scenario_id, n_rows=n_rows, world_index=world_index)
        got_id = str(world["world_identity"])
        if got_id != expected_id:
            raise V3WorldInvalid(VALIDITY_CHRONOLOGY, f"world_identity {got_id!r} != expected {expected_id!r}")

        y, preds = _candidate_predictions(world, feature_id, n_rows)
        diff = _scored_differential(world, y, preds, n_rows)

        support_count = int(np.sum(diff.support))
        if support_count < V3_SUPPORT_COUNT_MIN:
            raise V3WorldInvalid(
                VALIDITY_SUPPORT, f"support_count={support_count} < {V3_SUPPORT_COUNT_MIN}"
            )
        eff_n = effective_support_n(diff.support, support_count)
        if eff_n is None or not (1.0 <= eff_n <= support_count):
            raise V3WorldInvalid(VALIDITY_SUPPORT, f"effective_N invalid or out of range: {eff_n!r}")

        theta_hat = compute_theta_hat(diff.support, diff.d_star)

        w_seed = int(world_seed(expected_id))
        evidence = run_stationary_bootstrap(
            diff, theta_hat, world_seed_int=w_seed, feature_id=feature_id
        )

        era_effects = {}
        width = diff.d_star.shape[0] // len(SCORED_ERAS)
        for era_i, era_name in enumerate(SCORED_ERAS):
            era_effects[era_name] = float(
                np.mean(diff.d_star[era_i * width : (era_i + 1) * width])
            )
        unconditional_effect = float(np.mean(diff.d_star))

        mask = scored_mask(n_rows)
        rel_mae = None
        try:
            metrics = ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], mask)
            rel_mae = float(metrics["RELATIVE_MAE_IMPROVEMENT"])
        except IncompleteWorld as exc:
            raise V3WorldInvalid(VALIDITY_IDENTIFIABILITY, f"ae_metrics: {exc}") from exc

        detected = bool(
            theta_hat > 0.0 and evidence.p_one_sided <= V3_ALPHA_ONE_SIDED
        )

        return V3WorldRecord(
            scenario=scenario_id,
            n_rows=n_rows,
            world_index=world_index,
            world_id=expected_id,
            feature_id=feature_id,
            world_valid=True,
            support_count=support_count,
            support_fraction=support_count / diff.support.shape[0],
            support_run_count=_support_runs(diff.support),
            effective_n=eff_n,
            theta_hat=theta_hat,
            unconditional_effect=unconditional_effect,
            era_effects=era_effects,
            b_hat=evidence.b_hat,
            se_hat=evidence.se_hat,
            t_obs=evidence.t_obs,
            p_one_sided=evidence.p_one_sided,
            relative_mae_improvement=rel_mae,
            detected=detected,
        )
    except IncompleteWorld as exc:
        # IncompleteWorld covers several distinct frozen V1 failure messages:
        # "lookahead: ..." is a genuine chronology violation; everything else
        # ("design is not full rank", "non-finite coefficients/predictions",
        # "non-finite AE", "relative MAE undefined") is rank-deficiency or a
        # non-finite required statistic, i.e. guard 3, not guard 1.
        guard = VALIDITY_CHRONOLOGY if "lookahead" in str(exc) else VALIDITY_IDENTIFIABILITY
        return V3WorldRecord(
            scenario=scenario_id,
            n_rows=n_rows,
            world_index=world_index,
            world_id=expected_id,
            feature_id=feature_id,
            world_valid=False,
            validity_guard_failed=guard,
            validity_reason=str(exc),
        )
    except V3WorldInvalid as exc:
        return V3WorldRecord(
            scenario=scenario_id,
            n_rows=n_rows,
            world_index=world_index,
            world_id=expected_id,
            feature_id=feature_id,
            world_valid=False,
            validity_guard_failed=exc.guard,
            validity_reason=exc.reason,
        )


# =============================================================================
# Section 11: aggregate Monte Carlo acceptance -- pure machinery, not executed
# against canonical evidence by this unit.
# =============================================================================


def one_sided_wilson_bounds(x: int, n: int, z: float = V3_WILSON_Z_ONE_SIDED) -> tuple[float, float]:
    phat = x / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z / denom * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return center - half, center + half


def aggregate_verdict(cell: str, detected_count: int, planned_count: int = 400) -> str:
    """PASS/FAIL/INDETERMINATE per prereg section 11. Not invoked against
    canonical evidence by this implementation unit."""
    if cell not in V3_AGGREGATE_TARGETS:
        raise ValueError(f"unknown cell {cell!r}")
    target = V3_AGGREGATE_TARGETS[cell]
    lower, upper = one_sided_wilson_bounds(detected_count, planned_count)
    value = target["value"]
    if target["kind"] == "power_min":
        if lower >= value:
            return "PASS"
        if upper < value:
            return "FAIL"
        return "INDETERMINATE"
    # "fpr_max" or "detect_max": same ceiling convention
    if upper <= value:
        return "PASS"
    if lower > value:
        return "FAIL"
    return "INDETERMINATE"
