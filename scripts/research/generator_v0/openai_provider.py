"""Concrete text-only adapter. No SDK retries, redirects, tools, or ambient enablement."""
from __future__ import annotations
import hashlib
import http.client
from decimal import ROUND_CEILING
from .context import ContractError,canonical,Contexts
from .schema import parse_json
from .output_schemas import openai_response_format,assert_structured_payload
from .models import model_for,request_params_for,rates,spec,ROLE_MODEL_MAP,routing_digest
from .provider import Response

OPENAI_REQUEST_TIMEOUT_SECONDS=600
TIMEOUT_MIN_SECONDS=1
TIMEOUT_MAX_SECONDS=1800

def bounded_timeout(value=None):
    if value is None:value=OPENAI_REQUEST_TIMEOUT_SECONDS
    if type(value)!=int or not TIMEOUT_MIN_SECONDS<=value<=TIMEOUT_MAX_SECONDS:
        raise ContractError('invalid request timeout')
    return value

class ProviderFailure(ContractError):
    def __init__(self,message,wire=b''):
        super().__init__(message);self.wire_sha256=hashlib.sha256(wire).hexdigest() if wire else None

class HTTPS:
    def __call__(self,body,headers,timeout):
        conn=http.client.HTTPSConnection('api.openai.com',timeout=timeout)
        try:
            conn.request('POST','/v1/chat/completions',body=body,headers=headers)
            response=conn.getresponse();wire=response.read(4_000_001)
            if len(wire)>4_000_000:raise ProviderFailure('oversized provider response',wire)
            return response.status,wire
        finally:conn.close()

class OpenAIProvider:
    provider_id='OPENAI_CHAT_COMPLETIONS'
    real=True
    def __init__(self,api_key,*,allow_real=False,budget_micro_usd=0,model=None,transport=None,contexts=None,timeout_seconds=None):
        if model not in (None,''):raise ContractError('role-specific model map is authoritative; do not pass --model')
        if not isinstance(api_key,str) or not api_key.strip():raise ContractError('OPENAI_API_KEY is required')
        if allow_real is not True or type(budget_micro_usd)!=int or not 0<budget_micro_usd<=30_000_000:
            raise ContractError('explicit allow-real-llm and nonzero budget <= USD 30 required')
        for role,name in ROLE_MODEL_MAP.items():spec(name);request_params_for(role)
        self._key=api_key;self._allow=allow_real;self.cap=budget_micro_usd
        self.request_timeout_seconds=bounded_timeout(timeout_seconds)
        self.model_id='ROLE_SPECIFIC';self.role_model_map=dict(ROLE_MODEL_MAP)
        self.routing_digest=routing_digest();self.transport=transport or HTTPS()
        self.contexts=contexts or Contexts()

    def model_for(self,role):return model_for(role)
    def request_params_for(self,role):return request_params_for(role)

    def payload(self,request):
        role=request['role'];params=request['parameters'];maxout=params.get('max_output_tokens')
        row=spec(self.model_for(role))
        if type(maxout)!=int or not 1<=maxout<=row['MAX_OUTPUT_TOKENS']:raise ContractError('output token bound')
        if set(params)-{'max_output_tokens','slots'}:raise ContractError('unknown provider parameters')
        user={'context':request['context']}
        if 'slots' in params:user['slots']=params['slots']
        extra=self.request_params_for(role)
        if 'temperature' in extra and 'reasoning_effort' in extra:raise ContractError('conflicting sampling parameters')
        body={'model':self.model_for(role),'messages':[{'role':'system','content':request['prompt']},{'role':'user','content':canonical(user)}],
              'response_format':openai_response_format(role,self.contexts),'max_completion_tokens':maxout,'n':1,'stream':False,'store':False,'service_tier':'default'}
        body.update(extra)
        if body.get('stream') or body.get('store') or 'tools' in body:raise ContractError('tools or streaming forbidden')
        return body

    def bounds(self,request):
        payload=self.payload(request)
        # Count the whole request, including the json_schema, as a conservative token upper bound.
        upper=len(canonical(payload).encode())+1024
        maxout=payload['max_completion_tokens']
        if upper+maxout>1_000_000:raise ContractError('request exceeds conservative context bound')
        return upper,maxout

    def bound(self,request):
        inp,out=self.bounds(request)
        input_rate,output_rate=rates(request['role'])
        return int((input_rate*inp+output_rate*out).to_integral_value(rounding=ROUND_CEILING))

    def complete(self,request):
        if not self._allow or not self._key or not 0<self.cap<=30_000_000:raise ContractError('real call disabled')
        bound=self.bound(request)
        if bound>self.cap:raise ContractError('call exceeds authorized budget')
        body=canonical(self.payload(request)).encode()
        status,wire=self.transport(body,{'Authorization':'Bearer '+self._key,'Content-Type':'application/json'},self.request_timeout_seconds)
        if status!=200:raise ProviderFailure('provider HTTP '+str(status),wire)
        try:
            payload=parse_json(wire.decode('utf-8'))
            choices=payload['choices'];usage=payload['usage']
            if len(choices)!=1 or choices[0]['finish_reason']!='stop':raise ValueError('incomplete completion')
            message=choices[0]['message'];raw=message['content']
            if message.get('refusal') or message.get('tool_calls') or not isinstance(raw,str):raise ValueError('not a text completion')
            parsed=parse_json(raw)
            normalized=assert_structured_payload(request['role'],self.contexts,parsed)
            inp,out=usage['prompt_tokens'],usage['completion_tokens'];maxin,maxout=self.bounds(request)
            if type(inp)!=int or type(out)!=int or not 0<=inp<=maxin or not 0<=out<=maxout:raise ValueError('usage outside bound')
            input_rate,output_rate=rates(request['role'])
            cost=int((input_rate*inp+output_rate*out).to_integral_value(rounding=ROUND_CEILING))
        except (KeyError,TypeError,ValueError,IndexError,UnicodeError,ContractError) as e:
            raise ProviderFailure('malformed or incomplete provider envelope',wire) from e
        return Response(canonical(normalized),usage,cost,hashlib.sha256(wire).hexdigest())
