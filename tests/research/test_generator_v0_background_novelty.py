"""Transport reliability amendment: routed NOVELTY_CRITIC uses background Responses.

Only the transport of NOVELTY_CRITIC changes. Model, effort, prompt, schema,
application contract, budget authority and every other role are unchanged.
No network: every transport here is a scripted fake.
"""
import copy
import hashlib
import json
from decimal import Decimal, ROUND_CEILING

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
from scripts.research.generator_v0.roles import FEAS_PROMPT, NOVELTY_PROMPT, RED_PROMPT, RoleContractError, Roles
from scripts.research.generator_v0.routed_provider import RoutedProvider, offline_routed_provider

C = Contexts()
CAP = 3_000_000
CARDS = [fixture(s, C) for s in slot_plan(40)[:5]]
CARD = CARDS[0]
LEAVES = sorted(k for k, r in C.rows.items() if r['STATE'] != 'PARTIAL_OR_MIXED')
OKEY = 'sk-openai-test-DO-NOT-PERSIST-9876543210'
AKEY = 'sk-ant-test-DO-NOT-PERSIST-0123456789'

# Route identities and critic call keys at PR #217 head f614935 (before this amendment).
PRE_AMENDMENT_ROUTE_DIGESTS = {
    'FEASIBILITY_CRITIC': '842363ea5f0f7217673001ef25e86859196265cc1ea425bc8ac9a81b2a74b3f1',
    'GENERATOR': 'b3b37124680fb5c5a7c0c20270f5361023076958832c3b28e9621eb8671a98d7',
    'NOVELTY_CRITIC': 'b784767ebd44e50cfe7e3d86062b86984ad040f6b851cc0a6a330ad515714f03',
    'RED_TEAM': 'b51a1a31975979186ac0d65c1b4983737a44b70d4d97e680ac73a9125d51f9b9',
    'SELECTOR': 'f0a3cc7a6e6178df1f2fae0ba94893f47de1216d4aa67f442191872ea7d05f43',
}
PRE_AMENDMENT_KEYS = {'FEASIBILITY_CRITIC': 'e13d21ca9b9ab6cd3f513ebb527ebe8eae604c9bf64373b19768025ec02f434a',
                      'RED_TEAM': 'ef4bebf2407d036318befb3c78219de1666e1eabb86b2d58bf561a27e3bc8eb6',
                      'NOVELTY_CRITIC': '6f701215dcebfff46d0c5745d31adb12a1bc0ba52a2b5ff7f7aff5904b7825e2'}


def chat_routes():
    """The pre-amendment route table: NOVELTY_CRITIC on synchronous Chat Completions."""
    r = copy.deepcopy(routing.ROUTES)
    r['NOVELTY_CRITIC'].update(STRUCTURED_OUTPUT='OPENAI_CHAT_RESPONSE_FORMAT_JSON_SCHEMA_STRICT',
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


def router(transport, routes=None, clock=None, wait=3600):
    routes = routes or routing.ROUTES

    def refuse(*_a, **_k):
        raise AssertionError('no generator call in these tests')
    clock = clock or Clock()

    def sleep(seconds):
        clock.t += seconds
    return RoutedProvider({
        'ANTHROPIC': AnthropicProvider(AKEY, allow_real=True, budget_micro_usd=CAP, routes=routes, contexts=C, transport=refuse),
        'OPENAI': OpenAIProvider(OKEY, allow_real=True, budget_micro_usd=CAP, contexts=C, routes=routes, transport=transport,
                                 sleeper=sleep, clock=clock, background_max_wait_seconds=wait)}, routes)


def caller(transport, path=':memory:', routes=None, clock=None, wait=3600):
    ledger = Ledger(path, {'RUN_ID': 'bg-novelty', 'CAP_MICRO_USD': CAP})
    return Caller(C, ledger, router(transport, routes, clock, wait), CAP, True)


def novelty_answer(card=CARD, batch=CARDS):
    ctx = Roles(C, None).request('NOVELTY_CRITIC', card, batch)
    return MockResponder(C)({'role': 'NOVELTY_CRITIC', 'context': ctx, 'parameters': {}})


def created(rid='resp_nov_1', status='queued'):
    return 200, json.dumps({'id': rid, 'object': 'response', 'status': status}).encode()


def completed(text, rid='resp_nov_1', inp=9000, out=1500, reasoning=900, cached=4000):
    body = {'id': rid, 'object': 'response', 'status': 'completed', 'model': 'gpt-6-sol',
            'output': [{'type': 'reasoning', 'id': 'rs_1', 'summary': [{'type': 'summary_text', 'text': 'HIDDEN_REASONING_SENTINEL'}],
                        'encrypted_content': 'ENCRYPTED_REASONING_SENTINEL'},
                       {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]}],
            'usage': {'input_tokens': inp, 'output_tokens': out, 'output_tokens_details': {'reasoning_tokens': reasoning},
                      'input_tokens_details': {'cached_tokens': cached}}}
    return 200, json.dumps(body).encode()


def polled(status, rid='resp_nov_1'):
    return 200, json.dumps({'id': rid, 'object': 'response', 'status': status}).encode()


def chat(text, prompt=9000, completion=1500):
    return 200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': text}}],
                            'usage': {'prompt_tokens': prompt, 'completion_tokens': completion}}).encode()


def novelty(cal):
    return Roles(C, cal).novelty(CARD, CARDS)


def row(cal, role='NOVELTY_CRITIC'):
    return [r for r in cal.ledger.export_calls() if r['ROLE'] == role][-1]


def critic_request(cal, role, prompt, card=CARD, batch=None):
    ctx = Roles(C, cal).request(role, card, batch) if batch else Roles(C, cal).request(role, card)
    return cal.request(role, ctx, prompt, {'max_output_tokens': ROLE_OUTPUT_TOKEN_CAPS[role]}, role + ':' + card['CANDIDATE_ID'])


# 1-5 routing and request shape -------------------------------------------------------

def test_novelty_uses_background_responses_and_only_novelty_changed():
    routes = routing.validate_routes()
    assert routes['NOVELTY_CRITIC']['ENDPOINT'] == 'OPENAI_RESPONSES_BACKGROUND'
    assert routes['NOVELTY_CRITIC']['TRANSPORT']['PATH'] == '/v1/responses'
    assert routes['NOVELTY_CRITIC']['TRANSPORT']['BACKGROUND'] is True and routes['NOVELTY_CRITIC']['TRANSPORT']['STORE'] is True
    assert routes['NOVELTY_CRITIC']['TRANSPORT']['STREAM'] is False
    for role in ('FEASIBILITY_CRITIC', 'RED_TEAM', 'SELECTOR'):
        assert routes[role]['ENDPOINT'] == 'OPENAI_CHAT_COMPLETIONS' and routes[role] == chat_routes()[role]
    p = offline_routed_provider(C)
    assert p.uses_background('NOVELTY_CRITIC') is True
    assert not any(p.uses_background(r) for r in ('GENERATOR', 'FEASIBILITY_CRITIC', 'RED_TEAM', 'SELECTOR'))


def test_novelty_request_is_one_background_create_then_get_only():
    t = Script(created(), completed(novelty_answer()), (200, b'{}'))
    novelty(caller(t))
    (path, body), = t.posts()
    assert path == '/v1/responses' and t.gets() == ['/v1/responses/resp_nov_1']
    assert body['background'] is True and body['store'] is True and body['stream'] is False
    assert body['model'] == 'gpt-6-sol' and body['reasoning'] == {'effort': 'high'}
    assert body['max_output_tokens'] == ROLE_OUTPUT_TOKEN_CAPS['NOVELTY_CRITIC'] == 12000
    assert body['instructions'] == NOVELTY_PROMPT and body['service_tier'] == 'default'
    assert not {'tools', 'temperature', 'top_p', 'stream_options'} & set(body)


@pytest.mark.parametrize('role,prompt,model,effort', [('FEASIBILITY_CRITIC', FEAS_PROMPT, 'gpt-6-luna', 'low'),
                                                      ('RED_TEAM', RED_PROMPT, 'gpt-6-sol', 'high')])
def test_feasibility_and_red_team_remain_synchronous_chat_completions(role, prompt, model, effort):
    answer = MockResponder(C)({'role': role, 'context': Roles(C, None).request(role, CARD), 'parameters': {}})
    t = Script(chat(answer, prompt=500, completion=200))
    cal = caller(t)
    (Roles(C, cal).feasibility if role == 'FEASIBILITY_CRITIC' else Roles(C, cal).red_team)(CARD)
    (path, body), = t.posts()
    assert path == '/v1/chat/completions' and t.gets() == [] and len(t.log) == 1
    assert body['model'] == model and body['reasoning_effort'] == effort and body['store'] is False and body['stream'] is False


def test_novelty_model_and_effort_are_unchanged():
    assert routing.ROUTES['NOVELTY_CRITIC']['MODEL'] == chat_routes()['NOVELTY_CRITIC']['MODEL'] == 'gpt-6-sol'
    assert routing.ROUTES['NOVELTY_CRITIC']['PARAMS'] == {'reasoning_effort': 'high'}
    assert routing.ROUTES['NOVELTY_CRITIC']['MAX_OUTPUT_TOKENS'] == ROLE_OUTPUT_TOKEN_CAPS['NOVELTY_CRITIC']


# 6, 12-14 schema and result equivalence -----------------------------------------------

def test_novelty_schema_is_the_exact_strict_chat_schema():
    p = offline_routed_provider(C)
    cal = Caller(C, Ledger(':memory:', {'RUN_ID': 's'}), p, CAP, True)
    req = critic_request(cal, 'NOVELTY_CRITIC', NOVELTY_PROMPT, batch=CARDS)
    fmt = p.adapter_for('NOVELTY_CRITIC').responses_payload(req)['text']['format']
    chat_fmt = openai_response_format('NOVELTY_CRITIC', C, req)['json_schema']
    assert fmt == {'type': 'json_schema', 'name': chat_fmt['name'], 'strict': True, 'schema': chat_fmt['schema']}
    assert fmt['schema'] == role_schema('NOVELTY_CRITIC', C, provider=True, request=req)
    prior = fmt['schema']['properties']['PRIOR_RELATIONS']
    assert sorted(prior['properties']) == sorted(prior['required']) == LEAVES and len(LEAVES) == 31
    assert {'D4.ROLLING_CORRELATION_90D', 'D4.LEAD_LAG_1DAY', 'B2-06'} <= set(LEAVES)
    batch = fmt['schema']['properties']['BATCH_RELATIONS']
    assert sorted(batch['properties']) == sorted(batch['required']) == ['C002', 'C003', 'C004', 'C005']
    assert prior['additionalProperties'] is False and batch['additionalProperties'] is False


def test_background_and_chat_novelty_normalize_to_the_same_application_result():
    text = novelty_answer()
    bg = novelty(caller(Script(created(), completed(text), (200, b'{}'))))
    sync = novelty(caller(Script(chat(text)), routes=chat_routes()))
    assert bg == sync
    assert len(bg['PRIOR_RELATIONS']) == 31 and sorted(r['SIGNATURE_ID'] for r in bg['PRIOR_RELATIONS']) == LEAVES
    assert sorted(r['CANDIDATE_ID'] for r in bg['BATCH_RELATIONS']) == ['C002', 'C003', 'C004', 'C005']


def test_background_novelty_still_rejects_a_missing_batch_relation():
    payload = json.loads(novelty_answer())
    payload['BATCH_RELATIONS'].pop('C003')
    with pytest.raises(RoleContractError):
        novelty(caller(Script(created(), completed(canonical(payload)), (200, b'{}'))))


# 7-11 exactly-once create and polling ---------------------------------------------------

class Died(BaseException):
    pass


def test_create_persists_response_id_and_resume_only_polls(tmp_path):
    db = tmp_path / 'j.sqlite'
    t1 = Script(created(), Died('process died while polling'))
    with pytest.raises(Died):
        novelty(caller(t1, db))
    assert len(t1.posts()) == 1
    l = Ledger(db)
    r = [x for x in l.export_calls() if x['ROLE'] == 'NOVELTY_CRITIC'][0]
    assert r['STATE'] == 'BACKGROUND_SUBMITTED' and r['RESPONSE_ID'] == 'resp_nov_1'
    l.close()
    t2 = Script(completed(novelty_answer()), (200, b'{}'))
    result = novelty(caller(t2, db))
    assert t2.posts() == [] and t2.gets() == ['/v1/responses/resp_nov_1'] and result['JUDGMENTS']


def test_queued_and_in_progress_are_polled_with_get_only():
    t = Script(created(), polled('queued'), polled('in_progress'), polled('in_progress'), completed(novelty_answer()), (200, b'{}'))
    novelty(caller(t))
    assert len(t.posts()) == 1 and len(t.gets()) == 4
    assert [m for m, p, b in t.log] == ['POST', 'GET', 'GET', 'GET', 'GET', 'DELETE']


def test_create_timeout_before_response_id_is_uncertain_and_never_replayed(tmp_path):
    db = tmp_path / 'j.sqlite'
    t1 = Script(TimeoutError('create timed out'))
    with pytest.raises(CallUncertain):
        novelty(caller(t1, db))
    assert len(t1.posts()) == 1
    t2 = Script()
    with pytest.raises(CallUncertain):
        novelty(caller(t2, db))
    assert t2.log == []
    l = Ledger(db)
    assert [x['STATE'] for x in l.export_calls()] == ['UNCERTAIN']
    l.close()


@pytest.mark.parametrize('ack', [(502, b'<html>Bad Gateway</html>'), (200, b'{"object":"response"}'), (200, b'not json')])
def test_ambiguous_create_answer_is_uncertain_and_not_replayed(tmp_path, ack):
    db = tmp_path / 'j.sqlite'
    t1 = Script(ack)
    with pytest.raises(CallUncertain):
        novelty(caller(t1, db))
    assert len(t1.posts()) == 1
    t2 = Script()
    with pytest.raises(CallUncertain):
        novelty(caller(t2, db))
    assert t2.log == []


def test_polling_timeouts_never_post_again_and_resume_keeps_polling(tmp_path):
    db = tmp_path / 'j.sqlite'
    t1 = Script(created(), *[TimeoutError('poll')] * 5, polled('in_progress'), polled('in_progress'), polled('in_progress'))
    with pytest.raises(BackgroundPending):
        novelty(caller(t1, db, wait=20))
    assert len(t1.posts()) == 1 and len(t1.gets()) >= 2
    l = Ledger(db)
    assert l.export_calls()[0]['STATE'] == 'BACKGROUND_SUBMITTED'
    l.close()
    t2 = Script(TimeoutError('poll'), (503, b'{}'), completed(novelty_answer()), (200, b'{}'))
    novelty(caller(t2, db))
    assert t2.posts() == [] and len(t2.gets()) == 3


# 15-17 terminal failures, provenance, usage and cost --------------------------------------

def test_terminal_incomplete_is_billed_with_usage_and_fails_closed():
    body = {'id': 'resp_nov_1', 'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'},
            'output': [{'type': 'reasoning', 'id': 'rs', 'summary': [{'type': 'summary_text', 'text': 'HIDDEN_REASONING_SENTINEL'}]}],
            'usage': {'input_tokens': 9000, 'output_tokens': 12000, 'output_tokens_details': {'reasoning_tokens': 11900}}}
    wire = json.dumps(body).encode()
    cal = caller(Script(created(), (200, wire)))
    with pytest.raises(BilledFailure):
        cal.call('NOVELTY_CRITIC', Roles(C, cal).request('NOVELTY_CRITIC', CARD, CARDS), NOVELTY_PROMPT,
                 {'max_output_tokens': 12000}, 'NOVELTY_CRITIC:C001')
    r = row(cal)
    assert r['STATE'] == 'FAILED_WITH_COST' and r['COST_BASIS'] == 'USAGE'
    assert r['COST_MICRO_USD'] == 9000 * 2 + 12000 * 10 and r['RAW_RESPONSE_SHA256'] is None
    assert r['WIRE_SHA256'] == hashlib.sha256(wire).hexdigest()
    assert b'HIDDEN_REASONING_SENTINEL' not in canonical(cal.ledger.export_calls()).encode()
    assert cal.ledger.db.execute("SELECT count(*) FROM calls WHERE response LIKE '%HIDDEN_REASONING%'").fetchone()[0] == 0


def test_completed_without_output_text_is_billed_and_fails_closed():
    body = {'id': 'resp_nov_1', 'status': 'completed', 'output': [], 'usage': {'input_tokens': 9000, 'output_tokens': 50}}
    cal = caller(Script(created(), (200, json.dumps(body).encode())))
    with pytest.raises(BilledFailure):
        novelty(cal)
    r = row(cal)
    assert r['STATE'] == 'FAILED_WITH_COST' and r['COST_MICRO_USD'] == 9000 * 2 + 50 * 10 and r['RAW_RESPONSE_SHA256'] is None


def test_completed_malformed_text_is_a_content_failure_not_a_success():
    cal = caller(Script(created(), completed('this is not json'), (200, b'{}')))
    with pytest.raises(RoleContractError):
        novelty(cal)
    assert row(cal)['STATE'] == 'COMPLETE'   # billed, journaled, never admitted as a critic answer


def test_raw_and_wire_hashes_usage_cost_and_no_reasoning_persisted():
    text = novelty_answer()
    status, wire = completed(text, inp=9000, out=1500, reasoning=900, cached=4000)
    cal = caller(Script(created(), (status, wire), (200, b'{}')))
    novelty(cal)
    r = row(cal)
    assert r['STATE'] == 'COMPLETE' and r['RESPONSE_ID'] == 'resp_nov_1' and r['PROVIDER_STATUS'] == 'completed'
    assert r['RAW_RESPONSE_SHA256'] == hashlib.sha256(text.encode()).hexdigest()
    assert r['WIRE_SHA256'] == hashlib.sha256(wire).hexdigest() != r['RAW_RESPONSE_SHA256']
    assert r['USAGE'] == {'input_tokens': 9000, 'output_tokens': 1500, 'reasoning_tokens': 900, 'cached_tokens': 4000}
    rates = routing.PRICES['gpt-6-sol']
    expected = int((rates['INPUT'] * 9000 + rates['OUTPUT'] * 1500).to_integral_value(rounding=ROUND_CEILING))
    assert r['COST_MICRO_USD'] == expected == 33000          # cached input priced at the standard rate
    assert r['COST_MICRO_USD'] <= r['RESERVED_MICRO_USD']
    stored = cal.ledger.db.execute('SELECT response FROM calls WHERE key=?', (r['CALL_KEY'],)).fetchone()[0]
    assert 'HIDDEN_REASONING_SENTINEL' not in stored and 'ENCRYPTED_REASONING_SENTINEL' not in stored
    assert OKEY not in canonical(cal.ledger.export_calls()) and OKEY not in stored


# 18-19 identity ------------------------------------------------------------------------------

def dump_requests(routes=None):
    """Requests built exactly as the PR #217 identity dump built them."""
    p = offline_routed_provider(C, routes)
    cal = Caller(C, Ledger(':memory:', {'RUN_ID': 'id'}), p, CAP, True)
    card = fixture(slot_plan(40)[10], C)
    batch = [fixture(s, C) for s in slot_plan(40)[10:14]]
    return {'FEASIBILITY_CRITIC': critic_request(cal, 'FEASIBILITY_CRITIC', FEAS_PROMPT, card),
            'RED_TEAM': critic_request(cal, 'RED_TEAM', RED_PROMPT, card),
            'NOVELTY_CRITIC': critic_request(cal, 'NOVELTY_CRITIC', NOVELTY_PROMPT, card, batch)}


def test_transport_change_creates_a_new_novelty_call_identity():
    new, old = dump_requests(), dump_requests(chat_routes())
    assert digest(old['NOVELTY_CRITIC']) == PRE_AMENDMENT_KEYS['NOVELTY_CRITIC']
    assert digest(new['NOVELTY_CRITIC']) != PRE_AMENDMENT_KEYS['NOVELTY_CRITIC']
    assert new['NOVELTY_CRITIC']['provider'] == 'OPENAI_RESPONSES_BACKGROUND' != old['NOVELTY_CRITIC']['provider']
    assert routing.role_route_digest('NOVELTY_CRITIC') != PRE_AMENDMENT_ROUTE_DIGESTS['NOVELTY_CRITIC']
    p = offline_routed_provider(C)
    with pytest.raises(ContractError):
        p.bound(old['NOVELTY_CRITIC'])      # an old synchronous novelty request is refused by the new route


def test_luna_red_team_selector_and_generator_identities_are_unchanged():
    for role in ('FEASIBILITY_CRITIC', 'RED_TEAM', 'SELECTOR', 'GENERATOR'):
        assert routing.role_route_digest(role) == PRE_AMENDMENT_ROUTE_DIGESTS[role]
    new = dump_requests()
    for role in ('FEASIBILITY_CRITIC', 'RED_TEAM'):
        assert digest(new[role]) == PRE_AMENDMENT_KEYS[role]


def test_routes_fail_closed_on_unsupported_background_use():
    r = copy.deepcopy(routing.ROUTES)
    r['GENERATOR']['ENDPOINT'] = 'OPENAI_RESPONSES_BACKGROUND'
    with pytest.raises(ContractError):
        routing.validate_routes(r)
    r = copy.deepcopy(routing.ROUTES)
    r['FEASIBILITY_CRITIC']['ENDPOINT'] = 'OPENAI_STREAMING'
    with pytest.raises(ContractError):
        routing.validate_routes(r)


# 20 mixed fake E2E ----------------------------------------------------------------------------

def decisions(result):
    return {k: result[k] for k in ('CANDIDATES', 'REVIEWS', 'HARD_FAILS', 'REVIEW_FAILED', 'STREAM_A', 'STREAM_B', 'SHORTLIST', 'SELECTION_JUDGMENTS', 'STATUS')}


def test_mixed_e2e_reaches_the_same_application_decisions_as_the_synchronous_transport(tmp_path, monkeypatch):
    from scripts.research.generator_v0_gate.noisy import run_mixed_noisy_campaign
    bg_report, bg_l, bg_t = run_mixed_noisy_campaign(tmp_path / 'bg')
    bg = json.loads(bg_l.db.execute("SELECT payload FROM results WHERE key='campaign'").fetchone()[0])
    nov_paths = {p for m, p in bg_t.log if m == 'POST'}
    bg_rows = bg_l.export_calls()
    bg_l.close()
    monkeypatch.setattr(routing, 'ROUTES', chat_routes())
    sync_report, sync_l, sync_t = run_mixed_noisy_campaign(tmp_path / 'sync')
    sync = json.loads(sync_l.db.execute("SELECT payload FROM results WHERE key='campaign'").fetchone()[0])
    sync_l.close()
    assert bg_report['STATUS'] == sync_report['STATUS'] == 'PENDING_HUMAN_REVIEW'
    assert decisions(bg) == decisions(sync)
    assert '/v1/responses' in nov_paths
    nov = [r for r in bg_rows if r['ROLE'] == 'NOVELTY_CRITIC']
    assert nov and all(r['MODEL_PROVIDER'] == 'OPENAI_RESPONSES_BACKGROUND' for r in nov)
    assert all(r['MODEL_PROVIDER'] == 'OPENAI_CHAT_COMPLETIONS' for r in bg_rows if r['ROLE'] in ('FEASIBILITY_CRITIC', 'RED_TEAM', 'SELECTOR'))
    assert bg_report['POSTS'] == bg_report['JOURNAL_ROWS']        # one create POST per journaled novelty attempt
