"""B5: remaining-campaign preflight on fresh, derived and nested-derived journals,
scenario support, and the live budget gate. Offline; no POST."""
import json
import shutil
import sqlite3
import pytest
from pathlib import Path
from scripts.research.generator_v0.context import Contexts,ContractError,canonical
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.roles import current_signatures
from scripts.research.generator_v0.derive import (fresh_campaign_budget_preflight,remaining_campaign_budget_preflight,derive_complete_rounds,
    authorize_derived_continuation,campaign_bound,OBSERVED_MAX_CARD_BYTES,OBSERVED_MAX_SIGNATURE_BYTES,OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD)

REPO=Path(__file__).resolve().parents[2]
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'
C=Contexts()
# first-shadow-v7 ran under the pre-GV0CAL memory; its derive is bound to that version.
V7C=Contexts(memory_event='LEGACY_BOOTSTRAP')

def test_proxy_constants_are_the_observed_v7_maxima():
    db=sqlite3.connect('file:{}?mode=ro&immutable=1'.format(V7.as_posix()),uri=True)
    try:cards=[x for (r,) in db.execute('SELECT response FROM calls') for x in json.loads(json.loads(r)['raw'])['CANDIDATES']]
    finally:db.close()
    assert len(cards)==40
    assert max(len(canonical(x).encode()) for x in cards)==OBSERVED_MAX_CARD_BYTES
    assert max(len(canonical(x).encode()) for x in current_signatures(cards))==OBSERVED_MAX_SIGNATURE_BYTES

def test_fresh_journal_preflight(tmp_path):
    l=Ledger(tmp_path/'run.sqlite',{'RUN_ID':'fresh','CAP_MICRO_USD':17_100_000,'SIZE':40});l.close()
    pre=remaining_campaign_budget_preflight(tmp_path,C)
    assert pre['SPENT_MICRO_USD']==0 and pre['PROXY_CARDS']==40
    assert pre['REMAINING_GENERATION_ROUNDS']==['generation:%d'%i for i in range(4)]
    assert pre['WORST_CASE_REMAINING_MICRO_USD']==sum(s['BOUND_MICRO_USD'] for s in pre['STAGES'])
    assert pre==fresh_campaign_budget_preflight(40,17_100_000,C)|{'IMPORTED_GENERATION_ROUNDS':[]}
    assert pre['FITS_AUTHORIZED_REMAINING'] is (pre['WORST_CASE_REMAINING_MICRO_USD']<=17_100_000)
    # Reads are side-effect free.
    assert sorted(p.name for p in tmp_path.iterdir())==['run.sqlite']

def test_derived_journal_preflight_counts_v7_lineage(tmp_path):
    src=tmp_path/'v7';src.mkdir();shutil.copy(V7,src/'run.sqlite')
    derive_complete_rounds(src,tmp_path/'v8',2,V7C)
    pre=remaining_campaign_budget_preflight(tmp_path/'v8',V7C)
    assert pre['SPENT_MICRO_USD']==4_946_750 and pre['LINEAGE_PRIOR_MICRO_USD']==1_167_200 and pre['JOURNAL_SPENT_MICRO_USD']==3_779_550
    assert pre['REMAINING_AUTHORIZED_MICRO_USD']==17_100_000-4_946_750==12_153_250
    assert pre['REMAINING_GENERATION_ROUNDS']==['generation:3'] and pre['PROXY_CARDS']==10
    assert pre['MIN_TOTAL_CAP_MICRO_USD']==4_946_750+pre['WORST_CASE_REMAINING_MICRO_USD']

def test_nested_derive_lineage_preflight(tmp_path):
    src=tmp_path/'v7';src.mkdir();shutil.copy(V7,src/'run.sqlite')
    derive_complete_rounds(src,tmp_path/'v8',2,V7C)
    first=remaining_campaign_budget_preflight(tmp_path/'v8',V7C)
    authorize_derived_continuation(tmp_path/'v8','op','nested derive test')
    derive_complete_rounds(tmp_path/'v8',tmp_path/'v8b',2,V7C)
    nested=remaining_campaign_budget_preflight(tmp_path/'v8b',V7C)
    assert nested['SPENT_MICRO_USD']==first['SPENT_MICRO_USD']==4_946_750
    assert nested['WORST_CASE_REMAINING_MICRO_USD']==first['WORST_CASE_REMAINING_MICRO_USD']
    l=Ledger.open_readonly(tmp_path/'v8b'/'run.sqlite')
    try:assert [s['RUN_ID'] for s in l.get('lineage')['SOURCES']]==['first-shadow-v7','v8']
    finally:l.close()

def test_bound_monotone_in_caps_attempts_and_size():
    base=campaign_bound(C,40)
    lower=campaign_bound(C,40,caps={'NOVELTY_CRITIC':6000,'RED_TEAM':8000,'FEASIBILITY_CRITIC':6000,'SELECTOR':2000})
    assert lower['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD']<base['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD']
    assert campaign_bound(C,40,content_attempts=1)['WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD']==base['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD']
    assert campaign_bound(C,25)['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD']<base['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD']

def test_budget_scenario_report_is_current():
    from scripts.research.generator_v0_gate.budget import build,REPORT
    assert json.loads(REPORT.read_text(encoding='utf-8'))==json.loads(json.dumps(build(C)))

def test_live_run_refuses_when_worst_case_does_not_fit(tmp_path,monkeypatch):
    from scripts.research.generator_v0.__main__ import main
    monkeypatch.setenv('OPENAI_API_KEY','offline-test-key')
    import scripts.research.generator_v0.openai_provider as op
    monkeypatch.setattr(op,'_default_transport',lambda *a,**k:pytest.fail('network'),raising=False)
    d=tmp_path/'live'
    with pytest.raises(ContractError,match='does not fit'):
        main(['run','--provider','openai','--allow-real-llm','--budget-usd','17.1','--run-dir',str(d)])
    assert not d.exists()
    with pytest.raises(ContractError,match='requires --actor and --reason'):
        main(['run','--provider','openai','--allow-real-llm','--budget-usd','17.1','--run-dir',str(d),'--accept-budget-stop'])
    assert not d.exists()
