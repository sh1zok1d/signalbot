"""Non-outcome-bearing MARKET-01 episode-construction throughput bench.

Uses SYNTHETIC_SNAPSHOT only. Does not load CORE/OI snapshots, does not
consume the canonical reservation, and does not run confirmatory
OLS/bootstrap/classification.
"""

from __future__ import annotations

import argparse
import cProfile
import pstats
import time
from io import StringIO

import numpy as np

from scripts.research.market_01_episode_construction_fast import construct_episodes_fast
from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    BAR_MS,
    CALENDAR_DAY_MS,
    COMMON_START_MS,
    FIVE_MS,
    OiView,
    PriceView,
    SYNTHETIC_SNAPSHOT,
    construct_episodes,
)


def make_synthetic_views(
    *,
    n_days_hist: int = 30,
    n_days_eval: int = 2,
    seed: int = 1,
    price_sigma: float = 0.0003,
    oi_sigma: float = 0.00015,
    spike_every_5m: int = 40,
    spike_log: float = 0.012,
) -> tuple[PriceView, OiView]:
    """Contiguous 1m GBM-like price + 5m OI covering hist+eval days."""
    start_open = COMMON_START_MS - int(n_days_hist) * CALENDAR_DAY_MS
    n_min = int((n_days_hist + n_days_eval) * CALENDAR_DAY_MS / BAR_MS) + 180
    rng = np.random.default_rng(int(seed))
    logrets = rng.normal(0.0, float(price_sigma), size=n_min)
    # Sparse large 1m moves so some 30m impulses clear the 90th percentile.
    if spike_every_5m > 0:
        for i in range(0, n_min, int(spike_every_5m) * 5):
            logrets[i] += float(spike_log) * (1.0 if (i // 5) % 2 == 0 else -1.0)
    closes = 100.0 * np.exp(np.cumsum(logrets))
    open_ms = start_open + np.arange(n_min, dtype=np.int64) * BAR_MS
    price = PriceView(
        open_time_ms=open_ms,
        available_at_ms=open_ms + BAR_MS,
        close=np.asarray(closes, dtype=np.float64),
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )
    n_oi = int((n_min * BAR_MS) / FIVE_MS)
    oi_log = rng.normal(0.0, float(oi_sigma), size=n_oi)
    if spike_every_5m > 0:
        for i in range(0, n_oi, int(spike_every_5m)):
            oi_log[i] += 0.02
    oi_vals = 10.0 * np.exp(np.cumsum(oi_log))
    create = start_open + np.arange(n_oi, dtype=np.int64) * FIVE_MS
    oi = OiView(
        create_time_ms=create,
        available_at_ms=create + FIVE_MS,
        sum_open_interest=np.asarray(oi_vals, dtype=np.float64),
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )
    return price, oi


def _count(episodes) -> dict[str, int]:
    out = {
        "n": len(episodes),
        "occupying": 0,
        "eligible": 0,
        "candidate": 0,
        "baseline": 0,
    }
    for rec in episodes:
        if rec.occupies_slot:
            out["occupying"] += 1
        if rec.confirmatory_eligible:
            out["eligible"] += 1
            if rec.candidate:
                out["candidate"] += 1
            else:
                out["baseline"] += 1
    return out


def time_construct(fn, price, oi, *, repeats: int = 1) -> tuple[float, list]:
    elapsed = []
    episodes = []
    for _ in range(int(repeats)):
        t0 = time.perf_counter()
        episodes = fn(price, oi)
        elapsed.append(time.perf_counter() - t0)
    return min(elapsed), episodes


def profile_frozen(price, oi, *, sort: str = "tottime", lines: int = 30) -> str:
    pr = cProfile.Profile()
    pr.enable()
    construct_episodes(price, oi)
    pr.disable()
    buf = StringIO()
    stats = pstats.Stats(pr, stream=buf).sort_stats(sort)
    stats.print_stats(int(lines))
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-days-hist", type=int, default=30)
    parser.add_argument("--n-days-eval", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--profile-frozen", action="store_true")
    parser.add_argument("--skip-frozen", action="store_true")
    args = parser.parse_args(argv)

    price, oi = make_synthetic_views(
        n_days_hist=args.n_days_hist,
        n_days_eval=args.n_days_eval,
        seed=args.seed,
    )
    print(
        f"synthetic n_days_hist={args.n_days_hist} n_days_eval={args.n_days_eval} "
        f"seed={args.seed} n_1m={price.close.shape[0]} snapshot={price.snapshot_id}"
    )
    if args.profile_frozen:
        print(profile_frozen(price, oi))
    frozen_s = None
    frozen_ep = None
    if not args.skip_frozen:
        frozen_s, frozen_ep = time_construct(
            construct_episodes, price, oi, repeats=args.repeats
        )
        print(f"frozen_construct_episodes_s={frozen_s:.6f} {_count(frozen_ep)}")
    fast_s, fast_ep = time_construct(
        construct_episodes_fast, price, oi, repeats=args.repeats
    )
    print(f"fast_construct_episodes_s={fast_s:.6f} {_count(fast_ep)}")
    if frozen_s is not None and frozen_s > 0:
        print(f"speedup={frozen_s / fast_s:.2f}x")
    if frozen_ep is not None:
        from scripts.research.market_01_episode_construction_fast import (
            episode_field_pairs,
        )

        episode_field_pairs(frozen_ep, fast_ep)
        print("field_equality=EXACT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
