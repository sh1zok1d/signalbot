"""Exact Gaussian Bartlett multipliers.

    eta_t = L^{-1/2} * sum_{j=0}^{L-1} epsilon_{t-j}

with L-1 presample standard normals on each structural segment.
Segments do not share epsilon state, and the buffer is not circular.
"""

from __future__ import annotations

from scripts.research.self_referential_contrast_v1 import env_limits as _env_limits  # noqa: F401

import math

import numpy as np


def presample_count(length: int) -> int:
    if length < 1:
        raise ValueError("multiplier bandwidth must be positive")
    return length - 1


def epsilon_width(segment_length: int, bandwidth: int) -> int:
    return segment_length + presample_count(bandwidth)


def moving_average_multipliers(epsilon: np.ndarray, bandwidth: int) -> np.ndarray:
    """Map presample-prefixed epsilon to eta.

    `epsilon` has shape (n + L - 1,) or (R, n + L - 1). The first L - 1
    columns are the presample. Returns shape (n,) or (R, n).
    """
    if bandwidth < 1:
        raise ValueError("bandwidth must be positive")
    shocks = np.asarray(epsilon, dtype=np.float64)
    squeezed = False
    if shocks.ndim == 1:
        shocks = shocks[None, :]
        squeezed = True
    if shocks.ndim != 2:
        raise ValueError("epsilon must have shape (n+L-1,) or (R, n+L-1)")
    width = shocks.shape[1]
    if width < bandwidth:
        raise ValueError("epsilon buffer is shorter than the bandwidth")
    segment_length = width - (bandwidth - 1)
    cumulative = np.cumsum(shocks, axis=1)
    end = cumulative[:, bandwidth - 1 : bandwidth - 1 + segment_length]
    start = np.zeros((shocks.shape[0], segment_length), dtype=np.float64)
    if segment_length > 1:
        start[:, 1:] = cumulative[:, 0 : segment_length - 1]
    eta = (end - start) / math.sqrt(bandwidth)
    if squeezed:
        return eta[0]
    return eta


def bartlett_covariance(length: int, bandwidth: int) -> np.ndarray:
    """Frozen covariance k(|t-s|) = (1 - |t-s|/L)_+ on one segment."""
    index = np.arange(length, dtype=np.float64)
    lag = np.abs(index[:, None] - index[None, :])
    weights = np.zeros((length, length), dtype=np.float64)
    inside = lag < bandwidth
    weights[inside] = 1.0 - lag[inside] / bandwidth
    return weights


def multiplier_design_matrix(segment_length: int, bandwidth: int) -> np.ndarray:
    """eta = M @ epsilon / sqrt(L). Shape of M is (n, n+L-1)."""
    width = epsilon_width(segment_length, bandwidth)
    design = np.zeros((segment_length, width), dtype=np.float64)
    for t in range(segment_length):
        design[t, t : t + bandwidth] = 1.0
    return design
