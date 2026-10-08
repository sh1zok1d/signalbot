"""Joint week-block bootstrap for the four clock cells. Synthetic inputs only.

One draw resamples ISO weeks once and recomputes every cell mean inside that
draw. This module has no market loader. The CLI refuses an outcome read.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from . import constants as K

REFUSAL = "REFUSING_OUTCOME_BEFORE_OWNER_GO"


def one_draw(sums: dict[str, dict], mult: dict) -> dict | None:
    """`sums[cell][week] = (sum of pair deltas, n pairs)`."""
    means = {}
    for cell, by_week in sums.items():
        num = 0.0
        den = 0
        for week, m in mult.items():
            if m == 0 or week not in by_week:
                continue
            total, n = by_week[week]
            num += m * total
            den += m * n
        if den == 0:
            return None
        means[cell] = num / den
    if K.PRIMARY_CELL not in means:
        return None
    base = means[K.PRIMARY_CELL]
    return {
        "means": means,
        "contrasts": {cell: base - means[cell] for cell in means if cell != K.PRIMARY_CELL},
    }


def draw_multiplicity(weeks: list, rng: np.random.Generator) -> dict:
    choice = rng.choice(len(weeks), size=len(weeks), replace=True)
    return dict(Counter(weeks[int(i)] for i in choice))


def bootstrap(sums: dict[str, dict], *, draws: int, seed: int) -> dict:
    weeks = sorted({week for by_week in sums.values() for week in by_week})
    rng = np.random.default_rng(seed)
    valid = []
    invalid = 0
    for _ in range(draws):
        got = one_draw(sums, draw_multiplicity(weeks, rng))
        if got is None:
            invalid += 1
        else:
            valid.append(got)
    return {"valid": valid, "invalid": invalid, "draws": draws, "seed": seed}


def main() -> int:
    raise SystemExit(REFUSAL)


if __name__ == "__main__":
    raise SystemExit(main())
