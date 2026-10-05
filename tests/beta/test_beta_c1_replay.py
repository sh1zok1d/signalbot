"""C1 replay (C0 vs C1 on the same recorded inputs): pure report and read-only PG path."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.c1_replay import C0_VERSION, c0_config, run_c1_replay
from beta.config import BetaConfig
from beta.dry_run import sample_grid
from beta.state_tape import BUCKET, metric_key

CFG = BetaConfig.load()
IDENT = {"feature_schema_version": 1, "calculation_version": "a" * 16,
         "stage2_config_hash": "b" * 64, "stage2_config_version": "v"}
TIERS = {"none_below_days": 3, "low_below_days": 7, "building_below_days": 30}
T0 = datetime(2026, 8, 31, tzinfo=timezone.utc)         # a Monday


def _tape(days: int, seed: int = 4) -> dict:
    import random
    rng = random.Random(seed)
    out, price = {}, 100.0
    for i in range(days * 288):
        b = T0 + i * BUCKET
        weekend = b.weekday() >= 5
        scale = 0.4 if weekend else 1.0                   # calmer, thinner weekends
        move = rng.gauss(0, 0.001) * scale
        m = {"c:volume_notional_usd_sum": 1e6 * scale * (1 + rng.random()),
             "c:taker_delta_notional_usd_sum": move * 1e9}
        for ex in CFG.exchanges:
            m.update({metric_key(ex, "kline_open"): price, metric_key(ex, "kline_close"): price * (1 + move),
                      metric_key(ex, "kline_high"): price * (1 + abs(move) + 0.0005 * scale),
                      metric_key(ex, "kline_low"): price * (1 - abs(move) - 0.0005 * scale)})
        price *= 1 + move
        out[b] = m
    return out


def test_c0_config_is_the_pinned_v2_identity():
    from beta.context import KNOWN_CONTEXT_DIGESTS, verify_versions
    v = verify_versions(c0_config(CFG))
    assert v["context_version"] == C0_VERSION and v["context_digest"] == KNOWN_CONTEXT_DIGESTS[C0_VERSION]


def test_replay_reports_per_day_type_changes_and_push_gate_flips():
    metrics = _tape(38)
    hours = [datetime(2026, 10, 3, 4), datetime(2026, 10, 3, 14), datetime(2026, 10, 4, 9),   # Sat, Sat, Sun
             datetime(2026, 10, 4, 21), datetime(2026, 10, 5, 10), datetime(2026, 10, 6, 15)]  # Sun, Mon, Tue
    samples = [h.replace(tzinfo=timezone.utc) - BUCKET for h in hours]
    decisions = [{"decision_ts": b + BUCKET, "decision": "SUPPRESSED", "suppression_reason": "HOUR_NOT_UNUSUAL"}
                 for b in samples[::3]]
    rep = run_c1_replay(CFG, sample_buckets=samples, metrics_by_bucket=metrics, oi_rows=[],
                        liquidation_episodes=[], identity=IDENT, code_version="t", tiers=TIERS,
                        push_decisions=decisions)
    assert rep["samples"] == len(samples) and rep["c0"] == "BETA_CONTEXT_1H_V2" and rep["c1"] == "BETA_CONTEXT_1H_V3"
    we, wd = rep["by_day_type"]["WEEKEND"], rep["by_day_type"]["WEEKDAY"]
    assert we["samples"] > 0 and wd["samples"] > 0
    # the pooled reference sees calm weekends as "compressed"; the same-type one does not
    assert we.get("C0:compression_1h", 0) > we.get("C1:compression_1h", 0)
    assert we["btc_state_changed"] > 0
    assert sum(v.get("decisions", 0) for v in rep["push_decisions"].values()) == len(decisions)
    assert set(rep["gate_qualified_samples_per_day"]) == {"C0", "C1", "max_C0", "max_C1"}


@pytest.mark.skipif(not __import__("os").environ.get("BETA_TEST_DSN"), reason="BETA_TEST_DSN not set")
def test_replay_from_db_is_read_only():
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from beta_fakes import ScenarioReader, down_move, quiet, run
    from test_beta_pg_integration import B0, _detect, _rows, _setup
    import test_beta_pg_integration as pgi
    pgi.CALC = pgi.calc_version()

    async def body():
        from beta.c1_replay import run_c1_replay_from_db
        from common.stage2_config import Stage2Config
        from storage.beta_v0_store import BetaStore
        pool = await _setup()
        for i, sc in enumerate([down_move, down_move, quiet]):
            await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET)
        q = ("SELECT (SELECT count(*) FROM beta_state_tape) AS t, (SELECT count(*) FROM beta_context_snapshots) AS c,"
             " (SELECT count(*) FROM beta_push_decisions) AS d")
        before = await _rows(pool, q)
        async with BetaStore(pool).connect() as conn:
            rep = await run_c1_replay_from_db(conn, CFG, Stage2Config.load(), end=B0 + 3 * BUCKET, days=1,
                                              stride_buckets=1)
        assert rep["status"] == "OK" and rep["samples"] >= 1 and rep["tape_rows"] > 0
        assert await _rows(pool, q) == before                       # nothing written
        await pool.close()
    run(body())
