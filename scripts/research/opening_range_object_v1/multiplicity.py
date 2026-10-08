"""Family-wise rules for a later outcome read. No market labels enter this module.

Three families, three procedures. A marginal interval is not a candidate rule.
"""

from __future__ import annotations

import numpy as np

from . import constants as K


def simultaneous_max_t(point: dict, replicates: list, *, alpha: float = K.FAMILY_ALPHA) -> dict:
    """Single-step studentized max-T intervals from one joint bootstrap.

    `replicates` are draws of every statistic in `point` together. The critical
    value is the (1 − alpha) quantile of the max absolute studentized deviate
    inside this family only.
    """
    names = list(point)
    if len(replicates) < 2:
        raise ValueError("max-T needs at least two joint draws")
    if not names:
        raise ValueError("max-T family is empty")
    columns = []
    se = {}
    for name in names:
        column = np.asarray([float(draw[name]) for draw in replicates], dtype=np.float64)
        columns.append(column)
        spread = float(np.std(column, ddof=1))
        if spread == 0.0 and not np.all(column == float(point[name])):
            raise ValueError(f"zero spread with disagreeing draws for {name}")
        se[name] = spread
    centered = []
    for name, column in zip(names, columns):
        if se[name] == 0.0:
            centered.append(np.zeros(len(replicates), dtype=np.float64))
        else:
            centered.append((column - float(point[name])) / se[name])
    max_abs = np.max(np.abs(np.column_stack(centered)), axis=1)
    critical = float(np.quantile(max_abs, 1.0 - alpha, method="linear"))
    out = {}
    for name in names:
        half = critical * se[name]
        estimate = float(point[name])
        out[name] = {
            "point": estimate,
            "se": se[name],
            "critical": critical,
            "sim_lo": estimate - half,
            "sim_hi": estimate + half,
        }
    return out


def marginal_percentile(replicates: list, *, alpha: float = K.FAMILY_ALPHA) -> tuple[float, float]:
    """Printed uncertainty. Not a candidate rule."""
    column = np.asarray(replicates, dtype=np.float64)
    return (
        float(np.quantile(column, alpha / 2.0, method="linear")),
        float(np.quantile(column, 1.0 - alpha / 2.0, method="linear")),
    )


def bootstrap_p_value(point: float, replicates: list) -> float:
    """Two-sided recentered bootstrap p-value, with the add-one correction."""
    column = np.asarray(replicates, dtype=np.float64)
    if column.size == 0:
        raise ValueError("bootstrap p-value needs draws")
    extreme = int(np.sum(np.abs(column - float(point)) >= abs(float(point))))
    return (1 + extreme) / (column.size + 1)


def holm_adjusted(p_values: dict) -> dict:
    """Step-down Holm adjusted p-values. Ties break by name. Monotone in rank."""
    ordered = sorted(p_values.items(), key=lambda item: (float(item[1]), item[0]))
    m = len(ordered)
    adjusted = {}
    running = 0.0
    for rank, (name, raw) in enumerate(ordered, start=1):
        running = max(running, min(1.0, float(raw) * (m - rank + 1)))
        adjusted[name] = running
    return adjusted
