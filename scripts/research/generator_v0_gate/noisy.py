"""Noisy fake-provider campaign through the real OpenAIProvider code paths.

The fake HTTP transport answers Responses (background generator) and Chat
Completions (critics, selector) with deterministic synthetic content in the
strict provider (keyed) encodings, and injects faults by (role, target, attempt).
No network is used; the default HTTPS transport is never constructed.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from scripts.research.generator_v0.context import Contexts,canonical
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import MockResponder
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.provider import Caller
from scripts.research.generator_v0.runner import GENERATOR_PROMPT,run_campaign,accept_budget_stop,RESUMABLE_STATUSES
from scripts.research.generator_v0.roles import NOVELTY_PROMPT,FEAS_PROMPT,RED_PROMPT,SELECTOR_PROMPT

CAP=17_100_000   # the owner ceiling; the fresh worst case exceeds it, so every invocation records a budget-stop acceptance

def run(c,ledger,transport,factory=None):
    """One operator invocation through the library execution gate (no CLI)."""
    caller=Caller(c,ledger,(factory or provider_for)(transport,c),CAP,True)
    if ledger.get('status') in RESUMABLE_STATUSES and ledger.db.execute("SELECT 1 FROM results WHERE key='campaign'").fetchone() is None:
        accept_budget_stop(c,caller,40,'offline-gate','noisy harness accepts a clean STOPPED_BUDGET')
    return run_campaign(c,caller)

class Crash(BaseException):
    """Simulated process death after the request left the machine."""

def _chat(content,finish='stop',prompt=900,completion=120):
    return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':content}}],'usage':{'prompt_tokens':prompt,'completion_tokens':completion}}).encode()

class NoisyTransport:
    def __init__(self,contexts,faults=None,compact_mutator=None):
        self.respond=MockResponder(contexts);self.faults=dict(faults or {});self.compact_mutator=compact_mutator
        self.counts=Counter();self.log=[];self.payloads={};self.n=0
        self.prompts={NOVELTY_PROMPT:'NOVELTY_CRITIC',FEAS_PROMPT:'FEASIBILITY_CRITIC',RED_PROMPT:'RED_TEAM',SELECTOR_PROMPT:'SELECTOR'}

    def posts(self):return [x for x in self.log if x[0]=='POST']

    def anthropic(self,method,path,body,headers,timeout):
        """Fake Claude Messages endpoint (POST /v1/messages) for the routed GENERATOR."""
        self.log.append((method,path))
        assert headers.get('anthropic-version')=='2023-06-01' and headers.get('x-api-key')
        b=json.loads(body);user=json.loads(b['messages'][0]['content']);slots=user['slots']
        rnd=(int(slots[0]['CANDIDATE_ID'][1:])-1)//10
        self.counts[('GENERATOR',rnd)]+=1;fault=self.faults.get(('GENERATOR',rnd,self.counts[('GENERATOR',rnd)]))
        if fault=='crash':raise Crash('process died after POST GENERATOR round '+str(rnd))
        if fault=='529':return 529,b'{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}'
        if fault=='429':return 429,b'{"type":"error","error":{"type":"rate_limit_error","message":"slow down"}}'
        payload=json.loads(self.respond({'role':'GENERATOR','context':user['context'],'parameters':{'slots':slots}}))
        ids=[s['CANDIDATE_ID'] for s in slots]
        if fault=='drop_card':payload['CANDIDATES'].pop(ids[-1])
        if fault=='invalid_card':payload['CANDIDATES'][ids[4]]['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01 to 2024-12'
        if fault=='protected_card':payload['CANDIDATES'][ids[6]]['NO_LOOKAHEAD_RULE']='No 2025/2026 bars are permitted.'
        payload={'CANDIDATES':list(payload['CANDIDATES'].values())}   # Anthropic compact wire: array of cards
        if self.compact_mutator is not None:payload['CANDIDATES']=self.compact_mutator(rnd,payload['CANDIDATES'])
        self.n+=1
        stop='max_tokens' if fault=='max_tokens' else 'end_turn'
        text=canonical(payload) if stop=='end_turn' else canonical(payload)[:200]
        return 200,json.dumps({'id':'msg_noisy_'+str(self.n),'type':'message','role':'assistant','model':b['model'],
                               'content':[{'type':'thinking','thinking':'','signature':'synthetic'},{'type':'text','text':text}],
                               'stop_reason':stop,'stop_sequence':None,
                               'usage':{'input_tokens':6000,'output_tokens':32768 if stop=='max_tokens' else 9000}}).encode()

    def __call__(self,method,path,body,headers,timeout):
        self.log.append((method,path))
        if method=='DELETE':return 200,b'{}'
        if method=='GET':
            rid=path.rsplit('/',1)[1];kind,content=self.payloads[rid][:2]
            usage=self.payloads[rid][2] if len(self.payloads[rid])>2 else None
            if kind=='incomplete':
                return 200,json.dumps({'id':rid,'status':'incomplete','incomplete_details':{'reason':'max_output_tokens'},'usage':usage or {'input_tokens':5000,'output_tokens':32768,'output_tokens_details':{'reasoning_tokens':20000}}}).encode()
            if usage is None:
                return 200,json.dumps({'id':rid,'status':'completed','output_text':content,'usage':{'input_tokens':5000,'output_tokens':9000,'output_tokens_details':{'reasoning_tokens':4000}}}).encode()
            # Critic answers carry a reasoning item whose content must never be journaled.
            return 200,json.dumps({'id':rid,'status':'completed','output_text':content,'usage':usage,
                                   'output':[{'type':'reasoning','id':'rs_'+rid,'summary':[{'type':'summary_text','text':'SYNTHETIC_HIDDEN_REASONING'}]},
                                             {'type':'message','role':'assistant','content':[{'type':'output_text','text':content}]}]}).encode()
        b=json.loads(body)
        if path=='/v1/responses' and b.get('instructions') in self.prompts:
            # Routed background critic (NOVELTY_CRITIC, RED_TEAM): create is acknowledged 'queued'; the answer is read by GET.
            role=self.prompts[b['instructions']];ctx=json.loads(b['input'])['context']
            answer=self._critic(role,ctx)
            if answer[0]=='http':return answer[1],answer[2]
            kind,text=answer
            self.n+=1;rid='resp_noisy_'+str(self.n)
            usage={'input_tokens':900,'output_tokens':12000 if kind=='incomplete' else 120,'output_tokens_details':{'reasoning_tokens':60},'input_tokens_details':{'cached_tokens':0}}
            self.payloads[rid]=(kind,text,usage)
            return 200,json.dumps({'id':rid,'object':'response','status':'queued'}).encode()
        if path=='/v1/responses':
            user=json.loads(b['input']);slots=user['slots'];rnd=(int(slots[0]['CANDIDATE_ID'][1:])-1)//10
            self.counts[('GENERATOR',rnd)]+=1;fault=self.faults.get(('GENERATOR',rnd,self.counts[('GENERATOR',rnd)]))
            if fault=='429':return 429,b'{"error":{"type":"rate_limit"}}'
            payload=json.loads(self.respond({'role':'GENERATOR','context':user['context'],'parameters':{'slots':slots}}))
            ids=[s['CANDIDATE_ID'] for s in slots]
            if fault=='drop_card':payload['CANDIDATES'].pop(ids[-1])
            if fault=='invalid_card':payload['CANDIDATES'][ids[4]]['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01 to 2024-12'
            if fault=='protected_card':payload['CANDIDATES'][ids[6]]['NO_LOOKAHEAD_RULE']='No 2025/2026 bars are permitted.'
            self.n+=1;rid='resp_noisy_'+str(self.n)
            self.payloads[rid]=('incomplete' if fault=='incomplete' else 'completed',canonical(payload))
            return 200,json.dumps({'id':rid,'object':'response','status':'queued'}).encode()
        role=self.prompts[b['messages'][0]['content']];user=json.loads(b['messages'][1]['content'])
        answer=self._critic(role,user['context'])
        if answer[0]=='http':return answer[1],answer[2]
        kind,text=answer
        if kind=='incomplete':return 200,_chat(text,finish='length',completion=12000)
        return 200,_chat(text)

    def _critic(self,role,ctx):
        """Transport-neutral critic answer: ('http', status, body), ('incomplete', text) or ('completed', text)."""
        target=ctx['CANDIDATE']['CANDIDATE_ID'] if 'CANDIDATE' in ctx else 'selection'
        self.counts[(role,target)]+=1;fault=self.faults.get((role,target,self.counts[(role,target)]))
        if fault=='crash':raise Crash('process died after POST '+role+' '+target)
        if fault=='429':return 'http',429,b'{"error":{"type":"rate_limit"}}'
        if fault=='503':return 'http',503,b'{"error":{"type":"overloaded"}}'
        payload=json.loads(self.respond({'role':role,'context':ctx,'parameters':{}}))
        if fault=='length':return 'incomplete',canonical(payload)[:40]
        if fault=='malformed':return 'completed','this is not json'
        if role=='NOVELTY_CRITIC':
            enc=payload
            if fault=='omit_batch':enc['BATCH_RELATIONS'].pop(sorted(enc['BATCH_RELATIONS'])[0])
            text=canonical(enc)
            if fault=='dup_relation':
                first=sorted(enc['PRIOR_RELATIONS'])[0]
                text=text.replace('"PRIOR_RELATIONS":{','"PRIOR_RELATIONS":{"'+first+'":"ORTHOGONAL_MECHANISM",',1)
            return 'completed',text
        if role=='SELECTOR' and fault=='swap':
            ids=payload['ORDERED_CANDIDATE_IDS']
            if len(ids)>2:ids[0],ids[1]=ids[1],ids[0]
        return 'completed',canonical(payload)

def routed_provider_for(transport,contexts):
    """Anthropic Opus generator + OpenAI Sol/Luna critics, both through fake transports."""
    from scripts.research.generator_v0.anthropic_provider import AnthropicProvider
    from scripts.research.generator_v0.routed_provider import RoutedProvider
    from scripts.research.generator_v0.routing import ROUTES
    return RoutedProvider({'ANTHROPIC':AnthropicProvider('offline-gate-anthropic',allow_real=True,budget_micro_usd=CAP,transport=transport.anthropic,contexts=contexts),
                           'OPENAI':OpenAIProvider('offline-gate-openai',allow_real=True,budget_micro_usd=CAP,transport=transport,contexts=contexts,sleeper=lambda s:None,routes=ROUTES)},
                          ROUTES,sleeper=lambda s:None)

MIXED_FAULTS={
    # Critic faults sit on round-1 cards: generation:0 is closed by the UNKNOWN reconciliation of its 429.
    ('GENERATOR',0,1):'429',            # Anthropic documented rate_limit_error: UNCERTAIN, never replayed; reconciled UNKNOWN
    ('GENERATOR',1,1):'drop_card',      # compact omission -> missing slot HARD_FAIL
    ('GENERATOR',2,1):'invalid_card',   # non-canonical range -> one slot HARD_FAIL (provider schema)
    ('GENERATOR',3,1):'protected_card', # one slot HARD_FAIL; generator content is not retried
    ('NOVELTY_CRITIC','C015',1):'omit_batch',
    ('NOVELTY_CRITIC','C017',1):'length',
    ('FEASIBILITY_CRITIC','C018',1):'429',
    ('FEASIBILITY_CRITIC','C019',1):'malformed',
    ('FEASIBILITY_CRITIC','C019',2):'malformed',
    ('RED_TEAM','C011',1):'crash',      # crash after POST on a Sol call
    ('SELECTOR','selection',1):'swap',
}

def provider_for(transport,contexts):
    return OpenAIProvider('offline-gate',allow_real=True,budget_micro_usd=CAP,transport=transport,contexts=contexts,sleeper=lambda s:None)

DEFAULT_FAULTS={
    ('GENERATOR',0,1):'429',            # not billed; transport retry
    ('GENERATOR',1,1):'drop_card',      # wrong generation count -> one slot HARD_FAIL
    ('GENERATOR',2,1):'invalid_card',   # non-canonical LEGAL_RANGE -> one slot HARD_FAIL
    ('GENERATOR',3,1):'protected_card', # one slot HARD_FAIL; generator content is not retried
    ('NOVELTY_CRITIC','C005',1):'omit_batch',
    ('NOVELTY_CRITIC','C006',1):'dup_relation',
    ('NOVELTY_CRITIC','C007',1):'length',
    ('FEASIBILITY_CRITIC','C008',1):'429',
    ('FEASIBILITY_CRITIC','C012',1):'503',
    ('FEASIBILITY_CRITIC','C009',1):'malformed',
    ('FEASIBILITY_CRITIC','C009',2):'malformed',
    ('RED_TEAM','C010',1):'length',
    ('RED_TEAM','C010',2):'length',
    ('RED_TEAM','C011',1):'crash',
    ('SELECTOR','selection',1):'swap',
}

def run_mixed_noisy_campaign(run_dir,faults=MIXED_FAULTS,contexts=None):
    """The noisy campaign through the multi-provider router (Opus generator, Sol/Luna critics)."""
    return run_noisy_campaign(run_dir,faults,contexts,factory=routed_provider_for)

def run_noisy_campaign(run_dir,faults=DEFAULT_FAULTS,contexts=None,factory=None):
    """Run to PENDING_HUMAN_REVIEW through a crash, a pause and a reconciliation."""
    from scripts.research.generator_v0.ledger import CallUncertain
    c=contexts or Contexts();run_dir=Path(run_dir);run_dir.mkdir(parents=True,exist_ok=True)
    transport=NoisyTransport(c,faults);steps=[]
    ledger=Ledger(run_dir/'run.sqlite',{'RUN_ID':run_dir.name,'CAP_MICRO_USD':CAP})
    try:
        result=None
        for invocation in range(8):
            try:
                result=run(c,ledger,transport,factory)
                if invocation==0:steps.append('COMPLETED_WITHOUT_CRASH')
                break
            except Crash as e:
                steps.append('CRASH: '+str(e))
            except CallUncertain as e:
                steps.append('PAUSED: '+ledger.get('status'))
                row=[r for r in ledger.export_calls() if r['STATE'] in ('DISPATCHED','UNCERTAIN')][0];key=row['CALL_KEY']
                if row['STATE']=='UNCERTAIN':
                    # A provider HTTP answer whose billing is not established (e.g. an Anthropic
                    # 429/529): no provider evidence exists, so the only exit is UNKNOWN, which
                    # charges the reservation and closes that logical call (never POSTed again).
                    ledger.reconcile(key,'UNKNOWN',None,'offline-gate','uncertain provider HTTP answer; no provider-side evidence')
                    steps.append('RECONCILED_UNKNOWN: '+str(row['SLOT']))
                    continue
                # Possibly POSTed: an unsupported NOT_BILLED assertion is refused; the fake
                # provider's log is the evidence that the request arrived and was billed.
                try:
                    ledger.reconcile(key,'NOT_BILLED',None,'offline-gate','operator assertion only')
                    steps.append('UNEXPECTED: NOT_BILLED accepted without evidence')
                except Exception as refused:
                    steps.append('NOT_BILLED_WITHOUT_EVIDENCE_REFUSED')
                ledger.reconcile(key,'BILLED',500,'offline-gate','crash after POST; fake provider log shows the request arrived',
                                 {'PROVIDER_LOG_POSTS':len(transport.posts()),'SOURCE':'synthetic NoisyTransport log'})
                steps.append('RECONCILED_BILLED')
        if result is None:raise RuntimeError('noisy campaign did not finish within the invocation limit')
        steps.append('FINAL: '+result['STATUS'])
        calls=ledger.export_calls()
        report={
            'STEPS':steps,'STATUS':result['STATUS'],'METRICS':result['METRICS'],'SPEND':result['SPEND'],
            'SELECTOR_ADVISORY':result['SELECTOR_ADVISORY'],
            'HARD_FAIL_IDS':[h['CANDIDATE_ID'] for h in result['HARD_FAILS']],
            'REVIEW_FAILED_IDS':[r['CANDIDATE_ID'] for r in result['REVIEW_FAILED']],
            'CALL_STATES':dict(sorted(Counter(r['STATE'] for r in calls).items())),
            'POSTS':len(transport.posts()),'JOURNAL_ROWS':len(calls),
            'RETRY_ATTEMPTS':{'CONTENT':sum(1 for r in calls if r['CONTENT_ATTEMPT']),'TRANSPORT':sum(1 for r in calls if r['TRANSPORT_ATTEMPT'])},
            'STREAM_A':len(result['STREAM_A']),'STREAM_B':len(result['STREAM_B']),'SHORTLIST':result['SHORTLIST'],
            'ROLE_ROUTES':{role:sorted({'{} / {} / {}'.format(r['ROUTE_PROVIDER'],r['MODEL_PROVIDER'],r['MODEL_ID']) for r in calls if r['ROLE']==role})
                           for role in sorted({r['ROLE'] for r in calls})},
            'POSTS_BY_PATH':dict(sorted(Counter(p for m,p in transport.log if m=='POST').items())),
        }
        return report,ledger,transport
    except BaseException:
        ledger.close();raise

def derive_after_partial_work(base_dir,contexts=None):
    """Crash mid-critics, pause, derive the partial journal, continue the derived run."""
    from scripts.research.generator_v0.ledger import CallUncertain
    from scripts.research.generator_v0.derive import derive_complete_rounds,authorize_derived_continuation
    c=contexts or Contexts();base_dir=Path(base_dir)
    src=base_dir/'partial';src.mkdir(parents=True)
    faults={('RED_TEAM','C020',1):'crash',('GENERATOR',2,1):'invalid_card'}
    transport=NoisyTransport(c,faults)
    from scripts.research.generator_v0.derive import derived_config
    l=Ledger(src/'run.sqlite',derived_config('partial',{'SIZE':40,'CAP_MICRO_USD':CAP},c))
    try:run(c,l,transport)
    except Crash:pass
    try:run(c,l,transport)
    except CallUncertain:pass
    paused=l.get('status');source_total=l.total_charged_micro_usd();source_rows=len(l.export_calls())
    l.close()
    report=derive_complete_rounds(src,base_dir/'derived',3,c)
    authorize_derived_continuation(base_dir/'derived','offline-gate','continue after partial-work derive')
    t2=NoisyTransport(c,{})
    d=Ledger(base_dir/'derived'/'run.sqlite')
    result=run(c,d,t2)
    out={'SOURCE_STATUS':paused,'SOURCE_TOTAL_MICRO_USD':source_total,'SOURCE_ROWS':source_rows,
         'DERIVE_LINEAGE_PRIOR_MICRO_USD':report['LINEAGE_PRIOR_MICRO_USD'],'DERIVE_LINEAGE_TOTAL_MICRO_USD':report['LINEAGE_TOTAL_MICRO_USD'],
         'DERIVED_GENERATOR_POSTS':sum(1 for m,p in t2.log if m=='POST' and p=='/v1/responses'),'DERIVED_STATUS':result['STATUS'],
         'DERIVED_SPEND':result['SPEND'],'DERIVED_METRICS':result['METRICS'],'PRIOR_ATTEMPTS':report['PRIOR_ATTEMPT_COUNT']}
    d.close()
    return out
