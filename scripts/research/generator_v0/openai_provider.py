"""Mixed Chat Completions + background Responses adapter. No SDK retries or tools."""
from __future__ import annotations
import hashlib
import http.client
import time
from decimal import ROUND_CEILING
from .context import ContractError,canonical,Contexts,digest
from .schema import parse_json
from .output_schemas import openai_response_format,responses_text_format,assert_structured_payload,generator_schema_digest
from .models import model_for,request_params_for,rates,spec,ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,routing_digest,GENERATOR_MAX_OUTPUT_TOKENS
from .provider import Response,BackgroundPending

OPENAI_REQUEST_TIMEOUT_SECONDS=600
TIMEOUT_MIN_SECONDS=1
TIMEOUT_MAX_SECONDS=1800
CREATE_TIMEOUT_SECONDS=60
POLL_INTERVAL_SECONDS=3
POLL_GET_TIMEOUT_SECONDS=45
BACKGROUND_MAX_WAIT_SECONDS=3600
GENERATOR_ENDPOINT='RESPONSES'
CRITIC_ENDPOINT='CHAT_COMPLETIONS'
BACKGROUND_STORE_POLICY='STORE_TRUE_REQUIRED_FOR_RESUME'
# Official background guide (2026-09-23): after the ~10 minute polling window,
# a background Response is retained only if store=true is explicit. store=true
# is therefore required for crash-safe resume. After local COMPLETE persist,
# DELETE /v1/responses/{id} is a best-effort cleanup and must not fail the run.

def bounded_timeout(value=None):
    if value is None:value=OPENAI_REQUEST_TIMEOUT_SECONDS
    if type(value)!=int or not TIMEOUT_MIN_SECONDS<=value<=TIMEOUT_MAX_SECONDS:
        raise ContractError('invalid request timeout')
    return value

class ProviderFailure(ContractError):
    def __init__(self,message,wire=b'',envelope=None,http_status=None):
        super().__init__(message);self.wire_sha256=hashlib.sha256(wire).hexdigest() if wire else None
        self.envelope=envelope;self.http_status=http_status

class HTTPS:
    def __call__(self,method,path,body,headers,timeout):
        conn=http.client.HTTPSConnection('api.openai.com',timeout=timeout)
        try:
            conn.request(method,path,body=body or b'',headers=headers)
            response=conn.getresponse();wire=response.read(4_000_001)
            if len(wire)>4_000_000:raise ProviderFailure('oversized provider response',wire)
            return response.status,wire
        finally:conn.close()

class OpenAIProvider:
    provider_id='OPENAI_MIXED'
    real=True
    def __init__(self,api_key,*,allow_real=False,budget_micro_usd=0,model=None,transport=None,contexts=None,timeout_seconds=None,
                 create_timeout_seconds=CREATE_TIMEOUT_SECONDS,poll_interval_seconds=POLL_INTERVAL_SECONDS,
                 poll_get_timeout_seconds=POLL_GET_TIMEOUT_SECONDS,background_max_wait_seconds=BACKGROUND_MAX_WAIT_SECONDS,
                 sleeper=None,clock=None):
        if model not in (None,''):raise ContractError('role-specific model map is authoritative; do not pass --model')
        if not isinstance(api_key,str) or not api_key.strip():raise ContractError('OPENAI_API_KEY is required')
        if allow_real is not True or type(budget_micro_usd)!=int or not 0<budget_micro_usd<=30_000_000:
            raise ContractError('explicit allow-real-llm and nonzero budget <= USD 30 required')
        for role,name in ROLE_MODEL_MAP.items():spec(name);request_params_for(role)
        if type(create_timeout_seconds)!=int or not 1<=create_timeout_seconds<=TIMEOUT_MAX_SECONDS:raise ContractError('invalid create timeout')
        if type(poll_interval_seconds)!=int or not 2<=poll_interval_seconds<=5:raise ContractError('invalid poll interval')
        if type(poll_get_timeout_seconds)!=int or not 30<=poll_get_timeout_seconds<=60:raise ContractError('invalid poll GET timeout')
        if type(background_max_wait_seconds)!=int or not 1<=background_max_wait_seconds<=86400:raise ContractError('invalid background wait')
        self._key=api_key;self._allow=allow_real;self.cap=budget_micro_usd
        self.request_timeout_seconds=bounded_timeout(timeout_seconds)
        self.create_timeout_seconds=create_timeout_seconds
        self.poll_interval_seconds=poll_interval_seconds
        self.poll_get_timeout_seconds=poll_get_timeout_seconds
        self.background_max_wait_seconds=background_max_wait_seconds
        self._sleep=sleeper or time.sleep
        self._now=clock or time.monotonic
        self.model_id='ROLE_SPECIFIC';self.role_model_map=dict(ROLE_MODEL_MAP)
        self.contexts=contexts or Contexts()
        self.transport=transport or HTTPS()
        self.polling_policy={'INTERVAL_SECONDS':poll_interval_seconds,'GET_TIMEOUT_SECONDS':poll_get_timeout_seconds,'MAX_WAIT_SECONDS':background_max_wait_seconds,'CREATE_TIMEOUT_SECONDS':create_timeout_seconds}
        self.store_policy=BACKGROUND_STORE_POLICY
        self.routing_digest=self.identity_digest()

    def model_for(self,role):return model_for(role)
    def request_params_for(self,role):return request_params_for(role)
    def uses_background(self,role):return role=='GENERATOR'
    def endpoint_for(self,role):return 'OPENAI_RESPONSES' if role=='GENERATOR' else 'OPENAI_CHAT_COMPLETIONS'

    def transport_identity(self):
        return {
            'GENERATOR_ENDPOINT':GENERATOR_ENDPOINT,'GENERATOR_BACKGROUND':True,
            'GENERATOR_MODEL':ROLE_MODEL_MAP['GENERATOR'],
            'GENERATOR_REASONING_EFFORT':ROLE_REQUEST_PARAMS['GENERATOR']['reasoning_effort'],
            'GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST':generator_schema_digest(self.contexts),
            'BACKGROUND_STORE_POLICY':BACKGROUND_STORE_POLICY,
            'DELETE_AFTER_LOCAL_PERSIST':True,
            'POLLING_POLICY':self.polling_policy,
            'CRITIC_ENDPOINT':CRITIC_ENDPOINT,
            'GENERATOR_MAX_OUTPUT_TOKENS':GENERATOR_MAX_OUTPUT_TOKENS,
        }

    def identity_digest(self):
        return digest({'ROUTING':routing_digest(),'TRANSPORT':self.transport_identity()})

    def _headers(self):
        return {'Authorization':'Bearer '+self._key,'Content-Type':'application/json'}

    def _http(self,method,path,body,timeout):
        return self.transport(method,path,body,self._headers(),timeout)

    def chat_payload(self,request):
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

    def responses_payload(self,request):
        if request['role']!='GENERATOR':raise ContractError('Responses background is GENERATOR-only')
        params=request['parameters'];maxout=params.get('max_output_tokens')
        row=spec(self.model_for('GENERATOR'))
        if type(maxout)!=int or not 1<=maxout<=row['MAX_OUTPUT_TOKENS']:raise ContractError('output token bound')
        if set(params)-{'max_output_tokens','slots'}:raise ContractError('unknown provider parameters')
        user={'context':request['context']}
        if 'slots' in params:user['slots']=params['slots']
        effort=self.request_params_for('GENERATOR')['reasoning_effort']
        body={'model':self.model_for('GENERATOR'),'instructions':request['prompt'],'input':canonical(user),
              'background':True,'store':True,'stream':False,'service_tier':'default',
              'max_output_tokens':maxout,'reasoning':{'effort':effort},
              'text':{'format':responses_text_format('GENERATOR',self.contexts)}}
        if body.get('stream') or 'tools' in body or 'temperature' in body:raise ContractError('tools, streaming, or temperature forbidden')
        if body.get('store') is not True or body.get('background') is not True:raise ContractError('background store required')
        return body

    def payload(self,request):
        return self.responses_payload(request) if request['role']=='GENERATOR' else self.chat_payload(request)

    def bounds(self,request):
        payload=self.payload(request)
        upper=len(canonical(payload).encode())+1024
        maxout=payload.get('max_output_tokens') or payload.get('max_completion_tokens')
        if upper+maxout>1_000_000:raise ContractError('request exceeds conservative context bound')
        return upper,maxout

    def bound(self,request):
        inp,out=self.bounds(request)
        input_rate,output_rate=rates(request['role'])
        return int((input_rate*inp+output_rate*out).to_integral_value(rounding=ROUND_CEILING))

    def create_background(self,request):
        if not self._allow or not self._key or not 0<self.cap<=30_000_000:raise ContractError('real call disabled')
        body=canonical(self.responses_payload(request)).encode()
        status,wire=self._http('POST','/v1/responses',body,self.create_timeout_seconds)
        if status!=200:raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status)
        try:
            payload=parse_json(wire.decode('utf-8'));rid=payload['id'];st=payload['status']
            if not isinstance(rid,str) or not rid.strip():raise ValueError('missing response_id')
            if not isinstance(st,str):raise ValueError('missing status')
        except (KeyError,TypeError,ValueError,UnicodeError) as e:
            raise ProviderFailure('background create returned no usable response_id',wire) from e
        return {'response_id':rid,'provider_status':st,'store':True,'background':True,'poll_count':0}

    def retrieve_background(self,response_id):
        path='/v1/responses/'+response_id
        status,wire=self._http('GET',path,b'',self.poll_get_timeout_seconds)
        if status!=200:raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status)
        payload=parse_json(wire.decode('utf-8'))
        if payload.get('id')!=response_id:raise ProviderFailure('response_id mismatch',wire)
        return payload,wire

    def delete_background(self,response_id):
        try:
            self._http('DELETE','/v1/responses/'+response_id,b'',self.poll_get_timeout_seconds)
        except Exception:
            return

    def completed_cost(self,request,payload,wire):
        usage,cost,text=self._usage_cost(request,payload,require_text=True)
        return usage,cost,text,hashlib.sha256(wire).hexdigest()

    def terminal_usage_cost(self,request,payload):
        """Billable usage on a terminal non-completed Response. Does not parse output."""
        usage,cost,_=self._usage_cost(request,payload,require_text=False)
        return usage,cost

    def _usage_cost(self,request,payload,require_text=False):
        usage=payload['usage']
        inp=usage.get('input_tokens',usage.get('prompt_tokens'))
        out=usage.get('output_tokens',usage.get('completion_tokens'))
        maxin,maxout=self.bounds(request)
        if type(inp)!=int or type(out)!=int or not 0<=inp<=maxin or not 0<=out<=maxout:raise ValueError('usage outside bound')
        text=self._output_text(payload) if require_text else None
        input_rate,output_rate=rates(request['role'])
        cost=int((input_rate*inp+output_rate*out).to_integral_value(rounding=ROUND_CEILING))
        details=usage.get('output_tokens_details') or {}
        recorded={'input_tokens':inp,'output_tokens':out,'reasoning_tokens':details.get('reasoning_tokens')}
        return recorded,cost,text

    def _output_text(self,payload):
        text=payload.get('output_text')
        if isinstance(text,str) and text:return text
        chunks=[]
        for item in payload.get('output') or []:
            for part in item.get('content') or []:
                if part.get('type')=='output_text' and isinstance(part.get('text'),str):chunks.append(part['text'])
        if not chunks:raise ValueError('completed response had no output text')
        return ''.join(chunks)

    def complete(self,request):
        if request['role']=='GENERATOR':raise ContractError('GENERATOR uses background Responses, not synchronous complete')
        if not self._allow or not self._key or not 0<self.cap<=30_000_000:raise ContractError('real call disabled')
        bound=self.bound(request)
        if bound>self.cap:raise ContractError('call exceeds authorized budget')
        body=canonical(self.chat_payload(request)).encode()
        status,wire=self._http('POST','/v1/chat/completions',body,self.request_timeout_seconds)
        if status!=200:raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status)
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
