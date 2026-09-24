"""Authorized compact re-smoke. One Anthropic GENERATOR POST, then at most
one Luna feasibility call and one Sol novelty call. No RED_TEAM, no content
retry, no transport replay.

The absolute ceiling is enforced by the production ledger, not by a test:
lineage PRIOR_SPEND_MICRO_USD carries the historical smoke spend and
CAP_MICRO_USD is the absolute ceiling, so reserve() refuses any reservation
that would push lineage + journal + bound over it. A fresh ledger is not
given the absolute ceiling as new spend.
"""
from __future__ import annotations
import json
from .context import ContractError
from .ledger import Ledger, BudgetExceeded, CallUncertain
from .provider import BilledFailure, ProviderRejected
from .runner import (GENERATOR_PROMPT, generator_request_parameters, generator_identity,
                     generator_max_output_tokens, parse_round, call_wire_format, _intake_round)
from .roles import Roles, FEAS_PROMPT, NOVELTY_PROMPT, RoleContractError
from .models import ROLE_OUTPUT_TOKEN_CAPS
from .mock import slot_plan, fixture
from . import contract

ABSOLUTE_CAP_MICRO_USD = 3_100_000
HISTORICAL_SPEND_MICRO_USD = 713_332
NEW_SPEND_CAP_MICRO_USD = ABSOLUTE_CAP_MICRO_USD - HISTORICAL_SPEND_MICRO_USD
GENERATOR_MAX_NEW_POSTS = 1
FAILED_CALL_KEY = 'f8207e1f0fa229f24eec50b0c894d704dd32ad1fece59672e2d2440b47ea930e'
SMOKE_RUN_ID = 'generator-v0-compact-resmoke'
_LINEAGE_RULE = 'lineage prior spend + journal charges + new reservation <= CAP_MICRO_USD'


class SmokeStop(ContractError):
    """The re-smoke stops. Nothing in this process may POST again."""


def smoke_lineage():
    return {'PRIOR_SPEND_MICRO_USD': HISTORICAL_SPEND_MICRO_USD,
            'SOURCES': [{'RUN_ID': 'pr216-live-re-smoke', 'COST_MICRO_USD': HISTORICAL_SPEND_MICRO_USD, 'CALL_KEY': FAILED_CALL_KEY}],
            'RULE': _LINEAGE_RULE}


def smoke_config():
    return {'RUN_ID': SMOKE_RUN_ID, 'CAP_MICRO_USD': ABSOLUTE_CAP_MICRO_USD, 'PURPOSE': 'COMPACT_RE_SMOKE'}


def open_smoke_ledger(path):
    """Fresh journal: absolute cap, historical spend carried as lineage.
    Refuses a journal whose cap or lineage is anything else."""
    ledger = Ledger(path, smoke_config())
    lineage = ledger.get('lineage')
    if lineage is None:
        with ledger.transaction():
            ledger.set('lineage', smoke_lineage())
            ledger.event('SMOKE_LINEAGE_RECORDED', {'PRIOR_SPEND_MICRO_USD': HISTORICAL_SPEND_MICRO_USD, 'CAP_MICRO_USD': ABSOLUTE_CAP_MICRO_USD})
        lineage = ledger.get('lineage')
    if ledger.get('config')['CAP_MICRO_USD'] != ABSOLUTE_CAP_MICRO_USD or lineage.get('PRIOR_SPEND_MICRO_USD') != HISTORICAL_SPEND_MICRO_USD:
        raise SmokeStop('smoke ledger cap or lineage differs from the absolute ceiling')
    if ledger.lineage_prior_micro_usd() != HISTORICAL_SPEND_MICRO_USD:
        raise SmokeStop('smoke lineage prior spend is not the historical smoke spend')
    return ledger


def assert_smoke_authority(ledger, caller):
    """Fail closed before any POST. The caller cap is the absolute ceiling;
    historical spend is already inside the ledger total."""
    cfg = ledger.get('config') or {}
    if cfg.get('CAP_MICRO_USD') != ABSOLUTE_CAP_MICRO_USD:
        raise SmokeStop('smoke cap is not the absolute ceiling')
    if ledger.lineage_prior_micro_usd() != HISTORICAL_SPEND_MICRO_USD:
        raise SmokeStop('historical smoke spend is not in the ledger lineage')
    if caller.cap != ABSOLUTE_CAP_MICRO_USD:
        raise SmokeStop('caller cap must be the absolute ceiling, not a fresh new-spend budget')
    adapters = getattr(caller.provider, 'adapters', {})
    for adapter in adapters.values():
        if getattr(adapter, 'cap', ABSOLUTE_CAP_MICRO_USD) != ABSOLUTE_CAP_MICRO_USD:
            raise SmokeStop('adapter cap must be the absolute ceiling')
    remaining = ABSOLUTE_CAP_MICRO_USD - ledger.total_charged_micro_usd()
    if remaining < 0 or remaining > NEW_SPEND_CAP_MICRO_USD:
        raise SmokeStop('remaining authorization is outside the new-spend cap')
    return remaining


class _OneAnthropicPost:
    """Refuses a second Anthropic POST. Installed on the production adapter."""
    def __init__(self, inner):
        self.inner = inner
        self.posts = 0

    def __call__(self, method, path, body, headers, timeout):
        if self.posts >= GENERATOR_MAX_NEW_POSTS:
            raise SmokeStop('second Anthropic POST refused')
        self.posts += 1
        return self.inner(method, path, body, headers, timeout)


def _install_guards(caller):
    """One Anthropic POST, and no transport-retry sleep. OpenAI is untouched
    until the generator has completed; each critic is a separate single call."""
    anthropic = caller.provider.adapters['ANTHROPIC']
    guard = _OneAnthropicPost(anthropic.transport)
    anthropic.transport = guard
    def refuse_replay(_seconds):
        raise SmokeStop('transport replay refused')
    caller.provider._sleep = refuse_replay
    return guard


def _generator_rows(ledger):
    rows = []
    for key, request, state in ledger.db.execute('SELECT key,request,state FROM calls ORDER BY rowid'):
        req = json.loads(request)
        if req.get('role') == 'GENERATOR':
            rows.append((key, state))
    return rows


def _report(ledger, guard, **extra):
    out = {'ANTHROPIC_POSTS': guard.posts if guard else 0,
           'LEDGER_CHARGED_MICRO_USD': ledger.total_charged_micro_usd(),
           'LINEAGE_PRIOR_MICRO_USD': ledger.lineage_prior_micro_usd(),
           'CAP_MICRO_USD': ABSOLUTE_CAP_MICRO_USD,
           'GENERATOR_ROWS': _generator_rows(ledger),
           'CALLER_NEW_POSTS': None}
    out.update(extra)
    return out


def run_resmoke(contexts, caller):
    """The only re-smoke entry. Stops on any generator failure. Never calls
    _round_output, so MAX_CONTENT_ATTEMPTS cannot issue a second POST."""
    ledger = caller.ledger
    assert_smoke_authority(ledger, caller)
    guard = _install_guards(caller)
    rows = _generator_rows(ledger)
    if len(rows) > GENERATOR_MAX_NEW_POSTS:
        raise SmokeStop('smoke journal already holds more than one generator call')
    if rows and rows[0][1] != 'COMPLETE':
        return _report(ledger, guard, STATUS='STOPPED_GENERATOR_NOT_COMPLETE', GENERATOR_STATE=rows[0][1], CRITICS=False)
    if not rows:
        try:
            raw = caller.call('GENERATOR', contexts.generator(), GENERATOR_PROMPT,
                              generator_request_parameters(slot_plan(40)[:10], generator_max_output_tokens(caller.provider)),
                              'generation:0', content_attempt=0, identity=generator_identity(contexts, slot_plan(40)[:10]))
        except (BilledFailure, CallUncertain, ProviderRejected, BudgetExceeded, SmokeStop) as e:
            return _report(ledger, guard, STATUS='STOPPED_GENERATOR_' + type(e).__name__, CRITICS=False, DETAIL=str(e)[:300])
        key = caller.last_key
        if ledger.call_state(key) != 'COMPLETE':
            return _report(ledger, guard, STATUS='STOPPED_GENERATOR_NOT_COMPLETE', CRITICS=False)
        cards = parse_round(raw, contract.CONTRACT_ID, call_wire_format(ledger, key))
        if cards is None:
            return _report(ledger, guard, STATUS='STOPPED_UNUSABLE_ROUND', CRITICS=False)
        slots = slot_plan(40)[:10]
        admitted = _intake_round(contexts, ledger, 0, slots, contract.CONTRACT_ID, key, cards, [])
        if not admitted:
            return _report(ledger, guard, STATUS='STOPPED_NOTHING_ADMITTED', CRITICS=False)
    # Critics only after a COMPLETE, parseable, admitted round. One call each.
    # reserve() carries the historical spend, so a reservation past the ceiling
    # raises BudgetExceeded before any byte is sent.
    roles = Roles(contexts, caller)
    card = fixture(slot_plan(40)[0], contexts)
    critics = {}
    for name, fn in (('FEASIBILITY', lambda: roles.feasibility(card, 0)), ('NOVELTY', lambda: roles.novelty(card, [card], 0))):
        try:
            fn()
        except (RoleContractError, BilledFailure, CallUncertain, ProviderRejected, BudgetExceeded, SmokeStop) as e:
            critics[name] = 'STOPPED_' + type(e).__name__
            return _report(ledger, guard, STATUS='STOPPED_CRITIC', CRITICS=critics, DETAIL=str(e)[:300])
        critics[name] = 'COMPLETE'
    return _report(ledger, guard, STATUS='SMOKE_COMPLETE', CRITICS=critics)
