"""Generator V0 memory finalizer V1. Offline: no provider, no market data, no protected data.

Every test works in a temporary repository root built from the frozen design, the
rotation file, the immutable LEGACY_BOOTSTRAP delta and (where needed) the calibration
export. The golden GV0CAL reconstruction runs the finalizer; it never copies the
published rows as the answer.
"""
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from scripts.research.generator_v0 import memory_finalizer as fin
from scripts.research.generator_v0 import memory_store as store
from scripts.research.generator_v0.context import ROOT, DESIGN, ROTATION, MEMORY, MAP, AUTHORITY, PINS, MEMORY_HEAD, Contexts, ContractError, project, read
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import MockResponder, fixture, slot_plan
from scripts.research.generator_v0.provider import Caller, MockProvider
from scripts.research.generator_v0.roles import Roles
from scripts.research.generator_v0.runner import run_campaign

EXPORT = 'docs/research/GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.json'
GV0CAL_IDS = ['GV0CAL-C001', 'GV0CAL-C002', 'GV0CAL-C003', 'GV0CAL-C004', 'GV0CAL-C005']
GOLDEN = {  # the manually ingested calibration memory (commit 64a37a9) is the golden reference
    'GV0CAL-C001': ('CONSUMED', None),
    'GV0CAL-C002': ('CONSUMED', None),
    'GV0CAL-C003': ('DEFERRED_OR_BLOCKED', 'METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING'),
    'GV0CAL-C004': ('DEFERRED_OR_BLOCKED', 'METHOD_CONFOUNDING_CONTROL_INADEQUATE'),
    'GV0CAL-C005': ('CONSUMED', None),
}
FAULT_POINTS = ('BEFORE_STAGING_VALIDATION', 'AFTER_STAGING_BEFORE_PUBLISH', 'BEFORE_HEAD_SWITCH')
GENERATOR_FORBIDDEN = ('PIPELINE_SURVIVOR', 'RED_TEAM', 'REJECT', 'SUPPORTED', 'NO_USEFUL_STRUCTURE', 'PROMISING_PROTOTYPE',
                       'STATUS_EVIDENCE_CLASS', 'MARKET_TESTS', 'PIPELINE_DISPOSITION', 'BLOCKER', 'CONSUMED', 'DEFERRED',
                       'METHOD_CAUSAL', 'METHOD_CONFOUNDING', 'p-value', 'p_value', 'effect size', 'EFFECT_SIZE')


class Crash(BaseException):
    """Simulated process death."""


def legacy_bootstrap_inputs():
    """Read LEGACY_BOOTSTRAP from the committed chain only (never Git)."""
    ev = store.chain(ROOT)[0]
    delta = store.load_delta(ROOT, ev['MEMORY_DELTA_SHA256'])
    return delta['LEGACY_MEMORY'], delta['LEGACY_GOVERNANCE_ROWS'], ev['SOURCE_ARTIFACT_IDENTITY']


def fresh_root(tmp_path, name='repo'):
    root = tmp_path / name
    for rel in (DESIGN, ROTATION, EXPORT):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, root / rel)
    memory, rows, provenance = legacy_bootstrap_inputs()
    fin.bootstrap(root, memory, rows, provenance)
    return root


def export_source(root, campaign='GV0CAL', path=None):
    return fin.source_from_calibration_export(path or root / EXPORT, campaign, read(root / DESIGN))


def finalized_root(tmp_path, name='repo'):
    root = fresh_root(tmp_path, name)
    fin.finalize(root, export_source(root), apply=True)
    return root


def authoritative_bytes(root):
    """HEAD, the chain reachable from it, mirrors and pins. Content-addressed files placed
    before the HEAD switch are unreachable orphans, never authority."""
    rels = [MEMORY_HEAD, MEMORY, MAP, AUTHORITY, PINS]
    out = {r: (root / r).read_bytes() for r in rels}
    out['CHAIN'] = [e['EVENT_HASH'] for e in store.chain(root)]
    return out


def store_files(root):
    base = root / store.STORE
    return {str(p.relative_to(base)): p.read_bytes() for p in sorted(base.rglob('*'))
            if p.is_file() and '.staging' not in p.parts and p.name != '.finalize.lock'}


# 1 golden reconstruction ------------------------------------------------------------------------

def test_golden_gv0cal_reconstruction_runs_the_finalizer(tmp_path):
    root = fresh_root(tmp_path)
    assert not any(k.startswith('GV0CAL') for k in Contexts(root).blind)       # starts from the legacy baseline
    report = fin.finalize(root, export_source(root), apply=True)
    assert report['STATUS'] == 'FINALIZED' and report['NEW_SIGNATURE_IDS'] == GV0CAL_IDS
    assert (report['ATTEMPT_RECORDS'], report['NEW_CANONICAL_SIGNATURES'], report['LINKS_TO_PRIOR_SIGNATURES']) == (5, 5, 0)
    c = Contexts(root)
    for sid, (state, blocker) in GOLDEN.items():
        assert c.rows[sid]['STATE'] == state and c.rows[sid]['BLOCKER_CLASS_IF_ANY'] == blocker, sid
        if state == 'DEFERRED_OR_BLOCKED':
            assert c.rows[sid]['BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY']
        blind = c.blind[sid]
        assert set(blind) == {'ID', 'MECHANISM', 'INFORMATION_SOURCE', 'FUNCTION', 'TARGET_FAMILY', 'REGION_STATE'}
        assert blind['REGION_STATE'] == 'PRIOR_WORK_SIGNATURE' and blind['ID'] == sid
    assert len(c.blind) == len(c.authority['ROWS']) == 35
    # The independent reconstruction yields exactly the published GV0CAL state.
    published = [e for e in store.chain(ROOT) if e['CAMPAIGN_ID'] == 'GV0CAL'][0]
    rebuilt = [e for e in store.chain(root) if e['CAMPAIGN_ID'] == 'GV0CAL'][0]
    for k in ('RESULTING_MEMORY_DIGEST', 'RESULTING_BLIND_MAP_DIGEST', 'RESULTING_AUTHORITY_DIGEST', 'RESULTING_ATTEMPTS_DIGEST',
              'SOURCE_SHA256', 'MEMORY_DELTA_SHA256'):
        assert rebuilt[k] == published[k], k


def test_published_repository_state_is_the_golden_state():
    c = Contexts()
    for sid, (state, blocker) in GOLDEN.items():
        assert (c.rows[sid]['STATE'], c.rows[sid]['BLOCKER_CLASS_IF_ANY']) == (state, blocker)
    assert [e['CAMPAIGN_ID'] for e in store.chain(ROOT)] == ['LEGACY', 'GV0CAL', 'GV0R01']
    assert fin.verify(ROOT)['STATUS'] == 'VERIFIED'


def test_red_team_blocker_mapping_is_deterministic():
    feas = {'VERDICT': 'PASS', 'DATA_STATUS': 'DATA_READY', 'CHECKS': {}}
    def cls(*failed):
        return fin.blockers_for(feas, {'VERDICT': 'REJECT', 'CHECKS': {k: k not in failed for k in fin.RED_TEAM_CHECKS}})[0]['CLASS']
    assert cls('CAUSALITY', 'CONFOUNDING_ADDRESSED') == 'METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING'   # C003
    assert cls('CONFOUNDING_ADDRESSED') == 'METHOD_CONFOUNDING_CONTROL_INADEQUATE'                        # C004
    assert cls('CAUSALITY') == 'METHOD_CAUSAL_IDENTIFICATION_INADEQUATE'
    assert cls('NO_LOOKAHEAD', 'CAUSALITY') == 'METHOD_LOOKAHEAD_VIOLATION'
    assert cls('FALSIFIABLE') == 'METHOD_FALSIFIER_INADEQUATE'
    assert cls('BOUNDED_SEARCH') == 'METHOD_UNBOUNDED_SEARCH_SURFACE'
    assert cls('NO_TRADING_CLAIM') == 'METHOD_TRADING_CLAIM_OUT_OF_SCOPE'
    for _need, name in fin.RED_TEAM_BLOCKER_RULES:
        assert name in fin.BLOCKER_REQUIREMENTS


# 2 stable IDs ----------------------------------------------------------------------------------------

def test_stable_ids_are_deterministic_and_validated(tmp_path):
    assert fin.stable_id('GV0CAL', 'C001') == 'GV0CAL-C001'
    for bad in (('gv0cal', 'C001'), ('GV', 'C001'), ('LEGACY', 'C001'), ('GV0CAL', 'C1'), ('GV0CAL', 'c001'), ('GV0-CAL', 'C001'), (None, 'C001')):
        with pytest.raises(ContractError):
            fin.stable_id(*bad)
    a, b = finalized_root(tmp_path, 'a'), finalized_root(tmp_path, 'b')
    assert store_files(a) == store_files(b)                                   # byte-identical independent runs
    ids = [x['ATTEMPT_ID'] for x in Contexts(a).verify()['ATTEMPTS']]
    assert ids == GV0CAL_IDS and len(set(ids)) == len(ids)


# 3-4 idempotency ---------------------------------------------------------------------------------------

def test_same_campaign_same_source_is_a_no_op(tmp_path):
    root = finalized_root(tmp_path)
    before = store_files(root), authoritative_bytes(root)
    again = fin.finalize(root, export_source(root), apply=True)
    assert again['STATUS'] == 'ALREADY_FINALIZED' and again['NEW_EVENT'] is False and again['DERIVED_CACHES_REPAIRED'] == []
    assert (store_files(root), authoritative_bytes(root)) == before


def test_same_campaign_different_source_hard_fails(tmp_path):
    root = finalized_root(tmp_path)
    doc = json.loads((root / EXPORT).read_text())
    doc['NOTE'] += ' (edited)'
    changed = tmp_path / 'changed_export.json'
    changed.write_text(json.dumps(doc, indent=2) + '\n')
    before = store_files(root)
    with pytest.raises(ContractError, match='different source'):
        fin.finalize(root, export_source(root, path=changed), apply=True)
    assert store_files(root) == before


# 5-6 crash safety ----------------------------------------------------------------------------------------

@pytest.mark.parametrize('point', FAULT_POINTS)
def test_crash_before_publish_leaves_authoritative_state_unchanged(tmp_path, point):
    root = fresh_root(tmp_path)
    before = authoritative_bytes(root)
    head_before = store.read_head(root)

    def fault(p):
        if p == point:
            raise Crash(p)
    with pytest.raises(Crash):
        fin.finalize(root, export_source(root), apply=True, fault=fault)
    assert authoritative_bytes(root) == before and store.read_head(root) == head_before
    c = Contexts(root)                                                        # runtime still serves the old head
    assert not any(k.startswith('GV0CAL') for k in c.blind)
    assert fin.verify(root)['STATUS'] == 'VERIFIED'
    # Restart: the same campaign finalizes exactly once.
    assert fin.finalize(root, export_source(root), apply=True)['STATUS'] == 'FINALIZED'
    assert fin.finalize(root, export_source(root), apply=True)['STATUS'] == 'ALREADY_FINALIZED'
    assert [e['CAMPAIGN_ID'] for e in store.chain(root)] == ['LEGACY', 'GV0CAL']
    assert all(k in Contexts(root).blind for k in GV0CAL_IDS)


def test_crash_after_head_switch_fails_closed_until_derived_caches_are_repaired(tmp_path):
    root = fresh_root(tmp_path)

    def fault(p):
        if p == 'AFTER_HEAD_BEFORE_DERIVED_CACHES':
            raise Crash(p)
    with pytest.raises(Crash):
        fin.finalize(root, export_source(root), apply=True, fault=fault)
    with pytest.raises(ContractError):
        Contexts(root)                                                        # stale mirrors/pins are never trusted
    assert fin.verify(root)['STATUS'] == 'CHAIN_VERIFIED_DERIVED_CACHE_DRIFT'
    repaired = fin.finalize(root, export_source(root), apply=True)
    assert repaired['STATUS'] == 'ALREADY_FINALIZED' and repaired['DERIVED_CACHES_REPAIRED']
    assert fin.verify(root)['STATUS'] == 'VERIFIED' and 'GV0CAL-C003' in Contexts(root).rows


def test_concurrent_finalization_is_refused(tmp_path):
    root = fresh_root(tmp_path)
    with store.exclusive_lock(root):
        with pytest.raises(ContractError, match='lock'):
            fin.finalize(root, export_source(root), apply=True)


# 7-9 chain integrity and rebuild ------------------------------------------------------------------------

def _rewrite(path, mutate):
    obj = json.loads(path.read_text())
    mutate(obj)
    path.write_bytes(store.pretty(obj))


def test_old_event_tamper_fails_verification(tmp_path):
    root = finalized_root(tmp_path)
    ev0 = next((root / store.STORE / 'events').glob('000000-*.json'))
    _rewrite(ev0, lambda o: o['SUMMARY'].update(MEMORY_ENTRY_COUNT=31))
    with pytest.raises(ContractError, match='hash'):
        fin.verify(root)
    with pytest.raises(ContractError):
        Contexts(root)


def test_re_hashed_old_event_breaks_the_next_link(tmp_path):
    root = finalized_root(tmp_path)
    ev0 = next((root / store.STORE / 'events').glob('000000-*.json'))
    obj = json.loads(ev0.read_text())
    obj['SUMMARY']['MEMORY_ENTRY_COUNT'] = 31
    obj['EVENT_HASH'] = store.event_hash(obj)
    ev0.unlink()
    store.event_path(root, 0, obj['EVENT_HASH']).write_bytes(store.pretty(obj))
    with pytest.raises(ContractError):
        fin.verify(root)


def test_old_delta_tamper_fails_verification(tmp_path):
    root = finalized_root(tmp_path)
    ev0 = store.chain(root)[0]
    path = store.delta_path(root, ev0['MEMORY_DELTA_SHA256'])
    _rewrite(path, lambda o: o['LEGACY_MEMORY']['ENTRIES']['D2'].update(STATUS_EVIDENCE_CLASS='SUPPORTED'))
    with pytest.raises(ContractError, match='delta digest'):
        fin.verify(root)


def test_rebuild_from_bootstrap_and_deltas_equals_published_state(tmp_path):
    root = finalized_root(tmp_path)
    rebuilt = fin.rebuild(root)
    head = store.chain(root)[-1]
    assert rebuilt['STATUS'] == 'REBUILT_EQUALS_PUBLISHED'
    assert rebuilt['DIGESTS'] == {k: head[k] for k in rebuilt['DIGESTS']}
    assert fin.rebuild(ROOT)['STATUS'] == 'REBUILT_EQUALS_PUBLISHED'


# 10 generator leak ------------------------------------------------------------------------------------------

def test_generator_context_carries_no_disposition_or_outcome(tmp_path):
    c = Contexts(finalized_root(tmp_path))
    g = c.generator()
    c.validate('GENERATOR', g)
    rows = json.dumps({k: g['BLIND_MECHANISM_MAP_V0'][k] for k in GV0CAL_IDS}, sort_keys=True)
    whole = json.dumps(g['BLIND_MECHANISM_MAP_V0'], sort_keys=True)
    for word in GENERATOR_FORBIDDEN:
        assert word.lower() not in rows.lower(), word
        assert word not in whole, word
    assert 'GOVERNANCE_REGION_AUTHORITY_V0' not in g and 'MECHANISM_MEMORY_V0_RAW' not in g
    # Survivors and methodology-blocked signatures are indistinguishable to GENERATOR.
    shapes = {json.dumps(sorted(g['BLIND_MECHANISM_MAP_V0'][k])) + g['BLIND_MECHANISM_MAP_V0'][k]['REGION_STATE'] for k in GV0CAL_IDS}
    assert len(shapes) == 1


def test_market_outcome_in_full_memory_cannot_change_the_blind_projection():
    design = read(ROOT / DESIGN)
    memory = copy.deepcopy(Contexts().verify()['MEMORY'])
    base = project(memory, design)
    for label in ('SUPPORTED', 'NULL', 'NO_USEFUL_STRUCTURE', 'PROMISING_PROTOTYPE'):
        m = copy.deepcopy(memory)
        m['ENTRIES']['GV0CAL-C001'].update(STATUS_EVIDENCE_CLASS=label, MARKET_TESTS=[{'RESULT': label, 'P_VALUE': 0.01}])
        assert project(m, design) == base, label


def test_scrub_removes_outcome_language_before_it_reaches_blind_memory():
    design = read(ROOT / DESIGN)
    text = fin.scrub('Positive drift replicated in 2023 (p-value 0.03); BLOCKED earlier, PASS.', design)
    assert fin.OMITTED in text
    assert not re.search(design['BLIND_GENERATOR_CONTEXT']['CONTEXT_SCANNER']['DENYLIST_REGEX'], text, re.I)
    for pat, flags in fin.SCRUB_PATTERNS:
        assert not re.search(pat, text, flags)
    assert fin.scrub('Listing-age lifecycle drift in the Binance spot USDT cross-section', design) == \
        'Listing-age lifecycle drift in the Binance spot USDT cross-section'


# 11 novelty memory ---------------------------------------------------------------------------------------------

def _novelty_raw(c, card, target, relation):
    leaves = [k for k, r in c.rows.items() if r['STATE'] != 'PARTIAL_OR_MIXED']
    return {'PRIOR_RELATIONS': [{'SIGNATURE_ID': k, 'RELATION': relation if k == target else 'ORTHOGONAL_MECHANISM'} for k in leaves],
            'BATCH_RELATIONS': [], 'JUDGMENTS': {'NOVELTY': 2, 'MECHANISM_DISTANCE': 2, 'NON_RESCUE': 2}}


def test_novelty_critic_sees_the_durable_calibration_signatures():
    c = Contexts()
    card = fixture(slot_plan(40)[20], c)
    ctx = Roles(c, None).request('NOVELTY_CRITIC', card, [card])
    ids = {r['SIGNATURE_ID'] for r in ctx['GOVERNANCE_REGION_AUTHORITY_V0']['ROWS']}
    assert set(GV0CAL_IDS) <= ids and set(GV0CAL_IDS) <= set(ctx['BLIND_MECHANISM_MAP_V0'])
    from scripts.research.generator_v0.output_schemas import role_schema
    keys = role_schema('NOVELTY_CRITIC', c, provider=True, request={'context': ctx})['properties']['PRIOR_RELATIONS']['required']
    assert set(GV0CAL_IDS) <= set(keys)
    roles = Roles(c, None)
    expected = {
        'GV0CAL-C001': {'EXACT_DUPLICATE': 'REJECT', 'PARAMETER_NEIGHBOR': 'REJECT', 'FUNCTIONAL_RELABEL': 'REJECT',
                        'RESOLVES_BLOCKER': 'HUMAN_REVIEW', 'ORTHOGONAL_MECHANISM': 'ALLOW'},
        'GV0CAL-C003': {'EXACT_DUPLICATE': 'DEFER_BLOCKER_UNRESOLVED', 'PARAMETER_NEIGHBOR': 'REJECT',
                        'FUNCTIONAL_RELABEL': 'DEFER_BLOCKER_UNRESOLVED', 'RESOLVES_BLOCKER': 'ALLOW_TO_FEASIBILITY',
                        'ORTHOGONAL_MECHANISM': 'ALLOW'},
    }
    for sid, table in expected.items():
        for relation, verdict in table.items():
            assert roles._novelty(card, [card], _novelty_raw(c, card, sid, relation))['VERDICT'] == verdict, (sid, relation)


def test_feasibility_critic_sees_calibration_blocker_requirements():
    c = Contexts()
    ctx = Roles(c, None).request('FEASIBILITY_CRITIC', fixture(slot_plan(40)[20], c))
    blockers = {b['SIGNATURE_ID']: b['BLOCKER_CLASS_IF_ANY'] for b in ctx['BLOCKER_REQUIREMENTS']}
    assert blockers['GV0CAL-C003'] == 'METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING'
    assert blockers['GV0CAL-C004'] == 'METHOD_CONFOUNDING_CONTROL_INADEQUATE'


# 12-15 dispositions on a synthetic completed campaign ---------------------------------------------------------

def _review(c, card, relations=None, batch=None, feas=None, red=None, verdict='ALLOW', stream=None):
    leaves = [k for k, r in c.rows.items() if r['STATE'] != 'PARTIAL_OR_MIXED']
    rel = relations or {}
    f = feas or {'VERDICT': 'PASS', 'DATA_STATUS': 'DATA_READY', 'CHECKS': {k: True for k in ('OBSERVABLE_SUPPORTED', 'LEGAL_RANGE', 'POINT_IN_TIME', 'PROVENANCE', 'BLOCKER_RESOLVED')}}
    r = red or {'VERDICT': 'PASS', 'CHECKS': {k: True for k in fin.RED_TEAM_CHECKS}}
    novelty = {'VERDICT': verdict, 'JUDGMENTS': {}, 'PRIOR_RELATIONS': [{'SIGNATURE_ID': k, 'RELATION': rel.get(k, 'ORTHOGONAL_MECHANISM')} for k in leaves],
               'BATCH_RELATIONS': batch or []}
    return {'CANDIDATE_ID': card['CANDIDATE_ID'], 'STATE': 'REVIEWED', 'NOVELTY': novelty, 'FEASIBILITY': f, 'RED_TEAM': r,
            'STREAM': stream or fin._route(verdict, f, r)}


def _card(c, i, **over):
    card = fixture(slot_plan(40)[i], c)
    card.update(over)
    return card


def _payload(cards, reviews, hard_fails=()):
    return {'STATUS': 'PENDING_HUMAN_REVIEW', 'CANDIDATES': cards, 'REVIEWS': reviews, 'HARD_FAILS': list(hard_fails)}


def test_dispositions_link_duplicates_and_retain_distinct_blocked_regions(tmp_path):
    root = finalized_root(tmp_path)
    c = Contexts(root)
    cards = [_card(c, i) for i in range(12, 18)]
    ids = [x['CANDIDATE_ID'] for x in cards]
    others = lambda cid, rel=None: [{'CANDIDATE_ID': o, 'RELATION': (rel or {}).get(o, 'ORTHOGONAL_MECHANISM')} for o in ids if o != cid]
    blocked = {'VERDICT': 'PASS', 'DATA_STATUS': 'DATA_BLOCKED_PROVENANCE', 'CHECKS': {'OBSERVABLE_SUPPORTED': False, 'LEGAL_RANGE': True, 'POINT_IN_TIME': False, 'PROVENANCE': False, 'BLOCKER_RESOLVED': True}}
    cards[4]['DATA_STATUS'] = 'DATA_BLOCKED_PROVENANCE'
    reviews = [
        _review(c, cards[0], relations={'GV0CAL-C001': 'PARAMETER_NEIGHBOR'}, batch=others(ids[0]), verdict='REJECT'),      # neighbor of a prior
        _review(c, cards[1], batch=others(ids[1])),                                                                          # distinct survivor
        _review(c, cards[2], batch=others(ids[2], {ids[1]: 'EXACT_DUPLICATE'}), verdict='REJECT', stream='NOT_A_STREAM'),   # batch duplicate of [1]
        _review(c, cards[3], batch=others(ids[3]), red={'VERDICT': 'REJECT', 'CHECKS': {k: k != 'NO_LOOKAHEAD' for k in fin.RED_TEAM_CHECKS}}),
        _review(c, cards[4], batch=others(ids[4]), feas=blocked),                                                            # data blocked
        _review(c, cards[5], relations={'GV0CAL-C003': 'RESOLVES_BLOCKER'}, batch=others(ids[5]), verdict='ALLOW_TO_FEASIBILITY'),
    ]
    source = fin.source_from_campaign_payload(_payload(cards, reviews, [{'CANDIDATE_ID': 'C019', 'ROUND': 'generation:1', 'REASONS': [{'RULE': 'PROVIDER_SCHEMA'}]}]),
                                              'GV0SYN', {'KIND': 'SYNTHETIC_TEST_PAYLOAD'})
    report = fin.finalize(root, source, apply=True)
    assert report['ATTEMPT_RECORDS'] == 6 and report['NEW_CANONICAL_SIGNATURES'] == 3
    assert report['LINKS_TO_PRIOR_SIGNATURES'] == 2 and report['LINKS_TO_BATCH_ATTEMPTS'] == 1 and report['INVALID_OUTPUTS'] == 1
    v = Contexts(root).verify()
    attempts = {a['ATTEMPT_ID']: a for a in v['ATTEMPTS']}
    a = lambda i: attempts['GV0SYN-' + ids[i]]
    # 12: duplicate / neighbor links, no redundant blind region.
    assert a(0)['DISPOSITION'] == 'LINKED_PRIOR_DUPLICATE_OR_NEIGHBOR' and a(0)['SIGNATURE_ID'] is None
    assert a(0)['PRIOR_LINKS'] == [{'SIGNATURE_ID': 'GV0CAL-C001', 'RELATION': 'PARAMETER_NEIGHBOR', 'BASIS': 'NOVELTY_CRITIC'}]
    assert a(2)['DISPOSITION'] == 'LINKED_BATCH_DUPLICATE_OR_NEIGHBOR' and a(2)['BATCH_LINKS'][0]['CANONICAL_SIGNATURE_ID'] == 'GV0SYN-' + ids[1]
    assert a(5)['DISPOSITION'] == 'LINKED_PRIOR_BLOCKER_RESOLUTION_PROPOSAL' and a(5)['SIGNATURE_ID'] is None
    for i in (0, 2, 5):
        assert 'GV0SYN-' + ids[i] not in v['BLIND_MAP'] and 'GV0SYN-' + ids[i] not in v['MEMORY']['ENTRIES']
    # 13: a distinct RED_TEAM rejection stays as a blocked prior region.
    rows = store.rows_by_id(v['AUTHORITY']['ROWS'])
    assert rows['GV0SYN-' + ids[3]]['STATE'] == 'DEFERRED_OR_BLOCKED'
    assert rows['GV0SYN-' + ids[3]]['BLOCKER_CLASS_IF_ANY'] == 'METHOD_LOOKAHEAD_VIOLATION'
    # 14: a distinct data-blocked candidate is retained.
    assert rows['GV0SYN-' + ids[4]]['STATE'] == 'DEFERRED_OR_BLOCKED' and rows['GV0SYN-' + ids[4]]['BLOCKER_CLASS_IF_ANY'] == 'DATA_BLOCKED_PROVENANCE'
    assert rows['GV0SYN-' + ids[1]]['STATE'] == 'CONSUMED'
    # 15: an invalid generator output stays provenance only.
    delta = store.load_delta(root, store.chain(root)[-1]['MEMORY_DELTA_SHA256'])
    assert delta['INVALID_OUTPUTS'] == [{'CANDIDATE_ID': 'C019', 'ROUND': 'generation:1', 'RULES': ['PROVIDER_SCHEMA']}]
    assert 'GV0SYN-C019' not in attempts and 'GV0SYN-C019' not in v['BLIND_MAP']
    # Prior states are never rewritten by later campaigns.
    assert rows['GV0CAL-C003']['STATE'] == 'DEFERRED_OR_BLOCKED' and rows['GV0CAL-C001']['STATE'] == 'CONSUMED'


def test_review_failed_candidate_is_recorded_without_a_signature(tmp_path):
    root = finalized_root(tmp_path)
    c = Contexts(root)
    cards = [_card(c, 20), _card(c, 21)]
    reviews = [_review(c, cards[0], batch=[{'CANDIDATE_ID': cards[1]['CANDIDATE_ID'], 'RELATION': 'ORTHOGONAL_MECHANISM'}]),
               {'CANDIDATE_ID': cards[1]['CANDIDATE_ID'], 'STATE': 'REVIEW_FAILED', 'REASONS': [], 'STREAM': 'NOT_A_STREAM'}]
    fin.finalize(root, fin.source_from_campaign_payload(_payload(cards, reviews), 'GV0RVF', {'KIND': 'SYNTHETIC'}), apply=True)
    v = Contexts(root).verify()
    rec = [x for x in v['ATTEMPTS'] if x['ATTEMPT_ID'] == 'GV0RVF-' + cards[1]['CANDIDATE_ID']][0]
    assert rec['DISPOSITION'] == 'REVIEW_INCOMPLETE_NO_SIGNATURE' and rec['ATTEMPT_ID'] not in v['BLIND_MAP']


@pytest.mark.parametrize('mutate', [
    lambda rv: rv['NOVELTY'].update(VERDICT='REJECT'),                                           # verdict without a relation
    lambda rv: rv.update(STREAM='HIGH_VALUE_DATA_BLOCKED'),                                        # stream inconsistent with critics
    lambda rv: rv['NOVELTY']['PRIOR_RELATIONS'].append({'SIGNATURE_ID': 'NOPE', 'RELATION': 'EXACT_DUPLICATE'}),
])
def test_inconsistent_campaign_records_fail_closed(tmp_path, mutate):
    root = finalized_root(tmp_path)
    c = Contexts(root)
    card = _card(c, 22)
    rv = _review(c, card)
    mutate(rv)
    before = store_files(root)
    with pytest.raises(ContractError):
        fin.finalize(root, fin.source_from_campaign_payload(_payload([card], [rv]), 'GV0BAD', {'KIND': 'SYNTHETIC'}), apply=True)
    assert store_files(root) == before


# 16-18 design untouched, runtime acceptance, stale snapshots ----------------------------------------------------

def test_dynamic_memory_update_does_not_modify_the_frozen_design(tmp_path):
    root = fresh_root(tmp_path)
    design_before = (root / DESIGN).read_bytes()
    fin.finalize(root, export_source(root), apply=True)
    assert (root / DESIGN).read_bytes() == design_before
    design = json.loads(design_before)
    assert 'ROWS' not in design['GOVERNANCE_REGION_AUTHORITY_V0']                 # rows are memory, not design
    assert (ROOT / DESIGN).read_bytes() == design_before


def test_runtime_contexts_accept_the_published_dynamic_authority(tmp_path):
    root = finalized_root(tmp_path)
    c = Contexts(root)
    c.validate('GENERATOR', c.generator())
    header = {k: v for k, v in c.design['GOVERNANCE_REGION_AUTHORITY_V0'].items() if k != 'ROWS_SOURCE'}
    assert {k: v for k, v in c.authority.items() if k != 'ROWS'} == header
    assert c.memory_head == store.read_head(root)['HEAD_EVENT_HASH']
    legacy = Contexts(root, memory_event='LEGACY_BOOTSTRAP')
    assert len(legacy.blind) == 30 and not set(GV0CAL_IDS) & set(legacy.blind)


def test_a_context_refuses_a_head_published_after_it_was_built(tmp_path):
    root = fresh_root(tmp_path)
    c = Contexts(root)
    fin.finalize(root, export_source(root), apply=True)
    with pytest.raises(ContractError, match='memory head changed'):
        c.generator()


@pytest.mark.parametrize('damage', ['mirror', 'pins', 'head_snapshot', 'orphan_snapshot', 'head_to_missing_snapshot'])
def test_stale_or_partial_derived_state_is_not_authoritative(tmp_path, damage):
    root = finalized_root(tmp_path)
    head = store.read_head(root)
    sdir = store.snapshot_dir(root, head['SEQUENCE'], head['HEAD_EVENT_HASH'])
    if damage == 'mirror':
        _rewrite(root / MAP, lambda o: o['GV0CAL-C001'].update(FUNCTION='edited'))
    elif damage == 'pins':
        _rewrite(root / PINS, lambda o: o.update({MAP: '0' * 64}))
    elif damage == 'head_snapshot':
        _rewrite(sdir / store.SNAPSHOT_FILES['AUTHORITY'], lambda o: o['ROWS'][-2].update(STATE='CONSUMED', BLOCKER_CLASS_IF_ANY=None))
    elif damage == 'orphan_snapshot':
        # A fully written next snapshot/event that was never published by the HEAD switch.
        orphan = store.snapshot_dir(root, head['SEQUENCE'] + 1, 'f' * 64)
        shutil.copytree(sdir, orphan)
        c = Contexts(root)
        assert c.memory_head == head['HEAD_EVENT_HASH'] and fin.verify(root)['STATUS'] == 'VERIFIED'
        return
    elif damage == 'head_to_missing_snapshot':
        shutil.rmtree(sdir)
    with pytest.raises(ContractError):
        Contexts(root)


def test_reserved_market_test_result_event_is_not_implemented():
    with pytest.raises(ContractError, match='reserved'):
        store.apply_delta({'MEMORY': {'ENTRIES': {}, 'COVERAGE': {}}, 'ROWS': [], 'ATTEMPTS': []}, {'KIND': 'MARKET_TEST_RESULT'})


# Future 30-card behaviour: a completed zero-cost mock campaign through the real runner ---------------------------

def test_mock_30_card_campaign_finalizes_every_valid_attempt(tmp_path):
    root = finalized_root(tmp_path)
    c = Contexts(root)
    journal = tmp_path / 'run.sqlite'
    ledger = Ledger(journal, {'RUN_ID': 'mock-30'})
    result = run_campaign(c, Caller(c, ledger, MockProvider(MockResponder(c))), size=30)
    ledger.close()
    assert result['STATUS'] == 'PENDING_HUMAN_REVIEW'
    dry = fin.finalize(root, fin.source_from_run_journal(journal, 'GV0MOCK'))
    before = store_files(root)
    assert dry['STATUS'] == 'DRY_RUN' and store_files(root) == before
    report = fin.finalize(root, fin.source_from_run_journal(journal, 'GV0MOCK'), apply=True)
    assert report['ATTEMPT_RECORDS'] == len(result['CANDIDATES'])
    assert report['NEW_CANONICAL_SIGNATURES'] + report['LINKS_TO_PRIOR_SIGNATURES'] + report['LINKS_TO_BATCH_ATTEMPTS'] + report['REVIEW_INCOMPLETE'] == report['ATTEMPT_RECORDS']
    assert report['LINKS_TO_PRIOR_SIGNATURES'] >= 3              # mock D4 / D2 / B2-06 duplicates and neighbors link
    assert report['INVALID_OUTPUTS'] == len(result['HARD_FAILS'])
    after = Contexts(root)
    after.validate('GENERATOR', after.generator())
    assert len(after.blind) == 35 + report['NEW_CANONICAL_SIGNATURES']
    v = after.verify()
    dispositions = {a['DISPOSITION'] for a in v['ATTEMPTS'] if a['CAMPAIGN_ID'] == 'GV0MOCK'}
    assert {'LINKED_PRIOR_DUPLICATE_OR_NEIGHBOR', 'NEW_SIGNATURE_CONSUMED', 'NEW_SIGNATURE_DEFERRED_OR_BLOCKED'} <= dispositions
    assert (root / DESIGN).read_bytes() == (ROOT / DESIGN).read_bytes()
    assert fin.finalize(root, fin.source_from_run_journal(journal, 'GV0MOCK'), apply=True)['STATUS'] == 'ALREADY_FINALIZED'
    assert fin.rebuild(root)['STATUS'] == 'REBUILT_EQUALS_PUBLISHED'
