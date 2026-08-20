"""MATH-002B / issue #52 -- pure, DB-free computation helpers for the
historical 3/3 vs 2/3 consensus robustness study.

Everything in this module is pure (no I/O, no DB, no network, no clock) so
it can be unit-tested with tiny synthetic fixtures without ever touching a
real historical distribution. `scripts/research/math002b_consensus_robustness.py`
is the only caller that wires this to a real, read-only PostgreSQL source.

LOAD-BEARING: nothing here recomputes or replaces
`analytics.feature_engine.consensus.compute_consensus_features` -- that
remains the single source of truth for FULL3/BB/BO/BYO/BINANCE_ONLY
aggregates. This module only computes the PREDECLARED comparison metrics
(§11 of the MATH-002B task) on top of already-computed
`ConsensusFeatureVector` results, and small distribution summaries.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Optional, Sequence

# ---- variant names (frozen labels for this study only -- not a production
# concept, never persisted, never a calculation_version input) --------------
FULL3 = "FULL3"
BB = "BB"          # binance + bybit, omit okx
BO = "BO"          # binance + okx, omit bybit
BYO = "BYO"        # bybit + okx, omit binance
BINANCE_ONLY = "BINANCE_ONLY_RESEARCH_BASELINE"  # RESEARCH ONLY -- see module docstring

CONTROLLED_PAIR_NAMES = (BB, BO, BYO)


@dataclass(frozen=True)
class PairComparison:
    """One predeclared comparison of a controlled 2-venue variant against the
    real FULL3 (3/3) consensus for exactly one bucket/timeframe/family. Every
    field name matches a metric predeclared in MATH-002B §11-§12 BEFORE any
    historical result is inspected."""
    bucket_ts: object          # datetime, kept generic to stay DB-library-free here
    timeframe: str
    family: str
    pair_name: str
    omitted_venue: str

    full3_median: Optional[float]
    pair_median: Optional[float]
    full3_mad: Optional[float]
    pair_mad: Optional[float]

    full3_agreement: Optional[float]
    pair_agreement: Optional[float]
    full3_confidence: Optional[float]
    pair_confidence: Optional[float]

    full3_has_outlier: bool
    pair_has_outlier: bool

    full3_quality_gate_pass: Optional[bool]
    pair_quality_gate_pass: Optional[bool]

    def __post_init__(self) -> None:
        if self.pair_name not in CONTROLLED_PAIR_NAMES:
            raise ValueError(f"pair_name must be one of {CONTROLLED_PAIR_NAMES}, got {self.pair_name!r}")

    # ---- predeclared deltas (§12) ------------------------------------------
    @property
    def signed_median_delta(self) -> Optional[float]:
        """The RAW signed difference (`pair_median - full3_median`) -- honestly
        named as signed, never labeled "absolute". Use this when direction
        matters (e.g. as an input to `sign_flipped`); use
        `absolute_median_delta` for magnitude/distortion-size reporting."""
        if self.full3_median is None or self.pair_median is None:
            return None
        return self.pair_median - self.full3_median

    @property
    def absolute_median_delta(self) -> Optional[float]:
        """TRUE magnitude of the median distortion -- always >= 0 (tech-lead
        review round 1, finding 1: the prior implementation returned the raw
        SIGNED difference under an "absolute" name, which could understate
        large negative distortions in percentile/max summaries). Callers that
        need the signed value use `signed_median_delta` instead."""
        signed = self.signed_median_delta
        if signed is None:
            return None
        return abs(signed)

    @property
    def relative_median_delta(self) -> Optional[float]:
        """None (not zero, not a fabricated number) whenever FULL3 is zero or
        near-zero -- an unstable relative percentage must never silently
        stand in for a real value (MATH-002B §12: 'do not use unstable
        relative percentages when FULL3 is zero/near-zero')."""
        if self.full3_median is None or self.pair_median is None:
            return None
        if math.isclose(self.full3_median, 0.0, abs_tol=1e-9):
            return None
        return (self.pair_median - self.full3_median) / abs(self.full3_median)

    @property
    def sign_flipped(self) -> Optional[bool]:
        if self.full3_median is None or self.pair_median is None:
            return None
        return _sign(self.full3_median) != _sign(self.pair_median)

    @property
    def agreement_delta(self) -> Optional[float]:
        if self.full3_agreement is None or self.pair_agreement is None:
            return None
        return self.pair_agreement - self.full3_agreement

    @property
    def confidence_delta(self) -> Optional[float]:
        if self.full3_confidence is None or self.pair_confidence is None:
            return None
        return self.pair_confidence - self.full3_confidence

    @property
    def outlier_report_flip(self) -> bool:
        return self.full3_has_outlier != self.pair_has_outlier

    @property
    def quality_gate_flip(self) -> Optional[bool]:
        if self.full3_quality_gate_pass is None or self.pair_quality_gate_pass is None:
            return None
        return self.full3_quality_gate_pass != self.pair_quality_gate_pass


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


@dataclass(frozen=True)
class DistributionSummary:
    """count/median/p75/p90/p95/p99/max over a sample of finite floats
    (MATH-002B §11's required distribution shape). p99 is `None` when the
    sample is too small to make a p99 estimate meaningful (< 100 points) --
    never silently computed from an inadequate sample and presented as if
    it were reliable."""
    count: int
    median: Optional[float]
    p75: Optional[float]
    p90: Optional[float]
    p95: Optional[float]
    p99: Optional[float]
    max: Optional[float]


def summarize(values: Sequence[float]) -> DistributionSummary:
    finite = [v for v in values if v is not None and math.isfinite(v)]
    n = len(finite)
    if n == 0:
        return DistributionSummary(count=0, median=None, p75=None, p90=None,
                                    p95=None, p99=None, max=None)
    s = sorted(finite)

    def _pct(p: float) -> float:
        # Nearest-rank method -- simple, deterministic, no interpolation
        # assumptions that could silently misrepresent a small sample.
        idx = max(0, min(n - 1, math.ceil(p * n) - 1))
        return s[idx]

    return DistributionSummary(
        count=n,
        median=statistics.median(s),
        p75=_pct(0.75),
        p90=_pct(0.90),
        p95=_pct(0.95),
        p99=_pct(0.99) if n >= 100 else None,
        max=s[-1],
    )


def sign_flip_rate(comparisons: Sequence[PairComparison]) -> Optional[float]:
    flips = [c.sign_flipped for c in comparisons if c.sign_flipped is not None]
    if not flips:
        return None
    return sum(1 for f in flips if f) / len(flips)


def outlier_report_flip_rate(comparisons: Sequence[PairComparison]) -> Optional[float]:
    if not comparisons:
        return None
    return sum(1 for c in comparisons if c.outlier_report_flip) / len(comparisons)


def quality_gate_flip_rate(comparisons: Sequence[PairComparison]) -> Optional[float]:
    flips = [c.quality_gate_flip for c in comparisons if c.quality_gate_flip is not None]
    if not flips:
        return None
    return sum(1 for f in flips if f) / len(flips)
