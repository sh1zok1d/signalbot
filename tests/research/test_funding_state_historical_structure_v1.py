"""Synthetic checks for the funding-state design. No market file is loaded."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from scripts.research.funding_state_historical_structure_v1 import constants as K
from scripts.research.funding_state_historical_structure_v1 import model


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "research" / "FUNDING_STATE_HISTORICAL_STRUCTURE_V1_DESIGN.md"


def test_design_hash_and_frozen_choices():
    assert hashlib.sha256(DESIGN.read_bytes()).hexdigest() == K.DESIGN_SHA256
    assert K.FUNDING_N == 4749
    assert K.MIN_PAST == 90
    assert K.PRIMARY_BARS == 96
    assert K.SECONDARY_BARS == (12, 48)
    assert K.BOOT_DRAWS == 2000
    assert K.BOOT_SEED == 20261114
    assert K.BIN_EDGES == (0.10, 0.25, 0.75, 0.90)
    assert K.PRODUCT_INTEGRATION_CANDIDATE is False
    assert K.THRESHOLD_55_APPLIED is False
    assert K.PRACTICAL_RHO_APPLIED is False
    assert K.OI_OPENED is False
    assert K.PREMIUM_SCORED is False
    assert K.OBJECTS_2025_2026_USED is False


def test_scoring_source_has_no_percentile_cutoff_or_magnitude_bar():
    source = (ROOT / "scripts/research/funding_state_historical_structure_v1/model.py").read_text()
    assert "funding_pct" not in source
    assert ">= 55" not in source
    assert "rho >=" not in source
    body = source.split("def interpret", 1)[1]
    assert '["bins"]' not in body
    assert '["years"]' not in body
    assert '["sides"]' not in body
    assert '["secondary"]' not in body
    assert "BIN_EDGES" not in body


def test_past_only_rank_ignores_the_current_and_later_rates():
    rates = np.asarray([1.0, 2.0, 3.0, 0.0, 5.0])
    state = model.funding_state(rates, min_past=2)
    assert np.isnan(state[0]) and np.isnan(state[1])
    assert state[2] == (1.0 + 2.0) / 3.0
    assert state[3] == 1.0 / 4.0
    assert state[4] == (1.0 + 4.0) / 5.0
    later = rates.copy()
    later[4] = -9.0
    again = model.funding_state(later, min_past=2)
    assert again[2] == state[2] and again[3] == state[3]
    tied = model.funding_state(np.asarray([1.0, 1.0, 1.0]), min_past=1)
    assert tied[1] == (1.0 + 0.5) / 2.0
    assert tied[2] == (1.0 + 1.0) / 3.0


def test_long_adverse_is_the_downside_and_is_zero_when_price_holds():
    held = model.adverse_long(100.0, np.asarray([100.0, 101.0, 103.0]))
    assert held == 0.0
    dropped = model.adverse_long(100.0, np.asarray([99.0, 101.0]))
    assert dropped == -np.log(0.99)
    wide = model.absolute_excursion(100.0, np.asarray([98.0]), np.asarray([110.0]))
    assert wide == abs(np.log(1.10))


def test_incremental_association_survives_a_volatility_control():
    rng = np.random.default_rng(4)
    state = rng.random(1500)
    rv = rng.random(1500)
    outcome = state + 0.05 * rng.normal(size=1500)
    assert model.incremental_rho(state, outcome, rv) > 0.5
    copied = rv.copy()
    assert np.isnan(model.incremental_rho(state, copied, rv))


def test_bins_follow_the_frozen_edges():
    state = np.asarray([0.0, 0.099, 0.10, 0.25, 0.75, 0.90, 1.0])
    assert list(model.bin_id(state)) == [0, 0, 1, 2, 3, 4, 4]


def test_interpretation_uses_the_incremental_interval_only():
    def row(point, lo, hi, ok=True):
        return {
            "partial": point,
            "interval": {"partial": {"lo": lo, "hi": hi, "interpretable": ok}},
            "bins": [{"mean_adverse": 9.0}],
            "years": [{"partial": -1.0}],
            "sides": [{"spearman": -1.0}],
            "secondary": [{"partial": -1.0}],
        }

    above = model.interpret(row(0.2, 0.01, 0.4))
    assert above["code"] == K.CODE_POSITIVE
    assert above["product_integration_candidate"] is False
    assert above["causal_claim"] is False
    below = model.interpret(row(-0.2, -0.4, -0.01))
    assert below["code"] == K.CODE_NEGATIVE
    inside = model.interpret(row(0.2, -0.01, 0.4))
    assert inside["code"] == K.CODE_UNCERTAIN
    zero = model.interpret(row(0.0, 0.0, 0.2))
    assert zero["code"] == K.CODE_UNCERTAIN
    blind = model.interpret(row(0.2, None, None, ok=False))
    assert blind["code"] == K.CODE_NOT_INTERPRETABLE


def test_bootstrap_draw_is_reproducible():
    rng = np.random.default_rng(8)
    state = rng.random(80)
    outcome = state + 0.1 * rng.normal(size=80)
    rv = rng.random(80)
    weeks = [(2021, i // 10) for i in range(80)]
    first = model._bootstrap(state, outcome, rv, weeks, draws=25, seed=11)
    second = model._bootstrap(state, outcome, rv, weeks, draws=25, seed=11)
    assert first["partial"]["lo"] == second["partial"]["lo"]
    assert first["raw"]["hi"] == second["raw"]["hi"]
    assert first["weeks"] == 8


def test_this_module_does_not_load_the_evaluator():
    import sys

    assert "scripts.research.funding_state_historical_structure_v1.evaluate" not in sys.modules
    assert "scripts.research.funding_state_historical_structure_v1.data" not in sys.modules
