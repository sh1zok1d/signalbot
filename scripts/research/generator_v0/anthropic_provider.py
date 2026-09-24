"""First-party Claude Messages adapter (direct HTTP). No SDK, no SDK retries, no tools.

POST /v1/messages, synchronous, stream=false. The Caller's journal state
machine (RESERVED -> DISPATCHED -> COMPLETE / FAILED_* / UNCERTAIN, reconcile)
is the only retry authority; this adapter never retries.

Request: model, max_tokens (the route's frozen cap), system = the frozen role
prompt, one user message = canonical({context, slots}), stream=false,
output_config = {effort, format: {type: json_schema, schema}}. No thinking
parameter (Opus 5.5 runs adaptive thinking; effort is the control), no
temperature, tools, tool_choice, citations, cache_control, metadata or
stop_sequences. Batch and prompt caching are deliberately not used.

Response: only a `message` with the expected id prefix, the requested model,
stop_reason end_turn, valid usage, and exactly one non-empty text block is
usable. Thinking blocks are ignored and never persisted; only the final text is
returned verbatim (raw / raw_sha256) and the whole envelope is represented by
wire_sha256.
"""
from __future__ import annotations
import hashlib
import http.client
from decimal import Decimal,ROUND_CEILING
from .context import ContractError,canonical,Contexts,digest
from .schema import parse_json
from .output_schemas import anthropic_output_schema,anthropic_generator_schema_digest
from .provider import Response,ProviderFailure
from . import routing

API_VERSION='2023-06-01'
MESSAGES_PATH='/v1/messages'
HOST='api.anthropic.com'
REQUEST_TIMEOUT_SECONDS=900
MAX_WIRE_BYTES=4_000_000
# Provider-side scaffolding (structured-output grammar, system framing) is not
# visible in the request bytes; bound it with a fixed margin on top of bytes.
INPUT_OVERHEAD_TOKENS=4096
FORBIDDEN_BODY_KEYS=('tools','tool_choice','temperature','top_p','top_k','thinking','citations','cache_control',
                     'metadata','stop_sequences','service_tier','container','mcp_servers','speed')
USABLE_BLOCKS=('thinking','redacted_thinking','text')

class HTTPS:
    def __call__(self,method,path,body,headers,timeout):
        conn=http.client.HTTPSConnection(HOST,timeout=timeout)
        try:
            conn.request(method,path,body=body or b'',headers=headers)
            response=conn.getresponse();wire=response.read(MAX_WIRE_BYTES+1)
            if len(wire)>MAX_WIRE_BYTES:raise ProviderFailure('oversized provider response',wire,billing='UNCERTAIN')
            return response.status,wire
        finally:conn.close()

def classify_anthropic_http(status,wire):
    """(billing, retryable) for a non-200 Messages response.

    Deterministic request/auth/permission/billing/size/not-found rejections are
    NOT_BILLED and not retryable (operator pause). 429 rate_limit_error and 529
    overloaded_error are NOT_BILLED retryable only when the body is the
    documented error envelope for that status. Anything else, including 408,
    409, 500 and other 5xx or unrecognized bodies, is UNCERTAIN: a model run may
    have happened, so it is never retried automatically."""
    try:
        body=parse_json(wire.decode('utf-8'))
        etype=body['error']['type'] if isinstance(body,dict) and body.get('type')=='error' else None
    except Exception:
        etype=None
    if status in (400,401,402,403,404,413):return 'NOT_BILLED',False
    if status==429 and etype=='rate_limit_error':return 'NOT_BILLED',True
    if status==529 and etype=='overloaded_error':return 'NOT_BILLED',True
    return 'UNCERTAIN',False

def _ceil(x):
    return int(Decimal(x).to_integral_value(rounding=ROUND_CEILING))

def usage_cost(usage,model,maxin,maxout):
    """(recorded usage, micro-USD cost) or raise ValueError when usage is missing,
    malformed or outside the request bound. Output tokens are authoritative
    (they include adaptive-thinking tokens); cache tokens are priced at their
    own standard rates; a 1h/5m split falls back to the 1h (higher) rate."""
    if not isinstance(usage,dict):raise ValueError('usage missing')
    inp,out=usage.get('input_tokens'),usage.get('output_tokens')
    cr=usage.get('cache_read_input_tokens') or 0
    cw=usage.get('cache_creation_input_tokens') or 0
    split=usage.get('cache_creation') if isinstance(usage.get('cache_creation'),dict) else {}
    w5=split.get('ephemeral_5m_input_tokens') or 0;w1=split.get('ephemeral_1h_input_tokens') or 0
    for v in (inp,out,cr,cw,w5,w1):
        if type(v)!=int or v<0:raise ValueError('malformed usage')
    if w5+w1>cw:raise ValueError('inconsistent cache creation split')
    unsplit=cw-w5-w1
    if inp+cr+cw>maxin or out>maxout:raise ValueError('usage outside bound')
    p=routing.PRICES[model]
    cost=_ceil(p['INPUT']*inp+p['OUTPUT']*out+p['CACHE_READ']*cr+p['CACHE_WRITE_5M']*w5+p['CACHE_WRITE_1H']*(w1+unsplit))
    recorded={'input_tokens':inp,'output_tokens':out,'cache_read_input_tokens':cr,'cache_creation_input_tokens':cw,
              'cache_creation_5m_input_tokens':w5,'cache_creation_1h_input_tokens':w1}
    thinking=usage.get('thinking_tokens',(usage.get('output_tokens_details') or {}).get('thinking_tokens') if isinstance(usage.get('output_tokens_details'),dict) else None)
    if type(thinking)==int:recorded['thinking_tokens']=thinking
    return recorded,cost

class AnthropicProvider:
    provider_id='ANTHROPIC_MESSAGES'
    model_id='ROLE_SPECIFIC'
    real=True
    def __init__(self,api_key,*,allow_real=False,budget_micro_usd=0,routes=None,transport=None,contexts=None,
                 timeout_seconds=REQUEST_TIMEOUT_SECONDS,offline=False):
        """offline=True builds a bound-only adapter (preflight): no key, and it refuses to send."""
        self._routes={r:v for r,v in routing.validate_routes(routes).items() if v['PROVIDER']=='ANTHROPIC'}
        if not self._routes:raise ContractError('no role is routed to Anthropic')
        self._offline=offline is True
        if not self._offline:
            if not isinstance(api_key,str) or not api_key.strip():raise ContractError('ANTHROPIC_API_KEY is required')
            if allow_real is not True or type(budget_micro_usd)!=int or not 0<budget_micro_usd<=30_000_000:
                raise ContractError('explicit allow-real-llm and nonzero budget <= USD 30 required')
        if type(timeout_seconds)!=int or not 1<=timeout_seconds<=1800:raise ContractError('invalid request timeout')
        self._key=None if self._offline else api_key;self._allow=allow_real is True and not self._offline;self.cap=budget_micro_usd
        self.request_timeout_seconds=timeout_seconds
        self.contexts=contexts or Contexts()
        self.transport=transport or HTTPS()

    def _route(self,role):
        if role not in self._routes:raise ContractError('role is not routed to Anthropic: '+str(role))
        return self._routes[role]
    def roles(self):return tuple(sorted(self._routes))
    def model_for(self,role):return self._route(role)['MODEL']
    def request_params_for(self,role):return dict(self._route(role)['PARAMS'])
    def endpoint_for(self,role):return self._route(role)['ENDPOINT']
    def uses_background(self,role):self._route(role);return False

    def transport_identity(self):
        return {'ADAPTER':'ANTHROPIC_MESSAGES_DIRECT_HTTP','HOST':HOST,'PATH':MESSAGES_PATH,'API_VERSION':API_VERSION,
                'STREAM':False,'BATCH':False,'PROMPT_CACHING':False,'SDK_RETRIES':False,'INPUT_OVERHEAD_TOKENS':INPUT_OVERHEAD_TOKENS,
                'REQUEST_TIMEOUT_SECONDS':self.request_timeout_seconds,
                'ROLES':{r:{'MODEL':v['MODEL'],'PARAMS':v['PARAMS'],'MAX_OUTPUT_TOKENS':v['MAX_OUTPUT_TOKENS'],'STRUCTURED_OUTPUT':v['STRUCTURED_OUTPUT']} for r,v in sorted(self._routes.items())},
                'GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST':anthropic_generator_schema_digest(self.contexts) if 'GENERATOR' in self._routes else None}

    def _headers(self):
        return {'x-api-key':self._key,'anthropic-version':API_VERSION,'content-type':'application/json'}

    def payload(self,request):
        role=request['role'];r=self._route(role);params=request['parameters']
        if set(params)-{'max_output_tokens','slots'}:raise ContractError('unknown provider parameters')
        maxout=params.get('max_output_tokens')
        if maxout!=r['MAX_OUTPUT_TOKENS']:raise ContractError('output token cap differs from the route')
        user={'context':request['context']}
        if 'slots' in params:user['slots']=params['slots']
        body={'model':r['MODEL'],'max_tokens':maxout,'system':request['prompt'],
              'messages':[{'role':'user','content':canonical(user)}],'stream':False,
              'output_config':{'effort':r['PARAMS']['effort'],'format':{'type':'json_schema','schema':anthropic_output_schema(role,self.contexts,request)}}}
        if any(k in body for k in FORBIDDEN_BODY_KEYS):raise ContractError('forbidden request parameter')
        return body

    def bounds(self,request):
        body=self.payload(request)
        upper=len(canonical(body).encode('utf-8'))+INPUT_OVERHEAD_TOKENS
        maxout=body['max_tokens']
        if upper+maxout>routing.PRICES[body['model']]['CONTEXT_WINDOW_TOKENS']:raise ContractError('request exceeds conservative context bound')
        return upper,maxout

    def bound(self,request):
        """Standard input and output prices on the upper input and max_tokens.
        No cache or batch discount is ever applied."""
        inp,out=self.bounds(request);p=routing.PRICES[self.model_for(request['role'])]
        return _ceil(p['INPUT']*inp+p['OUTPUT']*out)

    def complete(self,request):
        if self._offline:raise ContractError('offline Anthropic adapter never sends')
        if not self._allow or not self._key or not 0<self.cap<=30_000_000:raise ContractError('real call disabled')
        role=request['role'];r=self._route(role)
        bound=self.bound(request)
        if bound>self.cap:raise ContractError('call exceeds authorized budget')
        maxin,maxout=self.bounds(request)
        body=canonical(self.payload(request)).encode('utf-8')
        status,wire=self.transport('POST',MESSAGES_PATH,body,self._headers(),self.request_timeout_seconds)
        if len(wire)>MAX_WIRE_BYTES:raise ProviderFailure('oversized provider response',wire[:1024],billing='UNCERTAIN')
        if status!=200:
            billing,retryable=classify_anthropic_http(status,wire)
            raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status,billing=billing,retryable=retryable)
        try:
            msg=parse_json(wire.decode('utf-8'))
            if not isinstance(msg,dict):raise ContractError('envelope is not an object')
        except (ContractError,UnicodeError) as e:
            raise ProviderFailure('unparseable 200 envelope',wire,billing='BILLED') from e
        recorded=cost=None
        try:
            recorded,cost=usage_cost(msg.get('usage'),r['MODEL'],maxin,maxout)
            if cost>bound:recorded,cost=dict(recorded,COST_EXCEEDED_BOUND=True),None
        except ValueError:
            recorded=cost=None
        mid=msg.get('id');envelope={'message_id':mid if isinstance(mid,str) else None,'stop_reason':msg.get('stop_reason')}
        if msg.get('type')!='message' or msg.get('role')!='assistant' or not isinstance(mid,str) or not mid.startswith('msg_'):
            raise ProviderFailure('malformed message envelope',wire,envelope=envelope,billing='BILLED',usage=recorded,cost=cost)
        if msg.get('model')!=r['MODEL']:
            raise ProviderFailure('unexpected model identity',wire,envelope=envelope,billing='BILLED',usage=recorded,cost=cost)
        if msg.get('stop_reason')!='end_turn':
            raise ProviderFailure('incomplete message: '+str(msg.get('stop_reason')),wire,envelope=envelope,billing='BILLED',usage=recorded,cost=cost)
        blocks=msg.get('content')
        if not isinstance(blocks,list) or any(not isinstance(b,dict) or b.get('type') not in USABLE_BLOCKS for b in blocks):
            raise ProviderFailure('unexpected content blocks',wire,envelope=envelope,billing='BILLED',usage=recorded,cost=cost)
        texts=[b.get('text') for b in blocks if b.get('type')=='text']
        if len(texts)!=1 or not isinstance(texts[0],str) or not texts[0]:
            raise ProviderFailure('not exactly one text block',wire,envelope=envelope,billing='BILLED',usage=recorded,cost=cost)
        if cost is None:
            raise ProviderFailure('usage missing or outside bound',wire,envelope=envelope,billing='BILLED',usage=recorded)
        # Verbatim final text only; thinking blocks are not returned or persisted.
        return Response(texts[0],recorded,cost,hashlib.sha256(wire).hexdigest())
