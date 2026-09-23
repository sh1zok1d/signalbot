"""Fault injection, state machine, retry/reconcile, selector advisory, lineage budget
and the first-shadow-v7 derive proof. Offline: fake transports only."""
import json
import random
import shutil
import socket
from pathlib import Path
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError,canonical
from scripts.research.generator_v0.ledger import Ledger,BudgetExceeded,CallUncertain,AttemptClosed
from scripts.research.generator_v0.provider import Caller,MockProvider,Response,ProviderFailure,ProviderThrottled,ProviderRejected,BilledFailure
from scripts.research.generator_v0.mock import MockResponder,fixture,slot_plan
from scripts.research.generator_v0.runner import run_campaign,RESUMABLE_STATUSES,MIN_VALID_CANDIDATES
from scripts.research.generator_v0.derive import derive_complete_rounds,authorize_derived_continuation,authorize_budget_extension,reconcile_call,remaining_campaign_budget_preflight,DERIVED_STATUS,CONTINUATION_STATUS
from scripts.research.generator_v0.__main__ import main
from scripts.research.generator_v0_gate.noisy import run_noisy_campaign,derive_after_partial_work,NoisyTransport,provider_for,Crash,CAP

REPO=Path(__file__).resolve().parents[2]
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'
V7_SHA='e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457'

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('network reached'))

# ------------------------------------------------------- noisy end-to-end

def test_noisy_end_to_end_reaches_pending_human_review(tmp_path):
    report,l,t=run_noisy_campaign(tmp_path/'noisy')
    try:
        assert report['STATUS']=='PENDING_HUMAN_REVIEW'
        assert report['STEPS'][0].startswith('CRASH') and report['STEPS'][1]=='PAUSED: PAUSED_UNCERTAIN_CALL'
        assert report['STEPS'][2]=='NOT_BILLED_WITHOUT_EVIDENCE_REFUSED' and report['STEPS'][3]=='RECONCILED_BILLED'
        m=report['METRICS']
        assert m['SLOTS']==40 and m['VALID']==37 and m['HARD_FAIL']==3
        assert set(report['HARD_FAIL_IDS'])=={'C020','C025','C037'}          # missing card, non-canonical range, protected year
        assert m['HARD_FAIL_BY_RULE']=={'NO_PROTECTED_YEARS':1,'PROVIDER_SCHEMA':1,'SLOT_IDENTITY':1}   # the non-canonical range fails the slot's strict schema first
        assert set(report['REVIEW_FAILED_IDS'])=={'C009','C010'} and m['REVIEW_FAILED']==2
        assert m['REVIEWED']==35
        assert m['CRITIC_COMPLETIONS']=={'FEASIBILITY':36,'NOVELTY':37,'RED_TEAM':35}
        assert m['CONTENT_RETRIES']=={'NOVELTY':3,'RED_TEAM':1}
        assert report['SELECTOR_ADVISORY']['STATUS']=='DISAGREES'
        assert report['CALL_STATES']=={'COMPLETE':117,'FAILED_NOT_BILLED':3,'FAILED_WITH_COST':4,'RECONCILED_BILLED':1}
        # Every POST is exactly one journal attempt: no COMPLETE call was ever POSTed again.
        assert report['POSTS']==report['JOURNAL_ROWS']
        keys=[r['CALL_KEY'] for r in l.export_calls()];assert len(keys)==len(set(keys))
        spend=report['SPEND'];assert spend['TOTAL_MICRO_USD']==spend['JOURNAL_MICRO_USD']==l.spent_micro_usd()
        assert spend['TOTAL_MICRO_USD']<=CAP
        # The deterministic order is authoritative even though the advisory selector disagreed.
        assert report['SHORTLIST']!=report['SELECTOR_ADVISORY']['PROPOSED'][:5]
        # Resume after completion is free and identical.
        posts=len(t.posts());again=run_campaign(Contexts(),Caller(Contexts(),l,provider_for(t,Contexts()),CAP,True))
        assert again['STATUS']=='PENDING_HUMAN_REVIEW' and len(t.posts())==posts
        states={x['CANDIDATE_ID']:x['STATE'] for x in l.candidates()}
        assert states['C009']=='REVIEW_FAILED' and states['C020']=='HARD_FAIL' and states['C001']=='REVIEWED'
    finally:l.close()

def test_derive_after_partial_work_preserves_lineage_and_reuses_generation(tmp_path):
    out=derive_after_partial_work(tmp_path)
    assert out['SOURCE_STATUS']=='PAUSED_UNCERTAIN_CALL'
    assert out['DERIVE_LINEAGE_TOTAL_MICRO_USD']==out['SOURCE_TOTAL_MICRO_USD']
    assert out['DERIVED_GENERATOR_POSTS']==0
    assert out['DERIVED_STATUS']=='PENDING_HUMAN_REVIEW'
    assert out['DERIVED_SPEND']['LINEAGE_PRIOR_MICRO_USD']==out['DERIVE_LINEAGE_PRIOR_MICRO_USD']
    assert out['DERIVED_SPEND']['TOTAL_MICRO_USD']>out['SOURCE_TOTAL_MICRO_USD']
    assert out['PRIOR_ATTEMPTS']==out['SOURCE_ROWS']-4

# ---------------------------------------------------------- selector

def test_selector_disagreement_malformed_and_unavailable_are_advisory(tmp_path):
    c=Contexts()
    for mode in ('swap','malformed','uncertain'):
        base=MockResponder(c)
        def answer(req,mode=mode):
            if req['role']=='SELECTOR':
                if mode=='malformed':return 'not json'
                if mode=='uncertain':raise ProviderFailure('gateway timeout',billing='UNCERTAIN')
                ids=json.loads(base(req))['ORDERED_CANDIDATE_IDS'];ids.reverse();return canonical({'ORDERED_CANDIDATE_IDS':ids})
            return base(req)
        l=Ledger(tmp_path/(mode+'.sqlite'),{'RUN_ID':mode})
        r=run_campaign(c,Caller(c,l,MockProvider(answer)))
        assert r['STATUS']=='PENDING_HUMAN_REVIEW'
        assert r['SELECTOR_ADVISORY']['STATUS']=={'swap':'DISAGREES','malformed':'MALFORMED','uncertain':'UNAVAILABLE'}[mode]
        assert r['SHORTLIST']==sorted(r['SELECTION_JUDGMENTS'],key=lambda k:tuple(-r['SELECTION_JUDGMENTS'][k][f] for f in ('MECHANISM_DISTANCE','INFORMATION_GAIN','FEASIBILITY','CHEAPNESS'))+(k,))[:5]
        l.close()

# --------------------------------------------------- retry / reconcile

def _roundtrip_provider(raw_by_attempt):
    class P(MockProvider):
        def __init__(s):super().__init__(None);s.n=0
        def complete(s,req):
            s.n+=1;out=raw_by_attempt(s.n,req)
            if isinstance(out,BaseException):raise out
            return Response(out,{'input_tokens':1,'output_tokens':1},0)
    return P()

def test_not_billed_failures_retry_under_new_keys_and_charge_nothing(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    p=_roundtrip_provider(lambda n,req:ProviderFailure('429',billing='NOT_BILLED',retryable=True) if n<3 else '{"ok":1}')
    cal=Caller(c,l,p)
    red={'CANDIDATE':fixture(slot_plan(40)[0],c),'METHODOLOGY_CHECKLIST':__import__('scripts.research.generator_v0.roles',fromlist=['CHECKLIST']).CHECKLIST,'PROTECTED_DATA_RULES':__import__('scripts.research.generator_v0.roles',fromlist=['PROTECTED']).PROTECTED}
    assert cal.call('RED_TEAM',red,'p',{'max_output_tokens':10},'s')=='{"ok":1}'
    assert [r['STATE'] for r in l.export_calls()]==['FAILED_NOT_BILLED','FAILED_NOT_BILLED','COMPLETE']
    assert [r['TRANSPORT_ATTEMPT'] for r in l.export_calls()]==[0,1,2] and l.spent_micro_usd()==0
    assert cal.call('RED_TEAM',red,'p',{'max_output_tokens':10},'s')=='{"ok":1}' and p.n==3   # COMPLETE is never re-POSTed

def test_non_retryable_rejection_pauses_and_resumes_with_new_attempt(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    state={'reject':True}
    base=MockResponder(c)
    def answer(req):
        if req['role']=='FEASIBILITY_CRITIC' and req['slot']=='FEASIBILITY_CRITIC:C003' and state['reject']:raise ProviderFailure('400 bad request',billing='NOT_BILLED',retryable=False)
        return base(req)
    p=MockProvider(answer)
    with pytest.raises(ProviderRejected):run_campaign(c,Caller(c,l,p))
    assert l.get('status')=='PAUSED_PROVIDER_REJECTED'
    state['reject']=False
    r=run_campaign(c,Caller(c,l,p));assert r['STATUS']=='PENDING_HUMAN_REVIEW'

def test_uncertain_call_pauses_and_reconcile_is_the_documented_exit(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'});flag={'timeout':True};base=MockResponder(c)
    def answer(req):
        if req['slot']=='NOVELTY_CRITIC:C004' and flag['timeout']:raise TimeoutError()
        return base(req)
    p=MockProvider(answer)
    with pytest.raises(CallUncertain):run_campaign(c,Caller(c,l,p))
    assert l.get('status')=='PAUSED_UNCERTAIN_CALL'
    ev=[json.loads(x) for (x,) in l.db.execute("SELECT payload FROM events WHERE kind='CAMPAIGN_PAUSED_UNCERTAIN_CALL'")]
    assert 'reconcile' in ev[0]['RESOLUTION']
    with pytest.raises(CallUncertain):run_campaign(c,Caller(c,l,p))           # never replayed automatically
    key=[r['CALL_KEY'] for r in l.export_calls() if r['STATE']=='UNCERTAIN'][0]
    with pytest.raises(ContractError,match='actor and reason'):l.reconcile(key,'NOT_BILLED',None,'','')
    with pytest.raises(ContractError,match='within the reserved bound'):l.reconcile(key,'BILLED',10**9,'op','usage page','evidence')
    with pytest.raises(ContractError,match='provider-side evidence'):l.reconcile(key,'NOT_BILLED',None,'op','provider dashboard shows no request')
    l.reconcile(key,'UNKNOWN',None,'op','no provider evidence available')
    with pytest.raises(ContractError,match='only RESERVED, DISPATCHED or UNCERTAIN'):l.reconcile(key,'UNKNOWN',None,'op','twice')
    flag['timeout']=False
    calls=p.calls
    r=run_campaign(c,Caller(c,l,p));assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    # The closed logical call is never POSTed again; that card is REVIEW_FAILED.
    assert not any(x for x in r['REVIEWS'] if x['CANDIDATE_ID']=='C004' and x['STATE']!='REVIEW_FAILED')
    assert l.logical_call_closed('NOVELTY_CRITIC|NOVELTY_CRITIC:C004')['CALL_KEY']==key

def test_budget_exhaustion_stops_cleanly_and_resumes_after_extension(tmp_path):
    c=Contexts()
    class Priced(MockProvider):
        def bound(s,req):return 100
        def complete(s,req):
            r=super().complete(req);return Response(r.raw,r.usage,40)
    src=tmp_path/'b';src.mkdir()
    from scripts.research.generator_v0.derive import derived_config
    l=Ledger(src/'run.sqlite',{'RUN_ID':'b','CAP_MICRO_USD':3000,'SIZE':40})
    p=Priced(MockResponder(c))
    with pytest.raises(BudgetExceeded):run_campaign(c,Caller(c,l,p,3000))
    assert l.get('status')=='STOPPED_BUDGET' and l.total_charged_micro_usd()<=3000
    assert not [r for r in l.export_calls() if r['STATE'] in ('RESERVED','UNCERTAIN')]
    l.close()
    l=Ledger(src/'run.sqlite');cfg=l.get('config');l.set('config',{**cfg,'CAP_MICRO_USD':6000});l.db.commit()
    r=run_campaign(c,Caller(c,l,p,6000));assert r['STATUS']=='PENDING_HUMAN_REVIEW' and l.total_charged_micro_usd()<=6000
    l.close()

def test_insufficient_valid_candidates_is_an_explicit_terminal_stop(tmp_path):
    c=Contexts();base=MockResponder(c)
    def answer(req):
        x=json.loads(base(req))
        if req['role']=='GENERATOR' and req['slot'] in ('generation:0','generation:1'):
            for card in x['CANDIDATES'].values():card['HORIZON']='through today'
        return canonical(x)
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'});p=MockProvider(answer)
    r=run_campaign(c,Caller(c,l,p))
    assert r['STATUS']=='STOPPED_INSUFFICIENT_VALID' and r['METRICS']['VALID']==20<MIN_VALID_CANDIDATES
    assert p.calls==4 and r['METRICS']['HARD_FAIL_BY_RULE']=={'NO_OPEN_ENDED_WINDOW':20,'SCOPE_NO_RECENCY':20}
    assert run_campaign(c,Caller(c,l,p))==r and p.calls==4

# --------------------------------------------------------- state machine

STATUSES=('CREATED','DERIVED_IMPORTED_REVALIDATED','DERIVED_CONTINUATION_AUTHORIZED','PAUSED_UNCERTAIN_CALL','PAUSED_PROVIDER_THROTTLED',
          'PAUSED_PROVIDER_REJECTED','PAUSED_BACKGROUND_PENDING','STOPPED_BUDGET','STOPPED_INSUFFICIENT_VALID','PENDING_HUMAN_REVIEW','MUTATED_REQUIRES_REVIEW','UNKNOWN_STATE')

@pytest.mark.parametrize('status',STATUSES)
def test_state_machine_generation_permission(tmp_path,status):
    from scripts.research.generator_v0.runner import PAUSE_STATUSES
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'});l.set('status',status)
    if status in PAUSE_STATUSES:l.event('CAMPAIGN_'+status,{'REASON':'synthetic cause'})
    l.db.commit()
    p=MockProvider(MockResponder(c))
    if status in RESUMABLE_STATUSES:
        assert run_campaign(c,Caller(c,l,p))['STATUS']=='PENDING_HUMAN_REVIEW'
    else:
        with pytest.raises(ContractError):run_campaign(c,Caller(c,l,p))
        assert p.calls==0

@pytest.mark.parametrize('status',('PAUSED_UNCERTAIN_CALL','PAUSED_PROVIDER_THROTTLED','PAUSED_PROVIDER_REJECTED','PAUSED_BACKGROUND_PENDING','STOPPED_BUDGET'))
def test_pause_status_without_its_causal_journal_event_is_refused(tmp_path,status):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'});l.set('status',status)
    l.event('CAMPAIGN_PAUSED_PROVIDER_THROTTLED' if status!='PAUSED_PROVIDER_THROTTLED' else 'CAMPAIGN_STOPPED_BUDGET',{'REASON':'a different cause'})
    l.db.commit();p=MockProvider(MockResponder(c))
    with pytest.raises(ContractError,match='no causal'):run_campaign(c,Caller(c,l,p))
    assert p.calls==0

@pytest.mark.parametrize('status',STATUSES)
def test_state_machine_continuation_authorization_only_from_derived(tmp_path,status):
    d=tmp_path/'run';d.mkdir();l=Ledger(d/'run.sqlite',{'RUN_ID':'x'});l.set('status',status);l.db.commit();l.close()
    if status==DERIVED_STATUS:assert authorize_derived_continuation(d,'op','go')['STATUS']==CONTINUATION_STATUS
    else:
        with pytest.raises(ContractError,match='DERIVED_IMPORTED_REVALIDATED'):authorize_derived_continuation(d,'op','go')

@pytest.mark.parametrize('cmd',[['inspect'],['review','--candidate-id','C001','--decision','DEFER','--reason','r','--actor','a'],
                                ['mutate','--candidate-id','C001','--field','NAME','--value-json','"x"','--reason','r','--actor','a'],
                                ['resume'],['authorize-derived-continuation','--actor','a','--reason','r'],
                                ['authorize-budget-extension','--actor','a','--reason','r','--new-cap-usd','17.1'],
                                ['remaining-budget-preflight'],['reconcile','--call-key','k','--resolution','NOT_BILLED','--actor','a','--reason','r']])
def test_sealed_journal_refused_by_content_hash_at_any_path(tmp_path,cmd):
    d=tmp_path/'somewhere'/'else';d.mkdir(parents=True);shutil.copy(V7,d/'run.sqlite')
    with pytest.raises(ContractError,match='sealed journal'):main(cmd+['--run-dir',str(d)])
    import hashlib
    assert hashlib.sha256((d/'run.sqlite').read_bytes()).hexdigest()==V7_SHA
    assert sorted(x.name for x in d.iterdir())==['run.sqlite']

def test_sealed_tracked_v7_path_is_refused_and_untouched():
    import hashlib
    before=sorted(x.name for x in V7.parent.iterdir())
    with pytest.raises(ContractError,match='sealed journal'):main(['inspect','--run-dir',str(V7.parent)])
    assert hashlib.sha256(V7.read_bytes()).hexdigest()==V7_SHA
    assert sorted(x.name for x in V7.parent.iterdir())==before

# ---------------------------------------------- lineage budget property

def _charge(state,cost,reserved):
    if state in ('COMPLETE','FAILED_WITH_COST','RECONCILED_BILLED'):return cost
    if state in ('FAILED_NOT_BILLED','RECONCILED_NOT_BILLED'):return 0
    return cost if cost is not None else reserved

def test_property_lineage_ceiling_holds_across_random_operation_sequences(tmp_path):
    """lineage_spend + journal_spend + new_reservation <= cap after every operation,
    across reserve/finish/billed/not-billed/uncertain/reconcile, partial rounds and repeated derives."""
    from scripts.research.generator_v0.derive import charge
    rng=random.Random(2026);cap=50_000
    for trial in range(40):
        base=tmp_path/('t%d'%trial);base.mkdir()
        l=Ledger(base/'run.sqlite',{'RUN_ID':'t','CAP_MICRO_USD':cap,'SIZE':40})
        lineage_truth=0;n=0
        for step in range(rng.randint(10,60)):
            op=rng.random();key='k%d_%d'%(trial,n);n+=1
            bound=rng.randint(1,4000)
            before=l.total_charged_micro_usd()
            try:
                l.reserve(key,{'n':key},bound,cap)
            except BudgetExceeded:
                assert before+bound>cap;continue
            assert l.total_charged_micro_usd()<=cap
            if op<0.4:l.finish(key,{'raw':'x'},rng.randint(0,bound),{})
            elif op<0.55:l.failed(key,'429',state='FAILED_NOT_BILLED')
            elif op<0.7:l.failed(key,'length',state='FAILED_WITH_COST',cost=rng.randint(0,bound),usage={})
            elif op<0.8:l.failed(key,'length',state='FAILED_WITH_COST')
            elif op<0.9:
                l.failed(key,'timeout',state='UNCERTAIN')
                if rng.random()<0.5:
                    with pytest.raises(ContractError):l.reconcile(key,'NOT_BILLED',None,'op','assertion only')
                    choice=rng.choice(['BILLED','UNKNOWN'])
                    l.reconcile(key,choice,rng.randint(1,bound) if choice=='BILLED' else None,'op','reason','evidence')
            elif op<0.95:l.mark_dispatched(key)       # crash after dispatch: charged at the bound
            # else: left RESERVED (crash before dispatch)
            rows=list(l.db.execute('SELECT state,cost,reserved FROM calls'))
            assert l.spent_micro_usd()==sum(_charge(*r) for r in rows)
            assert l.total_charged_micro_usd()<=cap
        journal=l.spent_micro_usd();total=l.total_charged_micro_usd();l.close()
        # Repeated derive through a synthetic lineage: never refunds spend.
        from scripts.research.generator_v0.ledger import Ledger as L2
        carried=total
        for k in range(rng.randint(1,3)):
            child=base/('child%d'%k);child.mkdir()
            c2=L2(child/'run.sqlite',{'RUN_ID':'c','CAP_MICRO_USD':cap,'SIZE':40})
            c2.set('lineage',{'PRIOR_SPEND_MICRO_USD':carried});c2.db.commit()
            assert c2.total_charged_micro_usd()==carried
            with pytest.raises(BudgetExceeded):c2.reserve('over',{'x':1},cap-carried+1,cap)
            c2.close()

def test_first_shadow_v7_derive_preserves_cumulative_spend(tmp_path):
    import hashlib
    src=tmp_path/'src';src.mkdir();shutil.copy(V7,src/'run.sqlite')
    report=derive_complete_rounds(src,tmp_path/'v8',2)
    assert report['IMPORTED_COST_MICRO_USD']==3779550
    assert report['LINEAGE_PRIOR_MICRO_USD']==1167200
    assert report['LINEAGE_TOTAL_MICRO_USD']==4946750
    assert report['REMAINING_MICRO_USD']==17_100_000-4946750==12153250
    assert report['IMPORTED_CONTRACTS']=={'generation:%d'%i:'GENERATOR_CONTRACT_V01_LEGACY' for i in range(3)}
    assert report['IMPORTED_INTAKE']=={'generation:%d'%i:{'CONTRACT':'GENERATOR_CONTRACT_V01_LEGACY','VALID':10,'HARD_FAIL':0} for i in range(3)}
    l=Ledger(tmp_path/'v8'/'run.sqlite')
    assert l.total_charged_micro_usd()==4946750 and l.spent_micro_usd()==3779550
    prior=l.get('lineage')['PRIOR_ATTEMPTS']
    assert len(prior)==1 and prior[0]['SLOT']=='generation:3' and prior[0]['CHARGED_MICRO_USD']==1167200
    verdicts=[x['VERDICT'] for x in prior[0]['INTAKE']['CARDS']]
    assert verdicts.count('HARD_FAIL')==9 and verdicts.count('VALID')==1
    l.close()
    with pytest.raises(ContractError,match='generation:3 \\(legacy v0.1, not grandfathered\\)'):derive_complete_rounds(src,tmp_path/'v9',3)
    # budget authority after derive is lineage-aware
    pre=remaining_campaign_budget_preflight(tmp_path/'v8')
    assert pre['SPENT_MICRO_USD']==4946750 and pre['REMAINING_AUTHORIZED_MICRO_USD']==12153250
    assert pre['WORST_CASE_REMAINING_MICRO_USD']==sum(s['BOUND_MICRO_USD'] for s in pre['STAGES'])
    # second-generation derive from the derived run still carries everything
    authorize_derived_continuation(tmp_path/'v8','op','go')
    report2=derive_complete_rounds(tmp_path/'v8',tmp_path/'v8b',2)
    assert report2['LINEAGE_TOTAL_MICRO_USD']==4946750
    assert hashlib.sha256((src/'run.sqlite').read_bytes()).hexdigest()==V7_SHA
    assert sorted(x.name for x in src.iterdir())==['run.sqlite']

def test_derive_refuses_source_with_uncheckpointed_wal(tmp_path):
    src=tmp_path/'src';src.mkdir();shutil.copy(V7,src/'run.sqlite');(src/'run.sqlite-wal').write_bytes(b'x'*32)
    with pytest.raises(ContractError,match='uncheckpointed WAL'):derive_complete_rounds(src,tmp_path/'dst',2)
    assert not (tmp_path/'dst').exists()

def test_crash_after_post_leaves_dispatched_charged_until_reconciled(tmp_path):
    """Crash-point coverage lives in test_generator_v0_crash_points.py; this is the noisy-transport variant."""
    c=Contexts();t=NoisyTransport(c,{('RED_TEAM','C002',1):'crash'})
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'crash'})
    with pytest.raises(Crash):run_campaign(c,Caller(c,l,provider_for(t,c),CAP,True))
    rows=[r for r in l.export_calls() if r['STATE']=='DISPATCHED']
    assert len(rows)==1 and l.spent_micro_usd()>=rows[0]['RESERVED_MICRO_USD']
    posts=len(t.posts())
    with pytest.raises(CallUncertain):run_campaign(c,Caller(c,l,provider_for(t,c),CAP,True))
    assert len(t.posts())==posts
    with pytest.raises(ContractError,match='provider-side evidence'):l.reconcile(rows[0]['CALL_KEY'],'NOT_BILLED',None,'op','no request in provider logs')
    l.reconcile(rows[0]['CALL_KEY'],'UNKNOWN',None,'op','no evidence either way')
    r=run_campaign(c,Caller(c,l,provider_for(t,c),CAP,True))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW' and 'C002' in [x['CANDIDATE_ID'] for x in r['REVIEW_FAILED']]
    assert t.counts[('RED_TEAM','C002')]==1       # the closed logical call was never POSTed again
    l.close()
