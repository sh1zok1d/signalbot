"""Schema and partition tests for the D7 gap-break counter. No market rows."""

from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.research.d7_eligible_index_gap_break_audit_v1 import audit_output_text
from scripts.research.d7_eligible_index_gap_break_v1 import (
    ALLOWED_OUTPUT_KEYS,
    GAP_END_MS,
    GAP_START_MS,
    HOUR_MS,
    PUBLISHED_GAP,
    PUBLISHED_T,
    PUBLISHED_YEAR_MASS,
    consistency_flags,
    count_eligible_geometry,
    sealed_json,
)


def _ms(year: int, month: int, day: int, hour: int) -> int:
    from datetime import datetime, timezone

    parsed = datetime(year, month, day, hour, tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def test_published_gap_bounds_are_the_frozen_interval() -> None:
    assert GAP_START_MS < GAP_END_MS
    assert "[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)" == PUBLISHED_GAP


def test_counter_splits_only_on_the_published_gap() -> None:
    hour = np.asarray(
        [
            _ms(2016, 12, 6, 21),
            _ms(2016, 12, 6, 22),
            _ms(2016, 12, 7, 12),
            _ms(2016, 12, 8, 0),
            _ms(2017, 1, 1, 0),
        ],
        dtype=np.int64,
    )
    year = np.asarray([2016, 2016, 2016, 2016, 2017], dtype=np.int64)
    eligible = np.asarray([True, False, True, True, True], dtype=bool)
    counts = count_eligible_geometry(hour, year, eligible)
    assert counts["ELIGIBLE_COUNT_BEFORE_GAP"] == 1
    assert counts["ELIGIBLE_INSIDE_PUBLISHED_GAP"] == 1
    assert counts["ELIGIBLE_COUNT_AFTER_GAP"] == 1
    assert counts["ELIGIBLE_2016_TOTAL"] == 3
    assert counts["ELIGIBLE_2017_TOTAL"] == 1
    assert counts["T"] == 4
    assert counts["ELIGIBLE_BEFORE_GAP_OUTSIDE_2016"] == 0
    flags = consistency_flags(counts)
    assert flags["CONSISTENT"] is False


def test_hour_aligned_gap_edges() -> None:
    assert _ms(2016, 12, 6, 22) < GAP_START_MS
    assert GAP_START_MS <= _ms(2016, 12, 7, 23) < GAP_END_MS
    assert _ms(2016, 12, 8, 0) >= GAP_END_MS
    assert HOUR_MS == 3_600_000


def test_published_masses_sum_to_t() -> None:
    assert sum(PUBLISHED_YEAR_MASS.values()) == PUBLISHED_T == 30354


def test_seal_rejects_sequences_and_extra_keys() -> None:
    payload = {key: 0 for key in ALLOWED_OUTPUT_KEYS}
    payload["CONSISTENT"] = False
    payload["YEAR_MASSES_MATCH_PUBLISHED"] = False
    payload["T_MATCHES_PUBLISHED"] = False
    payload["MINIMUM_REQUIRED_GEOMETRY"] = "ELIGIBLE_INDEX_GAP_BREAK"
    payload["GAP_HALF_OPEN"] = PUBLISHED_GAP
    payload["SOURCE_CANONICAL_GZ_SHA256"] = "a" * 64
    payload["EXTRACTOR_SHA256"] = "b" * 64
    payload["DERIVATION_RULE_SHA256"] = "c" * 64
    payload["DERIVATION_FILE_SHA256"] = "d" * 64
    text = sealed_json(payload)
    parsed = json.loads(text)
    assert set(parsed) == set(ALLOWED_OUTPUT_KEYS)
    with pytest.raises(RuntimeError, match="GEOMETRY_SEAL_KEYS"):
        sealed_json({**payload, "state": [1, 0, 1]})


def test_audit_rejects_forbidden_token_without_echoing_it(tmp_path, monkeypatch) -> None:
    repo = Path_repo()
    payload = {key: 0 for key in ALLOWED_OUTPUT_KEYS}
    payload["CONSISTENT"] = True
    payload["YEAR_MASSES_MATCH_PUBLISHED"] = True
    payload["T_MATCHES_PUBLISHED"] = True
    payload["MINIMUM_REQUIRED_GEOMETRY"] = "ELIGIBLE_INDEX_GAP_BREAK"
    payload["GAP_HALF_OPEN"] = PUBLISHED_GAP
    payload["SOURCE_CANONICAL_GZ_SHA256"] = "a" * 64
    payload["EXTRACTOR_SHA256"] = "b" * 64
    payload["DERIVATION_RULE_SHA256"] = "c" * 64
    payload["DERIVATION_FILE_SHA256"] = "d" * 64
    dirty = json.dumps(payload, sort_keys=True)[:-1] + ', "note": "state_defined"}'
    findings = audit_output_text(dirty, repo)
    assert "OUTPUT_FORBIDDEN_TOKEN" in findings or "OUTPUT_KEYS" in findings
    rendered = " ".join(findings)
    assert "state_defined" not in rendered


def Path_repo():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]
