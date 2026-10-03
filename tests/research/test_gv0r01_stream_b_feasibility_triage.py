"""GV0R01 Stream-B feasibility triage record. Offline: reads the sealed journal read-only
and committed records only. No market data, no outcomes."""
import hashlib
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRIAGE = REPO / 'docs/research/GV0R01_STREAM_B_FEASIBILITY_TRIAGE.json'
JOURNAL = REPO / 'docs/research/generator_v0_gv0r01/run.sqlite'
CLASSES = {'READY_WITH_EXISTING_DATA', 'READY_AFTER_FREE_PUBLIC_ACQUISITION', 'READY_AFTER_SMALL_PAID_ACQUISITION',
           'BLOCKED_EXPENSIVE_DATA', 'BLOCKED_POINT_IN_TIME_SEMANTICS', 'BLOCKED_MISSING_OBSERVABLE', 'BLOCKED_OTHER'}
SURFACES = {'GOOD_FRESH_SURFACE_AVAILABLE', 'FRESH_SURFACE_AVAILABLE_BUT_LIMITED', 'NO_CURRENT_INDEPENDENT_SURFACE', 'UNKNOWN'}


def _load():
    return json.loads(TRIAGE.read_text())


def test_triage_covers_exactly_the_sealed_stream_b_and_copies_exact_cards():
    t = _load()
    db = sqlite3.connect(f'file:{JOURNAL.resolve()}?mode=ro&immutable=1', uri=True)
    try:
        res = json.loads(db.execute("select payload from results where key='campaign'").fetchone()[0])
        assert t['STREAM_B'] == res['STREAM_B'] == sorted(t['CANDIDATES'])
        for cid in t['STREAM_B']:
            card = json.loads(db.execute('select card from candidates where id=?', (cid,)).fetchone()[0])
            copied = t['CANDIDATES'][cid]['CARD']
            assert all(copied[k] == card[k] for k in copied), cid
    finally:
        db.close()
    assert t['SOURCE']['SEALED_JOURNAL_SHA256'] == hashlib.sha256(JOURNAL.read_bytes()).hexdigest()


def test_every_candidate_has_a_deterministic_classification():
    t = _load()
    for cid, c in t['CANDIDATES'].items():
        tri = c['TRIAGE']
        assert tri['FEASIBILITY'] in CLASSES and tri['CONFIRMATION_SURFACE_STATUS'] in SURFACES
        assert tri['READY_TO_DESIGN'] is tri['FEASIBILITY'].startswith('READY_'), cid
    assert {r['ID'] for r in t['MATRIX']} == set(t['STREAM_B'])


def test_selection_is_one_ready_candidate_and_gv0r02_not_next():
    t = _load()
    ready = {cid for cid, c in t['CANDIDATES'].items() if c['TRIAGE']['READY_TO_DESIGN']}
    assert t['NEXT_CANDIDATE_FOR_DESIGN'].split('-')[-1] in ready
    assert t['RUN_GV0R02_NEXT'] is (not ready)
    assert set(t['FORBIDDEN_PRIORITY_DIMENSIONS']) >= {'expected profitability', 'any market outcome'}


def test_boundary_flags_and_untouched_authorities():
    t = _load()
    for flag in ('PROTECTED_2025_VALUES_OPENED', 'PROTECTED_2026_VALUES_OPENED', 'MARKET_OUTCOMES_COMPUTED',
                 'SCIENTIFIC_TEST_LEDGER_CHANGED', 'GENERATOR_V0_MEMORY_CHANGED', 'C013_CHANGED'):
        assert t[flag] is False, flag
    assert t['LLM_API_CALLS'] == 0 and t['METADATA_ACCESS_LOG']['PAYLOAD_GETS'] == 0
    assert t['PROGRAM_DECISION']['C013_PROGRAM_STATE'] == ['PROMISING_PROTOTYPE', 'CONFIRMATION_DEFERRED_LOW_POWER']
    ledger = json.loads((REPO / 'docs/research/SCIENTIFIC_TEST_LEDGER.json').read_text())
    gv0r01 = [x for x in ledger['TESTS'] if x['SEARCH_FAMILY_ID'] == 'SF-GENERATOR_V0-GV0R01']
    assert [x['TEST_FAMILY_ID'] for x in gv0r01] == ['TF-GV0R01-C013-MT1']
    assert ledger['SEARCH_FAMILIES'][0]['EXECUTED_TESTS'] == 1


def test_routing_docs_point_at_the_next_unit():
    unit = _load()['NEXT_UNIT']
    for rel in ('docs/CURRENT_RESEARCH_STATE.md', 'docs/RESEARCH_LEDGER.md', 'docs/DOCUMENTATION_INDEX.md'):
        assert unit in (REPO / rel).read_text(encoding='utf-8'), rel
