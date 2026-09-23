"""Provider-neutral request/call journal. No network import or implicit provider."""
from dataclasses import dataclass
import hashlib
from typing import Protocol
from .context import ContractError, digest

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
    def bound(self,request:dict)->int: ...
    def complete(self,request:dict)->Response: ...

class Caller:
    def __init__(self,contexts,ledger,provider,cap_micro_usd=0,allow_real=False):
        self.contexts,self.ledger,self.provider=contexts,ledger,provider
        self.cap,self.allow_real=cap_micro_usd,allow_real
        if type(self.cap)!=int or not 0<=self.cap<=30_000_000:raise ContractError('campaign cap')
        if provider.real and (not allow_real or self.cap<=0):raise ContractError('real calls not authorized')

    def call(self,role,context,prompt,parameters,slot):
        self.contexts.validate(role,context,prompt)
        if self.provider.real and (not self.allow_real or self.cap<=0):raise ContractError('real calls not authorized')
        req={'role':role,'context':context,'prompt':prompt,'prompt_version':'generator-v0.1','parameters':parameters,'provider':self.provider.provider_id,'model':self.provider.model_id,'slot':slot}
        key=digest(req);bound=self.provider.bound(req)
        saved=self.ledger.reserve(key,req,bound,self.cap)
        if saved is not None:return saved['raw']
        try:
            response=self.provider.complete(req)
            saved={'raw':response.raw,'raw_sha256':response.wire_sha256 or hashlib.sha256(response.raw.encode()).hexdigest()}
            self.ledger.finish(key,saved,response.cost_micro_usd,response.usage)
        except Exception as e:
            self.ledger.failed(key,type(e).__name__,getattr(e,'wire_sha256',None))
            raise
        return response.raw

class MockProvider:
    provider_id='MOCK_DETERMINISTIC'
    model_id='fixture-v1'
    real=False
    def __init__(self,responder=None):self.responder=responder;self.calls=0
    def bound(self,request):return 0
    def complete(self,request):
        if self.responder is None:raise ContractError('mock responder not configured')
        self.calls+=1
        return Response(self.responder(request),{'input_tokens':0,'output_tokens':0},0)
