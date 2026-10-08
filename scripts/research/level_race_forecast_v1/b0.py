"""B0: driftless first passage of two barriers in log price (design §2.1). No outcome is read here.

For a Brownian motion with variance sigma^2 per 5m bar started at z in (0, w), with w the log
distance between the barriers and s = sigma^2 tau / w^2:

    P_up      = z/w + sum_{n>=1} 2(-1)^n/(n pi) sin(n pi z/w) exp(-n^2 pi^2 s / 2)
    P_dn      = P_up(w - z)
    P_neither = sum_{n odd} 4/(n pi) sin(n pi z/w) exp(-n^2 pi^2 s / 2)
"""

from __future__ import annotations

import math

from . import constants as K


def _series(x: float, s: float) -> tuple[float, float]:
    """(sum for P_up, sum for P_neither) at relative start x = z/w in (0, 1)."""
    up = 0.0
    ne = 0.0
    for n in range(1, K.B0_MAX_TERMS + 1):
        e = math.exp(-(n * math.pi) ** 2 * s / 2.0)
        if e < K.B0_TERM_EPS:
            break
        sn = math.sin(n * math.pi * x)
        up += 2.0 * (-1.0) ** n / (n * math.pi) * sn * e
        if n % 2 == 1:
            ne += 4.0 / (n * math.pi) * sn * e
    return up, ne


def floor_renorm(p: tuple[float, float, float], eps: float = K.PROB_FLOOR) -> tuple[float, float, float]:
    q = [max(float(v), eps) for v in p]
    t = sum(q)
    return (q[0] / t, q[1] / t, q[2] / t)


def race_raw(price: float, upper: float, lower: float, sigma: float, tau_bars: float) -> tuple[float, float, float]:
    """(P upper first, P lower first, P neither) before the floor. Prices must be positive."""
    if not (upper > lower > 0 and price > 0 and sigma > 0 and tau_bars > 0):
        raise ValueError("invalid race geometry")
    w = math.log(upper) - math.log(lower)
    z = math.log(price) - math.log(lower)
    if z >= w:
        return (1.0, 0.0, 0.0)
    if z <= 0:
        return (0.0, 1.0, 0.0)
    x = z / w
    s = sigma * sigma * tau_bars / (w * w)
    up_sum, ne = _series(x, s)
    dn_sum, _ = _series(1.0 - x, s)
    p_up = min(max(x + up_sum, 0.0), 1.0)
    p_dn = min(max((1.0 - x) + dn_sum, 0.0), 1.0)
    p_ne = min(max(ne, 0.0), 1.0)
    return (p_up, p_dn, p_ne)


def race(price: float, upper: float, lower: float, sigma: float, tau_bars: float) -> tuple[float, float, float]:
    """B0 with the frozen floor (an out-of-corridor start gives 1 - 2 eps to the crossed side)."""
    return floor_renorm(race_raw(price, upper, lower, sigma, tau_bars))
