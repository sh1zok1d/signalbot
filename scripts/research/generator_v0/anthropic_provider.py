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

Message Batches (routing.ANTHROPIC_BATCH_ENDPOINT, ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1):
the same request params (without `stream`) are sent as the single request of a
Message Batch. The Caller runs it like a background Response:
  RESERVED -> DISPATCHED (custom_id and dispatch time journaled before the POST)
  -> BACKGROUND_SUBMITTED (PROVIDER_ACCEPTED: the batch id is journaled)
  -> polling by that id only -> COMPLETE.
The create is never POSTed twice. A create whose acknowledgement is lost
(timeout, 5xx, process death) is found again in the workspace listing by its
custom_id; a create that provably made no batch is closed NOT_BILLED and the
next transport attempt is a new call key. Poll errors never make a call
UNCERTAIN: the batch id is durable, so the call stays PENDING and a resume polls
the same id. errored / canceled / expired requests are not billed (official
batch docs); a succeeded request is validated exactly like a synchronous
message and priced at batch rates.
"""
from __future__ import annotations
import hashlib
import http.client
import json
import re
import time
from datetime import datetime,timezone
from decimal import Decimal,ROUND_CEILING
from .context import ContractError,canonical,Contexts,digest
from .schema import parse_json
from .output_schemas import anthropic_output_schema,anthropic_generator_schema_digest,ANTHROPIC_GENERATOR_WIRE_FORMAT
from .provider import Response,ProviderFailure,BackgroundPending
from . import routing

API_VERSION='2023-06-01'
MESSAGES_PATH='/v1/messages'
HOST='api.anthropic.com'
# 1800, not 900: a 32768-token live response took ~299s, so a full
# 100000-token response is ~912s and would expire at the old timeout.
REQUEST_TIMEOUT_SECONDS=1800
MAX_WIRE_BYTES=4_000_000
# Provider-side scaffolding (structured-output grammar, system framing) is not
# visible in the request bytes; bound it with a fixed margin on top of bytes.
INPUT_OVERHEAD_TOKENS=4096
FORBIDDEN_BODY_KEYS=('tools','tool_choice','temperature','top_p','top_k','thinking','citations','cache_control',
                     'metadata','stop_sequences','service_tier','container','mcp_servers','speed')
USABLE_BLOCKS=('thinking','redacted_thinking','text')
BATCHES_PATH='/v1/messages/batches'
BATCH_CREATE_TIMEOUT_SECONDS=120
BATCH_POLL_INTERVAL_SECONDS=30
BATCH_POLL_GET_TIMEOUT_SECONDS=60
# Per invocation. Most batches end within an hour; the provider expires a batch after 24 h.
BATCH_MAX_WAIT_SECONDS=6*3600
# Listing recovery of a lost create: clock skew allowance around the dispatch time, and how
# long after the create could have landed the absence of the batch is taken as proof.
BATCH_RECOVERY_SKEW_SECONDS=600
BATCH_RECOVERY_SETTLE_SECONDS=900
BATCH_LIST_PAGE=100
BATCH_ID_PREFIX='msgbatch_'
BATCH_RETRYABLE_ERRORS=('rate_limit_error','overloaded_error','api_error','timeout_error')
BATCH_POLL_PAUSE_STATUSES=(401,402,403,404)

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
    NOT_BILLED and not retryable (operator pause). Everything else is UNCERTAIN
    and never retried automatically, including a documented 429
    rate_limit_error or 529 overloaded_error: the documented error semantics do
    not establish that model work definitely did not occur, so under the
    conservative accounting rules the reservation stays charged until an
    operator reconciles the call. 408, 409, 500, other 5xx and unrecognized
    bodies are UNCERTAIN as before."""
    if status in (400,401,402,403,404,413):return 'NOT_BILLED',False
    return 'UNCERTAIN',False

def _ceil(x):
    return int(Decimal(x).to_integral_value(rounding=ROUND_CEILING))

def usage_cost(usage,model,maxin,maxout,prices=None):
    """(recorded usage, micro-USD cost) or raise ValueError when usage is missing,
    malformed or outside the request bound. Output tokens are authoritative
    (they include adaptive-thinking tokens); cache tokens are priced at their
    own standard rates; a 1h/5m split falls back to the 1h (higher) rate.
    prices: the route's price row (batch routes pass routing.BATCH_PRICES)."""
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
    p=prices or routing.PRICES[model]
    cost=_ceil(p['INPUT']*inp+p['OUTPUT']*out+p['CACHE_READ']*cr+p['CACHE_WRITE_5M']*w5+p['CACHE_WRITE_1H']*(w1+unsplit))
    recorded={'input_tokens':inp,'output_tokens':out,'cache_read_input_tokens':cr,'cache_creation_input_tokens':cw,
              'cache_creation_5m_input_tokens':w5,'cache_creation_1h_input_tokens':w1}
    thinking=usage.get('thinking_tokens',(usage.get('output_tokens_details') or {}).get('thinking_tokens') if isinstance(usage.get('output_tokens_details'),dict) else None)
    if type(thinking)==int:recorded['thinking_tokens']=thinking
    if prices is not None and isinstance(usage.get('service_tier'),str):recorded['service_tier']=usage['service_tier']
    return recorded,cost

def _iso(ts):
    return datetime.fromtimestamp(ts,timezone.utc).isoformat()

def _epoch(value):
    if not isinstance(value,str):raise ValueError('timestamp')
    return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

def strip_thinking(msg):
    """Message envelope with thinking content removed (type kept). Never journal thinking."""
    if not isinstance(msg,dict) or not isinstance(msg.get('content'),list):return msg
    blocks=[{'type':b.get('type')} if isinstance(b,dict) and b.get('type') in ('thinking','redacted_thinking') else b for b in msg['content']]
    return {**msg,'content':blocks}

class AnthropicProvider:
    provider_id='ANTHROPIC_MESSAGES'
    model_id='ROLE_SPECIFIC'
    real=True
    def __init__(self,api_key,*,allow_real=False,budget_micro_usd=0,routes=None,transport=None,contexts=None,
                 timeout_seconds=REQUEST_TIMEOUT_SECONDS,offline=False,create_timeout_seconds=BATCH_CREATE_TIMEOUT_SECONDS,
                 poll_interval_seconds=BATCH_POLL_INTERVAL_SECONDS,poll_get_timeout_seconds=BATCH_POLL_GET_TIMEOUT_SECONDS,
                 background_max_wait_seconds=BATCH_MAX_WAIT_SECONDS,sleeper=None,clock=None,wall_clock=None):
        """offline=True builds a bound-only adapter (preflight): no key, and it refuses to send.
        The batch parameters apply only to roles routed to Message Batches."""
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
        if type(create_timeout_seconds)!=int or not 10<=create_timeout_seconds<=600:raise ContractError('invalid batch create timeout')
        if type(poll_interval_seconds)!=int or not 5<=poll_interval_seconds<=300:raise ContractError('invalid batch poll interval')
        if type(poll_get_timeout_seconds)!=int or not 10<=poll_get_timeout_seconds<=300:raise ContractError('invalid batch poll GET timeout')
        if type(background_max_wait_seconds)!=int or not 1<=background_max_wait_seconds<=86400:raise ContractError('invalid batch wait')
        self.create_timeout_seconds=create_timeout_seconds
        self.poll_interval_seconds=poll_interval_seconds
        self.poll_get_timeout_seconds=poll_get_timeout_seconds
        self.background_max_wait_seconds=background_max_wait_seconds
        self._sleep=sleeper or time.sleep
        self._now=clock or time.monotonic
        self._wall=wall_clock or time.time
        self.contexts=contexts or Contexts()
        self.transport=transport or HTTPS()

    def _route(self,role):
        if role not in self._routes:raise ContractError('role is not routed to Anthropic: '+str(role))
        return self._routes[role]
    def roles(self):return tuple(sorted(self._routes))
    def model_for(self,role):return self._route(role)['MODEL']
    def request_params_for(self,role):return dict(self._route(role)['PARAMS'])
    def endpoint_for(self,role):return self._route(role)['ENDPOINT']
    def max_output_tokens_for(self,role):return self._route(role)['MAX_OUTPUT_TOKENS']
    def uses_background(self,role):return self._route(role)['ENDPOINT']==routing.ANTHROPIC_BATCH_ENDPOINT
    def _batched(self):return any(v['ENDPOINT']==routing.ANTHROPIC_BATCH_ENDPOINT for v in self._routes.values())
    # The Caller journals this adapter's provider acceptance externally (checkpoint) and
    # recovers a lost create from the listing; see provider.Caller.
    checkpoint_on_accept=True
    def prices_for(self,role):return routing.prices_for(self._route(role))

    def transport_identity(self):
        if self._batched():
            return {'ADAPTER':'ANTHROPIC_MESSAGE_BATCHES_DIRECT_HTTP','HOST':HOST,'PATH':BATCHES_PATH,'API_VERSION':API_VERSION,
                    'STREAM':False,'BATCH':True,'REQUESTS_PER_BATCH':1,'PROMPT_CACHING':False,'SDK_RETRIES':False,'INPUT_OVERHEAD_TOKENS':INPUT_OVERHEAD_TOKENS,
                    'CREATE_REPLAY':False,'PRICE_BASIS':'BATCH',
                    'POLLING_POLICY':{'CREATE_TIMEOUT_SECONDS':self.create_timeout_seconds,'INTERVAL_SECONDS':self.poll_interval_seconds,
                                      'GET_TIMEOUT_SECONDS':self.poll_get_timeout_seconds,'MAX_WAIT_SECONDS':self.background_max_wait_seconds},
                    'RECOVERY_POLICY':{'MATCH':'custom_id','SKEW_SECONDS':BATCH_RECOVERY_SKEW_SECONDS,'SETTLE_SECONDS':BATCH_RECOVERY_SETTLE_SECONDS,'LIST_PAGE':BATCH_LIST_PAGE},
                    'ROLES':{r:{'MODEL':v['MODEL'],'PARAMS':v['PARAMS'],'MAX_OUTPUT_TOKENS':v['MAX_OUTPUT_TOKENS'],'STRUCTURED_OUTPUT':v['STRUCTURED_OUTPUT'],'ENDPOINT':v['ENDPOINT']} for r,v in sorted(self._routes.items())},
                    'GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST':anthropic_generator_schema_digest(self.contexts) if 'GENERATOR' in self._routes else None}
        return {'ADAPTER':'ANTHROPIC_MESSAGES_DIRECT_HTTP','HOST':HOST,'PATH':MESSAGES_PATH,'API_VERSION':API_VERSION,
                'STREAM':False,'BATCH':False,'PROMPT_CACHING':False,'SDK_RETRIES':False,'INPUT_OVERHEAD_TOKENS':INPUT_OVERHEAD_TOKENS,
                'REQUEST_TIMEOUT_SECONDS':self.request_timeout_seconds,
                'ROLES':{r:{'MODEL':v['MODEL'],'PARAMS':v['PARAMS'],'MAX_OUTPUT_TOKENS':v['MAX_OUTPUT_TOKENS'],'STRUCTURED_OUTPUT':v['STRUCTURED_OUTPUT']} for r,v in sorted(self._routes.items())},
                'GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST':anthropic_generator_schema_digest(self.contexts) if 'GENERATOR' in self._routes else None}

    def wire_identity_for(self,role,request):
        """GENERATOR requests carry the compact wire format and the digest of the
        exact schema sent; both enter the call key."""
        if role!='GENERATOR':return None
        self._route(role)
        return {'provider_wire_format':ANTHROPIC_GENERATOR_WIRE_FORMAT,
                'provider_schema_digest':digest(anthropic_output_schema(role,self.contexts,request))}

    def _headers(self):
        return {'x-api-key':self._key,'anthropic-version':API_VERSION,'content-type':'application/json'}

    def payload(self,request):
        role=request['role'];r=self._route(role);params=request['parameters']
        if set(params)-{'max_output_tokens','slots'}:raise ContractError('unknown provider parameters')
        maxout=params.get('max_output_tokens')
        if maxout!=r['MAX_OUTPUT_TOKENS']:raise ContractError('output token cap differs from the route')
        user={'context':request['context']}
        if 'slots' in params:user['slots']=params['slots']
        schema=anthropic_output_schema(role,self.contexts,request)
        if role=='GENERATOR':
            if request.get('provider_wire_format')!=ANTHROPIC_GENERATOR_WIRE_FORMAT:raise ContractError('generator request lacks the Anthropic compact wire format')
            if request.get('provider_schema_digest')!=digest(schema):raise ContractError('generator request schema digest does not match the schema sent')
        body={'model':r['MODEL'],'max_tokens':maxout,'system':request['prompt'],
              'messages':[{'role':'user','content':canonical(user)}],'stream':False,
              'output_config':{'effort':r['PARAMS']['effort'],'format':{'type':'json_schema','schema':schema}}}
        # A batch request carries the same params without `stream` (stream is refused in batches).
        if self.uses_background(role):del body['stream']
        if any(k in body for k in FORBIDDEN_BODY_KEYS):raise ContractError('forbidden request parameter')
        return body

    def bounds(self,request):
        body=self.payload(request)
        upper=len(canonical(body).encode('utf-8'))+INPUT_OVERHEAD_TOKENS
        maxout=body['max_tokens']
        if upper+maxout>routing.PRICES[body['model']]['CONTEXT_WINDOW_TOKENS']:raise ContractError('request exceeds conservative context bound')
        return upper,maxout

    def bound(self,request):
        """The route's input and output prices on the upper input and max_tokens:
        standard prices, or the batch prices on a batch route. No cache discount."""
        inp,out=self.bounds(request);p=self.prices_for(request['role'])
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
        return self._message_response(msg,wire,r,maxin,maxout,bound)

    def _message_cost(self,msg,r,maxin,maxout,bound,prices=None):
        recorded=cost=None
        try:
            recorded,cost=usage_cost(msg.get('usage'),r['MODEL'],maxin,maxout,prices)
            if prices is not None and recorded.get('service_tier') not in (None,'batch'):
                # Not billed at the batch tier: price at standard rates (conservative).
                recorded,cost=usage_cost(msg.get('usage'),r['MODEL'],maxin,maxout,routing.PRICES[r['MODEL']])
                recorded['service_tier']=msg['usage']['service_tier']
            if cost>bound:recorded,cost=dict(recorded,COST_EXCEEDED_BOUND=True),None
        except ValueError:
            recorded=cost=None
        return recorded,cost

    def _message_response(self,msg,wire,r,maxin,maxout,bound,prices=None):
        """Response for a usable message, else ProviderFailure (BILLED). Shared by the
        synchronous path and Message Batch results."""
        recorded,cost=self._message_cost(msg,r,maxin,maxout,bound,prices)
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

    # ---- Message Batches (GENERATOR on routing.ANTHROPIC_BATCH_ENDPOINT) ----------------
    def _can_send(self):
        return not self._offline and self._allow and bool(self._key) and 0<self.cap<=30_000_000

    def _http(self,method,path,body,timeout):
        status,wire=self.transport(method,path,body,self._headers(),timeout)
        if len(wire)>MAX_WIRE_BYTES:raise ProviderFailure('oversized provider response',wire[:1024],billing='UNCERTAIN',retryable=True)
        return status,wire

    def dispatch_intent(self,key,run_id):
        """Journaled with DISPATCHED before the create POST: the custom_id that names this
        call's batch in the workspace listing, and the dispatch time that bounds the search."""
        cid='gv0-'+digest({'RUN_ID':run_id,'CALL_KEY':key})[:60]
        return {'RECOVERY':'LIST_BY_CUSTOM_ID','custom_id':cid,'dispatched_at':_iso(self._wall()),'provider_object':'message_batch'}

    @staticmethod
    def _check_batch(b):
        if not isinstance(b,dict) or b.get('type')!='message_batch':raise ValueError('not a message batch')
        if not isinstance(b.get('id'),str) or not b['id'].startswith(BATCH_ID_PREFIX):raise ValueError('batch id')
        if b.get('processing_status') not in ('in_progress','canceling','ended'):raise ValueError('batch status')
        counts=b.get('request_counts')
        if not isinstance(counts,dict) or any(type(v)!=int or v<0 for v in counts.values()):raise ValueError('request counts')
        _epoch(b.get('created_at'))
        return b

    def create_background(self,request,custom_id=None):
        """One create POST of a one-request batch. Never retried here."""
        if self._offline:raise ContractError('offline Anthropic adapter never sends')
        if not self.uses_background(request['role']):raise ContractError('role is not routed to Message Batches')
        if not self._can_send():raise ContractError('real call disabled')
        if not isinstance(custom_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',custom_id):raise ContractError('batch custom_id')
        if self.bound(request)>self.cap:raise ContractError('call exceeds authorized budget')
        body=canonical({'requests':[{'custom_id':custom_id,'params':self.payload(request)}]}).encode('utf-8')
        status,wire=self._http('POST',BATCHES_PATH,body,self.create_timeout_seconds)
        if status!=200:
            if status in (400,401,402,403,404,413):
                raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status,billing='NOT_BILLED',retryable=False)
            if status==429:
                raise ProviderFailure('provider HTTP 429',wire,http_status=status,billing='NOT_BILLED',retryable=True)
            # 5xx / 529 / anything else: a batch may exist. The Caller searches for it by custom_id.
            raise ProviderFailure('provider HTTP '+str(status),wire,http_status=status,billing='UNCERTAIN')
        try:
            b=self._check_batch(parse_json(wire.decode('utf-8')))
            if sum(b['request_counts'].values())!=1:raise ValueError('not a one-request batch')
        except (ContractError,UnicodeError,ValueError,TypeError) as e:
            raise ProviderFailure('batch create returned no usable batch id',wire) from e
        return {'response_id':b['id'],'provider_status':b['processing_status'],'custom_id':custom_id,
                'provider_object':'message_batch','created_at':b['created_at']}

    def _poll_status(self,status,wire):
        """Poll errors never close the call: the batch id is durable."""
        if status==200:return
        if status in BATCH_POLL_PAUSE_STATUSES:
            raise BackgroundPending('batch poll HTTP '+str(status)+': fix the credential or workspace, then resume; the batch id is kept and is only polled')
        raise ProviderFailure('batch poll HTTP '+str(status),wire,http_status=status,billing='UNCERTAIN',retryable=True)

    def _results(self,batch_id):
        status,wire=self._http('GET',BATCHES_PATH+'/'+batch_id+'/results',b'',self.poll_get_timeout_seconds)
        self._poll_status(status,wire)
        try:
            lines=[parse_json(x) for x in wire.decode('utf-8').splitlines() if x.strip()]
        except (ContractError,UnicodeError) as e:
            raise ProviderFailure('unparseable batch results',wire,retryable=True) from e
        return lines,wire

    def retrieve_tracked(self,tracker):
        """(payload, wire) for the Caller's poll loop: in_progress until the batch ends, then
        this call's single result: completed (succeeded) or errored / canceled / expired."""
        bid,cid=tracker.get('response_id'),tracker.get('custom_id')
        if not isinstance(bid,str) or not bid.startswith(BATCH_ID_PREFIX) or not isinstance(cid,str):
            raise ProviderFailure('journaled tracker is not a message batch')
        status,wire=self._http('GET',BATCHES_PATH+'/'+bid,b'',self.poll_get_timeout_seconds)
        self._poll_status(status,wire)
        try:
            b=self._check_batch(parse_json(wire.decode('utf-8')))
        except (ContractError,UnicodeError,ValueError,TypeError) as e:
            raise ProviderFailure('unparseable batch status',wire,retryable=True) from e
        if b['id']!=bid:raise ProviderFailure('batch id mismatch',wire)
        base={'id':bid,'custom_id':cid,'processing_status':b['processing_status'],'request_counts':b['request_counts']}
        if b['processing_status']!='ended':return {**base,'status':'in_progress'},wire
        lines,rwire=self._results(bid)
        if not lines:raise ProviderFailure('batch ended but its results are not readable yet',rwire,retryable=True)
        if len(lines)!=1 or not isinstance(lines[0],dict) or lines[0].get('custom_id')!=cid:
            raise ProviderFailure('batch results do not hold exactly this call',rwire)
        res=lines[0].get('result') if isinstance(lines[0].get('result'),dict) else {}
        kind=res.get('type')
        if kind=='succeeded':
            return {**base,'status':'completed','result_type':kind,'message':strip_thinking(res.get('message'))},rwire
        if kind in ('errored','canceled','expired'):
            err=res.get('error') if isinstance(res.get('error'),dict) else {}
            inner=err.get('error') if isinstance(err.get('error'),dict) else {}
            return {**base,'status':kind,'result_type':kind,'error_type':inner.get('type'),'request_id':err.get('request_id')},rwire
        raise ProviderFailure('unknown batch result type',rwire)

    def retrieve_background(self,response_id):
        raise ContractError('Message Batches are polled with their journaled tracker (retrieve_tracked)')

    def _batch_bounds(self,request):
        r=self._route(request['role']);maxin,maxout=self.bounds(request)
        return r,maxin,maxout,self.bound(request),self.prices_for(request['role'])

    def completed_cost(self,request,payload,wire):
        r,maxin,maxout,bound,prices=self._batch_bounds(request)
        resp=self._message_response(payload.get('message') if isinstance(payload.get('message'),dict) else {},wire,r,maxin,maxout,bound,prices)
        return resp.usage,resp.cost_micro_usd,resp.raw,resp.wire_sha256

    def terminal_usage_cost(self,request,payload):
        """Usage cost of a succeeded but unusable batch message (length stop, refusal, ...)."""
        r,maxin,maxout,bound,prices=self._batch_bounds(request)
        recorded,cost=self._message_cost(payload.get('message') if isinstance(payload.get('message'),dict) else {},r,maxin,maxout,bound,prices)
        if cost is None:raise ValueError('usage missing or outside bound')
        return recorded,cost

    def terminal_not_billed(self,request,payload):
        """Documented not-billed batch outcomes; None for anything else."""
        st=payload.get('status')
        if st=='errored':
            return {'RETRYABLE':payload.get('error_type') in BATCH_RETRYABLE_ERRORS,'DETAIL':'batch request errored: '+str(payload.get('error_type'))}
        if st=='expired':return {'RETRYABLE':True,'DETAIL':'batch expired before the request ran'}
        if st=='canceled':return {'RETRYABLE':False,'DETAIL':'batch canceled before the request ran'}
        return None

    def delete_background(self,response_id):
        """No cleanup: the batch and its results stay with the provider as audit evidence."""
        return None

    def find_background(self,intent):
        """Search the workspace listing for this call's batch after a lost create acknowledgement.

        FOUND    the one-request batch whose result carries this custom_id (adopted; never re-POSTed)
        PENDING  cannot decide yet (a candidate batch is still processing, or it is too early)
        ABSENT   every one-request batch in the dispatch window has ended without this custom_id,
                 and the window closed more than BATCH_RECOVERY_SETTLE_SECONDS ago: nothing was created."""
        cid=intent.get('custom_id')
        if not isinstance(cid,str):raise ContractError('recovery intent without custom_id')
        t0=_epoch(intent.get('dispatched_at'))
        lo=t0-BATCH_RECOVERY_SKEW_SECONDS;hi=t0+self.create_timeout_seconds+BATCH_RECOVERY_SKEW_SECONDS
        undecided=[];checked=[];after=None
        for _page in range(10000):
            path=BATCHES_PATH+'?limit='+str(BATCH_LIST_PAGE)+('&after_id='+after if after else '')
            status,wire=self._http('GET',path,b'',self.poll_get_timeout_seconds)
            self._poll_status(status,wire)
            try:
                page=parse_json(wire.decode('utf-8'))
                data=page['data']
                if not isinstance(data,list):raise ValueError('data')
                rows=[self._check_batch(b) for b in data]
            except (ContractError,UnicodeError,ValueError,TypeError,KeyError) as e:
                raise ProviderFailure('malformed batch listing',wire,retryable=True) from e
            older=False
            for b in rows:
                created=_epoch(b['created_at'])
                if created<lo:older=True;break
                if created>hi or sum(b['request_counts'].values())!=1:continue
                if b['processing_status']!='ended':undecided.append(b['id']);continue
                lines,_=self._results(b['id'])
                checked.append(b['id'])
                if [x.get('custom_id') if isinstance(x,dict) else None for x in lines]==[cid]:
                    return {'STATE':'FOUND','TRACKER':{'response_id':b['id'],'provider_status':b['processing_status'],'custom_id':cid,
                                                       'provider_object':'message_batch','created_at':b['created_at'],'RECOVERED_FROM_LISTING':True}}
            if older or page.get('has_more') is not True:break
            after=page.get('last_id')
            if not isinstance(after,str) or not after:raise ProviderFailure('batch listing has more pages but no cursor',wire,retryable=True)
        if undecided:
            return {'STATE':'PENDING','DETAIL':'one-request batches in the dispatch window are still processing: '+', '.join(undecided)}
        if self._wall()<hi+BATCH_RECOVERY_SETTLE_SECONDS:
            return {'STATE':'PENDING','DETAIL':'the dispatch window closed too recently to prove that no batch was created'}
        return {'STATE':'ABSENT','EVIDENCE':{'CUSTOM_ID':cid,'WINDOW_UTC':[_iso(lo),_iso(hi)],'ENDED_ONE_REQUEST_BATCHES_CHECKED':checked,
                                             'LISTED_AT_UTC':_iso(self._wall()),'RULE':'no batch in the workspace listing carries this custom_id'}}
