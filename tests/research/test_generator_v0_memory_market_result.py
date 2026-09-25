"""MARKET_TEST_RESULT memory event. Offline: synthetic scientific authorities in a
temporary repository root; no market data, no provider, no protected data.

The synthetic hypothesis is GV0CAL-C001 (a real signature in the reconstructed GV0CAL
memory). Result values are arbitrary fixtures, not real outcomes.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.generator_v0 import finalize_memory as cli
from scripts.research.generator_v0 import memory_finalizer as fin
from scripts.research.generator_v0 import memory_store as store
from scripts.research.generator_v0.context import ROOT, DESIGN, MAP, AUTHORITY, Contexts, ContractError, canonical, read
from tests.research.test_generator_v0_memory_finalizer import Crash, FAULT_POINTS, authoritative_bytes, finalized_root

LEDGER = fin.SCIENTIFIC_TEST_LEDGER
RESULT = 'docs/research/SYN_MARKET_TEST_RESULT.json'
PREREG = 'docs/research/SYN_MARKET_TEST_PREREG.json'
PERMIT = 'docs/research/SYN_MARKET_TEST_PERMIT.json'
TF = 'TF-SYN-C001-MT1'
HYP = 'GV0CAL-C001'
PERMIT_COMMIT = 'a' * 40
LEAK_TOKENS = ('PROMISING_PROTOTYPE', 'CLASSIFICATION', 'P_TWO_SIDED', 'POOLED', 'HAC_T', 'STATISTICAL_GATE',
               'ADJACENCY', 'MARKET_TEST_RESULTS', TF, '-0.0123456', '0.00456789')


def _write(root, rel, obj):
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_bytes(store.pretty(obj))
    return hashlib.sha256((root / rel).read_bytes()).hexdigest()


def market_fixture(root, tf=TF, hyp=HYP, result_rel=RESULT, mutate=None):
    """Consistent synthetic prereg, permit, result and closed ledger entry."""
    m = mutate or {}
    sf = 'SF-SYN'
    prereg = {'HYPOTHESIS_ID': hyp, 'TEST_FAMILY_ID': tf, 'SEARCH_FAMILY_ID': sf,
              'EVIDENCE_TIER': {'TIER': 'DISCOVERY_ONE_SHOT'}, 'PARAMS': {'PRIMARY_VARIANT': {'K': 5, 'H': 1, 'N': 50}}}
    prereg_rel = PREREG.replace('.json', '_' + tf + '.json')
    prereg_sha = _write(root, prereg_rel, prereg)
    permit = {'EXECUTION_AUTHORIZED': True, 'HYPOTHESIS_ID': hyp, 'TEST_FAMILY_ID': tf, 'SEARCH_FAMILY_ID': sf,
              'PREREG_SHA256': m.get('PERMIT_PREREG', prereg_sha), 'RERUN_AUTHORIZED': False,
              'PROTECTED_2025_2026_AUTHORIZED': False, 'DESIGN_CHANGE_AUTHORIZED': False}
    permit_rel = PERMIT.replace('.json', '_' + tf + '.json')
    _write(root, permit_rel, permit)
    gates = {g: True for g in fin.RESULT_GATES}
    result = {'SCHEMA': 'SYN_RESULT_V1', 'HYPOTHESIS_ID': hyp, 'TEST_FAMILY_ID': tf,
              'IDENTITY': {'PREREG_SHA256': m.get('RESULT_PREREG', prereg_sha),
                           'DATASET': {'DATASET_ID': 'SYN_PANEL', 'SNAPSHOT_ID': 'f' * 64}},
              'PRIMARY': {'K': 5, 'H': 1, 'N': 50, 'POOLED': -0.0123456, 'NULL': {'P_TWO_SIDED': 0.00456789},
                          'VALID_DAYS': 100, 'VALID_WEEKS': 20, 'MISSING_TARGET_RATE': 0.0, 'YEARLY': {'2020': -0.01},
                          'CONTROLLED': {'POOLED': -0.02, 'NULL': {'P_TWO_SIDED': 0.01}}},
              'ADJACENCY_DIAGNOSTIC': {'POOLED': -0.03},
              'EVALUATION': {'CLASSIFICATION': m.get('RESULT_CLASS', 'PROMISING_PROTOTYPE'), 'GATES': gates, 'HAC_T': -2.5,
                             'YEARS_SHARING_POOLED_SIGN': ['2020'], 'SECONDARY_CAN_CHANGE_CLASSIFICATION': False},
              'PROTECTED_2025_2026_OPENED': m.get('PROTECTED', False)}
    result_sha = _write(root, result_rel, result)
    entry = {'TEST_FAMILY_ID': tf, 'SEARCH_FAMILY_ID': sf, 'HYPOTHESIS_ID': hyp, 'PREREG_PATH': prereg_rel,
             'PREREG_SHA256': m.get('LEDGER_PREREG', prereg_sha), 'PRIMARY_TEST_COUNT': 1, 'SECONDARY_TEST_COUNT': 7,
             'MULTIPLICITY_METHOD': 'single primary', 'STATUS': m.get('STATUS', 'EXECUTED'),
             'RESULT_SHA256': m.get('LEDGER_RESULT_SHA', result_sha), 'CLASSIFICATION': m.get('LEDGER_CLASS', 'PROMISING_PROTOTYPE'),
             'RESULT_PATH': result_rel, 'EXECUTION_PERMIT_PATH': permit_rel, 'EXECUTION_PERMIT_COMMIT': PERMIT_COMMIT,
             'RERUN_AUTHORIZED': False}
    path = root / LEDGER
    ledger = json.loads(path.read_text()) if path.exists() else {'SCHEMA_VERSION': 'SCIENTIFIC_TEST_LEDGER_V1', 'TESTS': [],
                                                                 'SEARCH_FAMILIES': [{'SEARCH_FAMILY_ID': sf, 'EXECUTED_TESTS': 0}]}
    ledger['TESTS'] = [t for t in ledger['TESTS'] if t['TEST_FAMILY_ID'] != tf] + [entry]
    ledger['SEARCH_FAMILIES'][0]['EXECUTED_TESTS'] = sum(1 for t in ledger['TESTS'] if t['STATUS'] == 'EXECUTED')
    _write(root, LEDGER, ledger)
    return result_rel


@pytest.fixture
def root(tmp_path):
    r = finalized_root(tmp_path)
    market_fixture(r)
    return r


def source(r, result_rel=RESULT):
    return fin.source_from_market_test_result(r, result_rel)


def view_bytes(r):
    return {k: (r / rel).read_bytes() for k, rel in (('BLIND', MAP), ('AUTHORITY', AUTHORITY))}


# 1-2 dry run writes nothing; apply appends exactly one result -----------------------------------

def test_dry_run_writes_nothing_and_apply_appends_one_result(root):
    before = authoritative_bytes(root)
    dry = fin.finalize_market_test_result(root, source(root))
    assert dry['STATUS'] == 'DRY_RUN' and dry['NEW_EVENT'] is False and authoritative_bytes(root) == before
    out = fin.finalize_market_test_result(root, source(root), apply=True)
    assert out['STATUS'] == 'FINALIZED' and out['PROPOSED_EVENT_HASH'] == dry['PROPOSED_EVENT_HASH']
    events = store.chain(root)
    assert [e['EVENT_TYPE'] for e in events] == ['LEGACY_BOOTSTRAP', 'CAMPAIGN_FINALIZATION', 'MARKET_TEST_RESULT']
    assert events[-1]['CAMPAIGN_ID'] == 'SYNC001MT1'
    mem = read(root / 'docs/research/MECHANISM_MEMORY_V0.json')
    assert list(mem['MARKET_TEST_RESULTS']) == [TF]


# 3-9 existing state unchanged; only MEMORY changes -------------------------------------------------

def test_entries_rows_attempts_blind_and_authority_are_unchanged(root):
    design = read(root / DESIGN)
    pre = store.published(root, design)['VIEWS']
    pre_bytes = view_bytes(root)
    fin.finalize_market_test_result(root, source(root), apply=True)
    post = store.published(root, design)['VIEWS']
    assert post['MEMORY']['ENTRIES'] == pre['MEMORY']['ENTRIES']
    assert post['AUTHORITY'] == pre['AUTHORITY'] and post['ATTEMPTS'] == pre['ATTEMPTS']
    assert view_bytes(root) == pre_bytes
    assert len(post['MEMORY']['ENTRIES']) == len(pre['MEMORY']['ENTRIES'])
    assert len(post['ATTEMPTS']) == len(pre['ATTEMPTS'])
    d0, d1 = store.view_digests(pre), store.view_digests(post)
    assert [k for k in d0 if d0[k] != d1[k]] == ['RESULTING_MEMORY_DIGEST']
    assert {k: v for k, v in post['MEMORY'].items() if k != 'MARKET_TEST_RESULTS'} == pre['MEMORY']


# 10-13 full memory has the result; generator and novelty governance do not ------------------------

def test_full_memory_holds_result_but_generator_and_governance_do_not(root):
    fin.finalize_market_test_result(root, source(root), apply=True)
    rec = read(root / 'docs/research/MECHANISM_MEMORY_V0.json')['MARKET_TEST_RESULTS'][TF]
    assert rec['CLASSIFICATION'] == 'PROMISING_PROTOTYPE' and rec['SIGNATURE_ID'] == HYP
    assert rec['PRIMARY']['POOLED'] == -0.0123456 and rec['PRIMARY']['P_TWO_SIDED'] == 0.00456789
    assert rec['EXECUTION_PERMIT_COMMIT'] == PERMIT_COMMIT and rec['RERUN_AUTHORIZED'] is False
    c = Contexts(root)
    gen = canonical(c.generator())
    novelty = canonical({'BLIND': c.blind, 'AUTHORITY': c.authority})
    for tok in LEAK_TOKENS:
        assert tok not in gen, tok
        assert tok not in novelty, tok
    assert c.blind[HYP]['REGION_STATE'] == 'PRIOR_WORK_SIGNATURE'
    assert set(c.blind[HYP]) == set(read(root / DESIGN)['BLIND_GENERATOR_CONTEXT']['WHITELISTED_FIELDS']) | {'REGION_STATE'}


# 14 historical replay ---------------------------------------------------------------------------

def test_historical_versions_reproduce_exactly(root):
    design = read(root / DESIGN)
    events = store.chain(root)
    pre = {i: store.published_at(root, design, e['EVENT_HASH'])['VIEWS'] for i, e in enumerate(events)}
    fin.finalize_market_test_result(root, source(root), apply=True)
    for i, e in enumerate(events):
        assert store.published_at(root, design, e['EVENT_HASH'])['VIEWS'] == pre[i]
    assert 'MARKET_TEST_RESULTS' not in store.published_at(root, design, events[-1]['EVENT_HASH'])['VIEWS']['MEMORY']
    assert Contexts(root, memory_event=events[-1]['EVENT_HASH']).blind == Contexts(root).blind


# 15-20 fail-closed cross-links -----------------------------------------------------------------

@pytest.mark.parametrize('mutate,message', [
    ({'LEDGER_PREREG': '0' * 64}, 'prereg digest'),
    ({'PERMIT_PREREG': '0' * 64}, 'prereg digest'),
    ({'RESULT_PREREG': '0' * 64}, 'prereg digest'),
    ({'LEDGER_RESULT_SHA': '0' * 64}, 'ledger result digest'),
    ({'LEDGER_CLASS': 'NO_USEFUL_STRUCTURE'}, 'classification'),
    ({'STATUS': 'PREREGISTERED_NOT_EXECUTED'}, 'not EXECUTED'),
    ({'PROTECTED': True}, 'protected'),
])
def test_inconsistent_scientific_authorities_fail_closed(tmp_path, mutate, message):
    r = finalized_root(tmp_path)
    market_fixture(r, mutate=mutate)
    before = authoritative_bytes(r)
    with pytest.raises(ContractError, match=message):
        fin.finalize_market_test_result(r, source(r), apply=True)
    assert authoritative_bytes(r) == before


def test_unknown_or_non_generating_hypothesis_fails_closed(tmp_path):
    r = finalized_root(tmp_path)
    market_fixture(r, hyp='GV0CAL-C099')
    with pytest.raises(ContractError, match='did not generate a canonical signature'):
        source(r)
    r2 = finalized_root(tmp_path, 'repo2')
    market_fixture(r2, hyp='D2')   # a legacy signature with no generating attempt record
    with pytest.raises(ContractError, match='did not generate a canonical signature'):
        source(r2)


def test_non_canonical_result_bytes_fail_closed(root):
    raw = json.loads((root / RESULT).read_text())
    (root / RESULT).write_text(json.dumps(raw))
    with pytest.raises(ContractError, match='not canonical'):
        source(root)


def test_store_refuses_market_delta_that_adds_entries_or_unknown_signature(root):
    design = read(root / DESIGN)
    views = store.published(root, design)['VIEWS']
    state = {'MEMORY': views['MEMORY'], 'ROWS': views['AUTHORITY']['ROWS'], 'ATTEMPTS': views['ATTEMPTS']}
    delta = fin.build_market_delta(state, source(root))
    bad = copy.deepcopy(delta)
    bad['ADD_ENTRIES'] = {'X': {}}
    with pytest.raises(ContractError, match='may not add entries'):
        store.apply_delta(state, bad)
    bad = copy.deepcopy(delta)
    bad['ADD_MARKET_TEST_RESULTS'][TF]['SIGNATURE_ID'] = 'NOPE'
    with pytest.raises(ContractError, match='unknown signature'):
        store.apply_delta(state, bad)


# 21-22 idempotence and conflict ------------------------------------------------------------------

def test_identical_reapply_is_already_finalized(root):
    first = fin.finalize_market_test_result(root, source(root), apply=True)
    before = authoritative_bytes(root)
    again = fin.finalize_market_test_result(root, source(root), apply=True)
    assert again['STATUS'] == 'ALREADY_FINALIZED' and again['EVENT_HASH'] == first['PROPOSED_EVENT_HASH']
    assert authoritative_bytes(root) == before and len(store.chain(root)) == 3


def test_same_test_family_with_different_source_hard_fails(root):
    fin.finalize_market_test_result(root, source(root), apply=True)
    market_fixture(root, mutate={'RESULT_CLASS': 'NO_USEFUL_STRUCTURE', 'LEDGER_CLASS': 'NO_USEFUL_STRUCTURE'})
    with pytest.raises(ContractError, match='different source'):
        fin.finalize_market_test_result(root, source(root), apply=True)


# 23 a second distinct test family for the same signature ------------------------------------------

def test_second_test_family_for_same_signature_is_allowed(root):
    fin.finalize_market_test_result(root, source(root), apply=True)
    second = market_fixture(root, tf='TF-SYN-C001-MT2', result_rel=RESULT.replace('.json', '_MT2.json'))
    out = fin.finalize_market_test_result(root, source(root, second), apply=True)
    assert out['STATUS'] == 'FINALIZED' and out['MARKET_TEST_RESULT_COUNT'] == 2
    mem = read(root / 'docs/research/MECHANISM_MEMORY_V0.json')
    assert sorted(mem['MARKET_TEST_RESULTS']) == [TF, 'TF-SYN-C001-MT2']
    assert {r['SIGNATURE_ID'] for r in mem['MARKET_TEST_RESULTS'].values()} == {HYP}


# 24 verify / rebuild ---------------------------------------------------------------------------

def test_verify_and_rebuild_reproduce_the_market_event(root):
    fin.finalize_market_test_result(root, source(root), apply=True)
    v = fin.verify(root)
    assert v['STATUS'] == 'VERIFIED' and v['MARKET_TEST_RESULT_COUNT'] == 1
    assert v['EVENTS'][-1]['EVENT_TYPE'] == 'MARKET_TEST_RESULT'
    rb = fin.rebuild(root)
    assert rb['STATUS'] == 'REBUILT_EQUALS_PUBLISHED' and rb['DIGESTS'] == v['DIGESTS']
    ev = store.chain(root)[-1]
    assert set(ev) == set(store.EVENT_FIELDS) and store.event_hash(ev) == ev['EVENT_HASH']


def test_tampered_market_delta_fails_verification(root):
    fin.finalize_market_test_result(root, source(root), apply=True)
    ev = store.chain(root)[-1]
    path = store.delta_path(root, ev['MEMORY_DELTA_SHA256'])
    d = json.loads(path.read_text())
    d['ADD_MARKET_TEST_RESULTS'][TF]['CLASSIFICATION'] = 'NO_USEFUL_STRUCTURE'
    path.write_bytes(store.pretty(d))
    with pytest.raises(ContractError):
        fin.verify(root)


# 25-26 crash semantics -------------------------------------------------------------------------

@pytest.mark.parametrize('point', FAULT_POINTS)
def test_crash_before_head_switch_keeps_prior_authority(root, point):
    before = authoritative_bytes(root)

    def fault(p):
        if p == point:
            raise Crash(p)
    with pytest.raises(Crash):
        fin.finalize_market_test_result(root, source(root), apply=True, fault=fault)
    assert authoritative_bytes(root) == before
    assert fin.verify(root)['STATUS'] == 'VERIFIED'
    assert fin.finalize_market_test_result(root, source(root), apply=True)['STATUS'] == 'FINALIZED'


def test_crash_after_head_switch_is_detected_then_repaired(root):
    def fault(p):
        if p == 'AFTER_HEAD_BEFORE_DERIVED_CACHES':
            raise Crash(p)
    with pytest.raises(Crash):
        fin.finalize_market_test_result(root, source(root), apply=True, fault=fault)
    assert fin.verify(root)['STATUS'] == 'CHAIN_VERIFIED_DERIVED_CACHE_DRIFT'
    with pytest.raises(ContractError):
        Contexts(root)
    out = fin.finalize_market_test_result(root, source(root), apply=True)
    assert out['STATUS'] == 'ALREADY_FINALIZED' and out['DERIVED_CACHES_REPAIRED']
    assert fin.verify(root)['STATUS'] == 'VERIFIED'


# CLI -------------------------------------------------------------------------------------------

def test_cli_market_result_path_and_campaign_id_refusal(root, capsys):
    assert cli.main(['--dry-run', '--market-test-result', RESULT, '--root', str(root)]) == 0
    assert json.loads(capsys.readouterr().out)['STATUS'] == 'DRY_RUN'
    with pytest.raises(SystemExit):
        cli.main(['--dry-run', '--market-test-result', RESULT, '--campaign-id', 'GV0R01', '--root', str(root)])


# Published repository state ----------------------------------------------------------------------

GV0R01_EVENT = '416b22fabd1663be9094bce18c5bce2a8b3d062b0b01525a25395d195788bead'


def test_published_repository_carries_the_c013_result_in_full_memory_only():
    design = read(ROOT / DESIGN)
    pub = store.published(ROOT, design)
    assert [e['CAMPAIGN_ID'] for e in pub['EVENTS']] == ['LEGACY', 'GV0CAL', 'GV0R01', 'GV0R01C013MT1']
    assert pub['HEAD']['EVENT_TYPE'] == 'MARKET_TEST_RESULT'
    mem = pub['VIEWS']['MEMORY']
    assert len(mem['ENTRIES']) == 57 and len(pub['VIEWS']['ATTEMPTS']) == 35
    rec = mem['MARKET_TEST_RESULTS']['TF-GV0R01-C013-MT1']
    assert rec['CLASSIFICATION'] == 'PROMISING_PROTOTYPE' and rec['SIGNATURE_ID'] == 'GV0R01-C013'
    assert rec['RESULT_SHA256'] == hashlib.sha256((ROOT / rec['RESULT_PATH']).read_bytes()).hexdigest()
    old = store.published_at(ROOT, design, GV0R01_EVENT)['VIEWS']
    assert old['BLIND_MAP'] == pub['VIEWS']['BLIND_MAP'] and old['AUTHORITY'] == pub['VIEWS']['AUTHORITY']
    assert old['ATTEMPTS'] == pub['VIEWS']['ATTEMPTS'] and 'MARKET_TEST_RESULTS' not in old['MEMORY']
    c = Contexts()
    assert c.blind['GV0R01-C013']['REGION_STATE'] == 'PRIOR_WORK_SIGNATURE'
    gen = canonical(c.generator())
    for tok in ('PROMISING_PROTOTYPE', 'TF-GV0R01-C013-MT1', 'P_TWO_SIDED', 'MARKET_TEST_RESULTS', 'HAC_T'):
        assert tok not in gen and tok not in canonical(c.authority)
