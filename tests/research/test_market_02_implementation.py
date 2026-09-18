"""Synthetic-only tests for frozen MARKET-02 implementation."""

import numpy as np
import pytest

from scripts.research.market_02_oi_expansion_price_confirmation_lib import (
    ALPHA, CLASS_FRAGILE, CLASS_NO_EVIDENCE, CLASS_NOT_IDENTIFIABLE, CLASS_ROBUST,
    MARKET_02_BOOTSTRAP_SEED, SEED_MATERIAL_SHA256, design_matrix, evaluate_rows,
    fit, support_gate, usable_strata,
)


def _rows(effect=1.0, per=12):
    rows=[]; t=1598918400000
    strata=["HIGH|HIGH","HIGH|MID","HIGH|LOW"]
    eras=[1599459200000,1610000000000,1642000000000,1674000000000,1705000000000]
    seq=0
    for e in eras:
        for sid in strata:
            for j in range(per):
                rows.append({"decision_T_ms":e+seq*300000,"impulse_start_ms":e+seq*300000-3600000,
                    "continuation_return":effect if j%2==0 else 0.0,
                    "candidate_indicator":1 if j%2==0 else 0,"stratum_id":sid})
                seq+=1
    return rows


def test_seed_identity_exact():
    assert MARKET_02_BOOTSTRAP_SEED == 1852983754304692007
    assert SEED_MATERIAL_SHA256 == "19b71ee831e69f273338ef94e65ff4cc339eb6d8054c365fd160c7769955558f"


def test_design_no_intercept_candidate_last_and_beta():
    rows=[]
    for i in range(8):
        rows += [
            {"decision_T_ms":i,"continuation_return":3.0,"candidate_indicator":1,"stratum_id":"A"},
            {"decision_T_ms":i+20,"continuation_return":1.0,"candidate_indicator":0,"stratum_id":"A"},
            {"decision_T_ms":i+40,"continuation_return":4.0,"candidate_indicator":1,"stratum_id":"B"},
            {"decision_T_ms":i+60,"continuation_return":2.0,"candidate_indicator":0,"stratum_id":"B"},
        ]
    x,_=design_matrix(rows,["A","B"])
    assert x.shape[1] == 3
    assert np.all(x[:,0]+x[:,1] == 1.0)
    assert fit(rows,["A","B"])["beta_confirmation"] == pytest.approx(2.0)


def test_support_boundaries_and_nonusable_exclusion():
    rows=_rows()
    usable=usable_strata(rows)
    gate=support_gate(rows,usable)
    assert gate["ok"] is True
    assert len(usable) == 3


def test_insufficient_support_fail_closed():
    rows=_rows(per=2)
    r=evaluate_rows(rows)
    assert r["final_classification"] == CLASS_NOT_IDENTIFIABLE
    assert r["detected"] is False


def test_no_evidence_cannot_be_rescued():
    rows=_rows(effect=-1.0)
    r=evaluate_rows(rows)
    assert r["final_classification"] == CLASS_NO_EVIDENCE
    assert r["detected"] is False
    assert r["robustness"] is None


def test_result_governance_flags():
    r=evaluate_rows(_rows(effect=-1.0))
    assert r["MARKET_02_TEST_CALIBRATED"] is False
    assert r["MARKET_02_ARMED"] is False
    assert r["MARKET_02_EXECUTION_AUTHORIZED"] is False
    assert r["PROTECTED_OOS_TOUCHED"] is False
