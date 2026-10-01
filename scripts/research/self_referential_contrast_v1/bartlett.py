"""Exact Bartlett quadratic form.

The moving-sum identity is the frozen block-diagonal Bartlett matrix:

    T * V(a; B) = x' K x = (1/B) * sum_u (sum_{j=0}^{B-1} x_{u+j})^2

with x the globally demeaned series, read as zero outside each structural
segment. Windows that hang off a segment edge are included. No product
crosses a segment boundary.
"""

from __future__ import annotations

from scripts.research.self_referential_contrast_v1 import env_limits as _env_limits  # noqa: F401

import numpy as np

from scripts.research.self_referential_contrast_v1.constants import MACHINE_EPSILON


def contiguous_segments(segment_id: np.ndarray) -> list[tuple[int, int]]:
    """Maximal contiguous runs. A change of id is a structural gap."""
    ids = np.asarray(segment_id)
    if ids.ndim != 1 or ids.shape[0] == 0:
        raise ValueError("segment_id must be a non-empty 1d array")
    change = np.flatnonzero(ids[1:] != ids[:-1]) + 1
    bounds = np.concatenate(([0], change, [ids.shape[0]]))
    return [(int(bounds[i]), int(bounds[i + 1])) for i in range(bounds.shape[0] - 1)]


def variance_tolerance(t_count: int, bandwidth: int, gamma0: float) -> float:
    """Scale-aware tolerance. Not evaluated when gamma0 is 0."""
    if gamma0 <= 0.0:
        raise ValueError("tolerance is not evaluated at gamma0 = 0")
    return 4.0 * t_count * bandwidth * MACHINE_EPSILON * gamma0


def bartlett_variance(series: np.ndarray, segments: list[tuple[int, int]], bandwidth: int) -> tuple[np.ndarray, np.ndarray]:
    """Bartlett long-run variance for one or many series.

    `series` has shape (T,) or (R, T). Returns (V, gamma0), each shape (R,).
    Global demean is inside this operator. Block means are not removed here.
    """
    if bandwidth < 1:
        raise ValueError("bandwidth must be a positive integer")
    values = np.asarray(series, dtype=np.float64)
    if values.ndim == 1:
        values = values[None, :]
    if values.ndim != 2:
        raise ValueError("series must have shape (T,) or (R, T)")
    draw_count, t_count = values.shape
    if t_count < 1:
        raise ValueError("series length must be positive")
    centered = values - values.mean(axis=1, keepdims=True)
    gamma0 = np.sum(centered * centered, axis=1) / t_count
    quadratic = _segment_quadratic(centered, segments, bandwidth)
    variance = quadratic / t_count
    return variance, gamma0


def direct_quadratic_form(series: np.ndarray, segments: list[tuple[int, int]], bandwidth: int) -> float:
    """Dense x' K x on one series, after the same global demean."""
    values = np.asarray(series, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("direct quadratic form takes one series")
    centered = values - values.mean()
    total = 0.0
    width = int(bandwidth)
    for start, stop in segments:
        block = centered[start:stop]
        length = block.shape[0]
        for i in range(length):
            for j in range(length):
                lag = abs(i - j)
                if lag < width:
                    total += (1.0 - lag / width) * block[i] * block[j]
    return float(total)


def _segment_quadratic(centered: np.ndarray, segments: list[tuple[int, int]], bandwidth: int) -> np.ndarray:
    draw_count, t_count = centered.shape
    covered = 0
    quadratic = np.zeros(draw_count, dtype=np.float64)
    for start, stop in segments:
        if start < 0 or stop > t_count or stop < start:
            raise ValueError("segment bounds are outside the series")
        length = stop - start
        covered += length
        if length == 0:
            continue
        quadratic += _window_sum_of_squares(centered[:, start:stop], bandwidth)
    if covered != t_count:
        raise ValueError("segments must partition the eligible index")
    return quadratic


def _window_sum_of_squares(block: np.ndarray, bandwidth: int) -> np.ndarray:
    """(1/B) * sum_u (sum of B terms)^2, with zeros outside the block."""
    draw_count, length = block.shape
    if bandwidth == 1:
        return np.sum(block * block, axis=1)
    pad = bandwidth - 1
    extended = np.zeros((draw_count, length + 2 * pad), dtype=np.float64)
    extended[:, pad : pad + length] = block
    cumulative = np.cumsum(extended, axis=1)
    window_count = length + bandwidth - 1
    end = cumulative[:, bandwidth - 1 : bandwidth - 1 + window_count]
    start = np.zeros((draw_count, window_count), dtype=np.float64)
    start[:, 1:] = cumulative[:, 0 : window_count - 1]
    window = end - start
    return np.sum(window * window, axis=1) / bandwidth
