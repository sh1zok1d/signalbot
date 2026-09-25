"""B3: crash-after-POST state machine at five crash points.

Invariant: no execution path converts "possibly already POSTed" into a state
that allows an automatic or operator-triggered duplicate POST without explicit,
auditable evidence. A Crash is a BaseException (process death), so nothing in
the Caller catches it; the journal is left exactly as the process left it."""
import json
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.ledger import Ledger,CallUncertain
from scripts.research.generator_v0.provider import Caller,MockProvider,Response,CallClosed
from scripts.research.generator_v0.mock import MockResponder,fixture,slot_plan
from scripts.research.generator_v0.roles import CHECKLIST,PROTECTED

class Crash(BaseException):pass

C=Contexts()
CTX={'CANDIDATE':fixture(slot_plan(40)[0],C),'METHODOLOGY_CHECKLIST':CHECKLIST,'PROTECTED_DATA_RULES':PROTECTED}
ANSWER=MockResponder(C)({'role':'RED_TEAM','context':CTX,'parameters':{}})

class Provider(MockProvider):
    """Server log = requests that reached the provider. crash in ('send','ack') simulates death
    before the provider saw the request, or after it accepted (and billed) it."""
    def __init__(s,crash=None):super().__init__(None);s.crash=crash;s.server_log=[]
    def bound(s,req):return 1000
    def complete(s,req):
        if s.crash=='send':s.crash=None;raise Crash('died while sending')
        s.server_log.append(req.get('transport_attempt',0))
        if s.crash=='ack':s.crash=None;raise Crash('died after provider acknowledgement')
        return Response(ANSWER,{'input_tokens':10,'output_tokens':10},300)

def call(l,p,attempt=0):
    return Caller(C,l,p,5000).call('RED_TEAM',CTX,'p',{'max_output_tokens':10},'RED_TEAM:C001',content_attempt=attempt)

def rows(l):return [(r['STATE'],r['COST_MICRO_USD']) for r in l.export_calls()]

def test_crash_before_post_is_redispatched_under_the_same_key(tmp_path,monkeypatch):
    l=Ledger(tmp_path/'a.sqlite',{'RUN_ID':'a'});p=Provider()
    orig=l.mark_dispatched
    monkeypatch.setattr(l,'mark_dispatched',lambda k:(_ for _ in ()).throw(Crash('died before dispatch')))
    with pytest.raises(Crash):call(l,p)
    assert [r['STATE'] for r in l.export_calls()]==['RESERVED'] and p.server_log==[]
    monkeypatch.setattr(l,'mark_dispatched',orig)
    assert call(l,p)==ANSWER
    assert p.server_log==[0] and rows(l)==[('COMPLETE',300)]          # one POST, one row, same key

@pytest.mark.parametrize('point',['send','ack'])
def test_crash_after_dispatch_pauses_and_needs_evidence(tmp_path,point):
    """'send': the provider never saw it. 'ack': the provider accepted and billed it.
    Locally the two are indistinguishable, so both are treated as possibly POSTed."""
    l=Ledger(tmp_path/'b.sqlite',{'RUN_ID':'b'});p=Provider(point)
    with pytest.raises(Crash):call(l,p)
    assert [r['STATE'] for r in l.export_calls()]==['DISPATCHED'] and l.spent_micro_usd()==1000
    seen=list(p.server_log)
    with pytest.raises(CallUncertain):call(l,p)                         # automatic resume never re-POSTs
    assert p.server_log==seen
    key=l.export_calls()[0]['CALL_KEY']
    for evidence in ('','provider dashboard shows nothing',{'PROVIDER_RESPONSE_ID':'resp_x','PROVIDER_STATUS':'failed','BILLED_OUTPUT_TOKENS':0}):
        with pytest.raises(ContractError):l.reconcile(key,'NOT_BILLED',None,'op','assert unbilled',evidence)
    with pytest.raises(ContractError,match='requires evidence'):l.reconcile(key,'BILLED',300,'op','billed')
    with pytest.raises(CallUncertain):call(l,p)
    assert p.server_log==seen and [r['STATE'] for r in l.export_calls()]==['DISPATCHED']

def test_unknown_resolution_closes_the_logical_call(tmp_path):
    l=Ledger(tmp_path/'c.sqlite',{'RUN_ID':'c'});p=Provider('ack')
    with pytest.raises(Crash):call(l,p)
    key=l.export_calls()[0]['CALL_KEY']
    out=l.reconcile(key,'UNKNOWN',None,'op','no provider evidence')
    assert out['LOGICAL_CALL_CLOSED'] and out['COST_MICRO_USD']==1000 and l.spent_micro_usd()==1000
    for attempt in (0,1,2):
        with pytest.raises(CallClosed):call(l,p,attempt)                 # every content attempt, no POST
    assert p.server_log==[0] and len(l.export_calls())==1
    ev=[json.loads(x) for (x,) in l.db.execute("SELECT payload FROM events WHERE kind='CALL_RECONCILED'")]
    assert ev[0]['RESOLUTION']=='UNKNOWN' and ev[0]['ACTOR']=='op'

def test_billed_with_evidence_allows_one_audited_new_attempt(tmp_path):
    l=Ledger(tmp_path/'d.sqlite',{'RUN_ID':'d'});p=Provider('ack')
    with pytest.raises(Crash):call(l,p)
    key=l.export_calls()[0]['CALL_KEY']
    l.reconcile(key,'BILLED',300,'op','usage export shows the request',{'PROVIDER_USAGE_ROW':'synthetic-1'})
    from scripts.research.generator_v0.provider import BilledFailure
    with pytest.raises(BilledFailure):call(l,p)                         # the closed attempt itself is not re-sent
    assert call(l,p,attempt=1)==ANSWER                                   # a new content attempt, separately reserved
    assert rows(l)==[('RECONCILED_BILLED',300),('COMPLETE',300)] and p.server_log==[0,0]

def test_crash_before_journal_completion_is_possibly_posted(tmp_path,monkeypatch):
    l=Ledger(tmp_path/'e.sqlite',{'RUN_ID':'e'});p=Provider()
    monkeypatch.setattr(l,'finish',lambda *a,**k:(_ for _ in ()).throw(Crash('died before journal completion')))
    with pytest.raises(Crash):call(l,p)
    assert p.server_log==[0] and [r['STATE'] for r in l.export_calls()]==['DISPATCHED']
    monkeypatch.undo()
    with pytest.raises(CallUncertain):call(l,p)
    assert p.server_log==[0]

def test_crash_after_journal_completion_replays_from_the_journal(tmp_path,monkeypatch):
    l=Ledger(tmp_path/'f.sqlite',{'RUN_ID':'f'});p=Provider()
    orig=l.finish
    def finish_then_die(*a,**k):
        orig(*a,**k);raise Crash('died after journal completion')
    monkeypatch.setattr(l,'finish',finish_then_die)
    with pytest.raises(Crash):call(l,p)
    monkeypatch.undo()
    assert call(l,p)==ANSWER and p.server_log==[0] and rows(l)==[('COMPLETE',300)]

def test_not_billed_only_with_matching_provider_evidence(tmp_path):
    """Background calls carry a provider response_id; only evidence naming it can clear the charge."""
    l=Ledger(tmp_path/'g.sqlite',{'RUN_ID':'g'})
    l.reserve('k',{'role':'GENERATOR','slot':'generation:0'},1000,5000);l.mark_dispatched('k')
    l.failed('k','retrieve_error',state='UNCERTAIN',envelope={'response_id':'resp_42'})
    with pytest.raises(ContractError,match='response_id'):l.reconcile('k','NOT_BILLED',None,'op','r',{'PROVIDER_RESPONSE_ID':'resp_other','PROVIDER_STATUS':'failed','BILLED_OUTPUT_TOKENS':0})
    with pytest.raises(ContractError,match='zero billed'):l.reconcile('k','NOT_BILLED',None,'op','r',{'PROVIDER_RESPONSE_ID':'resp_42','PROVIDER_STATUS':'completed','BILLED_OUTPUT_TOKENS':0})
    out=l.reconcile('k','NOT_BILLED',None,'op','provider shows cancelled',json.dumps({'PROVIDER_RESPONSE_ID':'resp_42','PROVIDER_STATUS':'cancelled','BILLED_OUTPUT_TOKENS':0}))
    assert out['COST_MICRO_USD']==0 and l.spent_micro_usd()==0

def test_journal_without_dispatch_protocol_treats_reserved_as_possibly_posted(tmp_path):
    l=Ledger(tmp_path/'h.sqlite',{'RUN_ID':'h'})
    l.db.execute("DELETE FROM meta WHERE key='DISPATCH_PROTOCOL'");l.db.commit()
    l.reserve('k',{'role':'RED_TEAM','slot':'s'},100,500)
    with pytest.raises(CallUncertain):l.reserve('k',{'role':'RED_TEAM','slot':'s'},100,500)
    with pytest.raises(ContractError,match='provider-side evidence'):l.reconcile('k','NOT_BILLED',None,'op','r')

def test_reserved_under_protocol_cannot_be_reconciled(tmp_path):
    l=Ledger(tmp_path/'i.sqlite',{'RUN_ID':'i'})
    l.reserve('k',{'role':'RED_TEAM','slot':'s'},100,500)
    with pytest.raises(ContractError,match='never dispatched'):l.reconcile('k','UNKNOWN',None,'op','r')

def test_cli_reconcile_offers_no_evidence_free_not_billed(tmp_path):
    from scripts.research.generator_v0.__main__ import main
    d=tmp_path/'run';d.mkdir();l=Ledger(d/'run.sqlite',{'RUN_ID':'cli'})
    l.reserve('k',{'role':'RED_TEAM','slot':'s'},100,500);l.mark_dispatched('k');l.close()
    with pytest.raises(ContractError,match='provider-side evidence'):
        main(['reconcile','--run-dir',str(d),'--call-key','k','--resolution','NOT_BILLED','--actor','a','--reason','r'])
