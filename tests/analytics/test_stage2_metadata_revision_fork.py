"""Tech-lead review 4991738511's mandatory acceptance test: the calculation_
version fork mechanism connected end-to-end to the REAL Stage-2 feature-
assembly path -- `common.stage2_config.Stage2Config`, `analytics.
feature_engine.input_adapter.build_assembly_context`/
`assemble_exchange_feature_request`/`load_exchange_feature_request`, and a
REAL `storage.stage2_readers.ExchangeFeatureRawBundle` (never a hand-rolled
stand-in dict) -- not merely `storage/db.py`'s own history-table storage
layer (that half is proven for real against PostgreSQL separately in
`tests/storage/test_v2_instrument_history_readers.py`).

The prior round's `accepted_code_version` mechanism was correctly rejected:
it proved only that two STORED LABELS differed, never that this exact
assembly path was mechanically prevented from consuming NEW critical
metadata under an OLD `calculation_version`. This file is the executable
proof that gap is closed:

  1. `test_stale_config_revision_fails_closed_against_new_metadata` --
     freeze CONFIG at revision 1 + code_version=CODE, build a valid
     request against metadata A (tick=0.10) -> calculation_version=CV_A.
     Then metadata B (tick=0.50) is accepted, requiring revision 2 (the
     raw bundle's `required_metadata_revision` reflects this). Assembling
     AGAINST THE SAME, still-revision-1 config now raises
     `FeatureInputError` BEFORE any `ExchangeFeatureRequest` is
     constructed.
  2. `test_updated_config_revision_allows_new_metadata_and_forks_calculation_version`
     -- the SAME metadata B, now with config updated to revision 2,
     succeeds and produces `calculation_version=CV_B != CV_A`.
  3. `test_noncritical_metadata_change_does_not_require_new_revision` --
     metadata B / revision 2 remains active; changing only a non-critical
     field (price_precision) does not require a new revision (the raw
     bundle's `required_metadata_revision` stays 2, and config revision 2
     remains valid).

Uses a fake in-memory `Reader` (implementing the `RawBundleReader`
Protocol) exactly like `tests/analytics/test_exchange_feature_pipeline.py`
and `tests/analytics/test_exchange_feature_input_adapter.py` already do for
every other pipeline-level test -- REAL Stage2Config/assembly/dataclasses,
fake I/O only, no live database needed to prove THIS identity-fork
behavior. The real-Postgres proof of the ACTUAL atomic revision bump at
`Database.upsert_exchange_instrument`/`bootstrap_instrument_metadata_revision`
lives in `tests/storage/test_v2_instrument_history_readers.py`."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from common.stage2_config import Stage2Config
from analytics.feature_engine.input_adapter import (
    FeatureInputError, load_exchange_feature_request)
from storage.stage2_readers import ExchangeFeatureRawBundle

CFG = Stage2Config.load()
EX, SYM, MT = "binance", "BTCUSDT", "perp"
B = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
CODE = "code-vX"


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def _cfg_at_revision(rev: int) -> Stage2Config:
    raw = copy.deepcopy(CFG._raw)
    raw["defaults"]["instrument_metadata_revision"] = rev
    cfg = Stage2Config(raw)
    cfg._validate()
    return cfg


def _m(**kw):
    return MappingProxyType(dict(kw))


def _kline(minute, **kw):
    base = dict(exchange=EX, symbol=SYM, ts=B, open=100.0, high=110.0, low=95.0,
                close=101.0, volume=10.0, taker_buy_volume=1.0, taker_sell_volume=0.5)
    base.update(kw)
    return _m(**base)


def _cap(**kw):
    base = dict(exchange=EX, symbol=SYM, market_type=MT, metric="liquidations",
                live_supported=True, historical_supported=False, coverage_type="snapshot",
                expected_freshness_s=None, enabled=True)
    base.update(kw)
    return _m(**base)


def _inst(*, tick_size, price_precision=None, **kw):
    base = dict(exchange=EX, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
                quantity_unit="base", contract_multiplier=None, tick_size=tick_size,
                price_precision=price_precision, quantity_precision=None,
                metadata_source="exchange_api", fetched_at=B, is_stale=False, note=None)
    base.update(kw)
    return _m(**base)


def _bundle(*, tick_size, required_metadata_revision, price_precision=None):
    return ExchangeFeatureRawBundle(
        klines=(_kline(0),), open_interest=(), latest_funding=None, liquidations=(),
        instrument=_inst(tick_size=tick_size, price_precision=price_precision),
        liquidation_capability=_cap(),
        required_metadata_revision=required_metadata_revision)


class Reader:
    def __init__(self, bundle):
        self.bundle = bundle
        self.calls = []

    async def fetch_exchange_feature_raw_bundle(self, **kw):
        self.calls.append(kw)
        return self.bundle


def _build(cfg, bundle, *, code_version=CODE):
    return load_exchange_feature_request(
        Reader(bundle), cfg, exchange=EX, symbol=SYM, market_type=MT,
        timeframe="5m", bucket_ts=B, code_version=code_version,
        liquidation_feed_available=True)


# ============================================================================
# 1. OLD config (revision 1) + NEW metadata (requires revision 2) -> fail
# closed, no ExchangeFeatureRequest constructed.
# ============================================================================
def test_stale_config_revision_fails_closed_against_new_metadata():
    cfg_rev1 = _cfg_at_revision(1)

    # Metadata A (tick=0.10), matching revision 1 -- succeeds.
    bundle_a = _bundle(tick_size=0.10, required_metadata_revision=1)
    req_a = _run(_build(cfg_rev1, bundle_a))
    cv_a = req_a.calculation_version
    assert req_a.instrument_metadata.tick_size == 0.10

    # Metadata B (tick=0.50) has been deliberately accepted, requiring
    # revision 2 -- but THIS config is still pinned at revision 1.
    bundle_b = _bundle(tick_size=0.50, required_metadata_revision=2)
    with pytest.raises(FeatureInputError, match="instrument_metadata_revision"):
        _run(_build(cfg_rev1, bundle_b))

    # (kept for the next test) the CV_A computed above is asserted != CV_B there.
    assert cv_a == req_a.calculation_version   # unchanged by the failed attempt


# ============================================================================
# 2. Config updated to revision 2 + the SAME NEW metadata -> succeeds, and
# calculation_version genuinely forks (CV_B != CV_A).
# ============================================================================
def test_updated_config_revision_allows_new_metadata_and_forks_calculation_version():
    cfg_rev1 = _cfg_at_revision(1)
    cfg_rev2 = _cfg_at_revision(2)

    bundle_a = _bundle(tick_size=0.10, required_metadata_revision=1)
    req_a = _run(_build(cfg_rev1, bundle_a))
    cv_a = req_a.calculation_version

    bundle_b = _bundle(tick_size=0.50, required_metadata_revision=2)
    req_b = _run(_build(cfg_rev2, bundle_b))
    cv_b = req_b.calculation_version

    assert req_b.instrument_metadata.tick_size == 0.50
    assert cv_b != cv_a   # THE mandatory proof: a real, executable fork.

    # And revision 2's config can no longer serve the OLD metadata's own
    # required_metadata_revision=1 (a stale bundle would now be the
    # mismatch) -- the check is symmetric, not merely one-directional.
    stale_bundle_a = _bundle(tick_size=0.10, required_metadata_revision=1)
    with pytest.raises(FeatureInputError, match="instrument_metadata_revision"):
        _run(_build(cfg_rev2, stale_bundle_a))


# ============================================================================
# 3. Non-critical-only metadata change (price_precision) under an ALREADY
# adopted revision (2) requires NO further config change -- proves findings
# 10/14: only a deliberately-accepted CRITICAL change ever forks anything.
# ============================================================================
def test_noncritical_metadata_change_does_not_require_new_revision():
    cfg_rev2 = _cfg_at_revision(2)

    bundle_b = _bundle(tick_size=0.50, required_metadata_revision=2, price_precision=1)
    req_b = _run(_build(cfg_rev2, bundle_b))

    # Only price_precision changes -- required_metadata_revision correctly
    # STAYS 2 (a real deployment's storage layer never bumps it for a
    # non-critical change; see
    # tests/storage/test_v2_instrument_history_readers.py::
    # test_noncritical_field_only_change_does_not_bump_required_revision).
    bundle_b_precision_changed = _bundle(
        tick_size=0.50, required_metadata_revision=2, price_precision=9)
    req_b2 = _run(_build(cfg_rev2, bundle_b_precision_changed))

    assert req_b.calculation_version == req_b2.calculation_version   # no fork
    assert req_b2.instrument_metadata.price_precision == 9


# ============================================================================
# Sanity: an unresolved config/metadata revision mismatch is caught
# regardless of DIRECTION (config ahead of metadata is just as much a
# mismatch as metadata ahead of config) -- there is no implicit "greater
# than" tolerance, only exact equality.
# ============================================================================
def test_config_ahead_of_metadata_also_fails_closed():
    cfg_rev2 = _cfg_at_revision(2)
    bundle_still_rev1 = _bundle(tick_size=0.10, required_metadata_revision=1)
    with pytest.raises(FeatureInputError, match="instrument_metadata_revision"):
        _run(_build(cfg_rev2, bundle_still_rev1))
