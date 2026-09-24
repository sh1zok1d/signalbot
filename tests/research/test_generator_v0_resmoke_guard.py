"""Re-smoke operational guards. Offline: fake transports, dummy keys, no network."""
import json
import pytest
from scripts.research.generator_v0 import routing
from scripts.research.generator_v0.context import Contexts, canonical
from scripts.research.generator_v0.anthropic_provider import AnthropicProvider, REQUEST_TIMEOUT_SECONDS
from scripts.research.generator_v0.openai_provider import OpenAIProvider, OPENAI_REQUEST_TIMEOUT_SECONDS
from scripts.research.generator_v0.routed_provider import RoutedProvider, offline_routed_provider
from scripts.research.generator_v0.provider import Caller
from scripts.research.generator_v0.ledger import Ledger, BudgetExceeded
from scripts.research.generator_v0.runner import _round_output, generator_request_parameters, generator_max_output_tokens
from scripts.research.generator_v0.mock import MockResponder, slot_plan
from scripts.research.generator_v0.resmoke import (SmokeStop, open_smoke_ledger, run_resmoke,
    ABSOLUTE_CAP_MICRO_USD, HISTORICAL_SPEND_MICRO_USD, NEW_SPEND_CAP_MICRO_USD, GENERATOR_MAX_NEW_POSTS)

C = Contexts()
SLOTS = slot_plan(40)[:10]
AKEY = 'sk-ant-test-DO-NOT-PERSIST-0123456789'
OKEY = 'sk-openai-test-DO-NOT-PERSIST-9876543210'
CAP = ABSOLUTE_CAP_MICRO_USD


class Fake:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, method, path, body, headers, timeout):
        self.calls.append(timeout)
        a = self.answers.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a


def env(text, stop='end_turn', out=100):
    content = [{'type': 'thinking', 'thinking': '', 'signature': 'opaque'}]
    if text is not None:
        content.append({'type': 'text', 'text': text})
    body = {'id': 'msg_smoke_1', 'type': 'message', 'role': 'assistant', 'model': 'claude-opus-5-5',
            'content': content, 'stop_reason': stop, 'stop_sequence': None,
            'usage': {'input_tokens': 100, 'output_tokens': out}}
    return json.dumps(body).encode()


def gen_json():
    keyed = json.loads(MockResponder(C)({'role': 'GENERATOR', 'context': C.generator(), 'parameters': {'slots': SLOTS}}))
    return canonical({'CANDIDATES': list(keyed['CANDIDATES'].values())})


def caller(tmp_path, a_answers, o_answers=(), cap=CAP, lineage=True):
    path = tmp_path / 'smoke.sqlite'
    path.parent.mkdir(parents=True, exist_ok=True)
    if lineage:
        ledger = open_smoke_ledger(path)
    else:
        ledger = Ledger(path, {'RUN_ID': 'bare', 'CAP_MICRO_USD': cap, 'PURPOSE': 'BARE'})
    a, o = Fake(*a_answers), Fake(*o_answers)
    provider = RoutedProvider({
        'ANTHROPIC': AnthropicProvider(AKEY, allow_real=True, budget_micro_usd=cap, transport=a, contexts=C),
        'OPENAI': OpenAIProvider(OKEY, allow_real=True, budget_micro_usd=cap, transport=o, contexts=C, routes=routing.ROUTES, sleeper=lambda s: None),
    }, routing.ROUTES, sleeper=lambda s: None)
    return Caller(C, ledger, provider, cap, True), a, o


def test_routed_anthropic_timeout_is_1800_and_openai_is_unchanged():
    assert REQUEST_TIMEOUT_SECONDS == 1800
    offline = offline_routed_provider(C)
    assert offline.adapters['ANTHROPIC'].request_timeout_seconds == 1800
    ident = offline.transport_identity()['ADAPTERS']['ANTHROPIC']
    assert ident['REQUEST_TIMEOUT_SECONDS'] == 1800 and ident['STREAM'] is False and ident['BATCH'] is False
    sent = Fake((200, env(gen_json())))
    live = AnthropicProvider(AKEY, allow_real=True, budget_micro_usd=CAP, transport=sent, contexts=C)
    cal = Caller(C, open_smoke_ledger(':memory:'), RoutedProvider({
        'ANTHROPIC': live,
        'OPENAI': OpenAIProvider(OKEY, allow_real=True, budget_micro_usd=CAP, transport=Fake(), contexts=C, routes=routing.ROUTES),
    }), CAP, True)
    # The production complete() passes its timeout straight to the transport.
    from scripts.research.generator_v0.runner import GENERATOR_PROMPT, generator_identity
    cal.call('GENERATOR', C.generator(), GENERATOR_PROMPT, generator_request_parameters(SLOTS, generator_max_output_tokens(cal.provider)), 'generation:0', identity=generator_identity(C, SLOTS))
    assert sent.calls == [1800]
    assert offline.adapters['OPENAI'].request_timeout_seconds == OPENAI_REQUEST_TIMEOUT_SECONDS == 600


def test_smoke_refuses_to_post_without_historical_lineage(tmp_path):
    cal, a, o = caller(tmp_path, ((200, env(gen_json())),), lineage=False)
    with pytest.raises(SmokeStop, match='historical'):
        run_resmoke(C, cal)
    assert a.calls == [] and o.calls == []


def test_historical_spend_blocks_a_reservation_the_bare_ceiling_would_allow(tmp_path):
    """2_400_000 fits under 3_100_000 and does not fit once 713_332 is carried."""
    bound = 2_400_000
    assert bound <= ABSOLUTE_CAP_MICRO_USD
    assert HISTORICAL_SPEND_MICRO_USD + bound > ABSOLUTE_CAP_MICRO_USD
    bare = Ledger(tmp_path / 'bare.sqlite', {'RUN_ID': 'bare', 'CAP_MICRO_USD': CAP})
    bare.reserve('bare-key', {'role': 'GENERATOR'}, bound, CAP)
    smoke = open_smoke_ledger(tmp_path / 'smoke.sqlite')
    with pytest.raises(BudgetExceeded):
        smoke.reserve('smoke-key', {'role': 'GENERATOR'}, bound, CAP)
    assert smoke.total_charged_micro_usd() == HISTORICAL_SPEND_MICRO_USD
    assert bare.total_charged_micro_usd() == bound


def test_smoke_execution_stops_before_posting_a_bound_past_the_ceiling(tmp_path):
    cal, a, o = caller(tmp_path, ((200, env(gen_json())),))
    real = cal.provider.bound
    cal.provider.bound = lambda request: 2_400_000 if request['role'] == 'GENERATOR' else real(request)
    report = run_resmoke(C, cal)
    assert report['STATUS'] == 'STOPPED_GENERATOR_BudgetExceeded'
    assert report['ANTHROPIC_POSTS'] == 0 and a.calls == [] and o.calls == []
    assert report['LEDGER_CHARGED_MICRO_USD'] == HISTORICAL_SPEND_MICRO_USD
    assert NEW_SPEND_CAP_MICRO_USD == ABSOLUTE_CAP_MICRO_USD - HISTORICAL_SPEND_MICRO_USD


def test_billed_generator_failure_makes_no_second_post_and_no_critic(tmp_path):
    """The answer that would succeed on a content retry is never sent for."""
    answers = ((200, env('{"CAND', stop='max_tokens', out=100)), (200, env(gen_json())))
    cal, a, o = caller(tmp_path, answers)
    report = run_resmoke(C, cal)
    assert report['STATUS'].startswith('STOPPED_GENERATOR')
    assert a.calls == [1800] and o.calls == []
    assert [state for _, state in report['GENERATOR_ROWS']] == ['FAILED_WITH_COST']
    # A second invocation on the SAME journal does not POST.
    report2 = run_resmoke(C, Caller(C, cal.ledger, cal.provider, CAP, True))
    assert report2['STATUS'] == 'STOPPED_GENERATOR_NOT_COMPLETE'
    assert len(a.calls) == 1 and o.calls == []
    # The production round loop would have POSTed the second answer. The smoke does not.
    other, b, _ = caller(tmp_path / 'round', answers, cap=30_000_000, lineage=False)
    _round_output(C, other.ledger, other, 0, SLOTS)
    assert len(b.calls) == 2


def test_uncertain_generator_attempt_is_not_replayed(tmp_path):
    cal, a, o = caller(tmp_path, (TimeoutError('read timed out'), (200, env(gen_json()))))
    report = run_resmoke(C, cal)
    assert report['STATUS'] == 'STOPPED_GENERATOR_CallUncertain'
    assert [state for _, state in report['GENERATOR_ROWS']] == ['UNCERTAIN']
    assert len(a.calls) == 1 and o.calls == []
    report2 = run_resmoke(C, Caller(C, cal.ledger, cal.provider, CAP, True))
    assert report2['STATUS'] == 'STOPPED_GENERATOR_NOT_COMPLETE'
    assert len(a.calls) == 1
    # The reserved bound plus history leaves no room for another generator reservation,
    # so the production retry key is refused before dispatch.
    from scripts.research.generator_v0.runner import GENERATOR_PROMPT, generator_identity
    with pytest.raises(BudgetExceeded):
        cal.call('GENERATOR', C.generator(), GENERATOR_PROMPT,
                 generator_request_parameters(SLOTS, generator_max_output_tokens(cal.provider)),
                 'generation:0', content_attempt=1, identity=generator_identity(C, SLOTS))
    assert len(a.calls) == 1


def test_retryable_transport_failure_cannot_post_again(tmp_path, monkeypatch):
    import scripts.research.generator_v0.anthropic_provider as anthropic
    monkeypatch.setattr(anthropic, 'classify_anthropic_http', lambda status, wire: ('NOT_BILLED', True))
    cal, a, o = caller(tmp_path, ((429, b'rate'), (200, env(gen_json()))))
    report = run_resmoke(C, cal)
    assert 'replay' in report.get('DETAIL', '') or report['STATUS'].startswith('STOPPED')
    assert len(a.calls) == 1 and o.calls == []
    assert GENERATOR_MAX_NEW_POSTS == 1


def test_critics_do_not_run_unless_the_generator_completed(tmp_path):
    refused, a, o = caller(tmp_path / 'bad', ((200, env('not-json')), (400, b'no')))
    report = run_resmoke(C, refused)
    assert report['STATUS'] == 'STOPPED_UNUSABLE_ROUND' and report['CRITICS'] is False
    assert len(a.calls) == 1 and o.calls == []
    ok, a2, o2 = caller(tmp_path / 'ok', ((200, env(gen_json())),), ((400, b'no'),))
    report2 = run_resmoke(C, ok)
    assert report2['STATUS'] == 'STOPPED_CRITIC' and report2['CRITICS']['FEASIBILITY'].startswith('STOPPED')
    assert len(a2.calls) == 1 and len(o2.calls) == 1
