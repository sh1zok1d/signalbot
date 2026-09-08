"""Fixture-only machinery for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Implements the frozen prereg instrument. Production 3200-world execution is
not authorized and has no callable path. Tiny fixture configs are structurally
separate from frozen production authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

UNIT_ID = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1"
PREREG_JSON_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "research"
    / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
)
PREREG_MD_PATH = PREREG_JSON_PATH.with_suffix(".md")

WILSON_Z = 1.959963984540054
MATERIALITY_GATE = 0.02
PRODUCTION_BOOTSTRAP_REPLICATES = 500
PRODUCTION_PLACEBO_REPLICATES = 999
PRODUCTION_VISIBILITY_REPLICATES = 500
PRODUCTION_BLOCK_ROWS = 50
PRODUCTION_PRIMARY_N = 5000
PRODUCTION_SMALL_N = (2500, 10000)
PRODUCTION_WORLDS_PER_CELL = 400
PRODUCTION_PLANNED_TOTAL_WORLDS = 3200
FIXTURE_MAX_N_ROWS = 500
FIXTURE_MAX_REPLICATES = 50
ROOT_SEED = 20260908
RHO = 0.90
SUPPORT_SANITY_MIN = 50
NAMESPACES = ("DGP", "BOOTSTRAP", "PLACEBO", "VISIBILITY")
FEATURE_IDS = tuple(f"F{i:02d}" for i in range(1, 11))
TRUE_FEATURES = frozenset({"F03"})
PROXY_FEATURES = frozenset({"F01", "F02", "F08"})
FALSE_FEATURES = frozenset({"F04", "F05", "F06", "F07", "F09", "F10"})
SCORED_ERAS = ("E2", "E3", "E4", "E5")
ERA_NAMES = ("E1", "E2", "E3", "E4", "E5")
CONCLUSION_PRIORITY = (
    "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
    "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06",
    "METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06",
    "CALIBRATION_INDETERMINATE",
    "DISCOVERY_BOTTLENECK_BEFORE_B2_06",
    "VISIBILITY_FLOOR",
    "MODEL_FLOOR",
    "MATERIALITY_ONLY_DIAGNOSTIC",
    "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK",
)

PASS = "PASS"
FAIL = "FAIL"
INDETERMINATE = "INDETERMINATE"

_PREREG_CACHE: dict[str, Any] | None = None


class SyntheticExecutionNotAuthorized(RuntimeError):
    """Production synthetic calibration is not authorized."""

    def __init__(self, message: str = "SYNTHETIC_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


class IncompleteWorld(RuntimeError):
    """A world is numerically invalid and must remain in the denominator."""


def load_frozen_prereg() -> dict[str, Any]:
    global _PREREG_CACHE
    if _PREREG_CACHE is None:
        _PREREG_CACHE = json.loads(PREREG_JSON_PATH.read_text(encoding="utf-8"))
    return _PREREG_CACHE


def frozen_boundaries() -> dict[str, bool]:
    return dict(load_frozen_prereg()["boundaries"])


def frozen_production_authority() -> dict[str, Any]:
    prereg = load_frozen_prereg()
    return {
        "unit_id": UNIT_ID,
        "root_seed": int(prereg["rng_authority"]["root_seed"]),
        "rho": float(prereg["dgp"]["mechanism"]["rho"]),
        "primary_N": int(prereg["sample_sizes"]["primary_N"]),
        "small_sensitivity_N": list(prereg["sample_sizes"]["small_sensitivity_N"]),
        "bootstrap_replicates": int(prereg["bootstrap"]["replicates"]),
        "visibility_replicates": int(prereg["ground_truth_visibility"]["bootstrap_replicates"]),
        "placebo_replicates": int(prereg["placebo"]["replicates"]),
        "block_rows": int(prereg["bootstrap"]["block_rows"]),
        "worlds_per_primary_scenario": int(prereg["monte_carlo"]["worlds_per_primary_scenario"]),
        "planned_total_worlds": int(prereg["monte_carlo"]["planned_total_worlds"]),
        "materiality_gate": MATERIALITY_GATE,
        "wilson_z": WILSON_Z,
        "support_sanity_min": SUPPORT_SANITY_MIN,
        "synthetic_execution_authorized": False,
        "production_calibration_executed": False,
        "implementation_exists": True,
    }


def _uint64_from_digest(digest: bytes) -> int:
    return int.from_bytes(digest[:8], "big", signed=False)


def world_identity(scenario_id: str, n_rows: int, world_index: int) -> str:
    if world_index < 0:
        raise ValueError("world_index is zero-based and must be >= 0")
    return f"{UNIT_ID}|{scenario_id}|{n_rows}|{world_index}"


def world_seed(identity: str, *, root_seed: int = ROOT_SEED) -> int:
    payload = f"{root_seed}|{identity}".encode("utf-8")
    return _uint64_from_digest(hashlib.sha256(payload).digest())


def namespace_seed(
    world_seed_int: int,
    namespace: str,
    *context: object,
) -> int:
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown namespace {namespace!r}")
    parts = [str(world_seed_int), namespace, *[str(item) for item in context]]
    payload = "|".join(parts).encode("utf-8")
    return _uint64_from_digest(hashlib.sha256(payload).digest())


def pcg64_generator(seed_int: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(int(seed_int)))


def scenario_by_id(scenario_id: str) -> dict[str, Any]:
    for item in load_frozen_prereg()["scenarios"]:
        if item["id"] == scenario_id:
            return item
    raise KeyError(scenario_id)


def p01(target_support: float, rho: float = RHO) -> float:
    if target_support >= 1.0:
        raise ValueError("target_support must be < 1")
    return float(target_support) * (1.0 - float(rho)) / (1.0 - float(target_support))


def era_slices(n_rows: int) -> dict[str, slice]:
    if n_rows % 5 != 0:
        raise ValueError("N must be divisible by 5")
    width = n_rows // 5
    return {name: slice(i * width, (i + 1) * width) for i, name in enumerate(ERA_NAMES)}


def era_name_for_index(index: int, n_rows: int) -> str:
    width = n_rows // 5
    return ERA_NAMES[index // width]


def beta_series(scenario: Mapping[str, Any], n_rows: int) -> np.ndarray:
    slices = era_slices(n_rows)
    out = np.zeros(n_rows, dtype=np.float64)
    if "beta_by_era" in scenario:
        for name, slc in slices.items():
            out[slc] = np.float64(scenario["beta_by_era"][name])
        return out
    out[:] = np.float64(scenario["beta"])
    return out


def simulate_dgp(
    *,
    scenario_id: str,
    n_rows: int,
    world_index: int = 0,
    root_seed: int = ROOT_SEED,
) -> dict[str, np.ndarray]:
    """Simulate one synthetic world.

    Frozen PCG64 consumption on the DGP namespace stream, in order:
    ``U1[0:N]``, ``U2[0:N]``, Markov uniforms ``[0:N]``, ``RAW[0:N]``.
    Recurrences use innovation ``t`` for ``t >= 1``. ``X1_0 = X2_0 = ETA_0 = 0``,
    so ``U1[0]``, ``U2[0]``, and ``RAW[0]`` are drawn and unused. ``S_0`` uses
    the first Markov uniform against Bernoulli(p).
    """
    scenario = scenario_by_id(scenario_id)
    identity = world_identity(scenario_id, n_rows, world_index)
    seed = world_seed(identity, root_seed=root_seed)
    rng = pcg64_generator(namespace_seed(seed, "DGP"))
    n = int(n_rows)
    u1 = rng.standard_normal(n).astype(np.float64)
    u2 = rng.standard_normal(n).astype(np.float64)
    s_unif = rng.random(n).astype(np.float64)
    raw = (rng.standard_t(5, size=n) / np.sqrt(5.0 / 3.0)).astype(np.float64)

    x1 = np.zeros(n, dtype=np.float64)
    x2 = np.zeros(n, dtype=np.float64)
    s_phi_1 = np.sqrt(1.0 - 0.70**2)
    s_phi_2 = np.sqrt(1.0 - 0.40**2)
    for t in range(1, n):
        x1[t] = 0.70 * x1[t - 1] + s_phi_1 * u1[t]
        x2[t] = 0.40 * x2[t - 1] + s_phi_2 * u2[t]

    p = float(scenario["target_support"])
    trans01 = p01(p, RHO)
    s = np.zeros(n, dtype=np.float64)
    s[0] = 1.0 if s_unif[0] < p else 0.0
    for t in range(1, n):
        prob = RHO if s[t - 1] == 1.0 else trans01
        s[t] = 1.0 if s_unif[t] < prob else 0.0

    eta = np.zeros(n, dtype=np.float64)
    s_eta = np.sqrt(1.0 - 0.25**2)
    for t in range(1, n):
        eta[t] = 0.25 * eta[t - 1] + s_eta * raw[t]
    sigma = (1.0 + 0.30 * np.abs(x1)).astype(np.float64)
    noise = sigma * eta
    mu_base = (0.20 * x1 - 0.15 * x2).astype(np.float64)
    beta = beta_series(scenario, n)
    y = (mu_base + beta * s + noise).astype(np.float64)
    return {
        "t": np.arange(n, dtype=np.int64),
        "X1": x1,
        "X2": x2,
        "S": s,
        "U1": u1,
        "U2": u2,
        "RAW": raw,
        "ETA": eta,
        "SIGMA": sigma,
        "NOISE": noise,
        "MU_BASE": mu_base,
        "beta": beta,
        "Y": y,
        "world_identity": np.array(identity),
        "world_seed": np.array(seed, dtype=np.uint64),
    }


def candidate_features(world: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    s = np.asarray(world["S"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    f01 = np.zeros_like(s)
    f01[1:] = s[:-1]
    feats = {
        "F01": f01,
        "F02": s * (x1 > 0.0).astype(np.float64),
        "F03": s.copy(),
        "F04": (x1 > 0.0).astype(np.float64),
        "F05": (x2 > 0.0).astype(np.float64),
        "F06": (x1 > 1.0).astype(np.float64),
        "F07": (x2 < -1.0).astype(np.float64),
        "F08": s * (x2 > 0.0).astype(np.float64),
        "F09": ((x1 + x2) > 0.0).astype(np.float64),
        "F10": ((x1 - x2) > 0.0).astype(np.float64),
    }
    if set(feats) != set(FEATURE_IDS):
        raise RuntimeError("candidate library drifted")
    return feats


def taxonomy_of(feature_id: str | None) -> str:
    if feature_id is None or feature_id == "NO_CANDIDATE":
        return "NO_DISCOVERY"
    if feature_id in TRUE_FEATURES:
        return "TRUE_DISCOVERY"
    if feature_id in PROXY_FEATURES:
        return "PROXY_DISCOVERY"
    if feature_id in FALSE_FEATURES:
        return "FALSE_DISCOVERY"
    raise KeyError(feature_id)


def taxonomy_flags(label: str) -> dict[str, bool]:
    return {
        "TRUE_DISCOVERY": label == "TRUE_DISCOVERY",
        "PROXY_DISCOVERY": label == "PROXY_DISCOVERY",
        "FALSE_DISCOVERY": label == "FALSE_DISCOVERY",
        "NO_DISCOVERY": label == "NO_DISCOVERY",
        "ANY_EDGE_DECLARED": label in {"TRUE_DISCOVERY", "PROXY_DISCOVERY", "FALSE_DISCOVERY"},
        "USEFUL_DISCOVERY": label in {"TRUE_DISCOVERY", "PROXY_DISCOVERY"},
    }


def _design_matrix(*cols: np.ndarray) -> np.ndarray:
    n = len(cols[0])
    intercept = np.ones(n, dtype=np.float64)
    return np.column_stack((intercept, *[np.asarray(col, dtype=np.float64) for col in cols]))


def fit_lstsq(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0]:
        raise IncompleteWorld("design shape invalid")
    rank = int(np.linalg.matrix_rank(x))
    if rank < x.shape[1]:
        raise IncompleteWorld("design is not full rank")
    coef, _residuals, _rank, _sv = np.linalg.lstsq(x, y, rcond=None)
    coef = np.asarray(coef, dtype=np.float64)
    if coef.shape[0] != x.shape[1] or not np.all(np.isfinite(coef)):
        raise IncompleteWorld("non-finite coefficients")
    return coef


def predict(x: np.ndarray, coef: np.ndarray) -> np.ndarray:
    pred = np.asarray(x, dtype=np.float64) @ np.asarray(coef, dtype=np.float64)
    if not np.all(np.isfinite(pred)):
        raise IncompleteWorld("non-finite predictions")
    return pred.astype(np.float64)


def expanding_era_predictions(
    y: np.ndarray,
    x1: np.ndarray,
    x2: np.ndarray,
    feature: np.ndarray | None,
    n_rows: int,
) -> dict[str, np.ndarray]:
    """Fit using only prior eras; score the current era. E1 is training-only."""
    slices = era_slices(n_rows)
    base_pred = np.full(n_rows, np.nan, dtype=np.float64)
    cand_pred = np.full(n_rows, np.nan, dtype=np.float64)
    train_end_by_score_era: dict[str, int] = {}
    for era_i, era_name in enumerate(ERA_NAMES):
        if era_i == 0:
            continue
        train = slice(0, slices[era_name].start)
        score = slices[era_name]
        train_end_by_score_era[era_name] = train.stop
        if train.stop > score.start:
            raise IncompleteWorld("lookahead: future era entered earlier fit")
        y_train = y[train]
        x_base_train = _design_matrix(x1[train], x2[train])
        x_base_score = _design_matrix(x1[score], x2[score])
        base_coef = fit_lstsq(x_base_train, y_train)
        base_pred[score] = predict(x_base_score, base_coef)
        if feature is not None:
            x_cand_train = _design_matrix(x1[train], x2[train], feature[train])
            x_cand_score = _design_matrix(x1[score], x2[score], feature[score])
            cand_coef = fit_lstsq(x_cand_train, y_train)
            cand_pred[score] = predict(x_cand_score, cand_coef)
    return {
        "BASE_PRED": base_pred,
        "CAND_PRED": cand_pred,
        "train_end_by_score_era": train_end_by_score_era,  # type: ignore[dict-item]
    }


def scored_mask(n_rows: int) -> np.ndarray:
    mask = np.zeros(n_rows, dtype=bool)
    for name, slc in era_slices(n_rows).items():
        if name in SCORED_ERAS:
            mask[slc] = True
    return mask


def ae_metrics(
    y: np.ndarray,
    base_pred: np.ndarray,
    cand_pred: np.ndarray,
    mask: np.ndarray,
) -> dict[str, float]:
    y_s = y[mask]
    base_ae = np.abs(y_s - base_pred[mask])
    cand_ae = np.abs(y_s - cand_pred[mask])
    if not np.all(np.isfinite(base_ae)) or not np.all(np.isfinite(cand_ae)):
        raise IncompleteWorld("non-finite AE")
    mean_base = float(np.mean(base_ae))
    mean_cand = float(np.mean(cand_ae))
    if mean_base == 0.0:
        raise IncompleteWorld("relative MAE undefined: mean BASE_AE is 0")
    improvement = base_ae - cand_ae
    return {
        "MEAN_AE_IMPROVEMENT": float(np.mean(improvement)),
        "RELATIVE_MAE_IMPROVEMENT": float(1.0 - mean_cand / mean_base),
        "mean_BASE_AE": mean_base,
        "mean_CAND_AE": mean_cand,
    }


def support_diagnostics(
    s: np.ndarray,
    ae_improvement: np.ndarray,
    mask: np.ndarray,
    n_rows: int,
) -> dict[str, Any]:
    s_s = np.asarray(s[mask], dtype=np.float64)
    imp = np.asarray(ae_improvement[mask], dtype=np.float64)
    pos = s_s == 1.0
    n_pos = int(np.sum(pos))
    coverage = float(np.mean(pos)) if s_s.size else float("nan")
    cond = float(np.mean(imp[pos])) if n_pos else float("nan")
    n_off = int(np.sum(~pos))
    off = float(np.mean(imp[~pos])) if n_off else float("nan")
    run_lengths: list[int] = []
    scored_idx = np.flatnonzero(mask)
    current = 0
    prev_index = None
    width = n_rows // 5
    for idx, on in zip(scored_idx, pos):
        era_break = prev_index is not None and (idx // width) != (prev_index // width)
        gap = prev_index is not None and idx != prev_index + 1
        if on and not era_break and not gap:
            current += 1
        else:
            if current:
                run_lengths.append(current)
            current = 1 if on else 0
        prev_index = int(idx)
    if current:
        run_lengths.append(current)
    return {
        "SUPPORT_COVERAGE": coverage,
        "SUPPORT_CONDITIONAL_MEAN_AE_IMPROVEMENT": cond,
        "OFF_SUPPORT_MEAN_AE_IMPROVEMENT": off,
        "SUPPORT_RUN_LENGTHS": tuple(run_lengths),
        "SUPPORT_CLUSTER_COUNT": len(run_lengths),
        "N_positive": n_pos,
        "EFFECTIVE_SUPPORT_N": effective_support_n(s_s),
    }


def sample_acf(series: np.ndarray, lag: int) -> float:
    """Sample autocorrelation at ``lag`` using one series mean and ``c_k / c_0``."""
    x = np.asarray(series, dtype=np.float64)
    n = int(x.size)
    if lag <= 0 or lag >= n:
        return float("nan")
    centered = x - float(np.mean(x))
    c0 = float(np.dot(centered, centered))
    if c0 == 0.0:
        return float("nan")
    ck = float(np.dot(centered[:-lag], centered[lag:]))
    return ck / c0


def effective_support_n(scored_trigger: np.ndarray) -> float:
    s = np.asarray(scored_trigger, dtype=np.float64)
    n_pos = int(np.sum(s == 1.0))
    if n_pos <= 0:
        return float("nan")
    n = int(s.size)
    rhos: list[float] = []
    for lag in range(1, n):
        value = sample_acf(s, lag)
        if not np.isfinite(value):
            break
        rhos.append(value)
    included: list[float] = []
    cutoff = None
    for i in range(len(rhos) - 1):
        if rhos[i] + rhos[i + 1] <= 0.0:
            cutoff = i
            break
    if cutoff is None:
        included = list(rhos)
    else:
        included = list(rhos[:cutoff])
    denom = 1.0 + 2.0 * float(sum(included))
    n_eff = float(n_pos) / denom
    return float(min(max(n_eff, 1.0), float(n_pos)))


def era_blocks(era_length: int, block_rows: int) -> tuple[slice, ...]:
    if block_rows <= 0:
        raise ValueError("block_rows must be positive")
    blocks = []
    start = 0
    while start < era_length:
        stop = min(start + block_rows, era_length)
        blocks.append(slice(start, stop))
        start = stop
    return tuple(blocks)


def resample_era_rows(
    values: np.ndarray,
    block_rows: int,
    rng: np.random.Generator,
) -> np.ndarray | None:
    values = np.asarray(values)
    n = int(values.shape[0])
    blocks = era_blocks(n, block_rows)
    picks = rng.integers(0, len(blocks), size=len(blocks))
    parts = [values[blocks[int(i)]] for i in picks]
    concat = np.concatenate(parts, axis=0)
    if concat.shape[0] < n:
        return None
    return concat[:n]


def linear_quantile(samples: Sequence[float], q: float) -> float:
    arr = np.asarray(list(samples), dtype=np.float64)
    if arr.size == 0 or not np.all(np.isfinite(arr)):
        return float("nan")
    return float(np.quantile(arr, q, method="linear"))


@dataclass(frozen=True)
class FixtureExecutionConfig:
    """Test-only config. Structurally cannot authorize the frozen production grid."""

    n_rows: int
    scenario_id: str
    world_index: int = 0
    visibility_replicates: int = 3
    bootstrap_replicates: int = 3
    placebo_replicates: int = 3
    block_rows: int = 2

    def __post_init__(self) -> None:
        if self.n_rows % 5 != 0:
            raise ValueError("fixture N must be divisible by 5")
        if self.n_rows <= 0:
            raise ValueError("fixture N must be positive")
        if min(self.visibility_replicates, self.bootstrap_replicates, self.placebo_replicates) < 1:
            raise ValueError("fixture replicate counts must be >= 1")
        production_n = {PRODUCTION_PRIMARY_N, *PRODUCTION_SMALL_N}
        over_envelope = (
            self.n_rows > FIXTURE_MAX_N_ROWS
            or self.visibility_replicates > FIXTURE_MAX_REPLICATES
            or self.bootstrap_replicates > FIXTURE_MAX_REPLICATES
            or self.placebo_replicates > FIXTURE_MAX_REPLICATES
        )
        production_n_used = self.n_rows in production_n
        production_replicate = (
            self.visibility_replicates >= PRODUCTION_VISIBILITY_REPLICATES
            or self.bootstrap_replicates >= PRODUCTION_BOOTSTRAP_REPLICATES
            or self.placebo_replicates >= PRODUCTION_PLACEBO_REPLICATES
        )
        if over_envelope or production_n_used or production_replicate:
            raise SyntheticExecutionNotAuthorized(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED"
            )


def _scored_era_values(values: np.ndarray, n_rows: int) -> dict[str, np.ndarray]:
    slices = era_slices(n_rows)
    return {name: values[slices[name]] for name in SCORED_ERAS}


def block_bootstrap_samples(
    *,
    scored_era_values: Mapping[str, np.ndarray],
    replicates: int,
    block_rows: int,
    rng: np.random.Generator,
) -> list[np.ndarray | None]:
    out: list[np.ndarray | None] = []
    for _ in range(replicates):
        parts = []
        valid = True
        for name in SCORED_ERAS:
            resampled = resample_era_rows(scored_era_values[name], block_rows, rng)
            if resampled is None:
                valid = False
                break
            parts.append(resampled)
        out.append(np.concatenate(parts, axis=0) if valid else None)
    return out


def visibility_from_residuals(
    residual: np.ndarray,
    trigger: np.ndarray,
    n_rows: int,
    *,
    replicates: int,
    block_rows: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    stacked = np.column_stack((residual, trigger))
    era_map = _scored_era_values(stacked, n_rows)
    samples = []
    invalid = False
    for draw in block_bootstrap_samples(
        scored_era_values=era_map,
        replicates=replicates,
        block_rows=block_rows,
        rng=rng,
    ):
        if draw is None:
            invalid = True
            continue
        res = draw[:, 0]
        s = draw[:, 1]
        on = s == 1.0
        off = s == 0.0
        if not np.any(on) or not np.any(off):
            invalid = True
            continue
        stat = float(np.mean(res[on]) - np.mean(res[off]))
        if not np.isfinite(stat):
            invalid = True
            continue
        samples.append(stat)
    if invalid or len(samples) != replicates:
        return {
            "GROUND_TRUTH_VISIBLE": False,
            "visibility_invalid": True,
            "visibility_q025": float("nan"),
            "stays_in_denominator": True,
        }
    q025 = linear_quantile(samples, 0.025)
    return {
        "GROUND_TRUTH_VISIBLE": bool(q025 > 0.0),
        "visibility_invalid": False,
        "visibility_q025": q025,
        "stays_in_denominator": True,
    }


def prediction_bootstrap(
    ae_improvement_full: np.ndarray,
    n_rows: int,
    *,
    replicates: int,
    block_rows: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    era_map = _scored_era_values(ae_improvement_full, n_rows)
    samples = []
    invalid = False
    for draw in block_bootstrap_samples(
        scored_era_values=era_map,
        replicates=replicates,
        block_rows=block_rows,
        rng=rng,
    ):
        if draw is None or not np.all(np.isfinite(draw)):
            invalid = True
            continue
        samples.append(float(np.mean(draw)))
    if invalid or len(samples) != replicates:
        return {
            "bootstrap_positive": False,
            "bootstrap_invalid": True,
            "bootstrap_q025": float("nan"),
            "world_invalid": True,
            "stays_in_denominator": True,
        }
    q025 = linear_quantile(samples, 0.025)
    return {
        "bootstrap_positive": bool(q025 > 0.0),
        "bootstrap_invalid": False,
        "bootstrap_q025": q025,
        "world_invalid": False,
        "stays_in_denominator": True,
    }


def placebo_q95(
    *,
    world: Mapping[str, np.ndarray],
    feature: np.ndarray,
    n_rows: int,
    replicates: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    slices = era_slices(n_rows)
    mask = scored_mask(n_rows)
    stats: list[float] = []
    invalid = False
    for _ in range(replicates):
        permuted = np.asarray(feature, dtype=np.float64).copy()
        for slc in slices.values():
            idx = np.arange(slc.start, slc.stop)
            permuted[idx] = permuted[idx][rng.permutation(idx.size)]
        try:
            preds = expanding_era_predictions(y, x1, x2, permuted, n_rows)
            metrics = ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], mask)
            value = metrics["MEAN_AE_IMPROVEMENT"]
        except IncompleteWorld:
            invalid = True
            continue
        if not np.isfinite(value):
            invalid = True
            continue
        stats.append(float(value))
    if invalid or len(stats) != replicates:
        return {
            "placebo_q95": float("nan"),
            "placebo_invalid": True,
            "world_invalid": True,
            "stays_in_denominator": True,
        }
    return {
        "placebo_q95": linear_quantile(stats, 0.95),
        "placebo_invalid": False,
        "world_invalid": False,
        "stays_in_denominator": True,
    }


def era_mean_improvements(
    y: np.ndarray,
    base_pred: np.ndarray,
    cand_pred: np.ndarray,
    n_rows: int,
) -> dict[str, float]:
    slices = era_slices(n_rows)
    out: dict[str, float] = {}
    for name in SCORED_ERAS:
        slc = slices[name]
        base_ae = np.abs(y[slc] - base_pred[slc])
        cand_ae = np.abs(y[slc] - cand_pred[slc])
        out[name] = float(np.mean(base_ae - cand_ae))
    return out


def materiality_fraction_of_attainable(
    observed_relative_mae: float,
    asymptotic_max_relative_mae_improvement_approx: float,
) -> float:
    """Descriptive only. Unavailable when the frozen denominator is <= 0."""
    denom = float(asymptotic_max_relative_mae_improvement_approx)
    numer = float(observed_relative_mae)
    if denom <= 0.0 or not np.isfinite(denom) or not np.isfinite(numer):
        return float("nan")
    return numer / denom


def compose_gates(
    *,
    mean_ae_improvement: float,
    relative_mae_improvement: float,
    bootstrap_positive: bool,
    placebo_separation: bool,
    era_improvements: Mapping[str, float],
    candidate_positive_count: int,
) -> dict[str, bool]:
    primary_positive = bool(mean_ae_improvement > 0.0)
    material_relative_mae = bool(relative_mae_improvement >= MATERIALITY_GATE)
    era_stability = (
        int(sum(1 for name in SCORED_ERAS if era_improvements[name] > 0.0)) >= 3
    )
    support_sanity = bool(
        candidate_positive_count >= SUPPORT_SANITY_MIN and np.isfinite(candidate_positive_count)
    )
    model_detected = primary_positive and bootstrap_positive and placebo_separation
    strict_ex = model_detected and era_stability and support_sanity
    strict = strict_ex and material_relative_mae
    return {
        "primary_positive": primary_positive,
        "material_relative_mae": material_relative_mae,
        "bootstrap_positive": bootstrap_positive,
        "placebo_separation": placebo_separation,
        "era_stability": era_stability,
        "support_sanity": support_sanity,
        "MODEL_DETECTED": model_detected,
        "STRICT_PASS_EX_MATERIALITY": strict_ex,
        "STRICT_PASS": strict,
    }


def select_blind(
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    gate: str,
) -> str:
    eligible = [
        row
        for row in candidate_rows
        if (row.get("gates") or {}).get(gate) is True
    ]
    if not eligible:
        return "NO_CANDIDATE"
    eligible.sort(
        key=lambda row: (-float(row["MEAN_AE_IMPROVEMENT"]), str(row["feature_id"]))
    )
    return str(eligible[0]["feature_id"])


def wilson_interval(successes: int, n: int) -> dict[str, float]:
    if n <= 0:
        raise ValueError("Wilson n must be positive")
    if successes < 0 or successes > n:
        raise ValueError("Wilson successes out of range")
    phat = successes / n
    z = WILSON_Z
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    half = (z / denom) * np.sqrt(phat * (1.0 - phat) / n + z2 / (4.0 * n * n))
    return {
        "n": float(n),
        "successes": float(successes),
        "phat": float(phat),
        "center": float(center),
        "lower": float(center - half),
        "upper": float(center + half),
    }


def specificity_verdict(interval: Mapping[str, float], maximum: float) -> str:
    if interval["upper"] <= maximum:
        return PASS
    if interval["lower"] > maximum:
        return FAIL
    return INDETERMINATE


def power_verdict(interval: Mapping[str, float], minimum: float) -> str:
    if interval["lower"] >= minimum:
        return PASS
    if interval["upper"] < minimum:
        return FAIL
    return INDETERMINATE


def small_band(interval: Mapping[str, float]) -> str:
    lo, hi = interval["lower"], interval["upper"]
    bands = (
        ("HIGH", 0.80, 1.01),
        ("MODERATE", 0.50, 0.80),
        ("LOW", 0.20, 0.50),
        ("VERY_LOW", -0.01, 0.20),
    )
    for name, left, right in bands:
        if lo >= left and hi < right:
            return name
        if name == "HIGH" and lo >= 0.80 and hi <= 1.0 + 1e-15:
            return "HIGH"
        if name == "VERY_LOW" and lo >= 0.0 and hi < 0.20:
            return "VERY_LOW"
    if lo >= 0.80:
        return "HIGH"
    return INDETERMINATE


def mechanical_conclusion(
    *,
    incomplete_execution: bool,
    oracle_null_specificity: str,
    blind_null_specificity: str,
    trap_specificity: str,
    easy_oracle_power: str,
    moderate_oracle_power: str,
    easy_blind_useful: str,
    moderate_blind_useful: str,
    visibility_wilson_upper: float | None = None,
    model_detection_wilson_upper: float | None = None,
    materiality_only_failure: bool = False,
) -> str:
    if incomplete_execution:
        return "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    if FAIL in (oracle_null_specificity, blind_null_specificity, trap_specificity):
        return "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"
    if FAIL in (easy_oracle_power, moderate_oracle_power):
        return "METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06"
    required = (
        oracle_null_specificity,
        blind_null_specificity,
        trap_specificity,
        easy_oracle_power,
        moderate_oracle_power,
        easy_blind_useful,
        moderate_blind_useful,
    )
    if INDETERMINATE in required:
        return "CALIBRATION_INDETERMINATE"
    if FAIL in (easy_blind_useful, moderate_blind_useful):
        return "DISCOVERY_BOTTLENECK_BEFORE_B2_06"
    if visibility_wilson_upper is not None and visibility_wilson_upper < 0.50:
        return "VISIBILITY_FLOOR"
    if model_detection_wilson_upper is not None and model_detection_wilson_upper < 0.50:
        return "MODEL_FLOOR"
    if materiality_only_failure:
        return "MATERIALITY_ONLY_DIAGNOSTIC"
    return "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK"


@dataclass
class WorldEvaluation:
    valid: bool
    stays_in_denominator: bool
    invalid_reasons: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)


def evaluate_fixture_candidate(
    world: Mapping[str, np.ndarray],
    feature_id: str,
    config: FixtureExecutionConfig,
    *,
    include_placebo: bool = True,
    include_bootstrap: bool = True,
) -> WorldEvaluation:
    if not isinstance(config, FixtureExecutionConfig):
        raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")
    n = config.n_rows
    features = candidate_features(world)
    feature = features[feature_id]
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    s = np.asarray(world["S"], dtype=np.float64)
    reasons: list[str] = []
    try:
        preds = expanding_era_predictions(y, x1, x2, feature, n)
        mask = scored_mask(n)
        metrics = ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], mask)
        ae_imp_full = np.full(n, np.nan, dtype=np.float64)
        ae_imp_full[mask] = (
            np.abs(y[mask] - preds["BASE_PRED"][mask])
            - np.abs(y[mask] - preds["CAND_PRED"][mask])
        )
        diag = support_diagnostics(s, ae_imp_full, mask, n)
        era_imp = era_mean_improvements(y, preds["BASE_PRED"], preds["CAND_PRED"], n)
        cand_pos = int(np.sum(feature[mask] == 1.0))
    except IncompleteWorld as exc:
        return WorldEvaluation(
            valid=False,
            stays_in_denominator=True,
            invalid_reasons=(str(exc),),
            payload={"feature_id": feature_id},
        )

    identity = str(world.get("world_identity", world_identity(config.scenario_id, n, config.world_index)))
    wseed = int(world_seed(identity))
    vis = None
    boot = {"bootstrap_positive": False, "bootstrap_invalid": False, "bootstrap_q025": float("nan"), "world_invalid": False}
    plac = {"placebo_q95": float("nan"), "placebo_invalid": False, "world_invalid": False}
    try:
        vis = visibility_from_residuals(
            y - preds["BASE_PRED"],
            s,
            n,
            replicates=config.visibility_replicates,
            block_rows=config.block_rows,
            rng=pcg64_generator(namespace_seed(wseed, "VISIBILITY")),
        )
        # Visibility invalidity is diagnostic-only: GROUND_TRUTH_VISIBLE stays
        # false and visibility_invalid stays true, but the world remains valid.
        if include_bootstrap:
            boot = prediction_bootstrap(
                ae_imp_full,
                n,
                replicates=config.bootstrap_replicates,
                block_rows=config.block_rows,
                rng=pcg64_generator(namespace_seed(wseed, "BOOTSTRAP", feature_id)),
            )
            if boot["world_invalid"]:
                reasons.append("bootstrap_invalid")
        if include_placebo:
            plac = placebo_q95(
                world=world,
                feature=feature,
                n_rows=n,
                replicates=config.placebo_replicates,
                rng=pcg64_generator(namespace_seed(wseed, "PLACEBO", feature_id)),
            )
            if plac["world_invalid"]:
                reasons.append("placebo_invalid")
    except IncompleteWorld as exc:
        return WorldEvaluation(
            valid=False,
            stays_in_denominator=True,
            invalid_reasons=(str(exc),),
            payload={"feature_id": feature_id},
        )

    placebo_sep = (
        (not plac["placebo_invalid"])
        and np.isfinite(plac["placebo_q95"])
        and metrics["MEAN_AE_IMPROVEMENT"] > plac["placebo_q95"]
    )
    scenario = scenario_by_id(config.scenario_id)
    materiality_fraction = materiality_fraction_of_attainable(
        metrics["RELATIVE_MAE_IMPROVEMENT"],
        float(scenario.get("asymptotic_max_relative_mae_improvement_approx", 0.0)),
    )
    gates = compose_gates(
        mean_ae_improvement=metrics["MEAN_AE_IMPROVEMENT"],
        relative_mae_improvement=metrics["RELATIVE_MAE_IMPROVEMENT"],
        bootstrap_positive=bool(boot["bootstrap_positive"]),
        placebo_separation=bool(placebo_sep),
        era_improvements=era_imp,
        candidate_positive_count=cand_pos,
    )
    valid = not reasons
    payload = {
        "feature_id": feature_id,
        "MEAN_AE_IMPROVEMENT": metrics["MEAN_AE_IMPROVEMENT"],
        "RELATIVE_MAE_IMPROVEMENT": metrics["RELATIVE_MAE_IMPROVEMENT"],
        "gates": gates,
        "diagnostics": diag,
        "visibility": vis,
        "bootstrap": boot,
        "placebo": plac,
        "era_improvements": era_imp,
        "candidate_positive_count": cand_pos,
        "train_end_by_score_era": preds["train_end_by_score_era"],
        "MATERIALITY_FRACTION_OF_ATTAINABLE": materiality_fraction,
    }
    return WorldEvaluation(
        valid=valid,
        stays_in_denominator=True,
        invalid_reasons=tuple(reasons),
        payload=payload,
    )


def evaluate_fixture_world(config: FixtureExecutionConfig) -> dict[str, Any]:
    if not isinstance(config, FixtureExecutionConfig):
        raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")
    world = simulate_dgp(
        scenario_id=config.scenario_id,
        n_rows=config.n_rows,
        world_index=config.world_index,
    )
    rows = []
    any_invalid = False
    reasons: list[str] = []
    for feature_id in FEATURE_IDS:
        ev = evaluate_fixture_candidate(world, feature_id, config)
        if not ev.valid:
            any_invalid = True
            reasons.extend(ev.invalid_reasons)
        rows.append({"feature_id": feature_id, **ev.payload, "valid": ev.valid})
    selected_ex = select_blind(rows, gate="STRICT_PASS_EX_MATERIALITY")
    selected_strict = select_blind(rows, gate="STRICT_PASS")
    label = taxonomy_of(None if selected_ex == "NO_CANDIDATE" else selected_ex)
    return {
        "world_identity": str(world["world_identity"]),
        "valid": not any_invalid,
        "stays_in_denominator": True,
        "invalid_reasons": tuple(reasons),
        "candidates": rows,
        "selected_STRICT_PASS_EX_MATERIALITY": selected_ex,
        "selected_STRICT_PASS": selected_strict,
        "taxonomy": label,
        "taxonomy_flags": taxonomy_flags(label),
        "incomplete_execution": any_invalid,
    }


def run_frozen_production_grid(*_args: Any, **_kwargs: Any) -> None:
    raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")


def planned_production_grid_descriptor() -> dict[str, Any]:
    """Describe the frozen grid without executing it."""
    return {
        "planned_total_worlds": PRODUCTION_PLANNED_TOTAL_WORLDS,
        "worlds_per_cell": PRODUCTION_WORLDS_PER_CELL,
        "primary_N": PRODUCTION_PRIMARY_N,
        "small_N": list(PRODUCTION_SMALL_N),
        "callable": False,
        "synthetic_execution_authorized": False,
    }


def implementation_identity() -> dict[str, Any]:
    authority = frozen_production_authority()
    boundaries = frozen_boundaries()
    return {
        "stage": "fixture_implementation_review",
        "unit_id": UNIT_ID,
        "implementation_exists": True,
        "production_calibration_executed": False,
        "synthetic_execution_authorized": False,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "production_bootstrap_replicates": authority["bootstrap_replicates"],
        "production_placebo_replicates": authority["placebo_replicates"],
        "production_visibility_replicates": authority["visibility_replicates"],
        "planned_total_worlds": authority["planned_total_worlds"],
        "boundaries": boundaries,
        "real_data_path": False,
    }
