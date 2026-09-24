"""Transport reliability amendment: routed RED_TEAM uses background Responses.

Only the transport of RED_TEAM changes (as NOVELTY_CRITIC before it). Model, effort,
prompt, schema, token cap, application validation and every other role are unchanged.
No network: every transport here is a scripted fake.
"""
import copy
import hashlib
import json
from decimal import ROUND_CEILING

import pytest

from scripts.research.generator_v0 import routing
from scripts.research.generator_v0.anthropic_provider import AnthropicProvider
from scripts.research.generator_v0.context import Contexts, canonical, digest, ContractError
from scripts.research.generator_v0.ledger import Ledger, CallUncertain
from scripts.research.generator_v0.mock import MockResponder, fixture, slot_plan
from scripts.research.generator_v0.models import ROLE_OUTPUT_TOKEN_CAPS
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.output_schemas import openai_response_format, role_schema
from scripts.research.generator_v0.provider import BackgroundPending, BilledFailure, Caller
from scripts.research.generator_v0.roles import RED_PROMPT, FEAS_PROMPT, NOVELTY_PROMPT, RoleContractError, Roles
from scripts.research.generator_v0.routed_provider import RoutedProvider, offline_routed_provider

# Identities, bounds and leaf counts pinned here were computed under the pre-GV0CAL memory,
# so they are bound to that memory version (memory-chain event LEGACY_BOOTSTRAP).
C = Contexts(memory_event='LEGACY_BOOTSTRAP')
CAP = 3_000_000
CARDS = [fixture(s, C) for s in slot_plan(40)[:5]]
CARD = CARDS[0]
OKEY = 'sk-openai-test-DO-NOT-PERSIST-9876543210'
AKEY = 'sk-ant-test-DO-NOT-PERSIST-0123456789'

# Route digests and the representative synchronous RED_TEAM call key at PR #218 head caa71a24.
PR218_ROUTE_DIGESTS = {
    'GENERATOR': 'b3b37124680fb5c5a7c0c20270f5361023076958832c3b28e9621eb8671a98d7',
    'NOVELTY_CRITIC': '597296d5c91d0b9fe3af97429111b16ed780493a1d198a97ddf2154edd670760',
    'RED_TEAM': 'b51a1a31975979186ac0d65c1b4983737a44b70d4d97e680ac73a9125d51f9b9',
    'FEASIBILITY_CRITIC': '842363ea5f0f7217673001ef25e86859196265cc1ea425bc8ac9a81b2a74b3f1',
    'SELECTOR': 'f0a3cc7a6e6178df1f2fae0ba94893f47de1216d4aa67f442191872ea7d05f43',
}
PR218_RED_TEAM_KEY = 'ef4bebf2407d036318befb3c78219de1666e1eabb86b2d58bf561a27e3bc8eb6'
PR218_FEASIBILITY_KEY = 'e13d21ca9b9ab6cd3f513ebb527ebe8eae604c9bf64373b19768025ec02f434a'


def sync_red_team_routes():
    """The PR #218 route table: RED_TEAM on synchronous Chat Completions."""
    r = copy.deepcopy(routing.ROUTES)
    r['RED_TEAM'].update(STRUCTURED_OUTPUT='OPENAI_CHAT_RESPONSE_FORMAT_JSON_SCHEMA_STRICT',
                         ENDPOINT='OPENAI_CHAT_COMPLETIONS', TRANSPORT=routing.OPENAI_CHAT_TRANSPORT)
    return r


class Script:
    """Scripted transport. Each answer is (status, bytes) or an exception to raise."""
    def __init__(self, *answers):
        self.answers = list(answers)
        self.log = []

    def __call__(self, method, path, body, headers, timeout):
        self.log.append((method, path, json.loads(body) if body else None))
        a = self.answers.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a

    def posts(self):
        return [(p, b) for m, p, b in self.log if m == 'POST']

    def gets(self):
        return [p for m, p, b in self.log if m == 'GET']


class Clock:
    def __init__(self):
        self.t = 0

    def __call__(self):
        return self.t


class Died(BaseException):
    pass


def router(transport, routes=None, clock=None, wait=3600):
    routes = routes or routing.ROUTES
    clock = clock or Clock()

    def refuse(*_a, **_k):
        raise AssertionError('no generator call in these tests')

    def sleep(seconds):
        clock.t += seconds
    return RoutedProvider({
        'ANTHROPIC': AnthropicProvider(AKEY, allow_real=True, budget_micro_usd=CAP, routes=routes, contexts=C, transport=refuse),
        'OPENAI': OpenAIProvider(OKEY, allow_real=True, budget_micro_usd=CAP, contexts=C, routes=routes, transport=transport,
                                 sleeper=sleep, clock=clock, background_max_wait_seconds=wait)}, routes)


def caller(transport, path=':memory:', routes=None, clock=None, wait=3600):
    return Caller(C, Ledger(path, {'RUN_ID': 'bg-red-team', 'CAP_MICRO_USD': CAP}), router(transport, routes, clock, wait), CAP, True)


def answer(card=CARD, **checks):
    payload = json.loads(MockResponder(C)({'role': 'RED_TEAM', 'context': Roles(C, None).request('RED_TEAM', card), 'parameters': {}}))
    payload['CHECKS'].update(checks)
    return canonical(payload)


def created(rid='resp_red_1', status='queued'):
    return 200, json.dumps({'id': rid, 'object': 'response', 'status': status}).encode()


def completed(text, rid='resp_red_1', inp=3000, out=900, reasoning=600, cached=0):
    body = {'id': rid, 'object': 'response', 'status': 'completed', 'model': 'gpt-6-sol',
            'output': [{'type': 'reasoning', 'id': 'rs_1', 'summary': [{'type': 'summary_text', 'text': 'HIDDEN_REASONING_SENTINEL'}],
                        'encrypted_content': 'ENCRYPTED_REASONING_SENTINEL'},
                       {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]}],
            'usage': {'input_tokens': inp, 'output_tokens': out, 'output_tokens_details': {'reasoning_tokens': reasoning},
                      'input_tokens_details': {'cached_tokens': cached}}}
    return 200, json.dumps(body).encode()


def polled(status, rid='resp_red_1'):
    return 200, json.dumps({'id': rid, 'object': 'response', 'status': status}).encode()


def chat(text, prompt=3000, completion=900):
    return 200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': text}}],
                            'usage': {'prompt_tokens': prompt, 'completion_tokens': completion}}).encode()


def red(cal, card=CARD):
    return Roles(C, cal).red_team(card)


def row(cal):
    return [r for r in cal.ledger.export_calls() if r['ROLE'] == 'RED_TEAM'][-1]


def request(cal, role, prompt, card, batch=None):
    ctx = Roles(C, cal).request(role, card, batch) if batch else Roles(C, cal).request(role, card)
    return cal.request(role, ctx, prompt, {'max_output_tokens': ROLE_OUTPUT_TOKEN_CAPS[role]}, role + ':' + card['CANDIDATE_ID'])


def identity_requests(routes=None):
    """Requests built exactly as the PR #217/#218 identity dump built them."""
    cal = Caller(C, Ledger(':memory:', {'RUN_ID': 'id'}), offline_routed_provider(C, routes), CAP, True)
    card = fixture(slot_plan(40)[10], C)
    batch = [fixture(s, C) for s in slot_plan(40)[10:14]]
    return {'RED_TEAM': request(cal, 'RED_TEAM', RED_PROMPT, card),
            'FEASIBILITY_CRITIC': request(cal, 'FEASIBILITY_CRITIC', FEAS_PROMPT, card),
            'NOVELTY_CRITIC': request(cal, 'NOVELTY_CRITIC', NOVELTY_PROMPT, card, batch)}


# 1-3 routing, request shape, schema ------------------------------------------------------

def test_1_red_team_is_routed_to_background_responses():
    r = routing.validate_routes()['RED_TEAM']
    assert r['ENDPOINT'] == 'OPENAI_RESPONSES_BACKGROUND' and r['TRANSPORT'] == routing.OPENAI_RESPONSES_BACKGROUND_TRANSPORT
    assert r['STRUCTURED_OUTPUT'] == 'OPENAI_RESPONSES_TEXT_FORMAT_JSON_SCHEMA_STRICT'
    assert (r['PROVIDER'], r['MODEL'], r['PARAMS'], r['MAX_OUTPUT_TOKENS']) == ('OPENAI', 'gpt-6-sol', {'reasoning_effort': 'high'}, 8000)
    assert r['MAX_OUTPUT_TOKENS'] == ROLE_OUTPUT_TOKEN_CAPS['RED_TEAM'] == sync_red_team_routes()['RED_TEAM']['MAX_OUTPUT_TOKENS']
    for field in ('PROVIDER', 'MODEL', 'PARAMS', 'MAX_OUTPUT_TOKENS'):
        assert r[field] == sync_red_team_routes()['RED_TEAM'][field]
    p = offline_routed_provider(C)
    assert p.uses_background('RED_TEAM') and p.endpoint_for('RED_TEAM') == 'OPENAI_RESPONSES_BACKGROUND'


def test_2_create_is_background_store_no_stream_then_get_only():
    t = Script(created(), completed(answer()), (200, b'{}'))
    red(caller(t))
    (path, body), = t.posts()
    assert path == '/v1/responses' and t.gets() == ['/v1/responses/resp_red_1']
    assert [m for m, p, b in t.log] == ['POST', 'GET', 'DELETE']
    assert body['background'] is True and body['store'] is True and body['stream'] is False
    assert body['model'] == 'gpt-6-sol' and body['reasoning'] == {'effort': 'high'} and body['max_output_tokens'] == 8000
    assert body['instructions'] == RED_PROMPT and body['service_tier'] == 'default'
    assert json.loads(body['input']) == {'context': Roles(C, None).request('RED_TEAM', CARD)}
    assert not {'tools', 'temperature', 'top_p', 'messages', 'response_format', 'reasoning_effort'} & set(body)


def test_3_red_team_schema_is_the_exact_strict_chat_schema():
    cal = Caller(C, Ledger(':memory:', {'RUN_ID': 's'}), offline_routed_provider(C), CAP, True)
    req = request(cal, 'RED_TEAM', RED_PROMPT, CARD)
    fmt = cal.provider.adapter_for('RED_TEAM').responses_payload(req)['text']['format']
    chat_fmt = openai_response_format('RED_TEAM', C, req)['json_schema']
    assert fmt == {'type': 'json_schema', 'name': chat_fmt['name'], 'strict': True, 'schema': chat_fmt['schema']}
    assert fmt['name'] == 'red_team' and fmt['schema'] == role_schema('RED_TEAM', C, provider=True)
    s = fmt['schema']
    assert sorted(s['required']) == ['CHECKS', 'JUDGMENTS'] and s['additionalProperties'] is False
    assert sorted(s['properties']['CHECKS']['required']) == sorted(['NO_LOOKAHEAD', 'CAUSALITY', 'FALSIFIABLE', 'BOUNDED_SEARCH', 'CONFOUNDING_ADDRESSED', 'NO_TRADING_CLAIM'])
    assert sorted(s['properties']['JUDGMENTS']['required']) == sorted(['FALSIFIABILITY', 'NO_LOOKAHEAD_QUALITY', 'CONFOUNDING_AWARENESS', 'SEARCH_SURFACE_DISCIPLINE', 'NULL_INFORMATION_GAIN'])


# 4-7 completion, reasoning, hashes ----------------------------------------------------------

def test_4_successful_completed_response_is_admitted():
    cal = caller(Script(created(), completed(answer()), (200, b'{}')))
    out = red(cal)
    assert out['VERDICT'] == 'PASS' and all(out['CHECKS'].values()) and set(out['JUDGMENTS']) >= {'NULL_INFORMATION_GAIN'}
    r = row(cal)
    assert r['STATE'] == 'COMPLETE' and r['RESPONSE_ID'] == 'resp_red_1' and r['PROVIDER_STATUS'] == 'completed'
    assert r['MODEL_PROVIDER'] == 'OPENAI_RESPONSES_BACKGROUND'


def test_5_reasoning_tokens_captured_reasoning_content_not_persisted():
    cal = caller(Script(created(), completed(answer(), reasoning=600, cached=128), (200, b'{}')))
    red(cal)
    r = row(cal)
    assert r['USAGE'] == {'input_tokens': 3000, 'output_tokens': 900, 'reasoning_tokens': 600, 'cached_tokens': 128}
    stored = cal.ledger.db.execute('SELECT response FROM calls WHERE key=?', (r['CALL_KEY'],)).fetchone()[0]
    for sentinel in ('HIDDEN_REASONING_SENTINEL', 'ENCRYPTED_REASONING_SENTINEL'):
        assert sentinel not in stored and sentinel not in canonical(cal.ledger.export_calls())
    assert OKEY not in stored and OKEY not in canonical(cal.ledger.export_calls())


def test_6_7_raw_sha_is_model_text_and_wire_sha_is_terminal_envelope():
    text = answer()
    status, wire = completed(text)
    cal = caller(Script(created(), (status, wire), (200, b'{}')))
    red(cal)
    r = row(cal)
    assert r['RAW_RESPONSE_SHA256'] == hashlib.sha256(text.encode()).hexdigest()
    assert r['WIRE_SHA256'] == hashlib.sha256(wire).hexdigest() != r['RAW_RESPONSE_SHA256']


# 8-14 exactly-once create, polling, resume, delete ---------------------------------------------

def test_8_create_timeout_is_uncertain_and_never_replayed(tmp_path):
    db = tmp_path / 'j.sqlite'
    t1 = Script(TimeoutError('create timed out'))
    with pytest.raises(CallUncertain):
        red(caller(t1, db))
    assert len(t1.posts()) == 1
    t2 = Script()
    with pytest.raises(CallUncertain):
        red(caller(t2, db))
    assert t2.log == []
    l = Ledger(db)
    assert [x['STATE'] for x in l.export_calls()] == ['UNCERTAIN']
    l.close()


@pytest.mark.parametrize('ack', [(502, b'<html>Bad Gateway</html>'), (200, b'{"object":"response"}'), (200, b'not json')])
def test_9_ambiguous_create_is_uncertain_and_never_replayed(tmp_path, ack):
    db = tmp_path / 'j.sqlite'
    t1 = Script(ack)
    with pytest.raises(CallUncertain):
        red(caller(t1, db))
    assert len(t1.posts()) == 1
    t2 = Script()
    with pytest.raises(CallUncertain):
        red(caller(t2, db))
    assert t2.log == []


def test_10_response_id_is_persisted_before_polling(tmp_path):
    db = tmp_path / 'j.sqlite'
    t = Script(created(), Died('process died on the first GET'))
    with pytest.raises(Died):
        red(caller(t, db))
    assert len(t.posts()) == 1 and t.gets() == ['/v1/responses/resp_red_1']
    l = Ledger(db)
    r, = l.export_calls()
    assert r['STATE'] == 'BACKGROUND_SUBMITTED' and r['RESPONSE_ID'] == 'resp_red_1'
    l.close()


def test_11_polling_failure_leaves_resumable_get_only_state(tmp_path):
    db = tmp_path / 'j.sqlite'
    t = Script(created(), *[TimeoutError('poll')] * 5, polled('in_progress'), polled('in_progress'), polled('in_progress'))
    with pytest.raises(BackgroundPending):
        red(caller(t, db, wait=20))
    assert len(t.posts()) == 1 and len(t.gets()) >= 2
    l = Ledger(db)
    r, = l.export_calls()
    assert r['STATE'] == 'BACKGROUND_SUBMITTED' and r['RESPONSE_ID'] == 'resp_red_1' and r['COST_MICRO_USD'] is None
    l.close()


def test_12_13_resume_with_response_id_makes_zero_posts_and_completes(tmp_path):
    db = tmp_path / 'j.sqlite'
    with pytest.raises(Died):
        red(caller(Script(created(), Died('died')), db))
    t2 = Script(TimeoutError('poll'), (503, b'{}'), polled('in_progress'), completed(answer()), (200, b'{}'))
    out = red(caller(t2, db))
    assert t2.posts() == [] and t2.gets() == ['/v1/responses/resp_red_1'] * 4
    assert out['VERDICT'] == 'PASS'
    l = Ledger(db)
    r, = l.export_calls()
    assert r['STATE'] == 'COMPLETE' and r['RESPONSE_ID'] == 'resp_red_1'
    l.close()


@pytest.mark.parametrize('delete_answer', [ConnectionResetError('delete failed'), (500, b'{}'), TimeoutError('delete timed out')])
def test_14_best_effort_delete_does_not_affect_logical_completion(delete_answer):
    cal = caller(Script(created(), completed(answer()), delete_answer))
    out = red(cal)
    assert out['VERDICT'] == 'PASS' and row(cal)['STATE'] == 'COMPLETE'
    assert cal.ledger.unresolved_calls() == []


# 15 application validation unchanged ------------------------------------------------------------

@pytest.mark.parametrize('checks', [{}, {'NO_LOOKAHEAD': False}, {'CAUSALITY': False, 'BOUNDED_SEARCH': False}])
def test_15_same_semantic_answer_normalizes_identically_on_both_transports(checks):
    text = answer(**checks)
    bg = red(caller(Script(created(), completed(text), (200, b'{}'))))
    sync = red(caller(Script(chat(text)), routes=sync_red_team_routes()))
    assert bg == sync
    assert bg['VERDICT'] == ('PASS' if not checks else 'REJECT')


@pytest.mark.parametrize('mutate', [lambda p: p.pop('JUDGMENTS'), lambda p: p['CHECKS'].pop('NO_TRADING_CLAIM'),
                                    lambda p: p['JUDGMENTS'].update(FALSIFIABILITY=4), lambda p: p.update(EXTRA=1)])
def test_15_invalid_red_team_answers_are_still_refused_on_background(mutate):
    payload = json.loads(answer())
    mutate(payload)
    with pytest.raises(RoleContractError):
        red(caller(Script(created(), completed(canonical(payload)), (200, b'{}'))))
    with pytest.raises(RoleContractError):
        red(caller(Script(chat(canonical(payload))), routes=sync_red_team_routes()))


def test_15_malformed_completed_text_is_a_content_failure_not_a_success():
    cal = caller(Script(created(), completed('this is not json'), (200, b'{}')))
    with pytest.raises(RoleContractError):
        red(cal)
    assert row(cal)['STATE'] == 'COMPLETE'


# 16-19 identity ---------------------------------------------------------------------------------------

def test_16_route_and_call_identity_change_and_old_key_is_not_reusable():
    assert routing.role_route_digest('RED_TEAM', sync_red_team_routes()) == PR218_ROUTE_DIGESTS['RED_TEAM']
    assert routing.role_route_digest('RED_TEAM') != PR218_ROUTE_DIGESTS['RED_TEAM']
    old, new = identity_requests(sync_red_team_routes())['RED_TEAM'], identity_requests()['RED_TEAM']
    assert digest(old) == PR218_RED_TEAM_KEY and digest(new) != PR218_RED_TEAM_KEY
    assert old['provider'] == 'OPENAI_CHAT_COMPLETIONS' and new['provider'] == 'OPENAI_RESPONSES_BACKGROUND'
    with pytest.raises(ContractError):
        offline_routed_provider(C).bound(old)     # an old synchronous red-team request is refused by the new route


def test_16_a_completed_synchronous_red_team_row_is_never_served_to_the_background_route(tmp_path):
    db = tmp_path / 'j.sqlite'
    sync = Script(chat(answer()))
    red(caller(sync, db, routes=sync_red_team_routes()))
    assert len(sync.posts()) == 1
    bg = Script(created(), completed(answer()), (200, b'{}'))
    red(caller(bg, db))
    assert [p for p, b in bg.posts()] == ['/v1/responses']
    l = Ledger(db)
    rows = [r for r in l.export_calls() if r['ROLE'] == 'RED_TEAM']
    assert [r['MODEL_PROVIDER'] for r in rows] == ['OPENAI_CHAT_COMPLETIONS', 'OPENAI_RESPONSES_BACKGROUND']
    assert rows[0]['CALL_KEY'] != rows[1]['CALL_KEY']
    l.close()


def test_17_18_19_other_route_identities_are_unchanged():
    for role in ('GENERATOR', 'NOVELTY_CRITIC', 'FEASIBILITY_CRITIC', 'SELECTOR'):
        assert routing.role_route_digest(role) == PR218_ROUTE_DIGESTS[role]
    assert routing.validate_routes()['NOVELTY_CRITIC']['ENDPOINT'] == 'OPENAI_RESPONSES_BACKGROUND'
    assert routing.validate_routes()['FEASIBILITY_CRITIC']['ENDPOINT'] == 'OPENAI_CHAT_COMPLETIONS'
    assert routing.validate_routes()['SELECTOR']['ENDPOINT'] == 'OPENAI_CHAT_COMPLETIONS'
    assert routing.validate_routes()['GENERATOR']['ENDPOINT'] == 'ANTHROPIC_MESSAGES'
    assert digest(identity_requests()['FEASIBILITY_CRITIC']) == PR218_FEASIBILITY_KEY
    assert identity_requests()['NOVELTY_CRITIC'] == identity_requests(sync_red_team_routes())['NOVELTY_CRITIC']


def test_18_feasibility_stays_synchronous_chat_completions():
    ans = MockResponder(C)({'role': 'FEASIBILITY_CRITIC', 'context': Roles(C, None).request('FEASIBILITY_CRITIC', CARD), 'parameters': {}})
    t = Script(chat(ans, prompt=500, completion=200))
    Roles(C, caller(t)).feasibility(CARD)
    (path, body), = t.posts()
    assert path == '/v1/chat/completions' and t.gets() == [] and len(t.log) == 1
    assert body['model'] == 'gpt-6-luna' and body['reasoning_effort'] == 'low' and body['store'] is False


# 20 cost reservation and accounting --------------------------------------------------------------------

def test_20_cost_and_reservation_accounting():
    cal = caller(Script(created(), polled('in_progress'), completed(answer(), inp=3000, out=900, cached=2000), (200, b'{}')))
    req = request(cal, 'RED_TEAM', RED_PROMPT, CARD)
    body = cal.provider.adapter_for('RED_TEAM').responses_payload(req)
    rates = routing.PRICES['gpt-6-sol']
    expected_bound = int((rates['INPUT'] * (len(canonical(body).encode()) + 1024) + rates['OUTPUT'] * 8000).to_integral_value(rounding=ROUND_CEILING))
    assert cal.provider.bound(req) == expected_bound
    red(cal)
    r = row(cal)
    assert r['RESERVED_MICRO_USD'] == expected_bound
    expected_cost = int((rates['INPUT'] * 3000 + rates['OUTPUT'] * 900).to_integral_value(rounding=ROUND_CEILING))
    assert r['COST_MICRO_USD'] == expected_cost == 15000 <= r['RESERVED_MICRO_USD']      # cached input priced at the standard rate
    assert len(cal.ledger.export_calls()) == 1 and cal.ledger.spent_micro_usd() == expected_cost   # GET polls reserve nothing


def test_20_terminal_incomplete_is_billed_with_usage_and_never_retried():
    body = {'id': 'resp_red_1', 'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'},
            'output': [{'type': 'reasoning', 'id': 'rs', 'summary': [{'type': 'summary_text', 'text': 'HIDDEN_REASONING_SENTINEL'}]}],
            'usage': {'input_tokens': 3000, 'output_tokens': 8000, 'output_tokens_details': {'reasoning_tokens': 7900}}}
    wire = json.dumps(body).encode()
    t = Script(created(), (200, wire))
    cal = caller(t)
    with pytest.raises(BilledFailure):
        cal.call('RED_TEAM', Roles(C, cal).request('RED_TEAM', CARD), RED_PROMPT, {'max_output_tokens': 8000}, 'RED_TEAM:C001')
    r = row(cal)
    assert r['STATE'] == 'FAILED_WITH_COST' and r['COST_BASIS'] == 'USAGE' and r['COST_MICRO_USD'] == 3000 * 2 + 8000 * 10
    assert r['RAW_RESPONSE_SHA256'] is None and r['WIRE_SHA256'] == hashlib.sha256(wire).hexdigest()
    assert len(t.posts()) == 1
    assert cal.ledger.db.execute("SELECT count(*) FROM calls WHERE response LIKE '%HIDDEN_REASONING%'").fetchone()[0] == 0
