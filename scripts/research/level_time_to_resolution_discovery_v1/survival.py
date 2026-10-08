"""Kaplan-Meier any-resolution survival and restricted mean unresolved time.

Event = first BREAK, REJECT, or AMBIGUOUS barrier interaction. Administrative
censoring is at 240 minutes. No Cox model and no hazard regression.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from . import constants as K


def km_jumps(times: np.ndarray, events: np.ndarray, tau: float = K.RESTRICT_MIN) -> list[tuple]:
    """(time, S before, S after, at risk, events) at each observed resolution time."""
    times = np.asarray(times, dtype=float)
    events = np.asarray(events, dtype=int)
    if times.size == 0:
        return []
    event_times = np.unique(times[(events == 1) & (times <= tau)])
    survival = 1.0
    jumps = []
    for t in event_times:
        at_risk = int(np.sum(times >= t))
        died = int(np.sum((times == t) & (events == 1)))
        if at_risk <= 0 or died <= 0:
            continue
        before = survival
        survival *= 1.0 - died / at_risk
        jumps.append((float(t), float(before), float(survival), at_risk, died))
    return jumps


def survival_at(jumps: list[tuple], t: float) -> float:
    """P(T > t). A resolution at exactly t has already happened."""
    value = 1.0
    for when, _before, after, _n, _d in jumps:
        if when <= t:
            value = after
        else:
            break
    return float(value)


def rmut(jumps: list[tuple], tau: float = K.RESTRICT_MIN) -> float:
    """Area under P(still unresolved) from 0 to tau."""
    area = 0.0
    prev = 0.0
    survival = 1.0
    for when, _before, after, _n, _d in jumps:
        if when >= tau:
            area += survival * (tau - prev)
            return float(area)
        area += survival * (when - prev)
        prev = when
        survival = after
    area += survival * (tau - prev)
    return float(area)


def checkpoints(jumps: list[tuple]) -> dict:
    out = {}
    for t in K.CHECKPOINTS:
        unresolved = survival_at(jumps, float(t))
        out[str(t)] = {"unresolved": unresolved, "resolved_by": 1.0 - unresolved}
    return out


def interval_hazards(times: np.ndarray, events: np.ndarray) -> list[dict]:
    """Resolved during (left, right] divided by still unresolved at left."""
    times = np.asarray(times, dtype=float)
    events = np.asarray(events, dtype=int)
    rows = []
    for left, right in K.INTERVALS:
        at_risk = int(np.sum(times > left))
        resolved = int(np.sum((events == 1) & (times > left) & (times <= right)))
        rate = None if at_risk == 0 else resolved / at_risk
        rows.append({
            "left": left, "right": right, "resolved": resolved,
            "at_risk": at_risk, "rate": rate,
        })
    return rows


def km_quantile(jumps: list[tuple], level: float) -> Optional[float]:
    """Smallest event time where survival drops to the level or below. None if not reached."""
    for when, _before, after, _n, _d in jumps:
        if after <= level:
            return float(when)
    return None


def observed_quartiles(times: np.ndarray) -> dict:
    if times.size == 0:
        return {"n": 0, "q25": None, "q50": None, "q75": None}
    q25, q50, q75 = np.quantile(times, [0.25, 0.5, 0.75])
    return {"n": int(times.size), "q25": float(q25), "q50": float(q50), "q75": float(q75)}


def cumulative_incidence(times: np.ndarray, kinds: np.ndarray) -> dict:
    """Aalen-Johansen incidence of BREAK and of REJECT. AMBIGUOUS competes and is neither."""
    times = np.asarray(times, dtype=float)
    kinds = np.asarray(kinds)
    jumps_any = km_jumps(times, (kinds != "CENSORED").astype(int))
    causes = ("BREAK", "REJECT", "AMBIGUOUS")
    cif = {name: [] for name in causes}
    running = {name: 0.0 for name in causes}
    survival_before = {when: before for when, before, _after, _n, _d in jumps_any}
    event_times = [when for when, _b, _a, _n, _d in jumps_any]
    for when in event_times:
        at_risk = int(np.sum(times >= when))
        before = survival_before[when]
        for name in causes:
            died = int(np.sum((times == when) & (kinds == name)))
            if at_risk > 0 and died:
                running[name] += before * (died / at_risk)
            cif[name].append((when, running[name]))
    out = {}
    for name in ("BREAK", "REJECT"):
        points = {}
        for t in K.CHECKPOINTS:
            value = 0.0
            for when, level in cif[name]:
                if when <= t:
                    value = level
                else:
                    break
            points[str(t)] = float(value)
        out[name] = points
    out["n_ambiguous"] = int(np.sum(kinds == "AMBIGUOUS"))
    out["n_censored"] = int(np.sum(kinds == "CENSORED"))
    out["n_break"] = int(np.sum(kinds == "BREAK"))
    out["n_reject"] = int(np.sum(kinds == "REJECT"))
    return out


def summarize(times: np.ndarray, events: np.ndarray, kinds: np.ndarray) -> dict:
    jumps = km_jumps(times, events)
    return {
        "n": int(times.size),
        "n_resolved": int(np.sum(events == 1)),
        "n_censored": int(np.sum(events == 0)),
        "rmut": rmut(jumps),
        "checkpoints": checkpoints(jumps),
        "hazards": interval_hazards(times, events),
        "km_q25": km_quantile(jumps, 0.75),
        "km_q50": km_quantile(jumps, 0.50),
        "km_q75": km_quantile(jumps, 0.25),
        "incidence": cumulative_incidence(times, kinds),
        "break_times": observed_quartiles(times[kinds == "BREAK"]),
        "reject_times": observed_quartiles(times[kinds == "REJECT"]),
    }
