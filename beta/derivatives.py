"""Derivatives in numbers with «обычно» (backlog G2; PRODUCT_DECISION_V2 §2).

Each derivatives number on the 24h surfaces gets a comparable «обычно» with its N:
- **OI change over 24h.** The live number is the venue median of the 24h change
  (`horizons`). Its «обычно» is the median absolute change of non-overlapping UTC-day
  windows over the whole Binance OI history (nightly build, `oi_change_stats`). The
  comparator is Binance only, and the text says so.
- **Funding.** The live 24h mean of `c:funding_rate_median` beside the median of the same
  mean over the 30 prior days, from the same tape (`funding_typical`).
- **Long/short accounts.** Binance's account ratio from the research feed
  (`beta_feed_metrics_5m`), only where that feed runs: the latest value beside the median of
  the daily means of the 30 prior days (`BetaConn.long_short_summary`).

Below MIN_DAYS a comparator is not shown. Nothing here is a forecast or a signal; it is a
description of the current value against its own history.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

import numpy as np

DERIVATIVES_VERSION = "BETA_DERIVATIVES_V1"
DAY_BARS = 288
PRIOR_DAYS = 30
MIN_DAYS = 20                                  # the horizon baselines' maturity (horizons._MATURE_DAYS)
FUNDING_MIN_BUCKETS = DAY_BARS // 2


def oi_change_stats(b) -> dict:
    """Absolute 24h OI change of each UTC day (midnight to midnight, non-overlapping) over the whole
    history: median, 90th percentile and N days. Pure."""
    from .hist_series import BAR_MS
    times = b.times
    mid = np.flatnonzero(times % 86_400_000 == 0)
    mid = mid[mid >= DAY_BARS]
    a, z = b.oi[mid - DAY_BARS], b.oi[mid]
    ok = np.isfinite(a) & np.isfinite(z) & (a > 0)
    ch = np.abs(z[ok] / a[ok] - 1.0) * 100.0
    out = {"version": DERIVATIVES_VERSION, "source": "binance", "n_days": int(ch.size),
           "median_abs_pct": None, "p90_abs_pct": None, "from_ms": None, "to_ms": None}
    if ch.size >= MIN_DAYS:
        days = mid[ok]
        out.update(median_abs_pct=float(np.median(ch)), p90_abs_pct=float(np.quantile(ch, 0.9)),
                   from_ms=int(b.t0 + (int(days[0]) - DAY_BARS) * BAR_MS), to_ms=int(b.t0 + int(days[-1]) * BAR_MS))
    return out


def funding_typical(metrics_by_bucket: Mapping[datetime, Mapping[str, Any]], as_of_bucket: datetime) -> dict:
    """The median, over the PRIOR_DAYS prior days, of the 24h mean of `c:funding_rate_median` (a day
    counts with at least half of its buckets present). Pure."""
    from .horizons import _median
    from .state_tape import BUCKET
    means = []
    for d in range(1, PRIOR_DAYS + 1):
        end = as_of_bucket - timedelta(days=d)
        vals = [float(row["c:funding_rate_median"]) for i in range(DAY_BARS)
                if (row := metrics_by_bucket.get(end - i * BUCKET)) is not None
                and row.get("c:funding_rate_median") is not None]
        if len(vals) >= FUNDING_MIN_BUCKETS:
            means.append(sum(vals) / len(vals))
    return {"days": len(means), "median": _median(means) if len(means) >= MIN_DAYS else None}


def derivatives_block(*, horizons: Mapping[str, Any], funding: Optional[Mapping[str, Any]],
                      oi_stats: Optional[Mapping[str, Any]], long_short: Optional[Mapping[str, Any]]) -> dict:
    """The by-value block every 24h surface renders (stored with the view)."""
    h24 = (horizons or {}).get("24h") or {}
    oi = oi_stats or {}
    return {"version": DERIVATIVES_VERSION,
            "oi_24h": {"change_pct": h24.get("oi_change_pct"), "typical_abs_pct": oi.get("median_abs_pct"),
                       "p90_abs_pct": oi.get("p90_abs_pct"), "n_days": int(oi.get("n_days") or 0),
                       "source": oi.get("source")},
            "funding_24h": {"avg": h24.get("funding_rate_avg"), "typical": (funding or {}).get("median"),
                            "n_days": int((funding or {}).get("days") or 0)},
            "long_short": dict(long_short) if long_short else None}
