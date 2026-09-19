"""MARKET-05 gated scientific data boundary.

Real CORE BTC/ETH scientific outcome loading is refused until a later
ARM authorization. Protected 2025/2026 scientific parse is always
forbidden for development execution.

Synthetic/fixture loaders may construct bars in memory. They still may
not surface protected-OOS timestamps to evaluator logic.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from scripts.research.market05_cross_asset_authority import (
    Market05ExecutionNotAuthorized,
    refuse_bound_scientific_inputs,
    require_execution_authorized_before_outcome_load,
)
from scripts.research.market05_cross_asset_lib import (
    Bar,
    EligibleRow,
    HORIZON_MS,
    Market05ProtectedOOSError,
    PROTECTED_OOS_START_MS,
    assert_development_decision_time,
    assert_no_protected_open_times,
    assert_outcome_window_inside_development,
    build_eligible_row,
    feature_open_times,
    outcome_open_times,
    prefix_open_time,
)


def reject_protected_scientific_bars(bars: Sequence[Bar]) -> None:
    assert_no_protected_open_times([bar.open_time_ms for bar in bars])


def filter_development_open_times(open_times_ms: Iterable[int]) -> list[int]:
    """Reject the whole stream if any protected timestamp is present.

    Development loaders must not silently drop 2025+ bars and continue.
    """
    values = [int(ts) for ts in open_times_ms]
    assert_no_protected_open_times(values)
    return values


def load_feature_window(t_ms: int, bars: Sequence[Bar]) -> list[Bar]:
    assert_development_decision_time(t_ms)
    reject_protected_scientific_bars(bars)
    wanted = set(feature_open_times(t_ms)) | {prefix_open_time(t_ms)}
    selected = [bar for bar in bars if bar.open_time_ms in wanted]
    for bar in selected:
        if bar.open_time_ms >= int(t_ms):
            raise Market05ProtectedOOSError("MARKET_05_FEATURE_BAR_AT_OR_AFTER_T")
    return selected


def load_outcome_window(t_ms: int, bars: Sequence[Bar]) -> list[Bar]:
    assert_development_decision_time(t_ms)
    assert_outcome_window_inside_development(t_ms)
    reject_protected_scientific_bars(bars)
    wanted = set(outcome_open_times(t_ms))
    selected = [bar for bar in bars if bar.open_time_ms in wanted]
    for bar in selected:
        if bar.open_time_ms + 60_000 > PROTECTED_OOS_START_MS:
            raise Market05ProtectedOOSError("MARKET_05_OUTCOME_BAR_CROSSES_PROTECTED_OOS")
        if bar.open_time_ms < int(t_ms) or bar.open_time_ms >= int(t_ms) + HORIZON_MS:
            raise Market05ProtectedOOSError("MARKET_05_OUTCOME_WINDOW_MISMATCH")
    return selected


def load_real_development_scientific_rows(
    *,
    origin: str | None = None,
    btc_snapshot_id: str | None = None,
    eth_snapshot_id: str | None = None,
    dataset_id: str | None = None,
) -> list[EligibleRow]:
    """Production scientific row loader. Always refuses before ARM.

    Must not load CORE outcome rows. Tests patch/spy this boundary.
    """
    require_execution_authorized_before_outcome_load()
    refuse_bound_scientific_inputs(
        origin=origin,
        btc_snapshot_id=btc_snapshot_id,
        eth_snapshot_id=eth_snapshot_id,
        dataset_id=dataset_id,
    )
    raise Market05ExecutionNotAuthorized("MARKET_05_EXECUTION_NOT_AUTHORIZED")


def build_fixture_eligible_row(
    t_ms: int,
    btc_bars: Sequence[Bar],
    btc_prefix: Bar,
    eth_bars: Sequence[Bar],
    eth_prefix: Bar,
) -> EligibleRow | None:
    """Fixture-only constructor. Still enforces development/OOS fences."""
    reject_protected_scientific_bars(list(btc_bars) + list(eth_bars) + [btc_prefix, eth_prefix])
    return build_eligible_row(t_ms, btc_bars, btc_prefix, eth_bars, eth_prefix)
