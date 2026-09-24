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
                if saved.get('_resume_background'):return self._await_background(key,req,saved)
                return saved['raw']
            new_attempts+=1;self.stats['NEW_POSTS']+=1
            if t:self.stats['TRANSPORT_RETRIES']+=1
            self.ledger.mark_dispatched(key)
            try:
                return self._post(key,req,role)
            except ProviderFailure as e:
                if e.billing=='NOT_BILLED':
                    self.stats['NOT_BILLED']+=1
                    self.ledger.failed(key,type(e).__name__+': '+str(e),e.wire_sha256,state='FAILED_NOT_BILLED')
                    if not e.retryable:raise ProviderRejected('provider rejected the request without billing: '+str(e)) from e
                    self._sleep(new_attempts-1);continue
                if e.billing=='BILLED':
                    self.stats['BILLED_FAILURES']+=1
                    self.ledger.failed(key,type(e).__name__+': '+str(e),e.wire_sha256,state='FAILED_WITH_COST',envelope=e.envelope,cost=e.cost,usage=e.usage)
                    raise BilledFailure(str(e)) from e
                self.stats['UNCERTAIN']+=1
                self.ledger.failed(key,type(e).__name__+': '+str(e),e.wire_sha256,state='UNCERTAIN',envelope=e.envelope)
                raise CallUncertain('provider outcome uncertain; reconcile '+key) from e
            except (InfrastructureStop,BilledFailure):
                raise
            except Exception as e:
                # A row already closed (e.g. billed cost outside the bound, charged at the
                # reservation) keeps its state; the integrity error surfaces unchanged.
                if self.ledger.call_state(key) not in ('RESERVED','DISPATCHED','BACKGROUND_SUBMITTED'):raise
                # Unknown local/transport failure after reservation: never assume unbilled.
                self.stats['UNCERTAIN']+=1
                self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None),state='UNCERTAIN')
                raise CallUncertain('provider outcome uncertain; reconcile '+key) from e
        raise ProviderThrottled('attempt keys exhausted for this logical call')

    def _post(self,key,req,role):
        uses=getattr(self.provider,'uses_background',lambda _role:False)
        if uses(role):
            created=self.provider.create_background(req)
            if not isinstance(created,dict) or not created.get('response_id'):
                raise ProviderFailure('background create returned no response_id')
            self.ledger.submit_background(key,{k:created[k] for k in created if not str(k).startswith('_')})
            return self._await_background(key,req,created)
        response=self.provider.complete(req)
        saved={'raw':response.raw,'raw_sha256':hashlib.sha256(response.raw.encode('utf-8')).hexdigest()}
        if response.wire_sha256:saved['wire_sha256']=response.wire_sha256
        self.ledger.finish(key,saved,response.cost_micro_usd,response.usage)
        return response.raw

    def _await_background(self,key,req,tracker):
        rid=tracker['response_id'];p=self.provider
        deadline=p._now()+p.background_max_wait_seconds
        while True:
            try:
                payload,wire=p.retrieve_background(rid)
            except Exception as e:
                if _retryable(e) or getattr(e,'retryable',False):
                    if p._now()>=deadline:raise BackgroundPending('background generation still in progress; resume to continue polling')
                    p._sleep(p.poll_interval_seconds);continue
                # The response exists but its outcome is unknown: reconcile with the response_id.
                self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None),state='UNCERTAIN',envelope={'response_id':rid,'provider_status':'retrieve_error'})
                raise CallUncertain('background retrieve failed; reconcile '+key) from e
            st=payload.get('status')
            self.ledger.submit_background(key,{'response_id':rid,'provider_status':st,'store':True,'background':True})
            if st in ('queued','in_progress'):
                if p._now()>=deadline:raise BackgroundPending('background generation still in progress; resume to continue polling')
                p._sleep(p.poll_interval_seconds);continue
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
            usage=cost=None
            extract=getattr(p,'terminal_usage_cost',None)
            if extract is not None:
                try:usage,cost=extract(req,payload)
                except Exception:usage=cost=None
            self.ledger.failed(key,'background_'+str(st),hashlib.sha256(wire).hexdigest(),state='FAILED_WITH_COST',envelope=envelope,cost=cost,usage=usage)
            raise BilledFailure('background generation '+str(st))

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
