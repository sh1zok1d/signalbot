"""Generic self-referential smooth-functional contrast.

The primary method is the studentized full-influence dependent wild
bootstrap. Sensitivity is the normal-critical full-influence HAC and does
not change the primary decision.
"""

from __future__ import annotations

from scripts.research.self_referential_contrast_v1 import env_limits as _env_limits  # noqa: F401

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

import numpy as np

from scripts.research.self_referential_contrast_v1.bartlett import (
    bartlett_variance,
    contiguous_segments,
    variance_tolerance,
)
from scripts.research.self_referential_contrast_v1.constants import (
    ALPHA,
    AMENDMENT_ID,
    ASSUMPTION_MANIFEST_REFERENCE,
    NORMAL_QUANTILE_95,
    PRIMARY_METHOD,
    PROFILE_ID,
    R_CONFIRMATORY,
    SENSITIVITY_METHOD,
    SENSITIVITY_ROLE,
    STATUS_BOOTSTRAP_DEGENERATE,
    STATUS_BOOTSTRAP_NUMERICAL,
    STATUS_ESTIMAND_UNDEFINED,
    STATUS_IMPLEMENTATION_ERROR,
    STATUS_PRIMARY_COMPLETED,
    STATUS_VARIANCE_DEGENERATE,
)
from scripts.research.self_referential_contrast_v1.multipliers import (
    epsilon_width,
    moving_average_multipliers,
)

EpsilonSampler = Callable[[int, int, int], np.ndarray]


@dataclass(frozen=True)
class ContrastInput:
    x: np.ndarray
    y: np.ndarray
    cell: np.ndarray
    block: np.ndarray
    segment_id: np.ndarray
    declared_cells: tuple[Any, ...]
    h_mechanical: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CellMoments:
    cell: Any
    m0: float
    m_x: float
    m_y: float
    m_xy: float
    d: float | None


def maintained_assumption_manifest() -> dict[str, Any]:
    return {
        "reference": ASSUMPTION_MANIFEST_REFERENCE,
        "assumption_3_1": "MAINTAINED_NOT_TESTED",
        "assumption_3_2": "MAINTAINED_NOT_TESTED",
        "assumptions_identified_with_each_other": False,
        "bounded_coordinates_make_moments_automatic": True,
        "bounded_coordinates_make_cumulants_automatic": False,
        "long_run_variance_in_gradient_direction": "MAINTAINED_NOT_TESTED",
        "verified_on_input_series": False,
        "numeric_g_required": "ONLY_FOR_FINITE_UNIFORM_CLAIM",
        "g_max": None,
    }


def ceil_cube_root(t_count: int) -> int:
    if t_count < 1:
        raise ValueError("T must be positive")
    root = int(round(t_count ** (1.0 / 3.0)))
    while root * root * root < t_count:
        root += 1
    while root > 1 and (root - 1) * (root - 1) * (root - 1) >= t_count:
        root -= 1
    return root


def bandwidths(t_count: int, h_mechanical: int) -> dict[str, Any]:
    if h_mechanical < 0:
        raise ValueError("H_mechanical must be nonnegative")
    cube = ceil_cube_root(t_count)
    bandwidth = max(int(h_mechanical), cube)
    return {
        "T": int(t_count),
        "H_mechanical": int(h_mechanical),
        "ceil_T_one_third": cube,
        "B_T": bandwidth,
        "L_T": bandwidth,
        "MECHANICAL_FLOOR_BINDS": int(h_mechanical) >= cube,
    }


def _as_float_vector(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.shape[0] == 0:
        raise ValueError(f"{name} must be a non-empty 1d array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains a non-finite value")
    return array


def primitive_moments(data: ContrastInput) -> dict[str, Any]:
    x = _as_float_vector(data.x, "x")
    y = _as_float_vector(data.y, "y")
    if y.shape[0] != x.shape[0]:
        raise ValueError("x and y must have the same length")
    cell = np.asarray(data.cell)
    if cell.shape != x.shape:
        raise ValueError("cell labels must align with x")
    declared = tuple(data.declared_cells)
    t_count = int(x.shape[0])
    unknown = [value for value in _unique_labels(cell) if value not in set(declared)]
    if unknown:
        raise ValueError("cell label is not in the declared cell list")
    cells: list[CellMoments] = []
    empty: list[Any] = []
    for name in declared:
        mask = cell == name
        count = int(np.count_nonzero(mask))
        if count == 0:
            empty.append(name)
            cells.append(CellMoments(name, 0.0, 0.0, 0.0, 0.0, None))
            continue
        m0 = count / t_count
        m_x = float(np.sum(x[mask]) / t_count)
        m_y = float(np.sum(y[mask]) / t_count)
        m_xy = float(np.sum(x[mask] * y[mask]) / t_count)
        d_value = m_xy - (m_x * m_y) / m0
        cells.append(CellMoments(name, m0, m_x, m_y, m_xy, d_value))
    m_hat = float(sum(item.m_x for item in cells))
    if empty or m_hat == 0.0 or not declared:
        return {
            "status": STATUS_ESTIMAND_UNDEFINED,
            "T": t_count,
            "cells": cells,
            "empty_cells": tuple(empty),
            "M_hat": m_hat,
            "theta_hat": None,
            "method_switched": False,
        }
    numerator = float(sum(item.d for item in cells if item.d is not None))
    theta = numerator / m_hat
    return {
        "status": "DEFINED",
        "T": t_count,
        "cells": cells,
        "empty_cells": (),
        "M_hat": m_hat,
        "N_hat": numerator,
        "theta_hat": theta,
        "method_switched": False,
    }


def analytic_partials(moments: Mapping[str, Any]) -> dict[Any, dict[str, float]]:
    """Closed-form partial derivatives of g at m_hat. No finite differences."""
    if moments["status"] != "DEFINED":
        raise ValueError("partials are undefined when the estimand is undefined")
    mass = float(moments["M_hat"])
    theta = float(moments["theta_hat"])
    partials: dict[Any, dict[str, float]] = {}
    for item in moments["cells"]:
        pi = item.m_x / item.m0
        mu = item.m_y / item.m0
        partials[item.cell] = {
            "m_xy": 1.0 / mass,
            "m_y": -(pi) / mass,
            "m_x": -(mu) / mass - theta / mass,
            "m0": (pi * mu) / mass,
        }
    return partials


def gradient_influence(data: ContrastInput, moments: Mapping[str, Any] | None = None) -> np.ndarray:
    """phi_t = grad g(m_hat)' (Z_t - m_hat)."""
    computed = primitive_moments(data) if moments is None else moments
    if computed["status"] != "DEFINED":
        raise ValueError("influence is undefined when the estimand is undefined")
    x = _as_float_vector(data.x, "x")
    y = _as_float_vector(data.y, "y")
    cell = np.asarray(data.cell)
    partials = analytic_partials(computed)
    dot_m = 0.0
    for item in computed["cells"]:
        grad = partials[item.cell]
        dot_m += (
            grad["m0"] * item.m0
            + grad["m_x"] * item.m_x
            + grad["m_y"] * item.m_y
            + grad["m_xy"] * item.m_xy
        )
    phi = np.empty(x.shape[0], dtype=np.float64)
    for index in range(x.shape[0]):
        grad = partials[cell[index]]
        dot_z = grad["m0"] + grad["m_x"] * x[index] + grad["m_y"] * y[index] + grad["m_xy"] * x[index] * y[index]
        phi[index] = dot_z - dot_m
    return phi


def product_identity_influence(data: ContrastInput, moments: Mapping[str, Any] | None = None) -> np.ndarray:
    """phi_t = u_t - theta_hat * X_t / M_hat."""
    computed = primitive_moments(data) if moments is None else moments
    if computed["status"] != "DEFINED":
        raise ValueError("influence is undefined when the estimand is undefined")
    x = _as_float_vector(data.x, "x")
    y = _as_float_vector(data.y, "y")
    cell = np.asarray(data.cell)
    mass = float(computed["M_hat"])
    theta = float(computed["theta_hat"])
    pi = {item.cell: item.m_x / item.m0 for item in computed["cells"]}
    mu = {item.cell: item.m_y / item.m0 for item in computed["cells"]}
    u_value = np.empty(x.shape[0], dtype=np.float64)
    for index in range(x.shape[0]):
        name = cell[index]
        u_value[index] = (x[index] - pi[name]) * (y[index] - mu[name]) / mass
    return u_value - theta * x / mass


def block_center(phi: np.ndarray, block: np.ndarray) -> np.ndarray:
    """One deterministic-block centering. Keys are the adapter block labels."""
    values = np.asarray(phi, dtype=np.float64)
    labels = np.asarray(block)
    if labels.shape != values.shape:
        raise ValueError("block labels must align with the influence")
    centered = np.empty_like(values)
    for name in _unique_labels(labels):
        mask = labels == name
        centered[mask] = values[mask] - values[mask].mean()
    return centered


def classify_observed_variance(variance: float, gamma0: float, bandwidth: int, t_count: int) -> str:
    if gamma0 == 0.0:
        return STATUS_VARIANCE_DEGENERATE
    tolerance = variance_tolerance(t_count, bandwidth, gamma0)
    if variance < -tolerance:
        return STATUS_IMPLEMENTATION_ERROR
    if variance <= 0.0:
        return STATUS_VARIANCE_DEGENERATE
    return "POSITIVE"


def classify_bootstrap_variance(variance: float, gamma0: float, bandwidth: int, t_count: int) -> str:
    if gamma0 == 0.0 or variance == 0.0:
        return STATUS_BOOTSTRAP_DEGENERATE
    tolerance = variance_tolerance(t_count, bandwidth, gamma0)
    if variance < -tolerance:
        return STATUS_IMPLEMENTATION_ERROR
    if variance < 0.0:
        return STATUS_BOOTSTRAP_NUMERICAL
    return "POSITIVE"


def counts_as_exceedance(studentized: float, t_obs: float) -> bool:
    """Ties use >=. Equality is an upper-tail count."""
    return float(studentized) >= float(t_obs)


def finite_r_tail(exceedance_count: int, replicates: int) -> dict[str, Any]:
    if replicates < 1:
        raise ValueError("R must be positive")
    if exceedance_count < 0 or exceedance_count > replicates:
        raise ValueError("exceedance count is outside 0..R")
    p_value = Fraction(1 + exceedance_count, replicates + 1)
    p_hat = Fraction(exceedance_count, replicates)
    se = math.sqrt(float(p_hat * (1 - p_hat) / replicates))
    return {
        "exceedance_count": int(exceedance_count),
        "R": int(replicates),
        "p_numerator": p_value.numerator,
        "p_denominator": p_value.denominator,
        "p_value": float(p_value),
        "monte_carlo_se": se,
        "reject": p_value <= Fraction(1, 20),
    }


def sensitivity_rejects(studentized: float, variance_positive: bool) -> bool:
    return bool(variance_positive) and float(studentized) > NORMAL_QUANTILE_95


def _unique_labels(labels: np.ndarray) -> list[Any]:
    seen: list[Any] = []
    for value in labels.tolist():
        if value not in seen:
            seen.append(value)
    return seen


def _validate_alignment(data: ContrastInput) -> np.ndarray:
    x = _as_float_vector(data.x, "x")
    y = _as_float_vector(data.y, "y")
    if y.shape != x.shape:
        raise ValueError("x and y must have the same length")
    for name, values in (
        ("cell", np.asarray(data.cell)),
        ("block", np.asarray(data.block)),
        ("segment_id", np.asarray(data.segment_id)),
    ):
        if values.shape != x.shape:
            raise ValueError(f"{name} must align with x")
    undeclared = [value for value in _unique_labels(np.asarray(data.cell)) if value not in set(data.declared_cells)]
    if undeclared:
        raise ValueError("cell label is not in the declared cell list")
    return x


def run_primary(
    data: ContrastInput,
    *,
    replicates: int = R_CONFIRMATORY,
    epsilon_sampler: EpsilonSampler,
    compute_sensitivity: bool = True,
    draw_batch_size: int = 64,
) -> dict[str, Any]:
    """Studentized full-influence DWB. The sampler is called as (draw, segment, width)."""
    _validate_alignment(data)
    moments = primitive_moments(data)
    rules = bandwidths(moments["T"], data.h_mechanical)
    manifest = maintained_assumption_manifest()
    base = {
        "profile_id": PROFILE_ID,
        "profile_version": AMENDMENT_ID,
        "primary_method": PRIMARY_METHOD,
        "method_switched": False,
        "maintained_assumption_manifest": manifest,
        "T": moments["T"],
        "B_T": rules["B_T"],
        "L_T": rules["L_T"],
        "MECHANICAL_FLOOR_BINDS": rules["MECHANICAL_FLOOR_BINDS"],
        "H_mechanical": rules["H_mechanical"],
        "R": int(replicates),
        "metadata": dict(data.metadata),
    }
    if moments["status"] != "DEFINED":
        base.update(
            {
                "inference_status": STATUS_ESTIMAND_UNDEFINED,
                "theta_hat": None,
                "observed_variance": None,
                "T_obs": None,
                "exceedance_count": None,
                "p_value": None,
                "monte_carlo_se": None,
                "primary_reject": False,
                "empty_cells": list(moments["empty_cells"]),
                "M_hat": moments["M_hat"],
                "INFERENCE_SENSITIVE": False,
                "sensitivity_role": SENSITIVITY_ROLE,
                "sensitivity_method": SENSITIVITY_METHOD if compute_sensitivity else None,
                "sensitivity_reject": False,
            }
        )
        return base
    phi = gradient_influence(data, moments)
    centered = block_center(phi, np.asarray(data.block))
    segments = contiguous_segments(np.asarray(data.segment_id))
    bandwidth = int(rules["B_T"])
    observed_v, observed_g0 = bartlett_variance(centered, segments, bandwidth)
    variance = float(observed_v[0])
    gamma0 = float(observed_g0[0])
    variance_status = classify_observed_variance(variance, gamma0, bandwidth, moments["T"])
    theta = float(moments["theta_hat"])
    if variance_status != "POSITIVE":
        base.update(
            {
                "inference_status": variance_status,
                "theta_hat": theta,
                "observed_variance": variance,
                "observed_gamma0": gamma0,
                "T_obs": None,
                "exceedance_count": None,
                "p_value": None,
                "monte_carlo_se": None,
                "primary_reject": False,
                "empty_cells": [],
                "M_hat": moments["M_hat"],
                "INFERENCE_SENSITIVE": False,
                "sensitivity_role": SENSITIVITY_ROLE,
                "sensitivity_method": SENSITIVITY_METHOD if compute_sensitivity else None,
                "sensitivity_reject": False,
                "cell_D": {str(item.cell): item.d for item in moments["cells"]},
            }
        )
        return base
    t_obs = math.sqrt(moments["T"]) * theta / math.sqrt(variance)
    tail = _bootstrap_tail(
        centered,
        segments,
        bandwidth,
        t_obs,
        replicates,
        epsilon_sampler,
        draw_batch_size,
    )
    if tail["inference_status"] != STATUS_PRIMARY_COMPLETED:
        base.update(
            {
                "inference_status": tail["inference_status"],
                "theta_hat": theta,
                "observed_variance": variance,
                "observed_gamma0": gamma0,
                "T_obs": t_obs,
                "exceedance_count": None,
                "p_value": None,
                "monte_carlo_se": None,
                "primary_reject": False,
                "failed_draw_index": tail["failed_draw_index"],
                "empty_cells": [],
                "M_hat": moments["M_hat"],
                "INFERENCE_SENSITIVE": False,
                "sensitivity_role": SENSITIVITY_ROLE,
                "sensitivity_method": SENSITIVITY_METHOD if compute_sensitivity else None,
                "sensitivity_reject": False,
                "cell_D": {str(item.cell): item.d for item in moments["cells"]},
            }
        )
        return base
    sens_reject = sensitivity_rejects(t_obs, True) if compute_sensitivity else False
    primary_reject = bool(tail["reject"])
    base.update(
        {
            "inference_status": STATUS_PRIMARY_COMPLETED,
            "theta_hat": theta,
            "observed_variance": variance,
            "observed_gamma0": gamma0,
            "T_obs": t_obs,
            "exceedance_count": tail["exceedance_count"],
            "p_value": tail["p_value"],
            "p_numerator": tail["p_numerator"],
            "p_denominator": tail["p_denominator"],
            "monte_carlo_se": tail["monte_carlo_se"],
            "primary_reject": primary_reject,
            "empty_cells": [],
            "M_hat": moments["M_hat"],
            "sensitivity_role": SENSITIVITY_ROLE,
            "sensitivity_method": SENSITIVITY_METHOD if compute_sensitivity else None,
            "sensitivity_reject": sens_reject,
            "INFERENCE_SENSITIVE": bool(compute_sensitivity and sens_reject != primary_reject),
            "cell_D": {str(item.cell): item.d for item in moments["cells"]},
            "phi_mean": float(phi.mean()),
            "centered_sum": float(centered.sum()),
        }
    )
    return base


def _bootstrap_tail(
    centered: np.ndarray,
    segments: list[tuple[int, int]],
    bandwidth: int,
    t_obs: float,
    replicates: int,
    epsilon_sampler: EpsilonSampler,
    draw_batch_size: int,
) -> dict[str, Any]:
    if replicates < 1:
        raise ValueError("R must be positive")
    if draw_batch_size < 1:
        raise ValueError("draw batch size must be positive")
    t_count = centered.shape[0]
    exceedance = 0
    scale = math.sqrt(t_count)
    for batch_start in range(0, replicates, draw_batch_size):
        batch_end = min(replicates, batch_start + draw_batch_size)
        draw_ids = range(batch_start, batch_end)
        batch = len(draw_ids)
        eta = np.empty((batch, t_count), dtype=np.float64)
        for segment_index, (start, stop) in enumerate(segments):
            width = epsilon_width(stop - start, bandwidth)
            shocks = np.empty((batch, width), dtype=np.float64)
            for row, draw_index in enumerate(draw_ids):
                shocks[row] = np.asarray(epsilon_sampler(draw_index, segment_index, width), dtype=np.float64)
            eta[:, start:stop] = moving_average_multipliers(shocks, bandwidth)
        starred = eta * centered[None, :]
        numerators = starred.sum(axis=1) / scale
        variances, gamma0 = bartlett_variance(starred, segments, bandwidth)
        for row, draw_index in enumerate(draw_ids):
            status = classify_bootstrap_variance(float(variances[row]), float(gamma0[row]), bandwidth, t_count)
            if status != "POSITIVE":
                return {"inference_status": status, "failed_draw_index": int(draw_index)}
            studentized = float(numerators[row]) / math.sqrt(float(variances[row]))
            if counts_as_exceedance(studentized, t_obs):
                exceedance += 1
    tail = finite_r_tail(exceedance, replicates)
    tail["inference_status"] = STATUS_PRIMARY_COMPLETED
    return tail


def canonical_result_json(result: Mapping[str, Any]) -> str:
    return json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)


def indexed_epsilon_sampler(entropy: bytes) -> EpsilonSampler:
    """Draw-indexed normals. Batch order does not change a draw's shocks."""

    def sample(draw_index: int, segment_index: int, width: int) -> np.ndarray:
        from scripts.research.self_referential_contrast_v1.seeds import generator_from_digest

        generator = generator_from_digest(entropy, spawn_key=(int(draw_index), int(segment_index)))
        return generator.standard_normal(width)

    return sample
