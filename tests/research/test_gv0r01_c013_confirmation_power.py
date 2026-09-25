"""GV0R01-C013 confirmation feasibility/design. Offline: reads only the immutable discovery
result and committed design records. No market data, no protected data, no execution."""
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from scripts.research import gv0r01_c013_confirmation_power as P

REPO = Path(__file__).resolve().parents[2]
DESIGN = REPO / 'docs/research/GV0R01_C013_CONFIRMATION_FEASIBILITY_AND_DESIGN.json'
POWER = REPO / 'docs/research/GV0R01_C013_CONFIRMATION_POWER.json'
LEDGER = REPO / 'docs/research/SCIENTIFIC_TEST_LEDGER.json'


def test_power_inputs_are_the_immutable_discovery_result_only():
    d = P.load()
    assert d['x'].size == 260 and d['a'].size == 260
    assert math.isclose(d['x'].mean(), d['pooled']) and math.isclose(d['a'].mean(), d['adj_pooled'])
    assert sorted(set(d['years'].tolist())) == [2020, 2021, 2022, 2023, 2024]


def test_power_refuses_a_different_discovery_result(monkeypatch):
    monkeypatch.setattr(P, 'RESULT_SHA256', '0' * 64)
    with pytest.raises(RuntimeError, match='digest'):
        P.load()


def test_power_simulation_is_deterministic(monkeypatch):
    monkeypatch.setattr(P, 'N_REP', 50)
    monkeypatch.setattr(P, 'GRID', (51, 103))
    monkeypatch.setattr(P, 'SIZE_GRID', (156,))
    assert P.run() == P.run()


def test_year_block_surfaces_are_whole_exposed_years_plus_one_contiguous_block():
    d = P.load()
    rng = np.random.Generator(np.random.PCG64(1))
    idx = P.surface_indices(rng, 103, 'YEAR_BLOCK', 260, d['years'])
    assert idx.size == 103
    first = idx[:52]
    assert (np.diff(first) == 1).all() and d['years'][first[0]] == d['years'][first[-1]]
    tail = idx[52:]
    assert (np.diff(tail) == 1).all() and len(set(d['years'][tail].tolist())) == 1


def test_confirmation_rule_helpers():
    assert P.hac_lag(51) == 3 and P.hac_lag(103) == 4 and P.hac_lag(364) == 5
    assert P.temporal_ok(np.array([-1.0] * 26 + [-1.0] * 25))
    assert not P.temporal_ok(np.array([-1.0] * 26 + [1.0] * 25))
    s = np.array([-1.0] * 78 + [1.0] * 26)          # 3 of 4 half-years negative
    assert P.temporal_ok(s)


def test_committed_power_record_matches_design_record():
    power = json.loads(POWER.read_text())
    design = json.loads(DESIGN.read_text())
    assert design['POWER']['RECORD_SHA256'] == hashlib.sha256(POWER.read_bytes()).hexdigest()
    assert power['INPUT_SHA256'] == P.RESULT_SHA256 and power['SEED'] == P.SEED
    assert power['PROTECTED_DATA_OPENED'] is False and power['MARKET_DATA_READ'] is False
    assert power['MIN_WEEKS_STAT_AND_DIRECTION_AT_DISCOVERY_EFFECT'] == 468
    yb = power['RESULTS']['YEAR_BLOCK']['DISCOVERY_EFFECT']
    for W in ('51', '86', '103'):
        assert yb[W]['STATISTICAL_AND_DIRECTION'] < 0.80
    assert all(r['FULL_PASS_EXCLUDING_CONTROL'] < 0.80 for r in power['SIZE_PLANNING_YEAR_BLOCK_DISCOVERY_EFFECT'].values())


def test_calendar_surfaces_are_complete_iso_weeks():
    design = json.loads(DESIGN.read_text())['SURFACES_EVALUATED']
    for key, weeks in (('A_2025_ONLY', 51), ('B1_2025_PLUS_2026_PREFIX', 86), ('B2_FULL_2025_2026', 103)):
        s = design[key]
        first, last = date.fromisoformat(s['FIRST_DECISION_DATE']), date.fromisoformat(s['LAST_DECISION_DATE'])
        assert first.weekday() == 0 and last.weekday() == 6 and first == date(2025, 1, 6)
        assert (last - first).days + 1 == 7 * weeks == s['DECISION_DAYS'] and s['WEEKS'] == weeks
        assert s['LEGAL_LAST_TARGET_BAR'] == s['LAST_DECISION_DATE']


def test_decision_is_wait_and_nothing_executable_was_created():
    d = json.loads(DESIGN.read_text())
    assert d['FRESH_SURFACE_DECISION'] == 'WAIT_FOR_MORE_FRESH_DATA'
    for flag in ('PREREG_CREATED', 'HARNESS_IMPLEMENTED', 'EXECUTION_AUTHORIZED', 'PROTECTED_DATA_OPEN_AUTHORIZED',
                 'PROTECTED_2025_VALUES_OPENED', 'PROTECTED_2026_VALUES_OPENED', 'CONFIRMATION_EXECUTED',
                 'NEW_MARKET_OUTCOME_CREATED', 'CONFIRMATION_TEST_REGISTERED', 'EXECUTED_TESTS_INCREMENTED'):
        assert d[flag] is False, flag
    enum = d['PROTECTED_METADATA_ENUMERATION']
    assert enum['OBJECT_PAYLOAD_GETS'] == 0 and enum['CHECKSUM_SIDECAR_GETS'] == 0 and enum['PROTECTED_VALUES_PARSED'] == 0
    for rel in ('GV0R01_C013_CONFIRMATION_PREREG.json', 'GV0R01_C013_CONFIRMATION_PREREG.md',
                'GV0R01_C013_CONFIRMATION_EXECUTION_PERMIT.json'):
        assert not (REPO / 'docs/research' / rel).exists()


def test_ledger_registers_no_confirmation_and_keeps_executed_count():
    ledger = json.loads(LEDGER.read_text())
    assert [t['TEST_FAMILY_ID'] for t in ledger['TESTS']] == ['TF-GV0R01-C013-MT1']
    fam = [f for f in ledger['SEARCH_FAMILIES'] if f['SEARCH_FAMILY_ID'] == 'SF-GENERATOR_V0-GV0R01'][0]
    assert fam['EXECUTED_TESTS'] == 1 and fam['REGISTERED_TESTS'] == 1


def test_design_keeps_the_frozen_primary_and_forbids_rescue():
    d = json.loads(DESIGN.read_text())['DESIGN_IF_A_POWERED_SURFACE_EXISTS']
    assert 'K=5, H=1, N=50' in d['SCIENTIFIC_RULE'] and 'never become the confirmatory primary' in d['SCIENTIFIC_RULE']
    assert 'No regime filter' in d['SIGN_REVERSAL'] and 'no parameter, horizon, sign or regime rescue' in d['COMBINATION']
