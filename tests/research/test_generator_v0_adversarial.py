"""Adversarial infrastructure tests. All transport is fake; no dataset payloads."""
import copy
import json
import socket
import sqlite3
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError,canonical
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.provider import Caller,MockProvider
from scripts.research.generator_v0.mock import MockResponder,fixture,slot_plan
from scripts.research.generator_v0.roles import Roles
from scripts.research.generator_v0.runner import run_campaign

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('Unexpected network connection'))

def setup(tmp_path,responder=None):
    c=Contexts();l=Ledger(tmp_path/'ledger.db',{'RUN_ID':'attack'});p=MockProvider(responder or MockResponder(c));return c,l,p,Caller(c,l,p)

@pytest.mark.parametrize('payload',[
 {'STATUS_EVIDENCE_CLASS':'PROMISING_PROTOTYPE'},
 {'RESULT_ARTIFACTS':{'MC_P':0.0002}},
 {'GOVERNANCE_REGION_AUTHORITY_V0':{'STATE':'CONSUMED'}},
 {'MECHANISM_MEMORY_V0_RAW':{'secret':'state'}},
])
def test_nested_generator_source_injection(tmp_path,payload):
    c,l,p,caller=setup(tmp_path);ctx=c.generator();ctx['GENERIC_METHODOLOGY'].update(payload)
    with pytest.raises(ContractError):caller.call('GENERATOR',ctx,'JSON',{},'attack')
    assert p.calls==0 and l.db.execute('SELECT count(*) FROM calls').fetchone()[0]==0

def test_mutating_returned_context_does_not_poison_trust(tmp_path):
    c,l,p,caller=setup(tmp_path);ctx=c.generator();ctx['BLIND_MECHANISM_MAP_V0']['D6']['FUNCTION']='blocked'
    with pytest.raises(ContractError):caller.call('GENERATOR',ctx,'JSON',{},'attack')
    c.validate('GENERATOR',c.generator())

def selector_context(c):
    row=dict(CANDIDATE_ID='C006',NOVELTY_VERDICT='ALLOW',MECHANISM_DISTANCE_JUDGMENT=2,FEASIBILITY_VERDICT='PASS',DATA_STATUS='DATA_READY',DATA_GAP_CLASS='NONE',RED_TEAM_VERDICT='PASS',HARD_FAILS=[],INFORMATION_GAIN_JUDGMENT=2,COST_JUDGMENT=2)
    return {'SANITIZED_CRITIC_OUTPUTS':[row],'DATA_STATUS':{'C006':'DATA_READY'},'SELECTION_JUDGMENTS':{'C006':dict(MECHANISM_DISTANCE=2,INFORMATION_GAIN=2,FEASIBILITY=2,CHEAPNESS=2)}}

@pytest.mark.parametrize('field,value',[('PRIOR_ID','D2'),('STATE','CONSUMED'),('RATIONALE','D2 was promising'),('DATA_GAP_CLASS','D2_PROMISING_PROTOTYPE'),('MECHANISM_DISTANCE_JUDGMENT','prior null'),('HARD_FAILS',['historical result'])])
def test_selector_rejects_unsanitized_nested_state(tmp_path,field,value):
    c,l,p,caller=setup(tmp_path);ctx=selector_context(c);ctx['SANITIZED_CRITIC_OUTPUTS'][0][field]=value
    with pytest.raises(ContractError):caller.call('SELECTOR',ctx,'JSON',{},'attack')
    assert p.calls==0

def test_unconfirmed_blocker_resolution_never_enters_stream_b(tmp_path):
    c,l,p,caller=setup(tmp_path);r=Roles(c,caller)
    assert r.route({'VERDICT':'ALLOW_TO_FEASIBILITY'},{'VERDICT':'PASS','DATA_STATUS':'DATA_BLOCKED_PROVENANCE','CHECKS':{'BLOCKER_RESOLVED':False}},{'VERDICT':'PASS'})=='NOT_A_STREAM'
    assert r.route({'VERDICT':'ALLOW'},{'VERDICT':'PASS','DATA_STATUS':'DATA_BLOCKED_PROVENANCE','CHECKS':{'BLOCKER_RESOLVED':False}},{'VERDICT':'PASS'})=='HIGH_VALUE_DATA_BLOCKED'

def test_asymmetric_batch_duplicate_is_not_counted_twice(tmp_path):
    c=Contexts();base=MockResponder(c)
    def answer(req):
        x=json.loads(base(req))
        if req['role']=='NOVELTY_CRITIC' and req['context']['CANDIDATE']['CANDIDATE_ID']=='C006':
            x['BATCH_RELATIONS']['C014']='FUNCTIONAL_RELABEL'
        return canonical(x)
    c,l,p,caller=setup(tmp_path,answer);result=run_campaign(c,caller)
    assert 'C014' not in result['STREAM_B']
    assert next(r for r in result['REVIEWS'] if r['CANDIDATE_ID']=='C014')['NOVELTY']['VERDICT']=='REJECT'

def test_registry_failure_rolls_back_and_reuses_all_provider_results(tmp_path,monkeypatch):
    c,l,p,caller=setup(tmp_path);original=l.save_card;counter=[0]
    def fail(card,decision=None):
        original(card,decision);counter[0]+=1
        if counter[0]==3:raise sqlite3.OperationalError('simulated partial write failure')
    monkeypatch.setattr(l,'save_card',fail)
    with pytest.raises(sqlite3.OperationalError):run_campaign(c,caller)
    assert l.db.execute('SELECT count(*) FROM cards').fetchone()[0]==0
    assert l.db.execute('SELECT count(*) FROM results').fetchone()[0]==0
    calls=p.calls;monkeypatch.setattr(l,'save_card',original)
    result=run_campaign(c,caller)
    assert p.calls==calls==125 and result['STATUS']=='PENDING_HUMAN_REVIEW'

def test_duplicate_generation_quarantines_slots_before_critics(tmp_path):
    c=Contexts();base=MockResponder(c);seen=[]
    def answer(req):
        x=json.loads(base(req));seen.append((req['role'],req['slot']))
        # Keyed output cannot carry a duplicate ID; the closest fault is C001's card under key C002.
        if req['role']=='GENERATOR' and req['slot']=='generation:0':x['CANDIDATES']['C002']=copy.deepcopy(x['CANDIDATES']['C001'])
        return canonical(x)
    c,l,p,caller=setup(tmp_path,answer)
    result=run_campaign(c,caller)
    assert result['STATUS']=='PENDING_HUMAN_REVIEW'
    hard={h['CANDIDATE_ID']:h['REASONS'] for h in result['HARD_FAILS']}
    assert set(hard)=={'C002'}
    assert hard['C002'][0]['RULE']=='PROVIDER_SCHEMA'
    assert not any(slot.endswith(':C002') for role,slot in seen if role!='GENERATOR')
    assert result['METRICS']['VALID']==39 and result['METRICS']['HARD_FAIL']==1

@pytest.mark.parametrize('size',[25,50])
def test_frozen_batch_bounds_run(tmp_path,size):
    c,l,p,caller=setup(tmp_path);r=run_campaign(c,caller,size)
    assert len(r['CANDIDATES'])==size and len(r['SHORTLIST'])<=5

def test_no_dataset_reads_in_full_mock(tmp_path,monkeypatch):
    from pathlib import Path
    original=Path.open
    def guarded(path,*args,**kwargs):
        if 'research_data' in path.parts:pytest.fail('Dataset payload path opened')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    c,l,p,caller=setup(tmp_path);run_campaign(c,caller)
