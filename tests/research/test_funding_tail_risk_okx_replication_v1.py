"""Synthetic checks for the OKX funding-extremity design. No market file is loaded."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from scripts.research.funding_tail_risk_okx_replication_v1 import constants as K
from scripts.research.funding_tail_risk_okx_replication_v1 import model
from scripts.research.funding_state_historical_structure_v1.model import funding_state


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_DESIGN.md"
DESIGN_JSON = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_DESIGN.json"


def test_design_hash_and_frozen_choices():
    assert hashlib.sha256(DESIGN.read_bytes()).hexdigest() == K.DESIGN_SHA256
    assert hashlib.sha256(DESIGN_JSON.read_bytes()).hexdigest() == K.DESIGN_JSON_SHA256
    assert K.FUNDING_N == 3329
    assert K.MIN_PAST == 90
    assert K.PRIMARY_BARS == 96
    assert K.BOOT_DRAWS == 2000
    assert K.BOOT_SEED == 20261115
    assert K.BIN_EDGES == (0.10, 0.25, 0.75, 0.90)
    assert K.THRESHOLD_55_APPLIED is False
    assert K.PRACTICAL_RHO_APPLIED is False
    assert K.OFF_GRID_N == 1
    assert K.ON_GRID_N == 3328
    assert K.RESIDUAL_MAX_MS == 5000


def test_scoring_source_has_no_magnitude_bar():
    source = (ROOT / "scripts/research/funding_tail_risk_okx_replication_v1/model.py").read_text()
    assert "rho >=" not in source
    assert ">= 55" not in source
    body = source.split("def interpret", 1)[1].split("def _shape", 1)[0]
    assert '["bins"]' not in body
    assert '["years"]' not in body
    assert '["sides"]' not in body
    assert '["contrasts"]' not in body
    assert "BIN_EDGES" not in body
    assert "PARENT_PARTIAL" not in body


def test_settlement_hour_does_not_round_forward():
    assert model.decision_time(K.FIRST_FUNDING_MS) == K.FIRST_FUNDING_MS
    assert model.decision_time(K.ONE_SECOND_MS) == K.ONE_SECOND_MS - 1000
    assert model.decision_time(K.OFF_GRID_MS) is None
    assert model.decision_time(K.FIRST_FUNDING_MS + 5000) == K.FIRST_FUNDING_MS
    assert model.decision_time(K.FIRST_FUNDING_MS + 5001) is None
    four = K.FIRST_FUNDING_MS + 4 * K.HOUR_MS
    assert model.decision_time(four) is None


def test_extremity_is_distance_from_the_past_only_center():
    rates = np.asarray([1.0, 2.0, 3.0, 0.0, 5.0])
    rank = funding_state(rates, min_past=2)
    distance = model.extremity(rank)
    assert np.isnan(distance[0]) and np.isnan(distance[1])
    assert distance[2] == abs((1.0 + 2.0) / 3.0 - 0.5)
    later = rates.copy()
    later[4] = -9.0
    again = model.extremity(funding_state(later, min_past=2))
    assert again[2] == distance[2] and again[3] == distance[3]


def test_upside_is_the_mirror_of_the_parent_downside():
    from scripts.research.funding_state_historical_structure_v1.model import absolute_excursion, adverse_long

    highs = np.asarray([101.0, 110.0])
    lows = np.asarray([98.0, 99.0])
    assert model.upside(100.0, np.asarray([99.0, 100.0])) == 0.0
    assert model.upside(100.0, highs) == np.log(1.10)
    assert adverse_long(100.0, lows) == -np.log(0.98)
    assert absolute_excursion(100.0, lows, highs) == abs(np.log(1.10))


def test_bins_follow_the_parent_edges():
    rank = np.asarray([0.0, 0.099, 0.10, 0.25, 0.75, 0.90, 1.0])
    assert list(model.bin_id(rank)) == [0, 0, 1, 2, 3, 4, 4]


def test_interpretation_uses_the_partial_interval_only():
    def row(point, lo, hi, ok=True):
        return {
            "partial": point,
            "spearman": -1.0,
            "interval": {"partial": {"lo": lo, "hi": hi, "interpretable": ok}},
            "bins": [{"mean_abs_excursion": 9.0}],
            "years": [{"partial": -1.0}],
            "sides": [{"spearman_extremity": -1.0}],
            "contrasts": {"upper": {"point": -1.0}, "lower": {"point": 1.0}},
        }

    supported = model.interpret(row(0.2, 0.01, 0.4))
    assert supported["code"] == K.CODE_SUPPORTED
    assert supported["product_integration_candidate"] is True
    assert supported["causal_claim"] is False
    uncertain = model.interpret(row(0.2, -0.01, 0.4))
    assert uncertain["code"] == K.CODE_UNCERTAIN
    assert uncertain["product_integration_candidate"] is False
    absent = model.interpret(row(-0.2, -0.4, -0.01))
    assert absent["code"] == K.CODE_NOT_OBSERVED
    zero = model.interpret(row(0.0, 0.0, 0.2))
    assert zero["code"] == K.CODE_NOT_OBSERVED
    blind = model.interpret(row(0.2, None, None, ok=False))
    assert blind["code"] == K.CODE_NOT_INTERPRETABLE
    assert blind["product_integration_candidate"] is False


def test_synthesis_does_not_replace_the_route():
    summary = {
        "spearman": 0.2,
        "partial": 0.05,
        "contrasts": {"upper": {"point": 0.01}, "lower": {"point": -0.02}},
    }
    label = {"code": K.CODE_UNCERTAIN}
    out = model.synthesis(summary, label)
    assert out["conclusion"] == "B_POINT_POSITIVE_UNCERTAIN"
    assert out["shape"] == "ASYMMETRIC"
    assert out["attenuation"] == "CONTROL_REDUCED_THE_POINT"
    assert out["similarity_cutoff_applied"] is False
    assert out["route_input"] is False
    assert out["market_03"] == "COMPATIBLE_WITH_HISTORICAL_DRAWDOWN_REDUCTION"
    assert out["causal_claim"] is False
    flat = model.synthesis(
        {"spearman": -0.1, "partial": -0.02, "contrasts": {"upper": {"point": -0.01}, "lower": {"point": -0.01}}},
        {"code": K.CODE_NOT_OBSERVED},
    )
    assert flat["conclusion"] == "C_NOT_OBSERVED"
    assert flat["shape"] == "TAILS_NOT_ABOVE_CENTER"
    assert flat["market_03"] == "NO_POSITIVE_EXTREMITY_ASSOCIATION_TO_PLACE_BESIDE_MARKET_03"


def test_bootstrap_draw_is_reproducible():
    rng = np.random.default_rng(8)
    rank = rng.random(80)
    outcome = np.abs(rank - 0.5) + 0.1 * rng.random(80)
    rv = rng.random(80)
    weeks = [(2021, i // 10) for i in range(80)]
    first = model._bootstrap(rank, model.extremity(rank), outcome, rv, weeks, draws=25, seed=11)
    second = model._bootstrap(rank, model.extremity(rank), outcome, rv, weeks, draws=25, seed=11)
    assert first["partial"]["lo"] == second["partial"]["lo"]
    assert first["raw"]["hi"] == second["raw"]["hi"]
    assert first["upper_tail"]["lo"] == second["upper_tail"]["lo"]
    assert first["weeks"] == 8


def test_this_module_does_not_load_the_evaluator():
    import sys

    assert "scripts.research.funding_tail_risk_okx_replication_v1.evaluate" not in sys.modules
    assert "scripts.research.funding_tail_risk_okx_replication_v1.data" not in sys.modules
