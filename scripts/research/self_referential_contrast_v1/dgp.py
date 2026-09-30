"""Synthetic global-null laws for the generic stress screen.

The builder returns aligned eligible pairs. The last clock point of each
structural segment is the lead of the last eligible hour and is not itself
an eligible row, so a lead does not cross a gap. Official screens are not
started by importing this module.
"""

from __future__ import annotations

from scripts.research.self_referential_contrast_v1 import env_limits as _env_limits  # noqa: F401

from dataclasses import dataclass

import numpy as np

from scripts.research.self_referential_contrast_v1.contrast import ContrastInput
from scripts.research.self_referential_contrast_v1.seeds import generator_from_digest, world_entropy
from scripts.research.self_referential_contrast_v1.validation_protocol import WorldSpec


@dataclass(frozen=True)
class _Segment:
    state: np.ndarray
    cell: np.ndarray


def build_generic_world(spec: WorldSpec, *, purpose: str) -> ContrastInput:
    if spec.t_count is None or spec.block_count is None or spec.gap is None:
        raise ValueError("generic world spec is missing geometry")
    entropy = world_entropy(
        suite_id=spec.suite_id,
        configuration_id=spec.configuration_id,
        world_index=spec.world_index,
        purpose=purpose,
    )
    generator = generator_from_digest(entropy, spawn_key=(1,))
    lengths = _eligible_lengths(spec.t_count, spec.gap)
    segments = _generate_segments(generator, spec, lengths)
    x_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    cell_parts: list[np.ndarray] = []
    segment_parts: list[np.ndarray] = []
    for index, segment in enumerate(segments):
        x_parts.append(segment.state[:-1])
        y_parts.append(segment.state[1:])
        cell_parts.append(segment.cell[:-1])
        segment_parts.append(np.full(segment.state.shape[0] - 1, index, dtype=np.int64))
    x = np.concatenate(x_parts)
    y = np.concatenate(y_parts)
    cell = np.concatenate(cell_parts)
    segment_id = np.concatenate(segment_parts)
    block = _deterministic_blocks(x.shape[0], spec.block_count)
    return ContrastInput(
        x=x,
        y=y,
        cell=cell,
        block=block,
        segment_id=segment_id,
        declared_cells=_declared_cells(spec),
        h_mechanical=0,
        metadata={
            "suite_id": spec.suite_id,
            "configuration_id": spec.configuration_id,
            "world_index": spec.world_index,
            "family": spec.family,
            "param": spec.param,
            "geometry_id": spec.geometry_id,
        },
    )


def _declared_cells(spec: WorldSpec) -> tuple[str, ...]:
    if spec.family in {"IID_BERNOULLI", "INTERLACED_LAG2", "MA_EVEN"}:
        return ("c0",)
    if spec.family in {"CANCELLING_CELLS", "LABEL_MARKOV"}:
        return ("c0", "c1")
    if spec.family == "VARIANCE_REGIMES":
        return ("c0", "c1", "c2", "c3")
    raise ValueError(f"unknown family {spec.family}")


def _eligible_lengths(t_count: int, gap: str) -> tuple[int, ...]:
    if gap == "none":
        return (t_count,)
    if gap != "interior":
        raise ValueError("unknown gap label")
    mid = t_count // 2
    return (mid, t_count - mid)


def _deterministic_blocks(t_count: int, block_count: int) -> np.ndarray:
    edges = [round(i * t_count / block_count) for i in range(block_count + 1)]
    labels = np.empty(t_count, dtype=object)
    for index in range(block_count):
        labels[edges[index] : edges[index + 1]] = f"b{index}"
    return labels


def _generate_segments(generator: np.random.Generator, spec: WorldSpec, lengths: tuple[int, ...]) -> list[_Segment]:
    if spec.family == "LABEL_MARKOV":
        return _label_markov(generator, spec.param, lengths)
    segments: list[_Segment] = []
    cursor = 0
    for length in lengths:
        clock = length + 1
        state, cell = _segment_path(generator, spec, clock, cursor)
        segments.append(_Segment(state=state, cell=cell))
        cursor += length
    return segments


def _segment_path(
    generator: np.random.Generator,
    spec: WorldSpec,
    clock: int,
    eligible_origin: int,
) -> tuple[np.ndarray, np.ndarray]:
    family = spec.family
    if family == "IID_BERNOULLI":
        state = _bernoulli(generator, 0.25, clock)
        return state, np.full(clock, "c0", dtype=object)
    if family == "INTERLACED_LAG2":
        rho = float(spec.param.split("=", 1)[1])
        return _interlaced(generator, rho, clock), np.full(clock, "c0", dtype=object)
    if family == "MA_EVEN":
        thetas = _ma_thetas(spec.param)
        return _ma_even(generator, thetas, clock), np.full(clock, "c0", dtype=object)
    if family == "CANCELLING_CELLS":
        coef = _fraction_param(spec.param)
        return _cancelling(generator, coef, clock, eligible_origin, spec.t_count or clock)
    if family == "VARIANCE_REGIMES":
        probs = _float_list(spec.param)
        return _variance_regime(generator, probs, clock, eligible_origin, spec.t_count or clock)
    raise ValueError(f"unknown family {family}")


def _bernoulli(generator: np.random.Generator, probability: float, size: int) -> np.ndarray:
    return (generator.random(size) < probability).astype(np.float64)


def _interlaced(generator: np.random.Generator, rho: float, clock: int) -> np.ndarray:
    state = np.empty(clock, dtype=np.float64)
    marginal = 0.30
    for time in range(clock):
        if time < 2:
            probability = marginal
        else:
            probability = marginal + rho * (state[time - 2] - marginal)
        state[time] = 1.0 if generator.random() < probability else 0.0
    return state


def _ma_thetas(param: str) -> tuple[float, ...]:
    raw = param.split("theta=", 1)[1]
    return tuple(float(part) for part in raw.split(","))


def _ma_even(generator: np.random.Generator, thetas: tuple[float, ...], clock: int) -> np.ndarray:
    order = len(thetas)
    shocks = _bernoulli(generator, 0.5, clock + 2 * order)
    state = np.empty(clock, dtype=np.float64)
    for time in range(clock):
        probability = 0.30
        for lag, theta in enumerate(thetas, start=1):
            shock = shocks[time + 2 * order - 2 * lag]
            probability += theta * (shock - 0.5)
        state[time] = 1.0 if generator.random() < probability else 0.0
    return state


def _fraction_param(param: str) -> float:
    raw = param.split("=", 1)[1]
    numerator, denominator = raw.split("/")
    return float(numerator) / float(denominator)


def _float_list(param: str) -> tuple[float, float]:
    raw = param.split("=", 1)[1]
    left, right = raw.split(",")
    return float(left), float(right)


def _cancelling(
    generator: np.random.Generator,
    coef: float,
    clock: int,
    eligible_origin: int,
    t_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    marginal = 0.30
    state = np.empty(clock, dtype=np.float64)
    cell = np.empty(clock, dtype=object)
    half = t_count // 2
    for time in range(clock):
        eligible_index = min(eligible_origin + time, eligible_origin + clock - 2)
        name = "c0" if eligible_index < half else "c1"
        cell[time] = name
        if time == 0 or cell[time] != cell[time - 1]:
            probability = marginal
        else:
            sign = coef if name == "c0" else -coef
            probability = marginal + sign * (state[time - 1] - marginal)
        state[time] = 1.0 if generator.random() < probability else 0.0
    return state, cell


def _variance_regime(
    generator: np.random.Generator,
    probs: tuple[float, float],
    clock: int,
    eligible_origin: int,
    t_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    state = np.empty(clock, dtype=np.float64)
    cell = np.empty(clock, dtype=object)
    for time in range(clock):
        eligible_index = min(eligible_origin + time, t_count - 1)
        bucket = min(3, (4 * eligible_index) // t_count)
        probability = probs[bucket % 2]
        cell[time] = f"c{bucket}"
        state[time] = 1.0 if generator.random() < probability else 0.0
    return state, cell


def _label_markov(generator: np.random.Generator, param: str, lengths: tuple[int, ...]) -> list[_Segment]:
    stay = float(param.split("=", 1)[1])
    probabilities = (0.20, 0.40)
    label = 0 if generator.random() < 0.5 else 1
    segments: list[_Segment] = []
    for length in lengths:
        clock = length + 1
        state = np.empty(clock, dtype=np.float64)
        cell = np.empty(clock, dtype=object)
        for time in range(clock):
            if time > 0 or segments:
                label = label if generator.random() < stay else 1 - label
            cell[time] = f"c{label}"
            state[time] = 1.0 if generator.random() < probabilities[label] else 0.0
        segments.append(_Segment(state=state, cell=cell))
    return segments
