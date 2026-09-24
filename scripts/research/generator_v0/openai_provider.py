"""Mixed Chat Completions + background Responses adapter. No SDK retries or tools."""
from __future__ import annotations
import hashlib
import http.client
import time
from decimal import ROUND_CEILING
from .context import ContractError,canonical,Contexts,digest
from .schema import parse_json
from .output_schemas import openai_response_format,responses_text_format,generator_schema_digest
from .schema import normalize_role_output
from .models import model_for,request_params_for,rates,spec,ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,routing_digest,GENERATOR_MAX_OUTPUT_TOKENS
from .provider import Response,BackgroundPending,ProviderFailure,classify_http

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
OPENAI_NETWORK_MODE_DIRECT='DIRECT'
OPENAI_NETWORK_MODE_CLOUD_PROXY='CLOUD_PROXY'
OPENAI_NETWORK_MODES=(OPENAI_NETWORK_MODE_DIRECT,OPENAI_NETWORK_MODE_CLOUD_PROXY)
# Official background guide (2026-09-23): after the ~10 minute polling window,
# a background Response is retained only if store=true is explicit. store=true
# is therefore required for crash-safe resume. After local COMPLETE persist,
# DELETE /v1/responses/{id} is a best-effort cleanup and must not fail the run.

def bounded_timeout(value=None):
    if value is None:value=OPENAI_REQUEST_TIMEOUT_SECONDS
    if type(value)!=int or not TIMEOUT_MIN_SECONDS<=value<=TIMEOUT_MAX_SECONDS:
        raise ContractError('invalid request timeout')
    return value

def strip_reasoning(payload):
    """Responses envelope without reasoning-item content (summaries, encrypted
    content). Only the item type and id survive; hidden reasoning is never
    journaled. wire_sha256 still hashes the untouched provider bytes."""
    if not isinstance(payload,dict) or not isinstance(payload.get('output'),list):return payload
    out=[{k:v for k,v in item.items() if k in ('type','id')} if isinstance(item,dict) and item.get('type')=='reasoning' else item
         for item in payload['output']]
    return {**payload,'output':out}

class HTTPS:
    def __call__(self,method,path,body,headers,timeout):
        conn=http.client.HTTPSConnection('api.openai.com',timeout=timeout)
        try:
            conn.request(method,path,body=body or b'',headers=headers)
            response=conn.getresponse();wire=response.read(4_000_001)
            if len(wire)>4_000_000:raise ProviderFailure('oversized provider response',wire,billing='UNCERTAIN')
            return response.status,wire
        finally:conn.close()

class OpenAIProvider:
    provider_id='OPENAI_MIXED'
    real=True
    def __init__(self,api_key,*,allow_real=False,budget_micro_usd=0,model=None,transport=None,contexts=None,timeout_seconds=None,
                 create_timeout_seconds=CREATE_TIMEOUT_SECONDS,poll_interval_seconds=POLL_INTERVAL_SECONDS,
                 poll_get_timeout_seconds=POLL_GET_TIMEOUT_SECONDS,background_max_wait_seconds=BACKGROUND_MAX_WAIT_SECONDS,
                 sleeper=None,clock=None,routes=None,offline=False,network_mode=OPENAI_NETWORK_MODE_DIRECT):
        """routes: the multi-provider routing registry (routing.ROUTES). When given,
        this adapter serves only the roles routed to OPENAI, with the registry's
        model, effort and prices (Chat Completions only, never GENERATOR).
        Without routes it is the legacy OpenAI-only provider (models.ROLE_MODEL_MAP).
        offline=True (routed only) builds a bound-only adapter that never sends."""
        if model not in (None,''):raise ContractError('role-specific model map is authoritative; do not pass --model')
        self._routes=None
        if routes is not None:
            from . import routing
            self._routes={r:v for r,v in routing.validate_routes(routes).items() if v['PROVIDER']=='OPENAI'}
            if 'GENERATOR' in self._routes:raise ContractError('routed OpenAI adapter does not serve GENERATOR')
            for role,v in self._routes.items():
                row=spec(v['MODEL'])
                if v['PARAMS'].get('reasoning_effort') not in row['REASONING_EFFORTS']:raise ContractError('unsupported reasoning_effort for model')
                price=routing.PRICES[v['MODEL']]
                if (price['INPUT'],price['OUTPUT'])!=(row['INPUT_RATE'],row['OUTPUT_RATE']):raise ContractError('routing price differs from verified model price')
        elif offline:
            raise ContractError('offline adapter requires routes')
        self._offline=offline is True
        if network_mode not in OPENAI_NETWORK_MODES:raise ContractError('unknown OpenAI network mode')
        self.network_mode=network_mode
        if self.network_mode==OPENAI_NETWORK_MODE_CLOUD_PROXY:
            from .cloud_openai_transport import CloudProxyOpenAITransport
            if transport is None:transport=CloudProxyOpenAITransport()
            elif not isinstance(transport,CloudProxyOpenAITransport):raise ContractError('CLOUD_PROXY requires CloudProxyOpenAITransport')
        if not self._offline:
            cloud=self.network_mode==OPENAI_NETWORK_MODE_CLOUD_PROXY
            if cloud:
                if api_key is None or (isinstance(api_key,str) and not api_key.strip()):api_key=None
                elif not isinstance(api_key,str):raise ContractError('OPENAI_API_KEY must be a string when provided')
            elif not isinstance(api_key,str) or not api_key.strip():raise ContractError('OPENAI_API_KEY is required')
            if allow_real is not True or type(budget_micro_usd)!=int or not 0<budget_micro_usd<=30_000_000:
                raise ContractError('explicit allow-real-llm and nonzero budget <= USD 30 required')
        if self._routes is None:
            for role,name in ROLE_MODEL_MAP.items():spec(name);request_params_for(role)
        if type(create_timeout_seconds)!=int or not 1<=create_timeout_seconds<=TIMEOUT_MAX_SECONDS:raise ContractError('invalid create timeout')
        if type(poll_interval_seconds)!=int or not 2<=poll_interval_seconds<=5:raise ContractError('invalid poll interval')
        if type(poll_get_timeout_seconds)!=int or not 30<=poll_get_timeout_seconds<=60:raise ContractError('invalid poll GET timeout')
        if type(background_max_wait_seconds)!=int or not 1<=background_max_wait_seconds<=86400:raise ContractError('invalid background wait')
        self._key=None if self._offline or api_key is None else api_key;self._allow=allow_real is True and not self._offline;self.cap=budget_micro_usd
        self.request_timeout_seconds=bounded_timeout(timeout_seconds)
        self.create_timeout_seconds=create_timeout_seconds
        self.poll_interval_seconds=poll_interval_seconds
        self.poll_get_timeout_seconds=poll_get_timeout_seconds
        self.background_max_wait_seconds=background_max_wait_seconds
        self._sleep=sleeper or time.sleep
        self._now=clock or time.monotonic
        self.model_id='ROLE_SPECIFIC'
        self.role_model_map=dict(ROLE_MODEL_MAP) if self._routes is None else {r:v['MODEL'] for r,v in self._routes.items()}
        self.contexts=contexts or Contexts()
        self.transport=transport or HTTPS()
        self.polling_policy={'INTERVAL_SECONDS':poll_interval_seconds,'GET_TIMEOUT_SECONDS':poll_get_timeout_seconds,'MAX_WAIT_SECONDS':background_max_wait_seconds,'CREATE_TIMEOUT_SECONDS':create_timeout_seconds}
        self.store_policy=BACKGROUND_STORE_POLICY
        self.routing_digest=self.identity_digest()

    def _route(self,role):
        if role not in self._routes:raise ContractError('role is not routed to OpenAI: '+str(role))
        return self._routes[role]
    def roles(self):return tuple(sorted(self._routes if self._routes is not None else ROLE_MODEL_MAP))
    def model_for(self,role):
        if self._routes is not None:return self._route(role)['MODEL']
        return model_for(role)
    def request_params_for(self,role):
        if self._routes is not None:return dict(self._route(role)['PARAMS'])
        return request_params_for(role)
    def uses_background(self,role):
        if self._routes is not None:
            from . import routing
            return self._route(role)['ENDPOINT'] in routing.BACKGROUND_ENDPOINTS
        return role=='GENERATOR'
    def endpoint_for(self,role):
        if self._routes is not None:return self._route(role)['ENDPOINT']
        return 'OPENAI_RESPONSES' if role=='GENERATOR' else 'OPENAI_CHAT_COMPLETIONS'
    def _rates(self,role):
        if self._routes is not None:
            from . import routing
            p=routing.PRICES[self._route(role)['MODEL']];return p['INPUT'],p['OUTPUT']
        return rates(role)

    def transport_identity(self):
        if self._routes is not None:
            ident={'ADAPTER':'OPENAI_CHAT_COMPLETIONS_DIRECT_HTTP','CRITIC_ENDPOINT':CRITIC_ENDPOINT,'STORE':False,'STREAM':False,
                    'SERVICE_TIER':'default','SDK_RETRIES':False,'REQUEST_TIMEOUT_SECONDS':self.request_timeout_seconds,
                    'BACKGROUND_ROLES':sorted(r for r in self._routes if self.uses_background(r)),
                    'BACKGROUND':{'ENDPOINT':'RESPONSES','STORE_POLICY':BACKGROUND_STORE_POLICY,'DELETE_AFTER_LOCAL_PERSIST':True,
                                  'POLLING_POLICY':self.polling_policy,'CREATE_REPLAY':False,'REASONING_ITEMS_PERSISTED':False},
                    'ROLES':{r:{'MODEL':v['MODEL'],'PARAMS':v['PARAMS'],'MAX_OUTPUT_TOKENS':v['MAX_OUTPUT_TOKENS'],'STRUCTURED_OUTPUT':v['STRUCTURED_OUTPUT']} for r,v in sorted(self._routes.items())}}
            return self._annotate_network(ident)
        ident={
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
        return self._annotate_network(ident)

    def _annotate_network(self,ident):
        if self.network_mode!=OPENAI_NETWORK_MODE_CLOUD_PROXY:return ident
        return {**ident,'OPENAI_NETWORK_MODE':OPENAI_NETWORK_MODE_CLOUD_PROXY,'OPENAI_API_KEY_REQUIRED':False,
                'AUTHORIZATION':'STRIPPED_AT_PROXY_BOUNDARY','DIRECT_API_HOST':False}

    def _can_send(self):
        if self._offline or not self._allow or type(self.cap)!=int or not 0<self.cap<=30_000_000:return False
        if self.network_mode==OPENAI_NETWORK_MODE_CLOUD_PROXY:
            from .cloud_openai_transport import CloudProxyOpenAITransport
            return isinstance(self.transport,CloudProxyOpenAITransport)
        return bool(self._key)

    def identity_digest(self):
        if self._routes is not None:
            from . import routing
            return digest({'ROUTING':routing.routing_digest(),'TRANSPORT':self.transport_identity()})
        return digest({'ROUTING':routing_digest(),'TRANSPORT':self.transport_identity()})

    def _headers(self):
        headers={'Content-Type':'application/json'}
        if self._key:headers['Authorization']='Bearer '+self._key
        return headers

    def _http(self,method,path,body,timeout):
        return self.transport(method,path,body,self._headers(),timeout)

    def chat_payload(self,request):
        role=request['role'];params=request['parameters'];maxout=params.get('max_output_tokens')
        row=spec(self.model_for(role))
        if type(maxout)!=int or not 1<=maxout<=row['MAX_OUTPUT_TOKENS']:raise ContractError('output token bound')
        if set(params)-{'max_output_tokens','slots'}:raise ContractError('unknown provider parameters')
        if self._routes is not None and maxout!=self._route(role)['MAX_OUTPUT_TOKENS']:raise ContractError('output token cap differs from the route')
        user={'context':request['context']}
        if 'slots' in params:user['slots']=params['slots']
        extra=self.request_params_for(role)
        if 'temperature' in extra and 'reasoning_effort' in extra:raise ContractError('conflicting sampling parameters')
        body={'model':self.model_for(role),'messages':[{'role':'system','content':request['prompt']},{'role':'user','content':canonical(user)}],
              'response_format':openai_response_format(role,self.contexts,request),'max_completion_tokens':maxout,'n':1,'stream':False,'store':False,'service_tier':'default'}
        body.update(extra)
        if body.get('stream') or body.get('store') or 'tools' in body:raise ContractError('tools or streaming forbidden')
        return body

    def responses_payload(self,request):
        role=request['role']
        if self._routes is None and role!='GENERATOR':raise ContractError('Responses background is GENERATOR-only')
        if self._routes is not None and not self.uses_background(role):raise ContractError('role is not routed to background Responses: '+str(role))
        params=request['parameters'];maxout=params.get('max_output_tokens')
        row=spec(self.model_for(role))
        if type(maxout)!=int or not 1<=maxout<=row['MAX_OUTPUT_TOKENS']:raise ContractError('output token bound')
        if set(params)-{'max_output_tokens','slots'}:raise ContractError('unknown provider parameters')
        if self._routes is not None and maxout!=self._route(role)['MAX_OUTPUT_TOKENS']:raise ContractError('output token cap differs from the route')
        user={'context':request['context']}
        if 'slots' in params:user['slots']=params['slots']
        effort=self.request_params_for(role)['reasoning_effort']
        body={'model':self.model_for(role),'instructions':request['prompt'],'input':canonical(user),
              'background':True,'store':True,'stream':False,'service_tier':'default',
              'max_output_tokens':maxout,'reasoning':{'effort':effort},
              'text':{'format':responses_text_format(role,self.contexts,request)}}
        if body.get('stream') or 'tools' in body or 'temperature' in body:raise ContractError('tools, streaming, or temperature forbidden')
        if body.get('store') is not True or body.get('background') is not True:raise ContractError('background store required')
        return body

    def payload(self,request):
        return self.responses_payload(request) if self.uses_background(request['role']) else self.chat_payload(request)

    def bounds(self,request):
        payload=self.payload(request)
        upper=len(canonical(payload).encode())+1024
        maxout=payload.get('max_output_tokens') or payload.get('max_completion_tokens')
        if upper+maxout>1_000_000:raise ContractError('request exceeds conservative context bound')
        return upper,maxout

    def bound(self,request):
        inp,out=self.bounds(request)
        input_rate,output_rate=self._rates(request['role'])
        return int((input_rate*inp+output_rate*out).to_integral_value(rounding=ROUND_CEILING))

    def create_background(self,request):
        if self._offline:raise ContractError('offline OpenAI adapter never sends')
        if not self.uses_background(request['role']):raise ContractError('role does not use background Responses')
        if not self._can_send():raise ContractError('real call disabled')
        if self._routes is not None and self.bound(request)>self.cap:raise ContractError('call exceeds authorized budget')
        body=canonical(self.responses_payload(request)).encode()
        status,wire=self._http('POST','/v1/responses',body,self.create_timeout_seconds)
        if status!=200:
            billing,retryable=classify_http(status)
            raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status,billing=billing,retryable=retryable)
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
        if status!=200:
            billing,retryable=classify_http(status)
            raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status,billing='UNCERTAIN',retryable=retryable or status>=500)
        payload=parse_json(wire.decode('utf-8'))
        if payload.get('id')!=response_id:raise ProviderFailure('response_id mismatch',wire)
        if self._routes is not None:payload=strip_reasoning(payload)
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
        input_rate,output_rate=self._rates(request['role'])
        cost=int((input_rate*inp+output_rate*out).to_integral_value(rounding=ROUND_CEILING))
        details=usage.get('output_tokens_details') or {}
        recorded={'input_tokens':inp,'output_tokens':out,'reasoning_tokens':details.get('reasoning_tokens')}
        if self._routes is not None:
            # Recorded only; cached input stays priced at the standard input rate (conservative).
            cached=(usage.get('input_tokens_details') or {}).get('cached_tokens')
            if type(cached)==int:recorded['cached_tokens']=cached
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
        """Synchronous critic call. Returns content text; content is judged by the consumer.

        HTTP errors are classified (classify_http). A 200 whose completion is
        truncated, refused or not text is a BILLED failure carrying its usage cost."""
        if request['role']=='GENERATOR':raise ContractError('GENERATOR uses background Responses, not synchronous complete')
        if self.uses_background(request['role']):raise ContractError('role uses background Responses, not synchronous complete')
        if self._offline:raise ContractError('offline OpenAI adapter never sends')
        if not self._can_send():raise ContractError('real call disabled')
        bound=self.bound(request)
        if bound>self.cap:raise ContractError('call exceeds authorized budget')
        body=canonical(self.chat_payload(request)).encode()
        status,wire=self._http('POST','/v1/chat/completions',body,self.request_timeout_seconds)
        if status!=200:
            billing,retryable=classify_http(status)
            raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status,billing=billing,retryable=retryable)
        try:
            payload=parse_json(wire.decode('utf-8'))
        except (ContractError,UnicodeError) as e:
            raise ProviderFailure('unparseable 200 envelope',wire,billing='BILLED') from e
        usage=payload.get('usage') if isinstance(payload,dict) else None
        cost=None;recorded=None
        try:
            inp,out=usage['prompt_tokens'],usage['completion_tokens'];maxin,maxout=self.bounds(request)
            if type(inp)==int and type(out)==int and 0<=inp<=maxin and 0<=out<=maxout:
                input_rate,output_rate=self._rates(request['role'])
                cost=int((input_rate*inp+output_rate*out).to_integral_value(rounding=ROUND_CEILING))
                details=usage.get('completion_tokens_details') or {}
                recorded={'prompt_tokens':inp,'completion_tokens':out,'reasoning_tokens':details.get('reasoning_tokens')}
        except (KeyError,TypeError):
            cost=None
        try:
            choices=payload['choices']
            if len(choices)!=1:raise ValueError('choice count')
            finish=choices[0].get('finish_reason');message=choices[0]['message'];raw=message.get('content')
        except (KeyError,TypeError,ValueError,IndexError) as e:
            raise ProviderFailure('malformed provider envelope',wire,billing='BILLED',usage=recorded,cost=cost) from e
        if finish!='stop':
            raise ProviderFailure('incomplete completion: '+str(finish),wire,envelope={'finish_reason':finish},billing='BILLED',usage=recorded,cost=cost)
        if message.get('refusal') or message.get('tool_calls') or not isinstance(raw,str) or not raw:
            raise ProviderFailure('not a text completion',wire,billing='BILLED',usage=recorded,cost=cost)
        if cost is None:
            raise ProviderFailure('usage missing or outside bound',wire,billing='BILLED')
        # Verbatim model text: the consumer validates the provider schema and normalizes.
        return Response(raw,recorded,cost,hashlib.sha256(wire).hexdigest())
