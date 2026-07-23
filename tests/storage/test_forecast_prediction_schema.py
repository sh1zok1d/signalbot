"""Structural assertions on the additive forecast_predictions DDL in
storage/stage2_schema.sql (no Docker / PostgreSQL). Robust parsing patterned on
the existing Stage 2 writer tests, plus schema/model/spec parity.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from analytics.forecasting import ForecastPrediction
from storage.stage2_serialization import FORECAST_PREDICTION_SPEC

SQL = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")


def _table_body(table: str) -> str:
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", SQL, re.S)
    assert m, f"{table} table not found"
    return m.group(1)


def _strip_sql_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


_FP_BODY = _table_body("forecast_predictions")
# forecast-predictions section = from its banner comment up to (but not including)
# the forecast_outcomes section that follows it in the same file.
_FP_SECTION = SQL[SQL.index("Shadow forecast predictions"):SQL.index("Shadow forecast OUTCOMES")]
_FP_SECTION_CODE = _strip_sql_comments(_FP_SECTION)     # comments removed, DDL only
_SQL_CODE = _strip_sql_comments(SQL)


def _columns(body: str) -> list[str]:
    cols = []
    col_re = re.compile(
        r"^\s*([a-z_][a-z0-9_]*)\s+"
        r"(TEXT|INTEGER|BIGINT|DOUBLE|TIMESTAMPTZ|BOOLEAN|JSONB|BIGSERIAL)\b")
    for line in body.splitlines():
        m = col_re.match(line)
        if m:
            cols.append(m.group(1))
    return cols


def _jsonb_columns(body: str) -> set[str]:
    return {c for c in _columns(body)
            if re.search(r"^\s*" + c + r"\s+JSONB\b", body, re.M)}


def _pk(body: str) -> list[str]:
    m = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", body, re.S)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


# ---- table presence & scope ------------------------------------------------
def test_exactly_one_forecast_predictions_table():
    assert len(re.findall(r"CREATE TABLE IF NOT EXISTS forecast_predictions\b", SQL)) == 1


def test_predictions_section_defines_only_forecast_predictions():
    # The forecast_outcomes table lives in its own section (covered by
    # test_forecast_outcome_schema.py); the predictions section must not define it.
    assert not re.search(r"CREATE TABLE IF NOT EXISTS forecast_outcomes\b", _FP_SECTION)
    assert re.search(r"CREATE TABLE IF NOT EXISTS forecast_predictions\b", _FP_SECTION)


def test_existing_stage2_tables_still_present():
    for t in ("exchange_feature_vectors", "consensus_feature_vectors",
              "percentile_snapshots", "data_health_snapshots",
              "stage2_watermarks", "stage2_recompute_queue"):
        assert re.search(r"CREATE TABLE IF NOT EXISTS " + t + r"\b", SQL), t


def test_forecast_section_does_not_touch_stage1_schema():
    for t in ("klines_1m", "open_interest", "funding_rate", "mark_price",
              "liquidations", "exchange_capabilities"):
        assert t not in _FP_SECTION, t
    assert "ALTER TABLE" not in _FP_SECTION


# ---- columns ---------------------------------------------------------------
def test_required_columns_present_in_order():
    expected = [
        "symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version",
        "calculation_version", "rule_version", "direction", "confidence", "horizon_set",
        "reasons", "component_scores", "final_score", "reference_price",
        "reference_price_source", "exchanges_expected_max", "min_coverage_ratio",
        "data_confidence_overall", "consensus_confidence", "is_partial_consensus",
        "consensus_snapshot", "config_hash", "config_version", "code_version",
        "created_at",
    ]
    assert _columns(_FP_BODY) == expected


def test_created_at_in_schema_but_not_model():
    assert "created_at" in _columns(_FP_BODY)
    model_fields = {f.name for f in dataclasses.fields(ForecastPrediction)}
    assert "created_at" not in model_fields


# ---- primary key -----------------------------------------------------------
def test_primary_key_exact_six_columns():
    assert _pk(_FP_BODY) == [
        "symbol", "market_type", "timeframe", "bucket_ts", "calculation_version",
        "rule_version"]


def test_pk_includes_bucket_calc_rule():
    pk = _pk(_FP_BODY)
    assert "bucket_ts" in pk and "calculation_version" in pk and "rule_version" in pk


# ---- CHECK constraints -----------------------------------------------------
def test_direction_check():
    assert re.search(r"direction\s+IN\s*\(\s*'LONG'\s*,\s*'SHORT'\s*,\s*'NEUTRAL'\s*\)", _FP_BODY)


def test_confidence_check_0_1():
    assert re.search(r"confidence\s*>=\s*0\.0\s*AND\s*confidence\s*<=\s*1\.0", _FP_BODY)


def test_final_score_check_neg1_1():
    assert re.search(r"final_score\s*>=\s*-1\.0\s*AND\s*final_score\s*<=\s*1\.0", _FP_BODY)


def test_reference_price_positive():
    assert re.search(r"reference_price\s*>\s*0\.0", _FP_BODY)


def test_reference_price_source_nonblank():
    assert "length(btrim(reference_price_source))" in _FP_BODY


def test_exchanges_expected_check():
    assert re.search(r"exchanges_expected_max\s*>=\s*1", _FP_BODY)


def test_coverage_check_0_1():
    assert re.search(r"min_coverage_ratio\s*>=\s*0\.0\s*AND\s*min_coverage_ratio\s*<=\s*1\.0", _FP_BODY)


def test_confidence_checks_0_100():
    assert re.search(r"data_confidence_overall\s*>=\s*0\.0\s*AND\s*data_confidence_overall\s*<=\s*100\.0", _FP_BODY, re.S)
    assert re.search(r"consensus_confidence\s*>=\s*0\.0\s*AND\s*consensus_confidence\s*<=\s*100\.0", _FP_BODY, re.S)


def test_jsonb_shape_checks():
    assert re.search(r"jsonb_typeof\(horizon_set\)\s*=\s*'array'", _FP_BODY)
    assert re.search(r"jsonb_typeof\(reasons\)\s*=\s*'array'", _FP_BODY)
    assert re.search(r"jsonb_typeof\(component_scores\)\s*=\s*'object'", _FP_BODY)
    assert re.search(r"jsonb_typeof\(consensus_snapshot\)\s*=\s*'object'", _FP_BODY)


# ---- hypertable, indexes, no FK/trigger/update -----------------------------
def test_hypertable_on_bucket_ts():
    assert re.search(r"create_hypertable\(\s*'forecast_predictions'\s*,\s*'bucket_ts'", _FP_SECTION, re.S)


def test_both_indexes_present():
    assert "ix_fp_symbol_tf_ts" in _FP_SECTION and "ix_fp_direction_ts" in _FP_SECTION
    assert re.search(r"forecast_predictions \(symbol, timeframe, bucket_ts DESC\)", _FP_SECTION)
    assert re.search(r"forecast_predictions \(direction, bucket_ts DESC\)", _FP_SECTION)


def test_no_fk_trigger_or_update():
    code = _FP_SECTION_CODE.upper()                      # comments stripped
    assert "REFERENCES" not in code and "FOREIGN KEY" not in code
    assert "TRIGGER" not in code
    assert "UPDATE" not in code                          # insert-once event table (no DO UPDATE)


# ---- schema / model / spec parity ------------------------------------------
def test_schema_columns_minus_created_at_equal_spec_columns():
    sql_cols = [c for c in _columns(_FP_BODY) if c != "created_at"]
    assert tuple(sql_cols) == FORECAST_PREDICTION_SPEC.columns


def test_pk_matches_spec():
    assert tuple(_pk(_FP_BODY)) == FORECAST_PREDICTION_SPEC.pk


def test_jsonb_sql_columns_match_spec():
    assert _jsonb_columns(_FP_BODY) == set(FORECAST_PREDICTION_SPEC.jsonb_columns)
