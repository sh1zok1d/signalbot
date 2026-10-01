"""Population-null oracle for the generic gating laws.

This module is test-only. It does not call the sample estimator and it is
not used by primary inference. Population theta is the contrast implied by
each family's declared transition law.
"""

from __future__ import annotations

from fractions import Fraction


def balanced_cancelling_sign(pair_index: int, t_count: int, gap: str) -> int:
    """Independent copy of the balanced cancelling-pair rule.

    +1 and -1 counts match for every T >= 2. Zero is a marginal pair.
    """
    if t_count < 2:
        raise ValueError("cancelling cells need at least two eligible hours")
    if gap not in {"none", "interior"}:
        raise ValueError("unknown gap label")
    half = t_count // 2
    if gap == "none":
        balanced = half - 1
        if pair_index < half:
            return 0 if pair_index == half - 1 else 1
        return -1 if pair_index - half < balanced else 0
    if pair_index < half:
        return 1
    return -1 if pair_index - half < half else 0


def cancelling_theta_from_signs(signs: list[int], coef: Fraction, t_count: int) -> Fraction:
    """Global contrast when every row has mean 0.30 and pair sign `signs[t]`.

    A marginal pair has sign 0. An autoregressive pair with coefficient
    sign * coef contributes sign * coef * 0.30 * 0.70 to the summed excess.
    """
    if len(signs) != t_count:
        raise ValueError("sign schedule must cover every eligible pair")
    signed = sum(signs)
    return signed * coef * Fraction(7, 10) / t_count


def population_theta(family: str, param: str, t_count: int, gap: str) -> Fraction:
    """Exact population theta. Zero is the gating requirement."""
    if t_count < 1:
        raise ValueError("T must be positive")
    if gap not in {"none", "interior"}:
        raise ValueError("unknown gap label")
    if family == "IID_BERNOULLI":
        return _iid_theta(param)
    if family == "INTERLACED_LAG2":
        return _interlaced_theta(param)
    if family == "MA_EVEN":
        return _ma_theta(param)
    if family == "CANCELLING_CELLS":
        return _cancelling_theta(param, t_count, gap)
    if family == "VARIANCE_REGIMES":
        return _variance_theta(param, t_count, gap)
    if family == "LABEL_MARKOV":
        return _label_theta(param, t_count, gap)
    raise ValueError(f"unknown family {family}")


def _iid_theta(param: str) -> Fraction:
    probability = _named_fraction(param, "p")
    if probability != Fraction(1, 4):
        raise ValueError("IID gating law is Bernoulli(0.25)")
    moment_xy = probability * probability
    excess = moment_xy - probability * probability
    return excess / probability


def _interlaced_theta(param: str) -> Fraction:
    rho = _named_fraction(param, "rho")
    marginal = Fraction(3, 10)
    # Lag-2 map fixes the marginal, and adjacent times sit on independent chains.
    fixed = marginal + rho * (marginal - marginal)
    joint = fixed * fixed
    excess = joint - fixed * fixed
    return excess / fixed


def _ma_theta(param: str) -> Fraction:
    thetas = _ma_coefficients(param)
    order = len(thetas)
    for time in range(order + 2):
        left = {time + 2 * order - 2 * lag for lag in range(1, order + 1)}
        right = {time + 1 + 2 * order - 2 * lag for lag in range(1, order + 1)}
        if left & right:
            raise ValueError("even moving average has a lag-1 shock overlap")
    marginal = Fraction(3, 10)
    max_shift = sum((abs(theta) for theta in thetas), Fraction(0)) * Fraction(1, 2)
    if marginal - max_shift < 0 or marginal + max_shift > 1:
        raise ValueError("moving-average probability would leave [0, 1]")
    joint = marginal * marginal
    excess = joint - marginal * marginal
    return excess / marginal


def _cancelling_theta(param: str, t_count: int, gap: str) -> Fraction:
    coef = _ratio_fraction(param)
    signs = [balanced_cancelling_sign(index, t_count, gap) for index in range(t_count)]
    return cancelling_theta_from_signs(signs, coef, t_count)


def _variance_theta(param: str, t_count: int, gap: str) -> Fraction:
    probs = _variance_probabilities(param)
    rows = _variance_pairs(t_count, gap, probs)
    grouped: dict[int, list[tuple[Fraction, Fraction]]] = {bucket: [] for bucket in range(4)}
    for bucket, px, py in rows:
        grouped[bucket].append((px, py))
    total_d = Fraction(0)
    total_m = Fraction(0)
    for pairs in grouped.values():
        if not pairs:
            raise ValueError("variance regime has an empty declared cell")
        count = Fraction(len(pairs))
        sum_x = sum((px for px, _py in pairs), Fraction(0))
        sum_y = sum((py for _px, py in pairs), Fraction(0))
        sum_xy = sum((px * py for px, py in pairs), Fraction(0))
        total_d += sum_xy / t_count - (sum_x / t_count) * (sum_y / t_count) / (count / t_count)
        total_m += sum_x / t_count
    if total_m == 0:
        raise ValueError("variance regime has zero candidate mass")
    return total_d / total_m


def _variance_pairs(
    t_count: int,
    gap: str,
    probs: tuple[Fraction, Fraction],
) -> list[tuple[int, Fraction, Fraction]]:
    lengths = _lengths(t_count, gap)
    origin = 0
    rows: list[tuple[int, Fraction, Fraction]] = []
    for length in lengths:
        clock = length + 1
        state_p: list[Fraction] = []
        state_bucket: list[int] = []
        for time in range(clock):
            eligible_index = min(origin + time, t_count - 1)
            bucket = min(3, (4 * eligible_index) // t_count)
            state_bucket.append(bucket)
            state_p.append(probs[bucket % 2])
        for time in range(length):
            rows.append((state_bucket[time], state_p[time], state_p[time + 1]))
        origin += length
    return rows


def _label_theta(param: str, t_count: int, gap: str) -> Fraction:
    stay = _named_fraction(param, "stay")
    if not (0 < stay < 1):
        raise ValueError("label stay probability must lie in (0, 1)")
    if gap not in {"none", "interior"} or t_count < 2:
        raise ValueError("label Markov population is undefined for this geometry")
    probabilities = (Fraction(1, 5), Fraction(2, 5))
    # Given the current label, the outcome is independent of the lead.
    # The lead's conditional mean depends on the label transition only.
    conditional_lead = tuple(
        stay * probabilities[label] + (1 - stay) * probabilities[1 - label] for label in (0, 1)
    )
    total_d = Fraction(0)
    total_m = Fraction(0)
    for label in (0, 1):
        # Any positive cell mass cancels. Stationary start gives mass T/2 in expectation
        # on a gap-free index; the same cancellation holds for every positive mass.
        mass = Fraction(t_count, 2)
        sum_x = probabilities[label] * mass
        sum_y = conditional_lead[label] * mass
        sum_xy = probabilities[label] * conditional_lead[label] * mass
        total_d += sum_xy / t_count - (sum_x / t_count) * (sum_y / t_count) / (mass / t_count)
        total_m += sum_x / t_count
    return total_d / total_m


def _lengths(t_count: int, gap: str) -> tuple[int, ...]:
    if gap == "none":
        return (t_count,)
    mid = t_count // 2
    if mid <= 0 or t_count - mid <= 0:
        raise ValueError("interior gap needs two positive segments")
    return (mid, t_count - mid)


def _named_fraction(param: str, name: str) -> Fraction:
    key, value = param.split("=", 1)
    if key != name:
        raise ValueError(f"expected {name}=, got {param}")
    return Fraction(value)


def _ratio_fraction(param: str) -> Fraction:
    raw = param.split("=", 1)[1]
    numerator, denominator = raw.split("/")
    return Fraction(numerator) / Fraction(denominator)


def _ma_coefficients(param: str) -> tuple[Fraction, ...]:
    raw = param.split("theta=", 1)[1]
    return tuple(Fraction(part) for part in raw.split(","))


def _variance_probabilities(param: str) -> tuple[Fraction, Fraction]:
    raw = param.split("=", 1)[1]
    left, right = raw.split(",")
    return Fraction(left), Fraction(right)
