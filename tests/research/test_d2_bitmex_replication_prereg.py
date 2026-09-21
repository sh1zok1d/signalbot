"""Tests for the outcome-blind D2 BitMEX replication preregistration.

Does not compute BitMEX D2 outcomes or open Binance 2025/2026 prices.
"""

from __future__ import annotations

import ast
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.research.d2_bitmex_pre2020 import (
    BAR_MS,
    D2OutcomeRefused,
    PRE2020_END_EXCLUSIVE,
    ProtectedBinanceRefused,
    RV_TRAILING_WINDOW,
    count_legal_decision_rows,
    utc_ms,
)
from scripts.research.d2_bitmex_replication_evaluator import (
    EXECUTION_AUTHORIZED,
    ExecutionNotAuthorized,
    assert_pre2020_future,
    compute_delta,
    compute_mu_rule,
    execute_replication,
    last_future_bar_end,
    pooled_k_is_forbidden,
    year_matched_control_replicate_means,
)
from scripts.research.d2_bitmex_replication_prereg import (
    BINDING_REL,
    CANDIDATE,
    D2_BITMEX_REPLICATION_RANDOM_SEED,
    EVIDENCE_CLASS,
    FORBIDDEN_SEEDS,
    FROZEN_EXPECTED_ELIGIBLE_N,
    FROZEN_FIRST_RULE_ELIGIBLE_T,
    FROZEN_LAST_RULE_ELIGIBLE_T,
    FROZEN_MISSING_BUCKET_COUNT,
    GAP_FIRST_OPEN,
    GAP_LAST_OPEN,
    JSON_REL,
    MD_REL,
    N_REPLICATES,
    PreregInconsistency,
    load_sealed_open_times,
    verify_frozen_eligibility,
)
from scripts.research.d2_confirmation_feasibility_and_design import (
    ProtectedPriceRefused,
    refuse_protected_price_path,
)
from scripts.research.discovery_sprint_01 import common as C


REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
D2_RESULT = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"
D2_RESULT_MD = "docs/research/discovery_results/D2_DISCOVERY_RESULT.md"
FEASIBILITY_JSON = "docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.json"
CONFIRMATION_JSON = "docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.json"


def _committed(rel: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=REPO)


def test_seed_is_new_and_replicates_frozen() -> None:
    assert D2_BITMEX_REPLICATION_RANDOM_SEED == 20260921125
    assert D2_BITMEX_REPLICATION_RANDOM_SEED not in FORBIDDEN_SEEDS
    assert N_REPLICATES == 10_000
    assert EXECUTION_AUTHORIZED is False


def test_frozen_eligibility_reproduces_1069() -> None:
    verified = verify_frozen_eligibility(REPO)
    assert verified["legal"]["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"] == FROZEN_EXPECTED_ELIGIBLE_N == 1069
    assert verified["legal"]["FIRST_RULE_ELIGIBLE_T"] == "2017-01-24T00:05:00.000Z"
    assert verified["legal"]["LAST_RULE_ELIGIBLE_T"] == "2019-12-30T00:05:00.000Z"
    assert verified["legal"]["WARMUP_DECISION_ROWS"] == RV_TRAILING_WINDOW == 250
    assert verified["year_eligible_n"] == {"2017": 341, "2018": 364, "2019": 364}
    assert sum(verified["year_eligible_n"].values()) == 1069
    assert verified["TRAILING_250_VALID_HISTORY_VERIFIED"] is True
    assert verified["KNOWN_GAP_NEVER_FILLED"] is True
    assert verified["gaps"]["missing_bucket_count"] == FROZEN_MISSING_BUCKET_COUNT == 288
    assert verified["D2_BITMEX_OUTCOME_COMPUTED"] is False


def test_last_eligible_future_is_before_2020() -> None:
    end = last_future_bar_end(FROZEN_LAST_RULE_ELIGIBLE_T)
    assert end == datetime(2019, 12, 31, 0, 5, tzinfo=UTC)
    assert end < PRE2020_END_EXCLUSIVE
    assert_pre2020_future(FROZEN_LAST_RULE_ELIGIBLE_T)
    with pytest.raises(ValueError):
        assert_pre2020_future(datetime(2019, 12, 31, 0, 5, tzinfo=UTC))
    with pytest.raises(ValueError):
        assert_pre2020_future(datetime(2020, 1, 1, 0, 5, tzinfo=UTC))


def test_known_288_bar_hole_never_filled() -> None:
    verified = verify_frozen_eligibility(REPO)
    gaps = verified["gaps"]
    assert gaps["missing_silently_accepted"] is False
    first = datetime.fromisoformat(gaps["missing_open_timestamps_head"][0].replace("Z", "+00:00"))
    last = datetime.fromisoformat(gaps["missing_open_timestamps_tail"][-1].replace("Z", "+00:00"))
    assert first == GAP_FIRST_OPEN
    assert last == GAP_LAST_OPEN
    n_expected = int(((utc_ms(GAP_LAST_OPEN) - utc_ms(GAP_FIRST_OPEN)) / BAR_MS) + 1)
    assert n_expected == 288
    # Synthetic: if those 288 were filled, census would not match frozen sha.
    present_extra = set(range(utc_ms(GAP_FIRST_OPEN), utc_ms(GAP_LAST_OPEN) + BAR_MS, BAR_MS))
    assert len(present_extra) == 288


def test_gap_adjacent_decisions_excluded() -> None:
    verified = verify_frozen_eligibility(REPO)
    # Reconstruct using count on a present set that includes everything except the gap
    # is already done; freeze that Dec 6/7/8 00:05 are not complete.
    from scripts.research.d2_bitmex_pre2020 import row_timestamp_complete

    _auth, opens, _gz, _jsonl = load_sealed_open_times(REPO)
    present = set(opens)
    raw = opens[0]
    for day in (6, 7, 8):
        t = datetime(2016, 12, day, 0, 5, tzinfo=UTC)
        assert row_timestamp_complete(
            utc_ms(t), present_open_ms=present, raw_open_ms=raw, assume_complete_grid=False
        ) is False


def test_filling_the_known_hole_would_change_legal_n() -> None:
    _auth, opens, _gz, _jsonl = load_sealed_open_times(REPO)
    present = set(opens)
    gap_ms = list(range(utc_ms(GAP_FIRST_OPEN), utc_ms(GAP_LAST_OPEN) + BAR_MS, BAR_MS))
    assert len(gap_ms) == 288
    assert present.isdisjoint(gap_ms)
    filled = set(present)
    filled.update(gap_ms)
    legal_filled = count_legal_decision_rows(filled, raw_open_ms=opens[0])
    assert int(legal_filled["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"]) != FROZEN_EXPECTED_ELIGIBLE_N
    assert legal_filled["FIRST_RULE_ELIGIBLE_T"] != "2017-01-24T00:05:00.000Z"


def test_fail_closed_on_canonical_hash_mismatch(tmp_path: Path) -> None:
    from scripts.research.d2_bitmex_pre2020 import AUTHORITY_REL
    from scripts.research.d2_bitmex_replication_prereg import CANONICAL_REL as CANON

    auth_src = REPO / AUTHORITY_REL
    dest_auth = tmp_path / AUTHORITY_REL
    dest_gz = tmp_path / CANON
    dest_auth.parent.mkdir(parents=True, exist_ok=True)
    dest_gz.parent.mkdir(parents=True, exist_ok=True)
    dest_auth.write_bytes(auth_src.read_bytes())
    dest_gz.write_bytes(b"not-the-canonical-gzip")
    with pytest.raises(PreregInconsistency, match="CANONICAL_GZ_HASH_MISMATCH"):
        load_sealed_open_times(tmp_path)


def test_trailing_250_is_valid_rows_not_calendar_fill() -> None:
    verified = verify_frozen_eligibility(REPO)
    complete = int(verified["legal"]["COMPLETE_DECISION_ROWS_INCLUDING_WARMUP"])
    eligible = int(verified["legal"]["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"])
    assert complete - RV_TRAILING_WINDOW == eligible
    assert FROZEN_FIRST_RULE_ELIGIBLE_T > datetime(2016, 5, 15, 0, 5, tzinfo=UTC) + timedelta(days=250)


def test_year_matched_controls_not_pooled_k() -> None:
    years = np.asarray([2017] * 10 + [2018] * 10 + [2019] * 10)
    sev = np.arange(30, dtype=np.float64)
    mask = np.zeros(30, dtype=bool)
    mask[[0, 1, 10, 20, 21, 22]] = True  # K = 2,1,3
    pooled_k_is_forbidden(years, mask)
    means = year_matched_control_replicate_means(
        years, sev, mask, seed=D2_BITMEX_REPLICATION_RANDOM_SEED, n_replicates=50
    )
    assert means.shape == (50,)
    # Each replicate from the frozen helper has exactly K_y per year.
    reps = C.rate_matched_random_abstention(
        years, mask, seed=D2_BITMEX_REPLICATION_RANDOM_SEED, n_replicates=50
    )
    for rep in reps:
        assert int(rep[years == 2017].sum()) == 2
        assert int(rep[years == 2018].sum()) == 1
        assert int(rep[years == 2019].sum()) == 3
        assert int(rep.sum()) == 6


def test_no_d2_bitmex_outcome_computed() -> None:
    with pytest.raises((D2OutcomeRefused, ExecutionNotAuthorized)):
        execute_replication()
    with pytest.raises((D2OutcomeRefused, ExecutionNotAuthorized)):
        compute_mu_rule()
    with pytest.raises((D2OutcomeRefused, ExecutionNotAuthorized)):
        compute_delta()
    tree = ast.parse((REPO / "scripts/research/d2_bitmex_replication_prereg.py").read_text())
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "arithmetic_mae" not in calls
    assert "rv_btc_24h" not in calls
    assert "evaluate_rule_1" not in calls


def test_no_binance_2025_2026_access() -> None:
    bad = REPO / "canonical" / "1m" / "monthly" / "2025-01.parquet"
    with pytest.raises((C.ProtectedYearRefused, ProtectedPriceRefused, ProtectedBinanceRefused)):
        refuse_protected_price_path(bad)
    also = REPO / "canonical" / "1m" / "monthly" / "2026-11.parquet"
    with pytest.raises((C.ProtectedYearRefused, ProtectedPriceRefused, ProtectedBinanceRefused)):
        refuse_protected_price_path(also)


def test_prereg_artifact_contract() -> None:
    path = REPO / JSON_REL
    if not path.is_file():
        pytest.skip("prereg JSON not written yet")
    prereg = json.loads(path.read_text(encoding="utf-8"))
    assert prereg["PREREG_FROZEN"] is True
    assert prereg["EVIDENCE_CLASS"] == EVIDENCE_CLASS
    assert prereg["CANDIDATE"] == CANDIDATE
    assert prereg["EXPECTED_ELIGIBLE_N"] == 1069
    assert prereg["FIRST_RULE_ELIGIBLE_T"] == "2017-01-24T00:05:00.000Z"
    assert prereg["LAST_RULE_ELIGIBLE_T"] == "2019-12-30T00:05:00.000Z"
    assert prereg["REPLICATION_RANDOM_SEED"] == 20260921125
    assert prereg["N_RANDOM_CONTROLS"] == 10_000
    assert prereg["STATISTICAL_GATE"] == "MU_RULE > CONTROL_P95"
    assert "0.20 * UNCONDITIONAL_MEAN" in prereg["PRACTICAL_GATE"]
    assert prereg["PRIMARY_PASS_RULE"] == "STATISTICAL_GATE and PRACTICAL_GATE"
    assert prereg["pooled_k_across_years_forbidden"] is True
    assert prereg["subsample_to_815_forbidden"] is True
    assert prereg["D2_BITMEX_OUTCOME_COMPUTED"] is False
    assert prereg["PROTECTED_2025_OPENED"] is False
    assert prereg["PROTECTED_2026_OPENED"] is False
    assert prereg["MARKET_07_CREATED"] is False
    assert prereg["CLASSIFICATION_ASSIGNED"] is None
    assert prereg["KNOWN_GAP_HANDLING"] == "NO_FILL_NO_INTERPOLATION_NO_FORWARD_FILL_NO_SYNTHETIC"
    assert prereg["no_p85_p95_companion"] is True
    assert prereg["RV_PCTL"] == 90.0
    assert prereg["RV_TRAILING_WINDOW"] == 250
    assert prereg["SOURCE"]["fail_closed_on_authority_byte_change"] is True
    assert prereg["SOURCE"]["reacquire_forbidden"] is True
    assert prereg["EXECUTION_AUTHORIZED"] is False
    assert prereg["NO_YEARLY_RESCUE"] is True
    assert prereg["NO_TWO_OF_THREE_YEAR_REQUIREMENT"] is True
    assert prereg["YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY"] is True
    assert prereg["NEXT_UNIT"] == "D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW"
    assert prereg["PR_READY_TO_MERGE"] is True
    assert prereg["CLASSIFICATIONS_FROZEN_UNASSIGNED"] == [
        "D2_BITMEX_REPLICATION_SUPPORTED",
        "D2_BITMEX_REPLICATION_NOT_SUPPORTED",
        "D2_BITMEX_REPLICATION_INVALID",
    ]
    binding = json.loads((REPO / BINDING_REL).read_text(encoding="utf-8"))
    assert binding["EXECUTION_AUTHORIZED"] is False
    assert binding["EXPECTED_ELIGIBLE_N"] == 1069
    md = (REPO / MD_REL).read_text(encoding="utf-8")
    assert "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION" in md
    assert "EXACT_BINANCE_CONFIRMATION" in md
    assert "MU_RULE" in md


def test_discovery_and_feasibility_bytes_unchanged() -> None:
    assert (REPO / D2_RESULT).read_bytes() == _committed(D2_RESULT)
    assert (REPO / D2_RESULT_MD).read_bytes() == _committed(D2_RESULT_MD)
    assert (REPO / FEASIBILITY_JSON).read_bytes() == _committed(FEASIBILITY_JSON)
    assert (REPO / CONFIRMATION_JSON).read_bytes() == _committed(CONFIRMATION_JSON)
