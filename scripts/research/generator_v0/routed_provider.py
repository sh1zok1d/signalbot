"""RoutedProvider: one Provider for the Caller, delegating by request role.

runner / roles -> Caller -> RoutedProvider -> {AnthropicProvider, OpenAIProvider}

The Caller keeps the single campaign budget, ledger, call-key identity and
retry/reconcile state machine. This router adds no state: it resolves the
role's route in the authoritative registry (routing.py), checks that the
adapter for that provider serves exactly that role with the same model,
parameters and endpoint, and delegates. A role never falls back to another
provider. Every request carries route_provider and route_digest (added by the
Caller from provider_for/route_digest_for), so a call made on one provider or
model can never be replayed as the same call on another.
"""
from __future__ import annotations
from .context import ContractError,digest
from . import routing

class RoutedProvider:
    provider_id='ROUTED_MULTI_PROVIDER'
    model_id='ROLE_SPECIFIC'
    def __init__(self,adapters,routes=None,sleeper=None):
        self.routes=routing.validate_routes(routes)
        if not isinstance(adapters,dict) or set(adapters)!={r['PROVIDER'] for r in self.routes.values()}:
            raise ContractError('exactly one adapter per routed provider is required')
        self.adapters=dict(adapters)
        for role,r in self.routes.items():
            a=self.adapters[r['PROVIDER']]
            if a.model_for(role)!=r['MODEL'] or a.request_params_for(role)!=r['PARAMS'] or a.endpoint_for(role)!=r['ENDPOINT']:
                raise ContractError('adapter disagrees with the routing registry for '+role)
            if a.uses_background(role)!=(r['ENDPOINT'] in routing.BACKGROUND_ENDPOINTS):
                raise ContractError('adapter background mode disagrees with the routing registry for '+role)
            for name,other in self.adapters.items():
                if name!=r['PROVIDER'] and role in other.roles():raise ContractError('role '+role+' is served by more than one provider')
        self.real=any(getattr(a,'real',False) for a in self.adapters.values())
        # Provider jobs: OpenAI background Responses and, on ladder routes, Anthropic Message
        # Batches. The Caller reaches each role's job adapter through background_for(role).
        bg=sorted({self.routes[role]['PROVIDER'] for role in self.routes if self.routes[role]['ENDPOINT'] in routing.BACKGROUND_ENDPOINTS})
        self._bg_providers=tuple(bg)
        self._bg_provider=bg[0] if len(bg)==1 else None
        if sleeper is not None:self._sleep=sleeper
        self.routing_digest=self.identity_digest()

    def _route(self,role):
        if role not in self.routes:raise ContractError('unknown role for routing: '+str(role))
        return self.routes[role]
    def adapter_for(self,role):return self.adapters[self._route(role)['PROVIDER']]
    def provider_for(self,role):return self._route(role)['PROVIDER']
    def route_digest_for(self,role):return routing.role_route_digest(role,self.routes)
    def model_for(self,role):return self._route(role)['MODEL']
    def request_params_for(self,role):return dict(self._route(role)['PARAMS'])
    def endpoint_for(self,role):return self._route(role)['ENDPOINT']
    def max_output_tokens_for(self,role):return self._route(role)['MAX_OUTPUT_TOKENS']
    def uses_background(self,role):return self._route(role)['ENDPOINT'] in routing.BACKGROUND_ENDPOINTS
    def wire_identity_for(self,role,request):
        fn=getattr(self.adapter_for(role),'wire_identity_for',None)
        return fn(role,request) if fn is not None else None

    def _check(self,request):
        role=request.get('role');r=self._route(role)
        for field,expected in (('provider',r['ENDPOINT']),('model',r['MODEL']),('route_provider',r['PROVIDER']),
                               ('route_digest',self.route_digest_for(role)),('model_request_params',r['PARAMS'])):
            if field in request and request[field]!=expected:raise ContractError('request '+field+' does not match the route for '+role)
        return self.adapter_for(role)

    def bound(self,request):return self._check(request).bound(request)
    def complete(self,request):return self._check(request).complete(request)

    # Provider jobs (background Responses for routed critics; Message Batches for the ladder
    # GENERATOR). Same Caller state machine: create is POSTed once; a known id is only polled.
    def background_for(self,role):
        if not self.uses_background(role):raise ContractError('role is not routed to a provider job endpoint: '+str(role))
        return _RoleJobs(self,role)
    def _background(self):
        if self._bg_provider is None:raise ContractError('provider jobs are reached per role (background_for)' if self._bg_providers else 'no role is routed to background Responses')
        return self.adapters[self._bg_provider]
    def create_background(self,request,**kw):
        a=self._check(request)
        if not self.uses_background(request['role']):raise ContractError('role is not routed to background Responses')
        return a.create_background(request,**kw)
    def retrieve_background(self,response_id):return self._background().retrieve_background(response_id)
    def delete_background(self,response_id):return self._background().delete_background(response_id)
    def completed_cost(self,request,payload,wire):return self._check(request).completed_cost(request,payload,wire)
    def terminal_usage_cost(self,request,payload):return self._check(request).terminal_usage_cost(request,payload)
    def _now(self):return self._background()._now()
    def _poll_sleep(self,seconds):return self._background()._sleep(seconds)
    @property
    def poll_interval_seconds(self):return self._background().poll_interval_seconds
    @property
    def background_max_wait_seconds(self):return self._background().background_max_wait_seconds

    def transport_identity(self):
        return {'ROUTER':'ROUTED_MULTI_PROVIDER','ROUTING_ID':routing.ROUTING_ID,
                'ADAPTERS':{name:a.transport_identity() for name,a in sorted(self.adapters.items())}}

    def identity_digest(self):
        return digest({'ROUTING':routing.routing_digest(self.routes),'TRANSPORT':self.transport_identity()})

class _RoleJobs:
    """One role's provider-job adapter as the Caller sees it. Cost and result methods keep
    the router's per-request route check."""
    def __init__(self,router,role):
        self._router,self._role=router,role
        self._adapter=router.adapter_for(role)
    def __getattr__(self,name):
        if name in ('retrieve_background','retrieve_tracked','delete_background','find_background','dispatch_intent',
                    'checkpoint_on_accept','_now','_sleep','poll_interval_seconds','background_max_wait_seconds'):
            return getattr(self._adapter,name)
        raise AttributeError(name)
    def _poll_sleep(self,seconds):return self._adapter._sleep(seconds)
    def completed_cost(self,request,payload,wire):return self._router._check(request).completed_cost(request,payload,wire)
    def terminal_usage_cost(self,request,payload):return self._router._check(request).terminal_usage_cost(request,payload)
    @property
    def terminal_not_billed(self):
        fn=getattr(self._adapter,'terminal_not_billed',None)
        return None if fn is None else (lambda request,payload:self._router._check(request).terminal_not_billed(request,payload))

def offline_routed_provider(contexts,routes=None):
    """Bound-only router for preflight and budget reports: needs no secret, never sends."""
    from .anthropic_provider import AnthropicProvider
    from .openai_provider import OpenAIProvider
    def refuse(*_a,**_k):raise ContractError('offline routed provider never sends')
    routes=routing.validate_routes(routes)
    return RoutedProvider({'ANTHROPIC':AnthropicProvider(None,routes=routes,contexts=contexts,transport=refuse,offline=True),
                           'OPENAI':OpenAIProvider(None,routes=routes,contexts=contexts,transport=refuse,offline=True)},routes)

def routed_run_identity(provider,contexts):
    """Run-config / preflight identity for a routed campaign. Never contains credentials."""
    from .output_schemas import generator_schema_digest,anthropic_generator_schema_digest,role_schema
    from .context import digest as _digest
    return {
        'ROUTING_ID':routing.ROUTING_ID,'ROUTING_TABLE':routing.routing_table(provider.routes),
        'ROLE_PROVIDER_MAP':routing.role_provider_map(provider.routes),'ROLE_MODEL_MAP':routing.role_model_map(provider.routes),
        'ROLE_REQUEST_PARAMS':routing.role_params(provider.routes),'PRICE_TABLE':routing.price_table(provider.routes),
        'ROUTING_DIGEST':provider.routing_digest,'TRANSPORT_IDENTITY':provider.transport_identity(),
        'SCHEMA_DIGESTS':{'GENERATOR_EXACT_PROVIDER_SCHEMA':generator_schema_digest(contexts),
                          'GENERATOR_ANTHROPIC_PROJECTION':anthropic_generator_schema_digest(contexts),
                          'FEASIBILITY_CRITIC':_digest(role_schema('FEASIBILITY_CRITIC',contexts,provider=True)),
                          'RED_TEAM':_digest(role_schema('RED_TEAM',contexts,provider=True)),
                          'SELECTOR':_digest(role_schema('SELECTOR',contexts,provider=True)),
                          'NOVELTY_CRITIC':'PER_REQUEST (keyed by the exact leaf signature IDs and batch candidate IDs)'},
    }

def _anthropic_credential(environ):
    """Documented Anthropic names. Never logged."""
    for name in ('SIGNALBOT_ANTHROPIC_API_KEY','ANTHROPIC_API_KEY'):
        value=environ.get(name,'')
        if isinstance(value,str) and value.strip():return value
    return ''

def live_routed_provider(contexts,cap,environ,openai_network_mode='DIRECT',routes=None):
    """Real routed provider. Never records or prints credentials.

    DIRECT (default, local/non-cloud): both OPENAI_API_KEY and ANTHROPIC_API_KEY,
    direct OpenAI HTTPS. CLOUD_PROXY is explicit: CloudProxyOpenAITransport, no
    OpenAI API key, Anthropic from SIGNALBOT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.
    HTTPS_PROXY does not select the mode.
    """
    from .anthropic_provider import AnthropicProvider
    from .openai_provider import OpenAIProvider,OPENAI_NETWORK_MODE_DIRECT,OPENAI_NETWORK_MODE_CLOUD_PROXY
    from .cloud_openai_transport import CloudProxyOpenAITransport
    if openai_network_mode not in (OPENAI_NETWORK_MODE_DIRECT,OPENAI_NETWORK_MODE_CLOUD_PROXY):
        raise ContractError('unknown OpenAI network mode')
    routes=routing.validate_routes(routes)
    if openai_network_mode==OPENAI_NETWORK_MODE_CLOUD_PROXY:
        akey=_anthropic_credential(environ)
        if not akey:raise ContractError('cloud routed mode requires SIGNALBOT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY')
        openai=OpenAIProvider(None,allow_real=True,budget_micro_usd=cap,contexts=contexts,routes=routes,
                              network_mode=OPENAI_NETWORK_MODE_CLOUD_PROXY,transport=CloudProxyOpenAITransport())
    else:
        okey=environ.get('OPENAI_API_KEY','');akey=environ.get('ANTHROPIC_API_KEY','')
        if not isinstance(okey,str) or not okey.strip() or not isinstance(akey,str) or not akey.strip():
            raise ContractError('routed live mode requires both OPENAI_API_KEY and ANTHROPIC_API_KEY')
        openai=OpenAIProvider(okey,allow_real=True,budget_micro_usd=cap,contexts=contexts,routes=routes)
    return RoutedProvider({'ANTHROPIC':AnthropicProvider(akey,allow_real=True,budget_micro_usd=cap,routes=routes,contexts=contexts),
                           'OPENAI':openai},routes)
