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
            if a.uses_background(role):raise ContractError('routed roles are synchronous')
            for name,other in self.adapters.items():
                if name!=r['PROVIDER'] and role in other.roles():raise ContractError('role '+role+' is served by more than one provider')
        self.real=any(getattr(a,'real',False) for a in self.adapters.values())
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
    def uses_background(self,role):self._route(role);return False
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

    def create_background(self,request):raise ContractError('routed provider does not use background calls')
    def retrieve_background(self,response_id):raise ContractError('routed provider does not use background calls')
    def delete_background(self,response_id):raise ContractError('routed provider does not use background calls')

    def transport_identity(self):
        return {'ROUTER':'ROUTED_MULTI_PROVIDER','ROUTING_ID':routing.ROUTING_ID,
                'ADAPTERS':{name:a.transport_identity() for name,a in sorted(self.adapters.items())}}

    def identity_digest(self):
        return digest({'ROUTING':routing.routing_digest(self.routes),'TRANSPORT':self.transport_identity()})

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

def live_routed_provider(contexts,cap,environ):
    """Real routed provider. Requires both keys; never records or prints them."""
    from .anthropic_provider import AnthropicProvider
    from .openai_provider import OpenAIProvider
    okey=environ.get('OPENAI_API_KEY','');akey=environ.get('ANTHROPIC_API_KEY','')
    if not okey.strip() or not akey.strip():raise ContractError('routed live mode requires both OPENAI_API_KEY and ANTHROPIC_API_KEY')
    routes=routing.validate_routes()
    return RoutedProvider({'ANTHROPIC':AnthropicProvider(akey,allow_real=True,budget_micro_usd=cap,routes=routes,contexts=contexts),
                           'OPENAI':OpenAIProvider(okey,allow_real=True,budget_micro_usd=cap,contexts=contexts,routes=routes)},routes)
