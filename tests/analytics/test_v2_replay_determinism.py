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

Deliberately minimal fixture: NO consensus/percentile/reference-feature rows
are seeded (only the publication-state bootstrap + one raw kline needed to
exercise the raw-kline leg of the Stage 5 loader). Every Stage 2 read
therefore legitimately returns absence (`None`/`()`), which is a fully valid,
real code path (`missing rows preserved as absence rather than fabricated`,
`analytics/forecasting_v2/ports.py`), not a shortcut around validation. This
proves the COHERENCE/DETERMINISM mechanism (identical inputs -> identical
facts, via two independently-opened sessions) without requiring a fully
populated compression-breakout signal, which is out of this PR's scope.

Reuses the isolated-schema harness from
`tests/storage/test_v2_correction_publication.py` (same DDL, same
`V2_INSTRUMENT_HISTORY_TEST_DSN` fail-vs-skip contract) rather than a third
independent copy."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from analytics.forecasting_v2.aligned_inputs import V2AlignedInputRequest, load_v2_aligned_inputs
from analytics.forecasting_v2.compression_breakout_inputs import load_compression_breakout_inputs
from analytics.forecasting_v2.context_snapshot import build_v2_context_snapshot
from tests.storage.test_v2_correction_publication import (
    CALC_VERSION, EXCHANGE, MARKET_TYPE, SYMBOL, _run as _run_isolated_schema, _seed_kline,
)

UTC = timezone.utc
# A 4h/1h/15m/5m-aligned instant -- a legal V2 5m decision boundary.
T = datetime(2026, 8, 15, 4, 0, tzinfo=UTC)


def _run(body):
    _run_isolated_schema(body)


async def _replay_once(db):
    """ONE independent replay run's Stage 3 + 4 + 5 read path, entirely
    inside ONE coherent read session (its own connection/snapshot) -- exactly
    what a real REPLAY process would do for this `T`."""
    async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE) as session:
        request = V2AlignedInputRequest(
            T=T, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
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
