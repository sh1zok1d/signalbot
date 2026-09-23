"""Concrete text-only adapter. No SDK retries, redirects, tools, or ambient enablement."""
from __future__ import annotations
import hashlib
import http.client
import json
from decimal import Decimal,ROUND_CEILING
from .context import ContractError,canonical
from .schema import parse_json
from .provider import Response

MODEL='gpt-4.1-mini-2025-04-14'
ENDPOINT='https://api.openai.com/v1/chat/completions'
# Standard uncached USD / million tokens, verified 2026-09-23.
INPUT_RATE=Decimal('0.40')
OUTPUT_RATE=Decimal('1.60')

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
    def __init__(self,api_key,*,allow_real=False,budget_micro_usd=0,model=MODEL,transport=None):
        if model!=MODEL:raise ContractError('model not in verified price/API configuration')
        if not isinstance(api_key,str) or not api_key.strip():raise ContractError('OPENAI_API_KEY is required')
        if allow_real is not True or type(budget_micro_usd)!=int or not 0<budget_micro_usd<=30_000_000:
            raise ContractError('explicit allow-real-llm and nonzero budget <= USD 30 required')
        self._key=api_key;self._allow=allow_real;self.cap=budget_micro_usd
        self.model_id=model;self.transport=transport or HTTPS()

    def payload(self,request):
        params=request['parameters'];maxout=params.get('max_output_tokens')
        if type(maxout)!=int or not 1<=maxout<=32768:raise ContractError('output token bound')
        if set(params)-{'max_output_tokens','slots'}:raise ContractError('unknown provider parameters')
        user={'context':request['context']}
        if 'slots' in params:user['slots']=params['slots']
        return {'model':self.model_id,'messages':[{'role':'system','content':request['prompt']},{'role':'user','content':canonical(user)}],
                'response_format':{'type':'json_object'},'temperature':0,'max_completion_tokens':maxout,'n':1,'stream':False,'store':False,'service_tier':'default'}

    def bounds(self,request):
        payload=self.payload(request)
        # Byte-level tokenization cannot exceed UTF-8 bytes for ordinary text.
        # Add 1024 tokens for message framing; reject oversized requests before HTTP.
        upper=sum(len(m['content'].encode()) for m in payload['messages'])+1024
        maxout=payload['max_completion_tokens']
        if upper+maxout>1_000_000:raise ContractError('request exceeds conservative context bound')
        return upper,maxout

    def bound(self,request):
        inp,out=self.bounds(request)
        return int((INPUT_RATE*inp+OUTPUT_RATE*out).to_integral_value(rounding=ROUND_CEILING))

    def complete(self,request):
        if not self._allow or not self._key or not 0<self.cap<=30_000_000:raise ContractError('real call disabled')
        bound=self.bound(request)
        if bound>self.cap:raise ContractError('call exceeds authorized budget')
        body=canonical(self.payload(request)).encode()
        status,wire=self.transport(body,{'Authorization':'Bearer '+self._key,'Content-Type':'application/json'},60)
        if status!=200:raise ProviderFailure('provider HTTP '+str(status),wire)
        try:
            payload=parse_json(wire.decode('utf-8'))
            choices=payload['choices'];usage=payload['usage']
            if len(choices)!=1 or choices[0]['finish_reason']!='stop':raise ValueError('incomplete completion')
            message=choices[0]['message'];raw=message['content']
            if message.get('refusal') or message.get('tool_calls') or not isinstance(raw,str):raise ValueError('not a text completion')
            inp,out=usage['prompt_tokens'],usage['completion_tokens'];maxin,maxout=self.bounds(request)
            if type(inp)!=int or type(out)!=int or not 0<=inp<=maxin or not 0<=out<=maxout:raise ValueError('usage outside bound')
            cost=int((INPUT_RATE*inp+OUTPUT_RATE*out).to_integral_value(rounding=ROUND_CEILING))
        except (KeyError,TypeError,ValueError,IndexError,UnicodeError) as e:
            raise ProviderFailure('malformed or incomplete provider envelope',wire) from e
        # Do not parse model JSON here: journal this paid response before schema checks.
        return Response(raw,usage,cost,hashlib.sha256(wire).hexdigest())
