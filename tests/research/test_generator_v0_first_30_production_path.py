"""Offline repair of the first 30-card production path. Fake transports only."""
import json
from collections import Counter

import pytest

from scripts.research.generator_v0.cloud_openai_transport import CloudProxyOpenAITransport
from scripts.research.generator_v0.context import Contexts, ContractError
from scripts.research.generator_v0.derive import (
    OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD, fresh_campaign_budget_preflight,
)
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import fixture, slot_plan
from scripts.research.generator_v0.models import ROLE_OUTPUT_TOKEN_CAPS
from scripts.research.generator_v0.provider import Caller
from scripts.research.generator_v0.roles import FEAS_PROMPT, NOVELTY_PROMPT, RED_PROMPT, Roles
from scripts.research.generator_v0.routed_provider import live_routed_provider, offline_routed_provider
from scripts.research.generator_v0.runner import (
    FIRST_30_CARD_SIZE, GENERATOR_CONTENT_ATTEMPTS, MAX_GENERATOR_POSTS_30,
    BudgetGateRefused, accept_budget_stop, enforce_campaign_budget, run_campaign,
)
from scripts.research.generator_v0_gate.noisy import CAP, NoisyTransport, routed_provider_for
from scripts.research.generator_v0 import memory_finalizer as fin
from tests.research.test_generator_v0_memory_finalizer import finalized_root

CAP30 = OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD
# Memory head the first 30-card run (GV0R01) was authorized and executed against.
# Its bounds and the GV0CAL-only finalizer fixture are pinned to that version.
GV0CAL_HEAD = '358f06d4e2d1f7d1657c89544fc702d7dffe7bf6c1ec920ceab4228f7a50c3ad'


def _campaign(tmp_path, name, faults=None, mutator=None):
    c = Contexts(memory_event=GV0CAL_HEAD)
    transport = NoisyTransport(c, faults or {}, compact_mutator=mutator)
    ledger = Ledger(tmp_path / name, {'RUN_ID': name, 'CAP_MICRO_USD': CAP})
    caller = Caller(c, ledger, routed_provider_for(transport, c), CAP, True)
    accept_budget_stop(c, caller, FIRST_30_CARD_SIZE, 'offline-repair', 'accept clean budget stop')
    result = run_campaign(c, caller, FIRST_30_CARD_SIZE)
    return result, ledger, transport


def _gen_posts(transport):
    return dict(Counter(rnd for (role, rnd) in transport.counts if role == 'GENERATOR'))


def test_constants():
    assert GENERATOR_CONTENT_ATTEMPTS == 1 and MAX_GENERATOR_POSTS_30 == 3 and FIRST_30_CARD_SIZE == 30


def test_successful_30_cards_post_generator_exactly_three_times(tmp_path):
    result, ledger, transport = _campaign(tmp_path, 'ok.sqlite')
    try:
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert result['METRICS']['SLOTS'] == 30 and result['METRICS']['VALID'] == 30
        assert _gen_posts(transport) == {0: 1, 1: 1, 2: 1}
        assert sum(_gen_posts(transport).values()) == 3
    finally:
        ledger.close()


def test_unusable_round_0_is_not_replayed(tmp_path):
    result, ledger, transport = _campaign(tmp_path, 'u.sqlite', mutator=lambda rnd, cards: cards if rnd else 'not-a-round')
    try:
        assert result['STATUS'] == 'STOPPED_INSUFFICIENT_VALID'
        posts = _gen_posts(transport)
        assert posts[0] == 1 and sum(posts.values()) <= 3 and 0 not in [k for k, v in posts.items() if v > 1]
    finally:
        ledger.close()


def test_billed_max_tokens_round_1_is_not_replayed(tmp_path):
    result, ledger, transport = _campaign(tmp_path, 'b.sqlite', faults={('GENERATOR', 1, 1): 'max_tokens'})
    try:
        assert result['STATUS'] == 'STOPPED_INSUFFICIENT_VALID'
        posts = _gen_posts(transport)
        assert posts[1] == 1 and sum(posts.values()) <= 3
        states = [r['STATE'] for r in ledger.export_calls() if r['SLOT'] == 'generation:1']
        assert states == ['FAILED_WITH_COST']
    finally:
        ledger.close()


def test_malformed_round_2_is_not_replayed(tmp_path):
    c = Contexts()
    transport = NoisyTransport(c, {})
    real = transport.anthropic

    def anthropic(method, path, body, headers, timeout):
        status, wire = real(method, path, body, headers, timeout)
        slots = json.loads(json.loads(body)['messages'][0]['content'])['slots']
        rnd = (int(slots[0]['CANDIDATE_ID'][1:]) - 1) // 10
        if rnd == 2 and status == 200:
            env = json.loads(wire)
            env['content'][1]['text'] = 'this is not json'
            env['stop_reason'] = 'end_turn'
            return 200, json.dumps(env).encode()
        return status, wire

    transport.anthropic = anthropic
    ledger = Ledger(tmp_path / 'm.sqlite', {'RUN_ID': 'm', 'CAP_MICRO_USD': CAP})
    caller = Caller(c, ledger, routed_provider_for(transport, c), CAP, True)
    accept_budget_stop(c, caller, 30, 'offline-repair', 'accept clean budget stop')
    result = run_campaign(c, caller, 30)
    try:
        assert result['STATUS'] == 'STOPPED_INSUFFICIENT_VALID'
        posts = _gen_posts(transport)
        assert posts[2] == 1 and sum(posts.values()) <= 3
    finally:
        ledger.close()


def test_successful_30_card_campaign_makes_zero_selector_calls(tmp_path):
    result, ledger, transport = _campaign(tmp_path, 'sel.sqlite')
    try:
        assert result['SELECTOR_AUTHORITY'] == 'DETERMINISTIC_ORDINAL_ORDER'
        assert result['SELECTOR_ADVISORY'] == {'STATUS': 'NOT_CALLED', 'REASON': 'deterministic-only first 30-card run'}
        assert len(result['SHORTLIST']) == 5
        roles = Counter(r['ROLE'] for r in ledger.export_calls())
        assert roles['SELECTOR'] == 0 if 'SELECTOR' in roles else True
        assert 'SELECTOR' not in roles
        assert transport.counts.get(('SELECTOR', 'selection'), 0) == 0
    finally:
        ledger.close()


class _Resp:
    def __init__(self, status, wire):
        self.status = status
        self._wire = wire

    def read(self, _n):
        return self._wire


class _Conn:
    made = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.sent = None
        self.sock = object()
        _Conn.made.append(self)

    def set_tunnel(self, host, port):
        self.tunnel = (host, port)

    def connect(self):
        return None

    def request(self, method, path, body, headers):
        self.sent = (method, path, body, headers)

    def getresponse(self):
        method, path, body, headers = self.sent
        if method == 'DELETE':
            return _Resp(200, b'{}')
        if method == 'GET':
            rid = path.rsplit('/', 1)[1]
            wire = json.dumps({'id': rid, 'status': 'completed', 'output_text': '{}',
                               'usage': {'input_tokens': 8, 'output_tokens': 4, 'output_tokens_details': {'reasoning_tokens': 1}}}).encode()
            return _Resp(200, wire)
        if path == '/v1/responses':
            return _Resp(200, b'{"id":"resp_cloud","status":"queued"}')
        return _Resp(200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":1}'}}],
                                      'usage': {'prompt_tokens': 8, 'completion_tokens': 4, 'completion_tokens_details': {}}}).encode())

    def close(self):
        return None


class _TLS:
    def wrap_socket(self, sock, *, server_hostname):
        return sock


def _patch_proxy(monkeypatch):
    _Conn.made = []
    monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:40465')
    monkeypatch.setattr('scripts.research.generator_v0.cloud_openai_transport.http.client.HTTPConnection', _Conn)
    monkeypatch.setattr('scripts.research.generator_v0.cloud_openai_transport.ssl.create_default_context', lambda: _TLS())

    def direct(*_a, **_k):
        raise AssertionError('direct OpenAI HTTPSConnection')

    monkeypatch.setattr('scripts.research.generator_v0.openai_provider.http.client.HTTPSConnection', direct)


def _cloud(environ):
    return live_routed_provider(Contexts(), CAP30, environ, openai_network_mode='CLOUD_PROXY')


def _critic_request(provider, role, prompt):
    c = Contexts()
    ledger = Ledger(':memory:', {'RUN_ID': 'cloud'})
    caller = Caller(c, ledger, provider, CAP30, True)
    cards = [fixture(s, c) for s in slot_plan(30)]
    ctx = Roles(c, caller).request(role, cards[0], cards if role == 'NOVELTY_CRITIC' else None)
    return caller.request(role, ctx, prompt, {'max_output_tokens': ROLE_OUTPUT_TOKEN_CAPS[role]}, role + ':C001'), ledger


def test_cloud_routed_provider_uses_proxy_transport(monkeypatch):
    _patch_proxy(monkeypatch)
    provider = _cloud({'ANTHROPIC_API_KEY': 'anthropic-test'})
    openai = provider.adapter_for('NOVELTY_CRITIC')
    assert isinstance(openai.transport, CloudProxyOpenAITransport)
    assert openai.network_mode == 'CLOUD_PROXY'
    assert openai._key is None
    assert provider.adapter_for('FEASIBILITY_CRITIC') is openai
    assert provider.adapter_for('RED_TEAM') is openai


def test_cloud_construction_without_openai_key_succeeds(monkeypatch):
    _patch_proxy(monkeypatch)
    provider = _cloud({'SIGNALBOT_ANTHROPIC_API_KEY': 'anthropic-test', 'HTTPS_PROXY': 'http://127.0.0.1:9'})
    assert provider.adapter_for('FEASIBILITY_CRITIC')._key is None


def test_cloud_construction_without_anthropic_credential_fails(monkeypatch):
    _patch_proxy(monkeypatch)
    with pytest.raises(ContractError, match='ANTHROPIC'):
        _cloud({'OPENAI_API_KEY': 'should-not-be-required', 'HTTPS_PROXY': 'http://127.0.0.1:9'})


def test_https_proxy_does_not_select_cloud_mode():
    with pytest.raises(ContractError, match='OPENAI_API_KEY'):
        live_routed_provider(Contexts(), CAP30, {'HTTPS_PROXY': 'http://127.0.0.1:9', 'ANTHROPIC_API_KEY': 'a'}, openai_network_mode='DIRECT')


def _background(provider, role, prompt):
    req, ledger = _critic_request(provider, role, prompt)
    try:
        adapter = provider.adapter_for(role)
        created = adapter.create_background(req)
        adapter.retrieve_background(created['response_id'])
        adapter.delete_background(created['response_id'])
    finally:
        ledger.close()


def test_novelty_background_uses_proxy(monkeypatch):
    _patch_proxy(monkeypatch)
    provider = _cloud({'ANTHROPIC_API_KEY': 'anthropic-test'})
    _background(provider, 'NOVELTY_CRITIC', NOVELTY_PROMPT)
    methods = [c.sent[0] for c in _Conn.made]
    assert methods == ['POST', 'GET', 'DELETE']
    assert all(c.host == '127.0.0.1' and c.port == 40465 for c in _Conn.made)
    assert all(c.tunnel == ('api.openai.com', 443) for c in _Conn.made)
    assert all('authorization' not in {k.lower() for k in c.sent[3]} for c in _Conn.made)


def test_red_team_background_uses_proxy(monkeypatch):
    _patch_proxy(monkeypatch)
    provider = _cloud({'ANTHROPIC_API_KEY': 'anthropic-test'})
    _background(provider, 'RED_TEAM', RED_PROMPT)
    assert [c.sent[0] for c in _Conn.made] == ['POST', 'GET', 'DELETE']
    assert all(c.host == '127.0.0.1' and c.port == 40465 for c in _Conn.made)


def test_feasibility_synchronous_call_uses_proxy(monkeypatch):
    _patch_proxy(monkeypatch)
    provider = _cloud({'ANTHROPIC_API_KEY': 'anthropic-test'})
    req, ledger = _critic_request(provider, 'FEASIBILITY_CRITIC', FEAS_PROMPT)
    try:
        provider.adapter_for('FEASIBILITY_CRITIC').complete(req)
    finally:
        ledger.close()
    assert [c.sent[0] for c in _Conn.made] == ['POST']
    assert _Conn.made[0].sent[1] == '/v1/chat/completions'
    assert _Conn.made[0].host == '127.0.0.1' and _Conn.made[0].port == 40465


def test_canonical_cloud_execution_never_opens_direct_https(monkeypatch):
    _patch_proxy(monkeypatch)
    provider = _cloud({'ANTHROPIC_API_KEY': 'anthropic-test'})
    req, ledger = _critic_request(provider, 'FEASIBILITY_CRITIC', FEAS_PROMPT)
    try:
        provider.complete(req)
    finally:
        ledger.close()
    assert _Conn.made and all(type(c) is _Conn for c in _Conn.made)


def test_budget_stop_acceptance_is_unchanged(tmp_path):
    c = Contexts(memory_event=GV0CAL_HEAD)
    bound = offline_routed_provider(c)
    pre = fresh_campaign_budget_preflight(30, CAP30, c, bound_provider=bound)
    stages = {row['STAGE']: row['BOUND_MICRO_USD'] for row in pre['STAGES']}
    assert pre['WORST_CASE_REMAINING_MICRO_USD'] == 19_516_751
    assert pre['FITS_AUTHORIZED_REMAINING'] is False
    assert stages['generation:0'] == 2_139_480
    assert stages['generation:1'] == 2_139_540
    assert stages['generation:2'] == 2_140_244
    ledger = Ledger(tmp_path / 'budget.sqlite', {'RUN_ID': 'budget', 'CAP_MICRO_USD': CAP30})
    caller = Caller(c, ledger, bound, CAP30, True)
    try:
        with pytest.raises(BudgetGateRefused):
            enforce_campaign_budget(c, caller, 30)
        accept_budget_stop(c, caller, 30, 'owner', 'worst case does not fit; hard cap remains')
        allowed = enforce_campaign_budget(c, caller, 30)
        assert allowed['WORST_CASE_REMAINING_MICRO_USD'] == 19_516_751
        assert ledger.export_calls() == []
    finally:
        ledger.close()


def test_full_zero_cost_30_card_production_shape(tmp_path):
    result, ledger, transport = _campaign(tmp_path, 'full.sqlite')
    try:
        roles = Counter(r['ROLE'] for r in ledger.export_calls())
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert result['METRICS']['SLOTS'] == 30 and result['METRICS']['VALID'] == 30
        assert roles['GENERATOR'] == 3
        assert roles['NOVELTY_CRITIC'] == 30
        assert roles['FEASIBILITY_CRITIC'] == 30
        assert roles['RED_TEAM'] == 30
        assert 'SELECTOR' not in roles
        assert len(result['SHORTLIST']) == 5
        assert result['SELECTOR_ADVISORY']['STATUS'] == 'NOT_CALLED'
        assert ledger.get('status') == 'PENDING_HUMAN_REVIEW'
        root = finalized_root(tmp_path)
        before = (root / 'docs/research/generator_v0_memory/HEAD.json').read_bytes()
        dry = fin.finalize(root, fin.source_from_run_journal(tmp_path / 'full.sqlite', 'GV0R30'))
        assert dry['STATUS'] == 'DRY_RUN' and dry['NEW_EVENT'] is False
        assert (root / 'docs/research/generator_v0_memory/HEAD.json').read_bytes() == before
    finally:
        ledger.close()
