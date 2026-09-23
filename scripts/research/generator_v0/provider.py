"""Provider-neutral request/call journal. No network import or implicit provider."""
from dataclasses import dataclass
import hashlib
from typing import Protocol
from .context import ContractError, canonical, digest
from .schema import parse_json
from .output_schemas import assert_structured_payload

class BackgroundPending(ContractError):
    """Provider still queued/in_progress after the operator wait; resume the same response_id."""

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
        if type(self.cap)!=int or not 0<=self.cap<=30_000_000:raise ContractError('campaign cap')
        if provider.real and (not allow_real or self.cap<=0):raise ContractError('real calls not authorized')

    def call(self,role,context,prompt,parameters,slot):
        self.contexts.validate(role,context,prompt)
        if self.provider.real and (not self.allow_real or self.cap<=0):raise ContractError('real calls not authorized')
        endpoint=getattr(self.provider,'endpoint_for',lambda _role:self.provider.provider_id)(role)
        req={'role':role,'context':context,'prompt':prompt,'prompt_version':'generator-v0.1','parameters':parameters,'provider':endpoint,'model':self.provider.model_for(role),'slot':slot}
        extra=getattr(self.provider,'request_params_for',None)
        if extra is not None:req['model_request_params']=extra(role)
        key=digest(req);bound=self.provider.bound(req)
        saved=self.ledger.reserve(key,req,bound,self.cap)
        if saved is not None:
            if saved.get('_resume_background'):return self._await_background(key,req,saved)
            return saved['raw']
        uses=getattr(self.provider,'uses_background',lambda _role:False)
        if uses(role):
            try:
                created=self.provider.create_background(req)
                if not isinstance(created,dict) or not created.get('response_id'):
                    raise ContractError('background create returned no response_id')
                self.ledger.submit_background(key,{k:created[k] for k in created if not str(k).startswith('_')})
            except BackgroundPending:
                raise
            except Exception as e:
                self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None))
                raise
            return self._await_background(key,req,created)
        try:
            response=self.provider.complete(req)
            saved={'raw':response.raw,'raw_sha256':response.wire_sha256 or hashlib.sha256(response.raw.encode()).hexdigest()}
            self.ledger.finish(key,saved,response.cost_micro_usd,response.usage)
        except Exception as e:
            self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None))
            raise
        return response.raw

    def _await_background(self,key,req,tracker):
        rid=tracker['response_id'];p=self.provider
        deadline=p._now()+p.background_max_wait_seconds
        while True:
            try:
                payload,wire=p.retrieve_background(rid)
            except Exception as e:
                if _retryable(e):
                    if p._now()>=deadline:raise BackgroundPending('background generation still in progress; resume to continue polling')
                    p._sleep(p.poll_interval_seconds);continue
                self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None),state='FAILED',envelope={'response_id':rid,'provider_status':'retrieve_error'})
                raise
            st=payload.get('status')
            self.ledger.submit_background(key,{'response_id':rid,'provider_status':st,'store':True,'background':True})
            if st in ('queued','in_progress'):
                if p._now()>=deadline:raise BackgroundPending('background generation still in progress; resume to continue polling')
                p._sleep(p.poll_interval_seconds);continue
            if st=='completed':
                envelope={'response_id':rid,'provider_status':'completed','provider_envelope':payload}
                try:
                    usage,cost,text,sha=p.completed_cost(req,payload,wire)
                    saved={'raw':text,'raw_sha256':sha,**envelope}
                    self.ledger.finish(key,saved,cost,usage)
                except Exception as e:
                    self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None),state='FAILED',envelope=envelope)
                    raise
                p.delete_background(rid)
                parsed=parse_json(text)
                normalized=assert_structured_payload(req['role'],self.contexts,parsed)
                parsed_raw=canonical(normalized)
                self.ledger.attach_parsed(key,parsed_raw)
                return parsed_raw
            envelope={'response_id':rid,'provider_status':st,'provider_envelope':payload}
            usage=cost=None
            extract=getattr(p,'terminal_usage_cost',None)
            if extract is not None:
                try:usage,cost=extract(req,payload)
                except Exception:usage=cost=None
            self.ledger.failed(key,'background_'+str(st),hashlib.sha256(wire).hexdigest(),state='FAILED',envelope=envelope,cost=cost,usage=usage)
            raise ContractError('background generation '+str(st))

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
