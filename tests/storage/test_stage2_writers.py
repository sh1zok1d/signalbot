"""Stage 2.1 storage writers against a fake asyncpg pool (no real DB).

Exercises the four public `Database.upsert_*` methods and the isolated
`storage.stage2_serialization` bridge: batch behavior, exact model↔schema↔writer
parity, JSONB canonicalization, idempotent-correction SQL, and fail-loud
validation. No Docker / PostgreSQL / network / env required.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from analytics.data_quality.models import DataHealthSnapshot
from analytics.feature_engine.consensus_models import (
    ConsensusFeatureVector, CoverageEntry, OutlierEntry, ProvenanceEntry,
)
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.percentile_engine.models import PercentileSnapshot
from storage.db import Database
from storage.stage2_serialization import (
    CONSENSUS_FEATURE_SPEC, DATA_HEALTH_SNAPSHOT_SPEC, EXCHANGE_FEATURE_SPEC,
    PERCENTILE_SNAPSHOT_SPEC, Stage2SerializationError, dumps_canonical_jsonb,
    serialize_batch, to_jsonable,
)

UTC = timezone.utc
B = datetime(2026, 7, 22, 0, 0, 0, tzinfo=UTC)
H64 = "a" * 64
H16 = "b" * 16
ALL_SPECS = [EXCHANGE_FEATURE_SPEC, CONSENSUS_FEATURE_SPEC,
             PERCENTILE_SNAPSHOT_SPEC, DATA_HEALTH_SNAPSHOT_SPEC]


# ---- fake asyncpg pool -----------------------------------------------------
class FakeConn:
    def __init__(self):
        self.executemany_calls: list[tuple] = []
        self.execute_calls: list[tuple] = []

    async def executemany(self, sql, rows):
        self.executemany_calls.append((sql, list(rows)))

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        return "OK"


class _Acquire:
    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        self.pool.acquire_count += 1
        return self.pool.conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self):
        self.conn = FakeConn()
        self.acquire_count = 0

    def acquire(self):
        return _Acquire(self)


def _db():
    db = Database("postgresql://unused")
    db.pool = FakePool()
    return db


def _run(coro):
    return asyncio.run(coro)


def _writer(db, spec):
    return {
        "exchange_feature_vectors": db.upsert_exchange_feature_vectors,
        "consensus_feature_vectors": db.upsert_consensus_feature_vectors,
        "percentile_snapshots": db.upsert_percentile_snapshots,
        "data_health_snapshots": db.upsert_data_health_snapshots,
    }[spec.table]


# ---- model factories (build output dataclasses directly) -------------------
def make_efv(**over) -> ExchangeFeatureVector:
    base = dict(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, feature_schema_version=1, calculation_version=H16,
        price_move_pct=0.5, range_width_pct=1.25, close_price=65000.0,
        volume_raw=123.0, volume_raw_unit="base", volume_notional_usd=8_000_000.0,
        taker_buy_notional_usd=5_000_000.0, taker_sell_notional_usd=3_000_000.0,
        taker_delta_notional_usd=2_000_000.0, cvd_delta_notional_usd=-1_500_000.0,
        oi_change_pct=None, oi_unit=None, funding_rate=0.0001,
        long_liquidation_notional=None, short_liquidation_notional=None,
        liquidation_event_count=0, liquidation_feed_quality="snapshot",
        is_snapshot_feed=False, bars_expected=5, bars_present=5, has_gap=False,
        is_usable=True, config_hash=H64, config_version="2.1.0", code_version="deadbeef",
    )
    base.update(over)
    return ExchangeFeatureVector(**base)


def make_consensus(**over) -> ConsensusFeatureVector:
    coverage = MappingProxyType({
        "oi": CoverageEntry(available=2, expected=3, ratio=2 / 3),
    })
    provenance = MappingProxyType({
        "oi": ProvenanceEntry(contributing=("binance", "bybit"),
                              excluded=(("okx", "NO_HISTORICAL_DATA"),)),
    })
    confidence = MappingProxyType({"oi": 0.81, "funding": 0.9})
    feed_quality = MappingProxyType({"binance": "snapshot", "bybit": "full"})
    outliers = MappingProxyType({
        "oi_change_pct": MappingProxyType({
            "bybit": OutlierEntry(robust_z=4.1, reason="ROBUST_Z_THRESHOLD"),
        }),
    })
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version=H16,
        coverage_by_metric=coverage, provenance_by_metric=provenance,
        data_confidence_by_metric=confidence,
        exchanges_expected_max=3, min_coverage_ratio=2 / 3, data_confidence_overall=0.8,
        price_direction_agreement=1.0, flow_direction_agreement=0.66,
        oi_direction_agreement=None,
        price_move_pct_median=0.4, range_width_pct_median=1.1, oi_change_pct_median=None,
        funding_rate_median=0.0001, funding_rate_mad=0.00001,
        volume_notional_usd_sum=16_000_000.0, taker_buy_notional_usd_sum=9_000_000.0,
        taker_sell_notional_usd_sum=7_000_000.0, taker_delta_notional_usd_sum=2_000_000.0,
        cvd_delta_notional_usd_sum=-1_000_000.0,
        observed_long_liquidation_notional_sum=None,
        observed_short_liquidation_notional_sum=None,
        observed_liquidation_event_count_sum=None,
        liquidation_feed_quality_by_exchange=feed_quality,
        price_move_pct_mad=0.05, oi_change_pct_mad=None, outlier_exchanges=outliers,
        consensus_confidence=87.5, is_partial_consensus=False,
        config_hash=H64, config_version="2.1.0", code_version="deadbeef",
    )
    base.update(over)
    return ConsensusFeatureVector(**base)


def make_percentile(**over) -> PercentileSnapshot:
    base = dict(
        scope="exchange", exchange="binance", symbol="BTCUSDT", market_type="perp",
        metric="oi_change_pct", timeframe="5m", percentile_window="7d", bucket_ts=B,
        value=0.5, percentile_rank=0.9, sample_size=100,
        sample_window_start=datetime(2026, 7, 15, tzinfo=UTC),
        sample_window_end=datetime(2026, 7, 21, 23, 59, tzinfo=UTC),
        confidence_tier="mature", config_hash=H64, config_version="2.1.0",
        code_version="deadbeef", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return PercentileSnapshot(**base)


def make_health(**over) -> DataHealthSnapshot:
    base = dict(
        symbol="BTCUSDT", exchange="binance", market_type="perp", metric="ohlcv",
        snapshot_ts=B, last_event_at=datetime(2026, 7, 21, 23, 59, tzinfo=UTC),
        expected_interval_s=60, lateness_ms=60000, gap_count=0, largest_gap_s=None,
        backfill_status="complete",
        coverage_window_start=datetime(2026, 7, 21, tzinfo=UTC), coverage_window_end=B,
        is_stale=False, is_usable=True, config_hash=H64, config_version="2.1.0",
        code_version="deadbeef", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return DataHealthSnapshot(**base)


MAKERS = {
    "exchange_feature_vectors": make_efv,
    "consensus_feature_vectors": make_consensus,
    "percentile_snapshots": make_percentile,
    "data_health_snapshots": make_health,
}


def _make(spec, **over):
    return MAKERS[spec.table](**over)


# ============================================================================
# A. General writer behavior (all four)
# ============================================================================
@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_empty_list_returns_zero_and_does_not_acquire(spec):
    db = _db()
    assert _run(_writer(db, spec)([])) == 0
    assert db.pool.acquire_count == 0
    assert db.pool.conn.executemany_calls == []


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_empty_tuple_returns_zero_and_does_not_acquire(spec):
    db = _db()
    assert _run(_writer(db, spec)(())) == 0
    assert db.pool.acquire_count == 0
    assert db.pool.conn.executemany_calls == []


# Malformed batch CONTAINERS must fail before any pool assertion / acquire / DB
# call. str/bytes/bytearray are Sequences but are excluded; dict/set/generator
# and falsey non-sequences (None/False/0/"") are rejected, never treated as an
# empty batch.
_BAD_CONTAINERS = [
    None, False, True, 0, 3.5, "", "abc", b"", b"x", bytearray(b"x"),
    {}, {"a": 1}, set(), frozenset(), (i for i in range(3)), object(),
]


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
@pytest.mark.parametrize("bad", _BAD_CONTAINERS,
                         ids=lambda b: type(b).__name__ + repr(b)[:6])
def test_malformed_container_rejected_before_acquire(spec, bad):
    db = _db()
    with pytest.raises(Stage2SerializationError):
        _run(_writer(db, spec)(bad))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.executemany_calls == []


def test_nonempty_generator_rejected_before_acquire_not_consumed():
    db = _db()
    consumed = []

    def gen():
        for r in [make_efv(), make_efv(calculation_version="c" * 16)]:
            consumed.append(r)
            yield r

    with pytest.raises(Stage2SerializationError):
        _run(db.upsert_exchange_feature_vectors(gen()))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.executemany_calls == []
    assert consumed == []                      # generator was NOT consumed


def test_no_pool_but_empty_valid_batch_returns_zero_without_error():
    # a valid empty Sequence returns 0 even with no pool (no acquire attempted)
    db = Database("postgresql://unused")       # pool is None
    assert _run(db.upsert_percentile_snapshots([])) == 0


def test_return_count_from_validated_params_no_post_write_len_failure():
    # count is derived from validated params, not len(rows); a valid batch writes
    # and returns cleanly with exactly one executemany.
    db = _db()
    rows = [make_health(calculation_version="1" * 16), make_health(calculation_version="2" * 16)]
    n = _run(db.upsert_data_health_snapshots(rows))
    assert n == 2 == len(db.pool.conn.executemany_calls[0][1])


@pytest.mark.parametrize("bad", _BAD_CONTAINERS,
                         ids=lambda b: type(b).__name__ + repr(b)[:6])
def test_serialize_batch_rejects_malformed_container_directly(bad):
    # serialize_batch is independently importable/testable — validate it directly
    with pytest.raises(Stage2SerializationError):
        serialize_batch(EXCHANGE_FEATURE_SPEC, bad)


@pytest.mark.parametrize("empty", [[], ()])
def test_serialize_batch_empty_sequence_returns_empty_list(empty):
    assert serialize_batch(EXCHANGE_FEATURE_SPEC, empty) == []


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_one_row_single_acquire_single_executemany(spec):
    db = _db()
    n = _run(_writer(db, spec)([_make(spec)]))
    assert n == 1
    assert db.pool.acquire_count == 1
    assert len(db.pool.conn.executemany_calls) == 1
    sql, params = db.pool.conn.executemany_calls[0]
    assert sql == spec.insert_sql
    assert len(params) == 1


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_multi_row_batch_one_executemany_returns_count(spec):
    db = _db()
    rows = [_make(spec), _make(spec, calculation_version="c" * 16), _make(spec, timeframe="1h")] \
        if spec.table != "data_health_snapshots" else \
        [_make(spec), _make(spec, calculation_version="c" * 16), _make(spec, metric="funding",
                                                                        expected_interval_s=15)]
    n = _run(_writer(db, spec)(rows))
    assert n == len(rows)
    assert db.pool.acquire_count == 1
    assert len(db.pool.conn.executemany_calls) == 1
    assert len(db.pool.conn.executemany_calls[0][1]) == len(rows)


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_wrong_type_rejected_before_acquire(spec):
    db = _db()
    with pytest.raises(Stage2SerializationError):
        _run(_writer(db, spec)([object()]))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.executemany_calls == []


def test_mixed_batch_rejected_before_acquire():
    db = _db()
    rows = [make_efv(), make_consensus()]   # second row is the wrong model
    with pytest.raises(Stage2SerializationError):
        _run(db.upsert_exchange_feature_vectors(rows))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.executemany_calls == []


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_objects_unchanged_after_write(spec):
    db = _db()
    row = _make(spec)
    before = dataclasses.astuple  # not used for consensus (MappingProxyType); compare identity
    _run(_writer(db, spec)([row]))
    # frozen dataclass: still the same instance, fields intact
    assert getattr(row, "calculation_version") == H16
    if spec.table == "consensus_feature_vectors":
        # JSONB fields were serialized to a copy, not mutated in place
        assert isinstance(row.coverage_by_metric, MappingProxyType)


def test_no_pool_raises_before_write():
    db = Database("postgresql://unused")   # pool is None
    with pytest.raises(AssertionError):
        _run(db.upsert_exchange_feature_vectors([make_efv()]))


# ============================================================================
# B. Exchange feature writer
# ============================================================================
def test_efv_all_fields_included_computed_at_omitted():
    cols = EXCHANGE_FEATURE_SPEC.columns
    model_fields = tuple(f.name for f in dataclasses.fields(ExchangeFeatureVector))
    assert cols == model_fields
    assert "computed_at" not in cols


def test_efv_conflict_target_exact():
    assert EXCHANGE_FEATURE_SPEC.pk == (
        "exchange", "symbol", "market_type", "timeframe", "bucket_ts", "calculation_version")


def test_efv_pk_fields_not_in_update_assignments():
    updates = _parse_update_assignments(EXCHANGE_FEATURE_SPEC.insert_sql)
    for pk_col in EXCHANGE_FEATURE_SPEC.pk:
        assert pk_col not in updates


def test_efv_nullable_zero_false_preserved():
    row = make_efv(oi_change_pct=None, liquidation_event_count=0, has_gap=False,
                   is_usable=False)
    params = serialize_batch(EXCHANGE_FEATURE_SPEC, [row])[0]
    d = dict(zip(EXCHANGE_FEATURE_SPEC.columns, params))
    assert d["oi_change_pct"] is None
    assert d["liquidation_event_count"] == 0 and d["liquidation_event_count"] is not False
    assert d["has_gap"] is False
    assert d["is_usable"] is False


def test_efv_calculation_version_part_of_identity():
    assert "calculation_version" in EXCHANGE_FEATURE_SPEC.pk


# ============================================================================
# C. Consensus writer (JSONB)
# ============================================================================
def test_consensus_jsonb_columns_serialized_to_str():
    row = make_consensus()
    params = dict(zip(CONSENSUS_FEATURE_SPEC.columns,
                      serialize_batch(CONSENSUS_FEATURE_SPEC, [row])[0]))
    for col in CONSENSUS_FEATURE_SPEC.jsonb_columns:
        assert isinstance(params[col], str)
    # non-JSONB scalar left as-is
    assert params["consensus_confidence"] == 87.5


def test_consensus_mappingproxy_and_entries_shapes():
    row = make_consensus()
    p = dict(zip(CONSENSUS_FEATURE_SPEC.columns,
                 serialize_batch(CONSENSUS_FEATURE_SPEC, [row])[0]))
    assert json.loads(p["coverage_by_metric"]) == {
        "oi": {"available": 2, "expected": 3, "ratio": 2 / 3}}
    assert json.loads(p["provenance_by_metric"]) == {
        "oi": {"contributing": ["binance", "bybit"],
               "excluded": [["okx", "NO_HISTORICAL_DATA"]]}}
    assert json.loads(p["outlier_exchanges"]) == {
        "oi_change_pct": {"bybit": {"robust_z": 4.1, "reason": "ROBUST_Z_THRESHOLD"}}}
    assert json.loads(p["data_confidence_by_metric"]) == {"oi": 0.81, "funding": 0.9}
    assert json.loads(p["liquidation_feed_quality_by_exchange"]) == {
        "binance": "snapshot", "bybit": "full"}


def test_consensus_provenance_tuple_order_preserved():
    prov = MappingProxyType({
        "liquidations": ProvenanceEntry(
            contributing=("binance", "bybit", "okx"),
            excluded=(("okx", "A"), ("bybit", "B"))),
    })
    row = make_consensus(provenance_by_metric=prov)
    p = dict(zip(CONSENSUS_FEATURE_SPEC.columns,
                 serialize_batch(CONSENSUS_FEATURE_SPEC, [row])[0]))
    got = json.loads(p["provenance_by_metric"])["liquidations"]
    assert got["contributing"] == ["binance", "bybit", "okx"]   # order preserved
    assert got["excluded"] == [["okx", "A"], ["bybit", "B"]]    # tuple-of-tuple order preserved


def test_consensus_canonical_stable_regardless_of_insertion_order():
    a = MappingProxyType({"a": 0.1, "b": 0.2, "c": 0.3})
    b = MappingProxyType({"c": 0.3, "b": 0.2, "a": 0.1})
    sa = dumps_canonical_jsonb(a)
    sb = dumps_canonical_jsonb(b)
    assert sa == sb == '{"a":0.1,"b":0.2,"c":0.3}'


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_consensus_nan_inf_rejected_before_acquire(bad):
    db = _db()
    row = make_consensus(data_confidence_by_metric=MappingProxyType({"oi": bad}))
    with pytest.raises(Stage2SerializationError):
        _run(db.upsert_consensus_feature_vectors([row]))
    assert db.pool.acquire_count == 0


def test_consensus_unsupported_json_value_rejected():
    row = make_consensus(data_confidence_by_metric=MappingProxyType({"oi": object()}))
    with pytest.raises(Stage2SerializationError):
        serialize_batch(CONSENSUS_FEATURE_SPEC, [row])


def test_consensus_non_string_key_rejected():
    row = make_consensus(data_confidence_by_metric=MappingProxyType({1: 0.5}))
    with pytest.raises(Stage2SerializationError):
        serialize_batch(CONSENSUS_FEATURE_SPEC, [row])


def test_consensus_jsonb_roundtrips_through_json_loads():
    row = make_consensus()
    p = dict(zip(CONSENSUS_FEATURE_SPEC.columns,
                 serialize_batch(CONSENSUS_FEATURE_SPEC, [row])[0]))
    for col in CONSENSUS_FEATURE_SPEC.jsonb_columns:
        assert isinstance(json.loads(p[col]), (dict, list))


# ============================================================================
# D. Percentile writer
# ============================================================================
def test_percentile_exchange_scope_keeps_real_exchange():
    row = make_percentile(scope="exchange", exchange="okx")
    p = dict(zip(PERCENTILE_SNAPSHOT_SPEC.columns,
                 serialize_batch(PERCENTILE_SNAPSHOT_SPEC, [row])[0]))
    assert p["scope"] == "exchange" and p["exchange"] == "okx"


def test_percentile_consensus_scope_keeps_empty_exchange():
    row = make_percentile(scope="consensus", exchange="", metric="oi_change_pct_median")
    p = dict(zip(PERCENTILE_SNAPSHOT_SPEC.columns,
                 serialize_batch(PERCENTILE_SNAPSHOT_SPEC, [row])[0]))
    assert p["scope"] == "consensus" and p["exchange"] == ""   # NOT coerced to NULL


def test_percentile_none_scalars_remain_null():
    row = make_percentile(value=None, percentile_rank=None, sample_window_start=None,
                          sample_window_end=None)
    p = dict(zip(PERCENTILE_SNAPSHOT_SPEC.columns,
                 serialize_batch(PERCENTILE_SNAPSHOT_SPEC, [row])[0]))
    assert p["value"] is None and p["percentile_rank"] is None
    assert p["sample_window_start"] is None and p["sample_window_end"] is None


def test_percentile_sample_window_end_passed_unchanged():
    end = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    row = make_percentile(sample_window_end=end)
    p = dict(zip(PERCENTILE_SNAPSHOT_SPEC.columns,
                 serialize_batch(PERCENTILE_SNAPSHOT_SPEC, [row])[0]))
    assert p["sample_window_end"] == end and isinstance(p["sample_window_end"], datetime)


def test_percentile_conflict_target_exact():
    assert PERCENTILE_SNAPSHOT_SPEC.pk == (
        "scope", "exchange", "symbol", "market_type", "metric", "timeframe",
        "percentile_window", "bucket_ts", "calculation_version")


# ============================================================================
# E. Data Health writer
# ============================================================================
def test_health_scalars_passed_unchanged():
    row = make_health(lateness_ms=120001, gap_count=2, largest_gap_s=301,
                      is_stale=True, is_usable=False)
    p = dict(zip(DATA_HEALTH_SNAPSHOT_SPEC.columns,
                 serialize_batch(DATA_HEALTH_SNAPSHOT_SPEC, [row])[0]))
    assert p["lateness_ms"] == 120001 and p["gap_count"] == 2 and p["largest_gap_s"] == 301
    assert p["is_stale"] is True and p["is_usable"] is False


def test_health_event_driven_nulls_remain_null():
    row = make_health(metric="liquidations", expected_interval_s=None,
                      largest_gap_s=None, lateness_ms=None, last_event_at=None)
    p = dict(zip(DATA_HEALTH_SNAPSHOT_SPEC.columns,
                 serialize_batch(DATA_HEALTH_SNAPSHOT_SPEC, [row])[0]))
    assert p["expected_interval_s"] is None and p["largest_gap_s"] is None
    assert p["lateness_ms"] is None and p["last_event_at"] is None


def test_health_live_only_pk_exact():
    assert DATA_HEALTH_SNAPSHOT_SPEC.pk == (
        "symbol", "exchange", "market_type", "metric", "snapshot_ts", "calculation_version")


def test_health_has_no_status_source_or_raw_source_column():
    cols = set(DATA_HEALTH_SNAPSHOT_SPEC.columns)
    assert "status" not in cols
    assert "source" not in cols
    assert "raw_source" not in cols
    assert "source_mode" not in cols


def test_health_computed_at_omitted():
    assert "computed_at" not in DATA_HEALTH_SNAPSHOT_SPEC.columns


# ============================================================================
# F. Idempotency and correction SQL
# ============================================================================
@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_insert_uses_on_conflict_do_update(spec):
    assert "ON CONFLICT" in spec.insert_sql
    assert "DO UPDATE SET" in spec.insert_sql
    for banned in ("DELETE", "TRUNCATE", "REPLACE"):
        assert banned not in spec.insert_sql.upper()


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_all_non_pk_fields_updated_and_computed_at_now(spec):
    updates = _parse_update_assignments(spec.insert_sql)
    non_pk = [c for c in spec.columns if c not in spec.pk]
    for c in non_pk:
        assert updates.get(c) == f"EXCLUDED.{c}"
    assert updates.get("computed_at") == "now()"
    # PK columns are never updated
    for pk_col in spec.pk:
        assert pk_col not in updates


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_calculation_version_in_conflict_target_and_never_updated(spec):
    conflict = _parse_conflict_target(spec.insert_sql)
    assert "calculation_version" in conflict
    updates = _parse_update_assignments(spec.insert_sql)
    assert "calculation_version" not in updates


def test_different_calculation_version_is_distinct_identity():
    # two rows differing only by calculation_version are two params, same batch
    db = _db()
    rows = [make_health(calculation_version="1" * 16), make_health(calculation_version="2" * 16)]
    assert _run(db.upsert_data_health_snapshots(rows)) == 2
    params = db.pool.conn.executemany_calls[0][1]
    cv_idx = DATA_HEALTH_SNAPSHOT_SPEC.columns.index("calculation_version")
    assert {params[0][cv_idx], params[1][cv_idx]} == {"1" * 16, "2" * 16}


# ============================================================================
# G. Schema / model / writer parity
# ============================================================================
def _schema_columns(table: str) -> set[str]:
    sql = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", sql, re.S)
    assert m, f"{table} not found"
    cols = set()
    col_re = re.compile(
        r"^\s*([a-z_][a-z0-9_]*)\s+"
        r"(TEXT|INTEGER|BIGINT|DOUBLE|TIMESTAMPTZ|BOOLEAN|JSONB|BIGSERIAL)\b")
    for line in m.group(1).splitlines():
        mm = col_re.match(line)
        if mm:
            cols.add(mm.group(1))
    return cols


def _schema_table_body(table: str) -> str:
    sql = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", sql, re.S)
    assert m, f"{table} not found"
    return m.group(1)


def _schema_primary_key(table: str) -> list[str]:
    """Independently read `PRIMARY KEY (...)` from the real table DDL."""
    body = _schema_table_body(table)
    m = re.search(r"PRIMARY KEY \(([^)]*)\)", body)
    assert m, f"PRIMARY KEY not found for {table}"
    return [c.strip() for c in m.group(1).split(",")]


def _parse_insert_columns(sql: str) -> list[str]:
    m = re.search(r"INSERT INTO \w+\s*\(([^)]*)\)", sql, re.S)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


def _parse_placeholders(sql: str) -> list[str]:
    m = re.search(r"VALUES \(([^)]*)\)", sql, re.S)
    assert m
    return [p.strip() for p in m.group(1).split(",")]


def _parse_conflict_target(sql: str) -> list[str]:
    m = re.search(r"ON CONFLICT \(([^)]*)\)", sql)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


def _parse_update_assignments(sql: str) -> dict[str, str]:
    tail = sql.split("DO UPDATE SET", 1)[1]
    out = {}
    for part in tail.split(","):
        if "=" in part:
            lhs, rhs = part.split("=", 1)
            out[lhs.strip()] = rhs.strip()
    return out


@pytest.mark.parametrize("spec,model", [
    (EXCHANGE_FEATURE_SPEC, ExchangeFeatureVector),
    (CONSENSUS_FEATURE_SPEC, ConsensusFeatureVector),
    (PERCENTILE_SNAPSHOT_SPEC, PercentileSnapshot),
    (DATA_HEALTH_SNAPSHOT_SPEC, DataHealthSnapshot),
], ids=lambda x: getattr(x, "table", getattr(x, "__name__", "")))
def test_full_parity_schema_model_writer(spec, model):
    schema_cols = _schema_columns(spec.table)
    model_cols = {f.name for f in dataclasses.fields(model)}
    # 1. model == schema minus computed_at
    assert "computed_at" in schema_cols
    assert model_cols == schema_cols - {"computed_at"}
    # 2. writer columns == model fields, in field order, no invented columns
    assert spec.columns == tuple(f.name for f in dataclasses.fields(model))
    assert "computed_at" not in spec.columns
    # 3. INSERT column list == frozen writer column tuple
    assert _parse_insert_columns(spec.insert_sql) == list(spec.columns)
    # 4. conflict target == real table PK, parsed INDEPENDENTLY from the schema —
    #    not just Python-spec vs Python-derived SQL agreeing with each other.
    schema_pk = _schema_primary_key(spec.table)
    conflict_target = _parse_conflict_target(spec.insert_sql)
    assert schema_pk == list(spec.pk)          # real DDL PK == Python spec.pk
    assert schema_pk == conflict_target        # real DDL PK == ON CONFLICT target
    assert "calculation_version" in schema_pk  # never omitted
    # 5. DO UPDATE SET excludes every PK column
    updates = _parse_update_assignments(spec.insert_sql)
    for pk_col in spec.pk:
        assert pk_col not in updates


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_placeholders_are_exactly_positional_with_jsonb_only_on_consensus(spec):
    placeholders = _parse_placeholders(spec.insert_sql)
    columns = _parse_insert_columns(spec.insert_sql)
    assert len(placeholders) == len(columns) == len(spec.columns)
    for i, (col, ph) in enumerate(zip(columns, placeholders), start=1):
        if col in spec.jsonb_columns:
            assert ph == f"${i}::jsonb"        # ::jsonb ONLY as a suffix on JSONB cols
        else:
            assert ph == f"${i}"               # exactly positional, no cast


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_serialized_param_tuple_length_equals_column_count(spec):
    params = serialize_batch(spec, [_make(spec)])
    assert len(params) == 1
    assert len(params[0]) == len(spec.columns) == len(_parse_insert_columns(spec.insert_sql))


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.table)
def test_jsonb_columns_are_real_model_fields(spec):
    for col in spec.jsonb_columns:
        assert col in spec.columns


def test_only_consensus_has_jsonb_columns():
    assert EXCHANGE_FEATURE_SPEC.jsonb_columns == frozenset()
    assert PERCENTILE_SNAPSHOT_SPEC.jsonb_columns == frozenset()
    assert DATA_HEALTH_SNAPSHOT_SPEC.jsonb_columns == frozenset()
    assert CONSENSUS_FEATURE_SPEC.jsonb_columns == frozenset({
        "coverage_by_metric", "provenance_by_metric", "data_confidence_by_metric",
        "liquidation_feed_quality_by_exchange", "outlier_exchanges"})


def test_jsonb_placeholders_have_jsonb_cast():
    # every JSONB column's placeholder in the consensus INSERT is cast ::jsonb
    sql = CONSENSUS_FEATURE_SPEC.insert_sql
    cols = _parse_insert_columns(sql)
    values_line = re.search(r"VALUES \(([^)]*)\)", sql, re.S).group(1)
    placeholders = [p.strip() for p in values_line.split(",")]
    for col, ph in zip(cols, placeholders):
        if col in CONSENSUS_FEATURE_SPEC.jsonb_columns:
            assert ph.endswith("::jsonb")
        else:
            assert "::jsonb" not in ph


# ---- to_jsonable direct edge cases -----------------------------------------
def test_to_jsonable_bool_not_int():
    assert to_jsonable(True) is True
    assert to_jsonable(False) is False


def test_to_jsonable_none_passthrough():
    assert to_jsonable(None) is None


def test_to_jsonable_nested_dataclass():
    assert to_jsonable(CoverageEntry(1, 2, 0.5)) == {"available": 1, "expected": 2, "ratio": 0.5}
