"""Provider-neutral request/call journal. No network import or implicit provider.

Failure model (per attempt, never per campaign):
  NOT_BILLED  the provider did not run model work (429, 503, 4xx request errors).
              Charged 0. Retryable ones (429/503) back off and retry under a new
              transport-attempt key; others stop the campaign for an operator.
  BILLED      a completed, billed response that is unusable (length stop,
              refusal, malformed envelope). Charged its usage cost (or the
              reserved bound if usage is unknown). The consumer may retry once
              under a new content-attempt key.
  UNCERTAIN   genuinely unknown (timeout, connection loss, 5xx gateway errors,
              unusable create acknowledgement). Charged the reserved bound until
              an operator reconciles it (`reconcile`). Never replayed.
A COMPLETE attempt is returned from the journal and never POSTed again.

Dispatch: every attempt is committed DISPATCHED before the transport is called.
A crash before that leaves RESERVED (never sent; re-dispatched on resume). A
crash after it leaves DISPATCHED (possibly POSTed; pause for reconciliation).
A logical call (role, slot) closed by an UNKNOWN reconciliation raises
CallClosed without any POST, for every later content or transport attempt.

Resumable provider jobs (OpenAI background Responses, Anthropic Message Batches):
  RESERVED -> DISPATCHED -> BACKGROUND_SUBMITTED (PROVIDER_ACCEPTED: id journaled)
  -> polling that id only (POLLING) -> COMPLETE / FAILED_*.
After acceptance the call is never POSTed again; a poll that times out leaves it
BACKGROUND_SUBMITTED (PENDING) and a resume polls the same id. A Message Batch
also journals its custom_id with DISPATCHED, so a create whose acknowledgement is
lost (timeout, 5xx, process death) is found again in the provider listing
instead of becoming UNCERTAIN; a create that provably made no batch is closed
NOT_BILLED. errored / canceled / expired batch requests are NOT_BILLED.
"""
from dataclasses import dataclass
import hashlib
from typing import Protocol
from .context import ContractError, canonical, digest
from .schema import parse_json, normalize_role_output
from .ledger import AttemptClosed, BudgetExceeded, CallUncertain, InfrastructureStop, BILLED_CLOSED, NOT_BILLED_CLOSED
from . import contract

MAX_NEW_TRANSPORT_ATTEMPTS=3      # new NOT_BILLED retries per invocation
MAX_TRANSPORT_ATTEMPTS_TOTAL=12   # absolute attempt keys per logical call
BACKOFF_SECONDS=(2,8,30)
# Tracker fields kept across polls (Message Batches); OpenAI trackers have none of them.
TRACKER_KEEP=('custom_id','provider_object','created_at','dispatched_at','RECOVERED_FROM_LISTING')
_RETRY=object()

class BackgroundPending(InfrastructureStop):
    """Provider still queued/in_progress after the operator wait; resume the same response_id."""
class ProviderThrottled(InfrastructureStop):
    """Retryable not-billed failures persisted this invocation; resume later."""
class ProviderRejected(InfrastructureStop):
    """Non-retryable not-billed rejection (auth, request contract). Operator must fix."""
class BilledFailure(ContractError):
    """A billed attempt produced no usable content. Consumer decides on a content retry."""
class CallClosed(BilledFailure):
    """The logical call was closed by an evidence-free (UNKNOWN) reconciliation. Never POSTed again."""

class ProviderFailure(ContractError):
    def __init__(self,message,wire=b'',envelope=None,http_status=None,billing='UNCERTAIN',retryable=False,usage=None,cost=None):
        super().__init__(message);self.wire_sha256=hashlib.sha256(wire).hexdigest() if wire else None
        self.envelope=envelope;self.http_status=http_status
        if billing not in ('NOT_BILLED','BILLED','UNCERTAIN'):raise ValueError('billing class')
        self.billing=billing;self.retryable=retryable;self.usage=usage;self.cost=cost

def classify_http(status):
    """(billing, retryable) for a non-200 HTTP status from the provider."""
    if status in (429,503):return 'NOT_BILLED',True
    if status in (500,502,504) or status>=500:return 'UNCERTAIN',False
    return 'NOT_BILLED',False

@dataclass(frozen=True)
class Response:
    raw: str
    usage: dict
    cost_micro_usd: int
    wire_sha256: str = ''

class Provider(Protocol):
    provider_id: str
    model_id: str
    real: bool
    def model_for(self,role:str)->str: ...
    def bound(self,request:dict)->int: ...
    def complete(self,request:dict)->Response: ...

def _retryable(exc):
    if isinstance(exc,(TimeoutError,OSError)):return True
    status=getattr(exc,'http_status',None)
    return isinstance(status,int) and status>=500

class Caller:
    def __init__(self,contexts,ledger,provider,cap_micro_usd=0,allow_real=False):
        self.contexts,self.ledger,self.provider=contexts,ledger,provider
        self.cap,self.allow_real=cap_micro_usd,allow_real
        self.stats={'NEW_POSTS':0,'TRANSPORT_RETRIES':0,'NOT_BILLED':0,'BILLED_FAILURES':0,'UNCERTAIN':0}
        self.last_key=None
        if type(self.cap)!=int or not 0<=self.cap<=30_000_000:raise ContractError('campaign cap')
        if provider.real and (not allow_real or self.cap<=0):raise ContractError('real calls not authorized')

    def request(self,role,context,prompt,parameters,slot,content_attempt=0,identity=None):
        endpoint=getattr(self.provider,'endpoint_for',lambda _role:self.provider.provider_id)(role)
        req={'role':role,'context':context,'prompt':prompt,'prompt_version':contract.PROMPT_VERSION,'parameters':parameters,'provider':endpoint,'model':self.provider.model_for(role),'slot':slot}
        extra=getattr(self.provider,'request_params_for',None)
        if extra is not None:req['model_request_params']=extra(role)
        # Routed providers: the provider family and the role's route digest are part
        # of the request, hence of the call key (no cross-provider replay).
        family=getattr(self.provider,'provider_for',None)
        if family is not None:req['route_provider']=family(role);req['route_digest']=self.provider.route_digest_for(role)
        if identity:req.update(identity)
        # Provider-side output projection (wire format + its schema digest) is
        # part of the call key: a different projection is a different call.
        wire=getattr(self.provider,'wire_identity_for',None)
        if wire is not None:req.update(wire(role,req) or {})
        if content_attempt:req['content_attempt']=content_attempt
        return req

    def _sleep(self,n):
        sleep=getattr(self.provider,'_sleep',None)
        if sleep is not None:sleep(BACKOFF_SECONDS[min(n,len(BACKOFF_SECONDS)-1)])

    def call(self,role,context,prompt,parameters,slot,content_attempt=0,identity=None):
        self.contexts.validate(role,context,prompt)
        if self.provider.real and (not self.allow_real or self.cap<=0):raise ContractError('real calls not authorized')
        closed=self.ledger.logical_call_closed(str(role)+'|'+str(slot))
        if closed:raise CallClosed('logical call closed without evidence ('+closed['CALL_KEY']+'); not POSTed again')
        base=self.request(role,context,prompt,parameters,slot,content_attempt,identity)
        bound=self.provider.bound(base)
        new_attempts=0
        for t in range(MAX_TRANSPORT_ATTEMPTS_TOTAL):
            req=base if t==0 else {**base,'transport_attempt':t}
            key=digest(req);self.last_key=key
            if self.ledger.call_state(key) is None and new_attempts>=MAX_NEW_TRANSPORT_ATTEMPTS:
                raise ProviderThrottled('provider kept refusing without billing; resume later')
            try:saved=self.ledger.reserve(key,req,bound,self.cap)
            except AttemptClosed as closed:
                if closed.state in NOT_BILLED_CLOSED:continue
                raise BilledFailure('billed attempt without usable content ('+closed.state+')')
            if saved is not None:
                if saved.get('_resume_background') or saved.get('_recover_background'):
                    resumed=saved
                    out=self._settle(key,lambda:self._recover_background(key,req,resumed) if resumed.get('_recover_background') else self._await_background(key,req,resumed))
                    if out is _RETRY:self._sleep(0);continue
                    return out
                return saved['raw']
            new_attempts+=1;self.stats['NEW_POSTS']+=1
            if t:self.stats['TRANSPORT_RETRIES']+=1
            intent=self._intent(key,role)
            if intent is None:self.ledger.mark_dispatched(key)
            else:self.ledger.mark_dispatched(key,intent)
            try:
                return self._post(key,req,role,intent)
            except ProviderFailure as e:
                if e.billing=='NOT_BILLED':
                    self._not_billed(key,e)
                    if not e.retryable:raise ProviderRejected('provider rejected the request without billing: '+str(e)) from e
                    self._sleep(new_attempts-1);continue
                if e.billing=='BILLED':
                    self.stats['BILLED_FAILURES']+=1
                    self.ledger.failed(key,type(e).__name__+': '+str(e),e.wire_sha256,state='FAILED_WITH_COST',envelope=e.envelope,cost=e.cost,usage=e.usage)
                    raise BilledFailure(str(e)) from e
                if intent is not None and self.ledger.call_state(key)=='DISPATCHED':
                    # The create acknowledgement is unknown: find the job by custom_id, never re-POST.
                    out=self._settle(key,lambda:self._recover_background(key,req,intent))
                    if out is _RETRY:self._sleep(new_attempts-1);continue
                    return out
                self.stats['UNCERTAIN']+=1
                self.ledger.failed(key,type(e).__name__+': '+str(e),e.wire_sha256,state='UNCERTAIN',envelope=e.envelope)
                raise CallUncertain('provider outcome uncertain; reconcile '+key) from e
            except (InfrastructureStop,BilledFailure):
                raise
            except Exception as e:
                # A row already closed (e.g. billed cost outside the bound, charged at the
                # reservation) keeps its state; the integrity error surfaces unchanged.
                state=self.ledger.call_state(key)
                if state not in ('RESERVED','DISPATCHED','BACKGROUND_SUBMITTED'):raise
                if intent is not None and state=='DISPATCHED':
                    out=self._settle(key,lambda:self._recover_background(key,req,intent))
                    if out is _RETRY:self._sleep(new_attempts-1);continue
                    return out
                # Unknown local/transport failure after reservation: never assume unbilled.
                self.stats['UNCERTAIN']+=1
                self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None),state='UNCERTAIN')
                raise CallUncertain('provider outcome uncertain; reconcile '+key) from e
        raise ProviderThrottled('attempt keys exhausted for this logical call')

    def _bg(self,role):
        """The adapter view that runs this role's provider jobs (routed: per role)."""
        fn=getattr(self.provider,'background_for',None)
        return fn(role) if fn is not None else self.provider

    def _intent(self,key,role):
        """Recovery intent journaled with DISPATCHED (Message Batches only), else None."""
        if not getattr(self.provider,'uses_background',lambda _role:False)(role):return None
        fn=getattr(self._bg(role),'dispatch_intent',None)
        return fn(key,(self.ledger.get('config') or {}).get('RUN_ID')) if fn is not None else None

    def _not_billed(self,key,e):
        self.stats['NOT_BILLED']+=1
        self.ledger.failed(key,type(e).__name__+': '+str(e),e.wire_sha256,state='FAILED_NOT_BILLED',envelope=e.envelope)

    def _settle(self,key,run):
        """run() for a provider job. A not-billed terminal outcome closes the attempt
        FAILED_NOT_BILLED and returns _RETRY (retryable) or raises ProviderRejected."""
        try:
            return run()
        except ProviderFailure as e:
            if e.billing!='NOT_BILLED':raise
            self._not_billed(key,e)
            if not e.retryable:raise ProviderRejected('provider did not run the request: '+str(e)) from e
            return _RETRY

    def _accepted(self,key,req,tracker):
        """PROVIDER_ACCEPTED is journaled; checkpoint the journal externally where configured."""
        if getattr(self._bg(req['role']),'checkpoint_on_accept',False):
            self.ledger.checkpoint('PROVIDER_ACCEPTED',{'ROLE':req['role'],'SLOT':req.get('slot'),'CALL_KEY':key,'PROVIDER_ID':tracker['response_id']})

    def _post(self,key,req,role,intent=None):
        uses=getattr(self.provider,'uses_background',lambda _role:False)
        if uses(role):
            created=self.provider.create_background(req) if intent is None else self.provider.create_background(req,custom_id=intent['custom_id'])
            if not isinstance(created,dict) or not created.get('response_id'):
                raise ProviderFailure('background create returned no response_id')
            tracker={k:created[k] for k in created if not str(k).startswith('_')}
            if intent is not None:tracker['dispatched_at']=intent['dispatched_at']
            self.ledger.submit_background(key,tracker)
            self._accepted(key,req,tracker)
            return self._await_background(key,req,tracker)
        response=self.provider.complete(req)
        saved={'raw':response.raw,'raw_sha256':hashlib.sha256(response.raw.encode('utf-8')).hexdigest()}
        if response.wire_sha256:saved['wire_sha256']=response.wire_sha256
        self.ledger.finish(key,saved,response.cost_micro_usd,response.usage)
        return response.raw

    def _await_background(self,key,req,tracker):
        rid=tracker['response_id'];p=self._bg(req['role'])
        # Poll pacing is separate from transport-retry backoff (provider._sleep) where a
        # provider offers it, so a guard that refuses replay backoff cannot stop polling.
        sleep=getattr(p,'_poll_sleep',None) or p._sleep
        deadline=p._now()+p.background_max_wait_seconds
        keep={k:tracker[k] for k in TRACKER_KEEP if k in tracker}
        tracked=getattr(p,'retrieve_tracked',None)
        while True:
            try:
                payload,wire=tracked(tracker) if tracked is not None else p.retrieve_background(rid)
            except InfrastructureStop:
                raise
            except Exception as e:
                if _retryable(e) or getattr(e,'retryable',False):
                    if p._now()>=deadline:raise BackgroundPending('background generation still in progress; resume to continue polling')
                    sleep(p.poll_interval_seconds);continue
                # The response exists but its outcome is unknown: reconcile with the response_id.
                self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None),state='UNCERTAIN',envelope={**keep,'response_id':rid,'provider_status':'retrieve_error'})
                raise CallUncertain('background retrieve failed; reconcile '+key) from e
            st=payload.get('status')
            poll={'response_id':rid,'provider_status':st,'store':True,'background':True} if not keep else {**keep,'response_id':rid,'provider_status':st}
            self.ledger.submit_background(key,poll)
            if st in ('queued','in_progress'):
                if p._now()>=deadline:raise BackgroundPending('background generation still in progress; resume to continue polling')
                sleep(p.poll_interval_seconds);continue
            envelope={'response_id':rid,'provider_status':st,'provider_envelope':payload}
            if st=='completed':
                try:
                    usage,cost,text,sha=p.completed_cost(req,payload,wire)
                except Exception as e:
                    usage=cost=None
                    try:usage,cost=p.terminal_usage_cost(req,payload)
                    except Exception:usage=cost=None
                    self.ledger.failed(key,type(e).__name__,hashlib.sha256(wire).hexdigest(),state='FAILED_WITH_COST',envelope=envelope,cost=cost,usage=usage)
                    raise BilledFailure('completed response without usable text') from e
                # raw is the verbatim model text and raw_sha256 its hash; wire_sha256 hashes
                # the provider envelope. Nothing rewrites raw afterwards.
                self.ledger.finish(key,{'raw':text,'raw_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),'wire_sha256':sha,**envelope},cost,usage)
                p.delete_background(rid)
                return text
            not_billed=getattr(p,'terminal_not_billed',None)
            outcome=not_billed(req,payload) if not_billed is not None else None
            if outcome is not None:
                # Documented not-billed provider outcome (Message Batches errored/canceled/expired).
                raise ProviderFailure(outcome['DETAIL'],wire,envelope={**keep,**envelope},billing='NOT_BILLED',retryable=outcome['RETRYABLE'])
            usage=cost=None
            extract=getattr(p,'terminal_usage_cost',None)
            if extract is not None:
                try:usage,cost=extract(req,payload)
                except Exception:usage=cost=None
            self.ledger.failed(key,'background_'+str(st),hashlib.sha256(wire).hexdigest(),state='FAILED_WITH_COST',envelope=envelope,cost=cost,usage=usage)
            raise BilledFailure('background generation '+str(st))

    def _recover_background(self,key,req,intent):
        """A DISPATCHED provider job whose create acknowledgement was lost: search the provider
        listing by custom_id until found (then poll it), proven absent (NOT_BILLED), or the wait
        ends (PENDING; a resume searches again). Never POSTs."""
        p=self._bg(req['role']);find=getattr(p,'find_background',None)
        if find is None:raise CallUncertain('no provider listing to recover '+key+'; reconcile it')
        intent={k:v for k,v in intent.items() if not str(k).startswith('_')}
        sleep=getattr(p,'_poll_sleep',None) or p._sleep
        deadline=p._now()+p.background_max_wait_seconds
        pending='create acknowledgement lost; resume continues the search for custom_id '+str(intent.get('custom_id'))
        while True:
            try:
                found=find(intent)
            except InfrastructureStop:
                raise
            except Exception as e:
                if not (_retryable(e) or getattr(e,'retryable',False)):raise
                if p._now()>=deadline:raise BackgroundPending(pending) from e
                sleep(p.poll_interval_seconds);continue
            if found['STATE']=='FOUND':
                tracker={**found['TRACKER'],'dispatched_at':intent['dispatched_at']}
                self.ledger.submit_background(key,tracker)
                with self.ledger.transaction():
                    self.ledger.event('PROVIDER_JOB_RECOVERED',{'CALL_KEY':key,'PROVIDER_ID':tracker['response_id'],'CUSTOM_ID':intent['custom_id']})
                self._accepted(key,req,tracker)
                return self._await_background(key,req,tracker)
            if found['STATE']=='ABSENT':
                raise ProviderFailure('create was not accepted: no provider job carries this custom_id',
                                      envelope={**intent,'RECOVERY_EVIDENCE':found['EVIDENCE']},billing='NOT_BILLED',retryable=True)
            if p._now()>=deadline:raise BackgroundPending(pending+' ('+str(found.get('DETAIL'))+')')
            sleep(p.poll_interval_seconds)

class MockProvider:
    provider_id='MOCK_DETERMINISTIC'
    model_id='fixture-v1'
    real=False
    def __init__(self,responder=None):self.responder=responder;self.calls=0
    def model_for(self,role):return self.model_id
    def request_params_for(self,role):return {}
    def bound(self,request):return 0
    def uses_background(self,role):return False
    def endpoint_for(self,role):return self.provider_id
    def complete(self,request):
        if self.responder is None:raise ContractError('mock responder not configured')
        self.calls+=1
        return Response(self.responder(request),{'input_tokens':0,'output_tokens':0},0)
