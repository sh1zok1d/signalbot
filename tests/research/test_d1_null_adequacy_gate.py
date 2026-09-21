"""Focused tests for DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE adjudication.

Does not execute D1 science, does not open 2025/2026, and does not alter
D2-D5 results.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.discovery_sprint_01.d1_null_adequacy_adjudication import (
    D1NullAdequacyRefused,
    TARGET_TOKENS,
    adjudicate,
    execute_adequacy_gate,
    frozen_mapping_exists,
    observable_granularity_mismatch,
    refuse_protected_year,
)
from scripts.research.market_06_cross_venue_dislocation_evaluator import RV_RETURN_COUNT


REPO = Path(__file__).resolve().parents[2]
RESULT_RELS = tuple(
    f"docs/research/discovery_results/D{n}_DISCOVERY_RESULT.{ext}"
    for n in (2, 3, 4, 5)
    for ext in ("json", "md")
)


def _committed_bytes(rel: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=REPO)


def test_rv_return_count_is_288() -> None:
    assert RV_RETURN_COUNT == 288


def test_observable_granularity_mismatch_is_true() -> None:
    report = adjudicate(repo=REPO)
    assert report["D1_NULL_MODEL_OBSERVABLE_MISMATCH"] is True
    assert report["FROZEN_SAME_OBSERVABLE_MAPPING"] is False
    assert "24h-return path" in report["FROZEN_NULL_SURROGATE_GENERATION"]
    assert "ev.rv_btc_24h" in report["FROZEN_RV_20_FORMULA"]
    assert observable_granularity_mismatch(
        mapping=False,
        null_generation=report["FROZEN_NULL_SURROGATE_GENERATION"],
        rv20_formula=report["FROZEN_RV_20_FORMULA"],
    )
    assert not frozen_mapping_exists(
        (REPO / "docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.json").read_text(encoding="utf-8")
        + (REPO / "docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.json").read_text(encoding="utf-8")
    )


def test_mapping_function_does_not_accept_forbidden_substitutes() -> None:
    fake = (
        "use abs(daily_return) or GARCH sigma or squared daily return "
        "or synthetic conditional variance as RV; Brownian bridge allowed"
    )
    assert frozen_mapping_exists(fake) is False


def test_gate_underspecified_independently() -> None:
    report = adjudicate(repo=REPO)
    assert report["D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED"] is True
    joined = " ".join(report["UNDERSPECIFIED_GATE_QUANTITIES"])
    assert "LEVERAGE_PROXY_OR_CLAUSE" in joined
    assert "RV_20_SHORT_LAG_ACF_LAG_SET_UNENUMERATED" in joined
    assert "SKEW_KURTOSIS_JOINT_VS_INDIVIDUAL_UNSPECIFIED" in joined
    assert "ABS_OR_SQUARED_RETURN_ACF_OR_CLAUSE" in joined
    assert "NAN_DEGENERATE_TREATMENT_UNSPECIFIED" in joined
    assert "GARCH_ESTIMATION_UNSPECIFIED" in joined


def test_status_and_counters() -> None:
    report = adjudicate(repo=REPO)
    assert report["D1_STATUS"] == "DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH"
    assert report["D1_NULL_ADEQUACY_GATE_EXECUTED"] is False
    assert report["D1_NULL_ADEQUACY_GATE_RESULT"] is None
    assert report["D1_TARGET_OUTCOME_COMPUTED"] is False
    assert report["INTERNAL_DISCOVERY_CARDS_EXECUTED"] == 4
    assert report["INTERNAL_PROMISING_PROTOTYPES"] == 1
    assert report["D2_STATUS"] == "PROMISING_PROTOTYPE"
    assert report["MARKET_07_CREATED"] is False
    assert report["PROTECTED_2025_OPENED"] is False
    assert report["PROTECTED_2026_OPENED"] is False
    assert report["NEXT_UNIT"] == "D2_CONFIRMATION_FEASIBILITY_AND_DESIGN"


def test_execute_adequacy_gate_refused() -> None:
    with pytest.raises(D1NullAdequacyRefused, match="NOT_EXECUTABLE"):
        execute_adequacy_gate(repo=REPO)


def test_deterministic_adjudication() -> None:
    a = adjudicate(repo=REPO)
    b = adjudicate(repo=REPO)
    assert a == b
    with pytest.raises(D1NullAdequacyRefused) as first:
        execute_adequacy_gate(repo=REPO)
    with pytest.raises(D1NullAdequacyRefused) as second:
        execute_adequacy_gate(repo=REPO)
    assert str(first.value) == str(second.value)


def test_no_d1_target_statistic_computed() -> None:
    report = adjudicate(repo=REPO)
    assert report["D1_TARGET_OUTCOME_COMPUTED"] is False
    src = inspect.getsource(adjudicate) + inspect.getsource(execute_adequacy_gate)
    lowered = src.lower()
    assert "mean consecutive" not in lowered
    assert "state-transition" not in lowered
    for token in TARGET_TOKENS:
        assert report.get(token) is None
        assert token not in report


def test_adjudication_does_not_load_core_or_fit_garch() -> None:
    src = (REPO / "scripts/research/discovery_sprint_01/d1_null_adequacy_adjudication.py").read_text(
        encoding="utf-8"
    )
    assert "load_core" not in src
    assert "arch_model" not in src
    assert "from arch" not in src
    assert "import arch" not in src
    assert "fit_garch" not in src.lower()
    assert "MEAN_STATE_RUN_LENGTH =" not in src
    body = inspect.getsource(adjudicate) + inspect.getsource(execute_adequacy_gate)
    assert ".parquet" not in body


def test_refuse_protected_2025_2026() -> None:
    for period in ("2025-01", "2025-12", "2026-01", "2026-02"):
        with pytest.raises(C.ProtectedYearRefused):
            refuse_protected_year(period)
    refuse_protected_year("2024-12")
    refuse_protected_year("2020-02")


def test_assert_openable_blocks_protected_partitions(tmp_path: Path) -> None:
    bad_2025 = tmp_path / "canonical" / "1m" / "monthly" / "2025-01.parquet"
    bad_2025.parent.mkdir(parents=True)
    bad_2025.write_bytes(b"nope")
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(bad_2025)
    bad_2026 = tmp_path / "BTCUSDT-5m-2026-01.zip"
    bad_2026.write_bytes(b"nope")
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(bad_2026)


def test_d2_d5_result_bytes_unchanged() -> None:
    for rel in RESULT_RELS:
        current = (REPO / rel).read_bytes()
        committed = _committed_bytes(rel)
        assert current == committed, rel
        assert hashlib.sha256(current).hexdigest() == hashlib.sha256(committed).hexdigest()


def test_written_json_matches_adjudicate() -> None:
    report = adjudicate(repo=REPO)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    on_disk = (REPO / "docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.json").read_text(
        encoding="utf-8"
    )
    assert on_disk == payload
    md = (REPO / "docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.md").read_text(
        encoding="utf-8"
    )
    assert "DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH" in md
    assert "D1_NULL_ADEQUACY_GATE_EXECUTED" in md
    assert "D2_CONFIRMATION_FEASIBILITY_AND_DESIGN" in md
