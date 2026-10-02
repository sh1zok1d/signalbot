"""Pre-campaign hardening for GENERATOR_CONTRACT_V03. Mock providers only: no LLM calls, no market data.

1. memory_finalizer accepts V03 campaigns (RUNG_CONSISTENT, COMPLEXITY_CLASS, COMPONENTS) and only
   validates and copies them; V02 rules and digests are unchanged.
2. A budget stop before all 40 slots and mandatory reviews complete is INCOMPLETE_BUDGET_STOP: no
   official shortlist, partial journal kept, resume only of the same run with identical identity.
"""
import copy
import json

import pytest

from scripts.research.generator_v0 import memory_finalizer as fin
from scripts.research.generator_v0 import memory_store as store
from scripts.research.generator_v0 import runner
from scripts.research.generator_v0.context import ROOT, DESIGN, Contexts, ContractError, canonical, read
from scripts.research.generator_v0.derive import authorize_budget_extension
from scripts.research.generator_v0.ledger import BudgetExceeded, Ledger
from scripts.research.generator_v0.mock import MockResponder
from scripts.research.generator_v0.provider import Caller, MockProvider, Response
from scripts.research.generator_v0.runner import accept_budget_stop, ladder_config, run_campaign
from tests.research.test_generator_v0_memory_finalizer import fresh_root

V03 = 'GENERATOR_CONTRACT_V03'
CALL_COST = 1_000          # micro-USD per mock call


def ladder_run(path, responder=None, provider=None, cap=0, contexts=None):
    c = contexts or Contexts()
    ledger = Ledger(path, ladder_config(RUN_ID=path.parent.name, SIZE=40, CAP_MICRO_USD=cap))
    provider = provider or MockProvider(responder or MockResponder(c))
    return c, ledger, provider, Caller(c, ledger, provider, cap)


class RejectComplex(MockResponder):
    def __call__(self, request):
        out = super().__call__(request)
        if request['role'] == 'RED_TEAM' and request['context']['CANDIDATE']['COMPLEXITY_CLASS'] in ('INTERACTION', 'COMPOSITE'):
            payload = json.loads(out)
            payload['CHECKS']['RUNG_CONSISTENT'] = False
            return canonical(payload)
        return out


class PricedMock(MockProvider):
    """The deterministic mock with a fixed bound and cost per call, to exercise the budget gate."""
    def bound(self, request):
        return CALL_COST

    def complete(self, request):
        r = super().complete(request)
        return Response(r.raw, r.usage, CALL_COST)


# --------------------------------------------------------------------------- 1 finalizer
def test_v02_finalizer_rules_and_digest_are_unchanged():
    design = read(ROOT / DESIGN)
    head = store.chain(ROOT)[-1]
    assert fin.rules_digest(design) == head['RULES_DIGEST']          # the published chain's rules
    assert fin.rules_digest(design, V03) != head['RULES_DIGEST']
    assert 'RUNG_CONSISTENT' not in fin.RED_TEAM_CHECKS and 'COMPLEXITY_CLASS' not in fin.ATTEMPT_CARD_FIELDS
    assert fin.RED_TEAM_BLOCKER_RULES_V03[:len(fin.RED_TEAM_BLOCKER_RULES)] == fin.RED_TEAM_BLOCKER_RULES


def test_mock_v03_campaign_to_memory_finalizer_end_to_end(tmp_path):
    root = fresh_root(tmp_path)
    (tmp_path / 'run').mkdir()
    c, ledger, _, caller = ladder_run(tmp_path / 'run' / 'run.sqlite', contexts=Contexts(root))
    result = run_campaign(c, caller)
    ledger.close()
    source = fin.source_from_run_journal(tmp_path / 'run' / 'run.sqlite', 'GVLADDER')
    assert source['GENERATOR_CONTRACT'] == V03
    dry = fin.finalize(root, source)
    assert dry['STATUS'] == 'DRY_RUN' and dry['ATTEMPT_RECORDS'] == 40
    report = fin.finalize(root, source, apply=True)
    assert report['STATUS'] == 'FINALIZED'
    assert fin.verify(root)['STATUS'] == 'VERIFIED'
    head = store.chain(root)[-1]
    assert head['RULES_DIGEST'] == fin.rules_digest(read(root / DESIGN), V03)
    delta = store.load_delta(root, head['MEMORY_DELTA_SHA256'])
    assert delta['GENERATOR_CONTRACT'] == V03
    cards = {c['CANDIDATE_ID']: c for c in result['CANDIDATES']}
    reviews = {r['CANDIDATE_ID']: r for r in result['REVIEWS']}
    for a in delta['ATTEMPTS']:
        card = cards[a['CANDIDATE_ID']]
        # copied verbatim, never re-evaluated or rewritten
        assert a['CARD']['COMPLEXITY_CLASS'] == card['COMPLEXITY_CLASS']
        assert a['CARD']['COMPONENTS'] == card['COMPONENTS']
        assert a['CRITICS']['RED_TEAM']['VERDICT'] == reviews[a['CANDIDATE_ID']]['RED_TEAM']['VERDICT']
        assert a['STREAM'] == reviews[a['CANDIDATE_ID']]['STREAM']
    again = fin.finalize(root, source, apply=True)
    assert again['STATUS'] == 'ALREADY_FINALIZED'


def test_rung_inconsistency_maps_to_its_own_blocker(tmp_path):
    root = fresh_root(tmp_path)
    (tmp_path / 'run').mkdir()
    c = Contexts(root)
    _, ledger, _, caller = ladder_run(tmp_path / 'run' / 'run.sqlite', RejectComplex(c), contexts=c)
    result = run_campaign(c, caller)
    ledger.close()
    source = fin.source_from_run_journal(tmp_path / 'run' / 'run.sqlite', 'GVLADREJ')
    fin.finalize(root, source, apply=True)
    delta = store.load_delta(root, store.chain(root)[-1]['MEMORY_DELTA_SHA256'])
    complex_new = [a for a in delta['ATTEMPTS'] if a['CARD']['COMPLEXITY_CLASS'] in ('INTERACTION', 'COMPOSITE')
                   and a['DISPOSITION'].startswith('NEW_SIGNATURE')]
    assert complex_new
    for a in complex_new:
        assert 'RUNG_CONSISTENT' in a['CRITICS']['RED_TEAM']['FAILED_CHECKS']
        assert a['BLOCKERS'][0]['CLASS'] == 'METHOD_RUNG_INCONSISTENT'
    rows = {r['SIGNATURE_ID']: r for r in delta['ADD_ROWS']}
    assert rows[complex_new[0]['SIGNATURE_ID']]['BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY'].startswith(
        fin.BLOCKER_REQUIREMENTS_V03['METHOD_RUNG_INCONSISTENT'])
    assert all(r['SHORTLIST'] for r in [result]) and all(
        s['COMPLEXITY_CLASS'] in ('ATOMIC', 'CONDITIONAL') for s in result['SHORTLIST_RULE']['SEATS'])


def test_finalizer_validates_ladder_shape_and_refuses_mixing():
    f = {'VERDICT': 'PASS', 'DATA_STATUS': 'DATA_READY', 'CHECKS': {'LEGAL_RANGE': True}}
    v03_checks = {k: True for k in fin.RED_TEAM_CHECKS_V03}
    with pytest.raises(ContractError, match='RED_TEAM checks shape'):
        fin.blockers_for(f, {'VERDICT': 'PASS', 'CHECKS': v03_checks})          # V03 checks on a V02 card
    with pytest.raises(ContractError, match='RED_TEAM checks shape'):
        fin.blockers_for(f, {'VERDICT': 'PASS', 'CHECKS': {k: True for k in fin.RED_TEAM_CHECKS}}, ladder=True)
    assert fin.blockers_for(f, {'VERDICT': 'PASS', 'CHECKS': v03_checks}, ladder=True) == []
    with pytest.raises(ContractError, match='COMPONENTS'):
        fin._check_ladder_card({'CANDIDATE_ID': 'C001', 'COMPLEXITY_CLASS': 'INTERACTION', 'COMPONENTS': ['A']})
    with pytest.raises(ContractError, match='COMPLEXITY_CLASS'):
        fin._check_ladder_card({'CANDIDATE_ID': 'C001', 'COMPLEXITY_CLASS': 'SIMPLE', 'COMPONENTS': []})
    payload = {'STATUS': 'PENDING_HUMAN_REVIEW', 'CONTRACT': 'GENERATOR_CONTRACT_V02', 'REVIEWS': [],
               'CANDIDATES': [{'CANDIDATE_ID': 'C001', 'COMPLEXITY_CLASS': 'ATOMIC'}]}
    with pytest.raises(ContractError, match='ladder fields'):
        fin.source_from_campaign_payload(payload, 'GVMIX', {})


# --------------------------------------------------------------------------- 2-3 budget stop
def run_dir(tmp_path):
    d = tmp_path / 'ladder_run'
    d.mkdir()
    return d


def stopped_run(tmp_path, cap=2_500):
    d = run_dir(tmp_path)
    c, ledger, provider, caller = ladder_run(d / 'run.sqlite', provider=PricedMock(MockResponder(Contexts())), cap=cap)
    accept_budget_stop(c, caller, 40, 'owner', 'test: clean stop expected')
    with pytest.raises(BudgetExceeded):
        run_campaign(c, caller)
    return d, ledger, provider


def test_budget_stop_after_incomplete_rounds_has_no_shortlist(tmp_path):
    d, ledger, provider = stopped_run(tmp_path)
    assert ledger.get('status') == 'INCOMPLETE_BUDGET_STOP'
    assert provider.calls == 2                                              # rounds 0 and 1 only
    assert ledger.db.execute("SELECT payload FROM results WHERE key='campaign'").fetchone() is None
    ev = json.loads(ledger.db.execute("SELECT payload FROM events WHERE kind='CAMPAIGN_INCOMPLETE_BUDGET_STOP'").fetchone()[0])
    assert ev['COMPLETED_SHADOW_CAMPAIGN'] is False and ev['OFFICIAL_SHORTLIST'] is None
    assert ev['GENERATION_ROUNDS_COMPLETE'] == ['generation:0', 'generation:1']
    assert ev['CANDIDATES_RECORDED'] == 20 and ev['CRITIC_CALLS_COMPLETE'] == {}
    assert 'Only the same run may resume' in ev['RESOLUTION']
    assert len(ledger.candidates()) == 20                                   # partial cards kept
    ledger.close()
    with pytest.raises(ContractError, match='no completed campaign result'):
        fin.source_from_run_journal(d / 'run.sqlite', 'GVPARTIAL')       # never a finalizable campaign


def test_resume_is_refused_unless_the_run_identity_is_identical(tmp_path, monkeypatch):
    d, ledger, provider = stopped_run(tmp_path)
    ledger.close()
    with pytest.raises(ContractError, match='resume configuration differs'):
        Ledger(d / 'run.sqlite', ladder_config(RUN_ID='other', SIZE=40, CAP_MICRO_USD=2_500))
    authorize_budget_extension(d, 'owner', 'test extension', '1.00')
    ledger = Ledger(d / 'run.sqlite')
    c = Contexts()
    monkeypatch.setattr(runner, 'ladder_identity', lambda: {'CHANGED': True})
    with pytest.raises(ContractError, match='identity'):
        run_campaign(c, Caller(c, ledger, provider, 1_000_000))
    assert provider.calls == 2
    ledger.close()


def test_full_resume_reuses_obtained_cards_and_builds_the_shortlist_once(tmp_path):
    d, ledger, provider = stopped_run(tmp_path)
    before = {x['CANDIDATE_ID']: x for x in ledger.candidates()}
    ledger.close()
    authorize_budget_extension(d, 'owner', 'test extension', '1.00')
    ledger = Ledger(d / 'run.sqlite')
    c = Contexts()
    caller = Caller(c, ledger, provider, 1_000_000)
    result = run_campaign(c, caller)
    assert result['STATUS'] == 'PENDING_HUMAN_REVIEW' and ledger.get('status') == 'PENDING_HUMAN_REVIEW'
    assert provider.calls == 125                                             # rounds 0-1 were not POSTed again
    after = {x['CANDIDATE_ID']: x for x in ledger.candidates()}
    same = ('ROUND', 'CALL_KEY', 'CONTRACT', 'CARD', 'REASONS')               # obtained cards unchanged; only the
    assert all({k: after[i][k] for k in same} == {k: v[k] for k in same} for i, v in before.items())  # lifecycle moves
    assert {v['STATE'] for v in before.values()} == {'VALID'} and {after[i]['STATE'] for i in before} <= {'REVIEWED'}
    assert [s['SEAT'] for s in result['SHORTLIST_RULE']['SEATS']] == ['ATOMIC', 'ATOMIC', 'CONDITIONAL', 'CONDITIONAL', 'COMPLEX']
    assert run_campaign(c, caller) == result and provider.calls == 125      # built once
    ledger.close()


def test_v02_budget_stop_semantics_are_unchanged(tmp_path):
    c = Contexts()
    ledger = Ledger(tmp_path / 'v02.sqlite', {'RUN_ID': 'v02', 'SIZE': 40, 'CAP_MICRO_USD': 2_500})
    provider = PricedMock(MockResponder(c))
    caller = Caller(c, ledger, provider, 2_500)
    accept_budget_stop(c, caller, 40, 'owner', 'test')
    with pytest.raises(BudgetExceeded):
        run_campaign(c, caller)
    assert ledger.get('status') == 'STOPPED_BUDGET'
    ev = json.loads(ledger.db.execute("SELECT payload FROM events WHERE kind='CAMPAIGN_STOPPED_BUDGET'").fetchone()[0])
    assert set(ev) == {'REASON', 'RESOLUTION'}
    ledger.close()
