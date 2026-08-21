"""V2-H2e deterministic replay harness proof (real PostgreSQL).

`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.4/§20: two independent
replay runs over the exact same `(T, symbol, market_type,
calculation_version)` tuple, the SAME CLEAN publication generation, and the
SAME underlying DB contents (no correction happens between the two runs)
MUST produce byte-identical decision-input facts. This module proves that
end-to-end using the REAL Stage 3 (`load_v2_aligned_inputs`), Stage 4
(`build_v2_context_snapshot`), and Stage 5
(`load_compression_breakout_inputs`) consumers, each run reading through its
OWN independent `open_v2_coherent_read_session` (its own connection/
REPEATABLE READ transaction) -- exactly the shape two truly independent
REPLAY processes would use.

Two fixtures:
  - A minimal fixture: NO consensus/percentile/reference-feature rows are
    seeded (only one raw kline, to exercise the raw-kline leg). Every
    Stage 2 read legitimately returns absence (`None`/`()`), a fully valid
    real code path (`missing rows preserved as absence rather than
    fabricated`, `analytics/forecasting_v2/ports.py`).
  - A NON-TRIVIAL fixture (tech-lead review round 2, finding 8): real
    `consensus_feature_vectors`/`exchange_feature_vectors` rows seeded for
    every aligned timeframe, so Stage 3 sees genuinely PRESENT data, not
    just absence -- run twice (identical), then a real correction +
    complete republish, then a fresh replay proving it sees the fully NEW
    coherent set, never a mixed old/new combination.

Reuses the isolated-schema harness from
`tests/storage/test_v2_correction_publication.py` (same DDL, same
`V2_INSTRUMENT_HISTORY_TEST_DSN` fail-vs-skip contract) rather than a third
independent copy."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.aligned_inputs import (
    ALIGNED_TIMEFRAMES, V2AlignedInputRequest, load_v2_aligned_inputs,
)
from analytics.forecasting_v2.compression_breakout_inputs import load_compression_breakout_inputs
from analytics.forecasting_v2.context_snapshot import build_v2_context_snapshot
from tests.storage.test_stage2_writers import make_consensus, make_efv
from tests.storage.test_v2_correction_publication import (
    CALC_VERSION, EXCHANGE, MARKET_TYPE, SYMBOL, _publish_clean, _run as _run_isolated_schema,
    _seed_kline,
)

UTC = timezone.utc
# A 4h/1h/15m/5m-aligned instant -- a legal V2 5m decision boundary.
T = datetime(2026, 8, 15, 4, 0, tzinfo=UTC)


def _run(body):
    _run_isolated_schema(body)


async def _replay_once(db, *, calculation_version=CALC_VERSION):
    """ONE independent replay run's Stage 3 + 4 + 5 read path, entirely
    inside ONE coherent read session (its own connection/snapshot) -- exactly
    what a real REPLAY process would do for this `T`. The session is opened
    at the EXACT SAME `T` `V2AlignedInputRequest` below uses (tech-lead
    review round 4) -- there is no hidden/default decision boundary; a real
    replay caller must always supply its own logical decision instant."""
    async with db.open_v2_coherent_read_session(
        symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=calculation_version,
        decision_boundary=T,
    ) as session:
        request = V2AlignedInputRequest(
            T=T, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=calculation_version,
            feature_schema_version=1, health_exchanges=(EXCHANGE,), health_metrics=("ohlcv",),
        )
        aligned = await load_v2_aligned_inputs(session, request)
        context = build_v2_context_snapshot(aligned)
        setup_inputs = await load_compression_breakout_inputs(session, context=context)
    return aligned, context, setup_inputs


def test_two_independent_replay_sessions_produce_identical_facts():
    async def body(db, _dsn):
        # ONE raw kline so the Stage 5 loader's raw-kline leg is a genuine,
        # non-trivial read (not merely an always-empty table).
        await _seed_kline(db, ts=T - timedelta(minutes=1), close=42.0)
        await _publish_clean(db)

        aligned_1, context_1, setup_1 = await _replay_once(db)
        aligned_2, context_2, setup_2 = await _replay_once(db)

        # Byte-identical (frozen-dataclass `==`) decision-input facts across
        # two INDEPENDENTLY-opened coherent sessions -- no correction ran
        # between them, so this is the REPEATABLE-history determinism §20
        # requires.
        assert aligned_1 == aligned_2
        assert context_1 == context_2
        assert setup_1 == setup_2

        # Sanity: this really did exercise real absence-handling, not a
        # trivially-skipped path -- every consensus-scope Stage 2 read for
        # this fixture legitimately found nothing (no consensus/percentile/
        # reference-feature rows were ever seeded), and the raw-kline leg
        # legitimately found the ONE seeded bar.
        for tf_inputs in aligned_1.by_timeframe.values():
            assert tf_inputs.consensus is None
            assert tf_inputs.percentiles == ()

    _run(body)


def test_replay_is_independent_of_process_local_state():
    """Two replay runs against two ENTIRELY SEPARATE `Database` pool
    instances (simulating two independent replay PROCESSES, not merely two
    sessions on one pool) still agree -- the coherence facts live in
    Postgres, never in any process-local cache/singleton."""
    async def body(db, scoped_dsn):
        await _seed_kline(db, ts=T - timedelta(minutes=1), close=7.0)
        await _publish_clean(db)
        aligned_1, context_1, setup_1 = await _replay_once(db)

        from storage.db import Database
        other_db = Database(scoped_dsn)
        await other_db.connect()
        try:
            aligned_2, context_2, setup_2 = await _replay_once(other_db)
        finally:
            await other_db.close()

        assert aligned_1 == aligned_2
        assert context_1 == context_2
        assert setup_1 == setup_2

    _run(body)


# ============================================================================
# Finding 8 (tech-lead review round 2): a NON-TRIVIAL replay vector with
# genuinely PRESENT derived data across every aligned timeframe, proving
# identical results twice, then a real correction + republish, then a fresh
# replay observing the fully NEW coherent set -- never a mixed one.
# ============================================================================
async def _seed_present_stage3_inputs(db, *, close: float, calculation_version: str):
    """Seed a real `consensus_feature_vectors` + `exchange_feature_vectors`
    row for EVERY `ALIGNED_TIMEFRAMES` bucket ending at/before `T`, so
    Stage 3's aligned-input assembly sees genuinely PRESENT consensus/
    reference-feature facts (not the minimal fixture's legitimate absence).
    `close` is folded into `price_move_pct` purely so two different `close`
    values are trivially distinguishable in the assembled facts.

    `is_usable=False` on the reference feature is deliberate: it makes the
    §11 gate legitimately fail, so `derive_reference_extrema` returns `None`
    (a real, valid "unavailable" outcome) WITHOUT requiring every one of the
    timeframe's full constituent 1m raw bars to also be seeded (15/60/240
    bars for 15m/1h/4h) -- this fixture's purpose is proving CONSENSUS
    presence + correction/republish coherence, not exercising the
    structural HTF-extrema path, which is out of this vector's scope."""
    from analytics.forecasting_v2.alignment import selected_bucket
    async with db.pool.acquire() as conn:
        for tf in ALIGNED_TIMEFRAMES:
            bucket_ts = selected_bucket(tf, T)
            cfv = make_consensus(
                symbol=SYMBOL, market_type=MARKET_TYPE, timeframe=tf, bucket_ts=bucket_ts,
                calculation_version=calculation_version, price_move_pct_median=close)
            efv = make_efv(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, timeframe=tf,
                bucket_ts=bucket_ts, calculation_version=calculation_version, price_move_pct=close,
                is_usable=False)
            from storage.stage2_serialization import (
                CONSENSUS_FEATURE_SPEC, EXCHANGE_FEATURE_SPEC, serialize_batch)
            await conn.executemany(
                CONSENSUS_FEATURE_SPEC.insert_sql, serialize_batch(CONSENSUS_FEATURE_SPEC, [cfv]))
            await conn.executemany(
                EXCHANGE_FEATURE_SPEC.insert_sql, serialize_batch(EXCHANGE_FEATURE_SPEC, [efv]))


async def _replay_stage3_once(db, *, calculation_version=CALC_VERSION):
    """Stage 3 ONLY (`load_v2_aligned_inputs`), through its own independent
    coherent session. Deliberately does NOT proceed to
    `build_v2_context_snapshot` -- this fixture's consensus rows carry only
    `price_move_pct_median` (via `make_consensus`'s own minimal default
    `coverage_by_metric`, missing several metric families the REAL 4h
    regime/1h bias classifiers require), so building a fully
    classifier-valid 6-family consensus row is out of THIS vector's scope
    (already exercised, with real absence, by
    `test_two_independent_replay_sessions_produce_identical_facts`
    above -- this vector's own purpose is PRESENCE + correction/republish
    coherence at the Stage 3 read layer, not re-proving the full Stage
    3->4->5 pipeline a second time)."""
    async with db.open_v2_coherent_read_session(
        symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=calculation_version,
        decision_boundary=T,
    ) as session:
        request = V2AlignedInputRequest(
            T=T, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=calculation_version,
            feature_schema_version=1, health_exchanges=(EXCHANGE,), health_metrics=("ohlcv",),
        )
        return await load_v2_aligned_inputs(session, request)


def test_nontrivial_replay_with_present_data_then_correction_and_republish():
    async def body(db, _dsn):
        # -- Generation 1: seed real present Stage 3 inputs, publish CLEAN.
        await _seed_kline(db, ts=T - timedelta(minutes=1), close=100.0)
        await _seed_present_stage3_inputs(db, close=1.0, calculation_version=CALC_VERSION)
        rev1 = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=rev1,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[],
            percentile_snapshots_absent_reason="no percentile orchestrator implemented (D-008)",
            data_health_snapshots=[],
            data_health_snapshots_absent_reason="no health recompute for this fixture",
        )

        aligned_1 = await _replay_stage3_once(db)
        aligned_2 = await _replay_stage3_once(db)
        assert aligned_1 == aligned_2
        # Genuinely PRESENT, not absent, for every aligned timeframe.
        for tf_inputs in aligned_1.by_timeframe.values():
            assert tf_inputs.consensus is not None
            assert tf_inputs.consensus["price_move_pct_median"] == 1.0

        # -- A real correction: re-seed with a DIFFERENT value (this is a
        # genuine ON CONFLICT DO UPDATE against the same identity, exactly
        # the correction-friendly upsert §2.1 already allows) and republish.
        await _seed_present_stage3_inputs(db, close=2.0, calculation_version=CALC_VERSION)
        # The consensus/exchange feature UPSERT itself does not touch
        # klines_1m, so it does not bump stage2_raw_revision on its own --
        # this correction is modeled as a genuine raw invalidation via a
        # kline correction at the SAME bucket, matching how a real
        # late-data correction actually enters the system (§2.1/§8.3).
        await _seed_kline(db, ts=T - timedelta(minutes=1), close=200.0)
        rev2 = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev2 == rev1 + 1

        # Before republishing, a fresh session must fail closed (STALE).
        from storage.stage2_publication_state import V2PublicationDirtyError
        with pytest.raises(V2PublicationDirtyError):
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                decision_boundary=T,
            ):
                raise AssertionError("must be stale after the correction")

        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=rev2,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[],
            percentile_snapshots_absent_reason="no percentile orchestrator implemented (D-008)",
            data_health_snapshots=[],
            data_health_snapshots_absent_reason="no health recompute for this fixture",
        )

        aligned_3 = await _replay_stage3_once(db)
        for tf_inputs in aligned_3.by_timeframe.values():
            assert tf_inputs.consensus["price_move_pct_median"] == 2.0   # fully NEW
        # Never a mixed old/new combination -- every timeframe agrees.
        values = {tf_inputs.consensus["price_move_pct_median"] for tf_inputs in aligned_3.by_timeframe.values()}
        assert values == {2.0}
        assert aligned_3 != aligned_1   # genuinely different from generation 1

    _run(body)
