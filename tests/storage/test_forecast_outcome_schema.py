"""Structural assertions on the additive forecast_outcomes DDL in
storage/stage2_schema.sql (no Docker / PostgreSQL). Parsing mirrors
test_forecast_prediction_schema.py, plus schema/model/spec parity for the
correction-friendly outcome table.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from analytics.forecasting import ForecastOutcome
from storage.stage2_serialization import FORECAST_OUTCOME_SPEC

SQL = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")


def _table_body(table: str) -> str:
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", SQL, re.S)
    assert m, f"{table} table not found"
    return m.group(1)


def _strip_sql_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


_FO_BODY = _table_body("forecast_outcomes")
# outcome section = from its banner comment to EOF (predictions table is above it)
_FO_SECTION = SQL[SQL.index("Shadow forecast OUTCOMES"):]
_FO_SECTION_CODE = _strip_sql_comments(_FO_SECTION)


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


def _pk(body: str) -> list[str]:
    m = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", body, re.S)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


# ---- table presence & scope ------------------------------------------------
def test_exactly_one_forecast_outcomes_table():
    assert len(re.findall(r"CREATE TABLE IF NOT EXISTS forecast_outcomes\b", SQL)) == 1


def test_forecast_predictions_still_separate_table():
    assert re.search(r"CREATE TABLE IF NOT EXISTS forecast_predictions\b", SQL)
    # the two tables are distinct DDL blocks
    assert "forecast_predictions" not in _FO_BODY


def test_outcome_section_does_not_modify_stage1_or_prediction_tables():
    code = _FO_SECTION_CODE
    assert "ALTER TABLE" not in code
    # klines_1m appears ONLY inside the evaluation-source CHECK literal 'klines_1m',
    # never as a table the section creates/alters.
    assert not re.search(r"(CREATE|ALTER)\s+TABLE[^\n]*klines_1m", code)
    for t in ("open_interest", "funding_rate", "mark_price", "liquidations",
              "exchange_capabilities", "forecast_predictions"):
        assert not re.search(r"(CREATE|ALTER)\s+TABLE[^\n]*\b" + t + r"\b", code), t


# ---- columns ---------------------------------------------------------------
def test_required_columns_present_in_order():
    expected = [
        "symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version",
        "calculation_version", "rule_version", "horizon", "outcome_version",
        "direction", "prediction_confidence", "prediction_final_score",
        "reference_price", "reference_price_source", "evaluation_exchange",
        "evaluation_price_source", "evaluation_start_ts", "evaluation_end_ts",
        "target_bar_ts", "bars_expected", "bars_present", "target_close_price",
        "window_high_price", "window_low_price", "market_return_pct",
        "peak_return_pct", "trough_return_pct", "directional_return_pct",
        "mfe_pct", "mae_pct", "config_hash", "config_version", "code_version",
        "computed_at",
    ]
    assert _columns(_FO_BODY) == expected


def test_computed_at_in_schema_but_not_model():
    assert "computed_at" in _columns(_FO_BODY)
    model_fields = {f.name for f in dataclasses.fields(ForecastOutcome)}
    assert "computed_at" not in model_fields


def test_computed_at_defaults_to_now():
    assert re.search(r"computed_at\s+TIMESTAMPTZ\s+NOT NULL\s+DEFAULT now\(\)", _FO_BODY)


def test_directional_metric_columns_nullable():
    # NEUTRAL leaves these NULL, so they must NOT be NOT NULL.
    for col in ("directional_return_pct", "mfe_pct", "mae_pct"):
        assert re.search(r"^\s*" + col + r"\s+DOUBLE PRECISION\s*,?\s*$", _FO_BODY, re.M), col


# ---- primary key -----------------------------------------------------------
def test_primary_key_exact_ten_columns():
    assert _pk(_FO_BODY) == [
        "symbol", "market_type", "timeframe", "bucket_ts", "calculation_version",
        "rule_version", "horizon", "evaluation_exchange", "evaluation_price_source",
        "outcome_version"]


def test_pk_distinguishes_horizon_exchange_source_version():
    pk = _pk(_FO_BODY)
    for extra in ("horizon", "evaluation_exchange", "evaluation_price_source",
                  "outcome_version"):
        assert extra in pk, extra


# ---- CHECK constraints -----------------------------------------------------
def test_horizon_check():
    assert re.search(r"horizon\s+IN\s*\(\s*'15m'\s*,\s*'1h'\s*,\s*'4h'\s*\)", _FO_BODY)


def test_direction_check():
    assert re.search(r"direction\s+IN\s*\(\s*'LONG'\s*,\s*'SHORT'\s*,\s*'NEUTRAL'\s*\)", _FO_BODY)


def test_prediction_confidence_and_score_checks():
    assert re.search(r"prediction_confidence\s*>=\s*0\.0\s*AND\s*prediction_confidence\s*<=\s*1\.0", _FO_BODY, re.S)
    assert re.search(r"prediction_final_score\s*>=\s*-1\.0\s*AND\s*prediction_final_score\s*<=\s*1\.0", _FO_BODY, re.S)


def test_reference_price_and_source_checks():
    assert re.search(r"reference_price\s*>\s*0\.0", _FO_BODY)
    assert "length(btrim(reference_price_source))" in _FO_BODY


def test_evaluation_exchange_and_source_checks():
    assert "length(btrim(evaluation_exchange))" in _FO_BODY
    assert re.search(r"evaluation_price_source\s*=\s*'klines_1m'", _FO_BODY)


def test_window_order_and_target_bar_checks():
    assert re.search(r"evaluation_end_ts\s*>\s*evaluation_start_ts", _FO_BODY)
    assert re.search(r"target_bar_ts\s*=\s*evaluation_end_ts\s*-\s*INTERVAL\s*'1 minute'", _FO_BODY)


def test_bars_check():
    assert re.search(r"bars_expected\s*>\s*0", _FO_BODY)
    assert re.search(r"bars_present\s*=\s*bars_expected", _FO_BODY)


def test_horizon_window_check_all_three():
    assert re.search(r"horizon\s*=\s*'15m'\s*AND\s*bars_expected\s*=\s*15", _FO_BODY, re.S)
    assert re.search(r"horizon\s*=\s*'1h'\s*AND\s*bars_expected\s*=\s*60", _FO_BODY, re.S)
    assert re.search(r"horizon\s*=\s*'4h'\s*AND\s*bars_expected\s*=\s*240", _FO_BODY, re.S)
    assert "INTERVAL '15 minutes'" in _FO_BODY
    assert "INTERVAL '1 hour'" in _FO_BODY
    assert "INTERVAL '4 hours'" in _FO_BODY


def test_price_ordering_check():
    assert re.search(r"window_low_price\s*<=\s*target_close_price", _FO_BODY, re.S)
    assert re.search(r"target_close_price\s*<=\s*window_high_price", _FO_BODY, re.S)
    for col in ("target_close_price", "window_high_price", "window_low_price"):
        assert re.search(col + r"\s*>\s*0\.0", _FO_BODY), col


def test_return_order_check():
    assert re.search(r"peak_return_pct\s*>=\s*trough_return_pct", _FO_BODY)


def test_directional_metrics_check_neutral_vs_directional():
    # NEUTRAL: all three NULL; LONG/SHORT: all three NOT NULL with mfe>=0, mae<=0.
    assert re.search(r"direction\s*=\s*'NEUTRAL'\s*AND\s*directional_return_pct\s*IS\s*NULL", _FO_BODY, re.S)
    assert re.search(r"mfe_pct\s*IS\s*NULL\s*AND\s*mae_pct\s*IS\s*NULL", _FO_BODY, re.S)
    assert re.search(r"direction\s*IN\s*\(\s*'LONG'\s*,\s*'SHORT'\s*\)", _FO_BODY, re.S)
    assert re.search(r"mfe_pct\s*>=\s*0\.0", _FO_BODY)
    assert re.search(r"mae_pct\s*<=\s*0\.0", _FO_BODY)


# ---- hypertable, indexes, no FK/trigger ------------------------------------
def test_hypertable_on_bucket_ts():
    assert re.search(r"create_hypertable\(\s*'forecast_outcomes'\s*,\s*'bucket_ts'", _FO_SECTION, re.S)


def test_both_indexes_present():
    assert "ix_fo_symbol_horizon_ts" in _FO_SECTION and "ix_fo_direction_horizon_ts" in _FO_SECTION
    assert re.search(r"ON forecast_outcomes\s*\(\s*symbol,\s*horizon,\s*bucket_ts DESC", _FO_SECTION, re.S)
    assert re.search(r"ON forecast_outcomes\s*\(\s*direction,\s*horizon,\s*bucket_ts DESC", _FO_SECTION, re.S)


def test_no_fk_or_trigger():
    code = _FO_SECTION_CODE.upper()
    assert "REFERENCES" not in code and "FOREIGN KEY" not in code
    assert "TRIGGER" not in code


# ---- schema / model / spec parity ------------------------------------------
def test_schema_columns_minus_computed_at_equal_spec_columns():
    sql_cols = [c for c in _columns(_FO_BODY) if c != "computed_at"]
    assert tuple(sql_cols) == FORECAST_OUTCOME_SPEC.columns


def test_spec_columns_equal_model_fields():
    model_fields = tuple(f.name for f in dataclasses.fields(ForecastOutcome))
    assert FORECAST_OUTCOME_SPEC.columns == model_fields


def test_pk_matches_spec():
    assert tuple(_pk(_FO_BODY)) == FORECAST_OUTCOME_SPEC.pk


def test_no_jsonb_columns():
    assert FORECAST_OUTCOME_SPEC.jsonb_columns == frozenset()
    assert "JSONB" not in _FO_BODY
