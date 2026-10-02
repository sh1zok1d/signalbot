"""GENERATOR_CONTRACT_V03: the V02 card plus the complexity ladder (owner amendment 2026-10-02).

A V03 card is a V02 card with two more fields:
- COMPLEXITY_CLASS: assigned to the slot deterministically before any LLM call and copied
  exactly. The model never chooses its own rung.
- COMPONENTS: the independent components of an INTERACTION (2) or COMPOSITE (3-5) card;
  empty for ATOMIC and CONDITIONAL.

Every V02 rule applies unchanged to a V03 card. V03 adds two intake checks (COMPONENTS,
MAIN_EFFECT_BASELINE) and two critic-enforced rules: rung consistency (red team check
RUNG_CONSISTENT) and "simplicity is not banality" (novelty judgments).

Versioning is by slot and card content. A V02 slot plan has no COMPLEXITY_CLASS, so every
V02 schema, prompt, digest and check stays byte-identical; V03 applies only to ladder
slots and ladder cards. contract.py (V02) is not modified.
"""
from __future__ import annotations

from . import contract
from . import textnorm as tn
from .complexity import ATOMIC, COMPLEXITY_CLASSES, COMPONENT_COUNT, COMPOSITE, CONDITIONAL, INTERACTION
from .context import ContractError

CONTRACT_ID = 'GENERATOR_CONTRACT_V03'
PROMPT_VERSION = 'generator-v0.3'
LADDER_FIELDS = ('COMPLEXITY_CLASS', 'COMPONENTS')
MAX_COMPONENT_TEXT = 200
LADDER_SIZE = 40

# Owner-set initial mix for 40 slots: 16 ATOMIC, 14 CONDITIONAL, 7 INTERACTION, 3 COMPOSITE.
# Frozen literal, one 10-slot round per row. Rows are permuted so that each mechanism-family
# position meets different rungs across rounds.
_A, _C, _I, _P = ATOMIC, CONDITIONAL, INTERACTION, COMPOSITE
LADDER_SLOT_CLASSES_40 = (
    _A, _C, _I, _A, _C, _A, _C, _I, _A, _C,   # round 0: 4 A, 4 C, 2 I, 0 P
    _C, _A, _A, _P, _C, _I, _A, _C, _I, _A,   # round 1: 4 A, 3 C, 2 I, 1 P
    _I, _C, _A, _C, _A, _P, _C, _A, _C, _A,   # round 2: 4 A, 4 C, 1 I, 1 P
    _A, _C, _P, _A, _I, _C, _A, _C, _I, _A,   # round 3: 4 A, 3 C, 2 I, 1 P
)
LADDER_MIX_40 = {ATOMIC: 16, CONDITIONAL: 14, INTERACTION: 7, COMPOSITE: 3}

LADDER_PROMPT = ('Each slot also carries a COMPLEXITY_CLASS assigned by the system: write the card at exactly '
                 'that rung of the ladder ATOMIC, CONDITIONAL, INTERACTION, COMPOSITE. Simple rungs are wanted: '
                 'they build the library of base mechanisms that complex claims are later decomposed into.')

RUNG_TEXT = ('The card fits its COMPLEXITY_CLASS. ATOMIC: one mechanism, one observable, one outcome, unconditional. '
             'CONDITIONAL: one simple mechanism inside a regime stated in advance in FUNCTION. '
             'INTERACTION: two independent layers; the claim is the joint term beyond both main effects. '
             'COMPOSITE: one market state built from 3 to 5 independent components; the claim is the joint state '
             'beyond the components taken separately. A card that does not fit its rung fails review.')
NOT_BANAL_TEXT = ('Simplicity is not banality. An ATOMIC or CONDITIONAL card names a market mechanism: who acts, under '
                  'which constraint, and why the effect should exist. A threshold or transform of an indicator mapped '
                  'to a later outcome is a weak card and is scored low on novelty and mechanism distance.')


def _v03_rule(rule):
    if rule['ID'] == 'SCHEMA_FIELDS':
        return {**rule, 'TEXT': 'Each card has exactly the 29 required schema fields (the 27 V02 fields plus '
                                'COMPLEXITY_CLASS and COMPONENTS) and no others.'}
    if rule['ID'] == 'SLOT_IDENTITY':
        return {**rule, 'TEXT': 'Each card copies its slot CANDIDATE_ID, MECHANISM_FAMILY, INFORMATION_SOURCE and '
                                'COMPLEXITY_CLASS exactly; there is exactly one card per supplied slot. The slot '
                                'assigns the complexity class; never choose or change it.'}
    return dict(rule)


RULES = tuple(_v03_rule(r) for r in contract.RULES) + (
    {'ID': 'COMPONENTS', 'ENFORCEMENT': 'VALIDATOR',
     'TEXT': 'COMPONENTS is a list of distinct nonempty component mechanism names of at most 200 characters: empty '
             'for ATOMIC and CONDITIONAL, exactly 2 for INTERACTION, 3 to 5 for COMPOSITE.'},
    {'ID': 'MAIN_EFFECT_BASELINE', 'ENFORCEMENT': 'VALIDATOR',
     'TEXT': 'For INTERACTION and COMPOSITE, BASELINE_OR_NULL names every component exactly as written in COMPONENTS: '
             'the baseline controls each component\'s main effect and the claim is the joint term\'s increment over '
             'those main effects. A component need not have an effect of its own.'},
    {'ID': 'COMPLEXITY_RUNG', 'ENFORCEMENT': 'CRITIC', 'TEXT': RUNG_TEXT},
    {'ID': 'SIMPLE_IS_NOT_BANAL', 'ENFORCEMENT': 'CRITIC', 'TEXT': NOT_BANAL_TEXT},
)
RULE_IDS = tuple(r['ID'] for r in RULES)
# Critic-enforced rules: no intake check; the named critic output decides.
CRITIC_ENFORCEMENT = {'COMPLEXITY_RUNG': 'RED_TEAM.CHECKS.RUNG_CONSISTENT',
                      'SIMPLE_IS_NOT_BANAL': 'NOVELTY_CRITIC.JUDGMENTS (NOVELTY, MECHANISM_DISTANCE)'}


def generator_prompt():
    lines = [contract.BASE_PROMPT + ' ' + LADDER_PROMPT,
             'Hard rules. A card that breaks any rule is quarantined and does not reach review; the rest of the batch continues.']
    lines += [str(i + 1) + '. [' + r['ID'] + '] ' + r['TEXT'] for i, r in enumerate(RULES)]
    return '\n'.join(lines)


def is_ladder(obj) -> bool:
    """A slot or card is V03 iff it carries COMPLEXITY_CLASS (a V02 schema forbids the field)."""
    return isinstance(obj, dict) and 'COMPLEXITY_CLASS' in obj


def slot_plan(size=LADDER_SIZE):
    """The V02 slot plan with a deterministic COMPLEXITY_CLASS per slot. 40 slots only."""
    from .mock import slot_plan as v02_plan
    if size != LADDER_SIZE:
        raise ContractError('the V03 ladder slot plan is frozen for 40 slots')
    return [{**s, 'COMPLEXITY_CLASS': cls} for s, cls in zip(v02_plan(size), LADDER_SLOT_CLASSES_40)]


def ladder_diversity(plan):
    counts = {k: 0 for k in COMPLEXITY_CLASSES}
    for s in plan:
        if s.get('COMPLEXITY_CLASS') not in counts:
            raise ContractError('slot without a complexity class')
        counts[s['COMPLEXITY_CLASS']] += 1
    if counts != LADDER_MIX_40:
        raise ContractError('complexity mix differs from the frozen 16/14/7/3')


def _check_schema_fields(card, ctx, slot):
    required = set(ctx.design['CANDIDATE_SCHEMA']['REQUIRED_FIELDS']) | set(LADDER_FIELDS)
    return [] if set(card) == required else ['fields differ from the frozen 29-field V03 schema']


def _components(card):
    cls = card.get('COMPLEXITY_CLASS')
    comps = card.get('COMPONENTS')
    if cls not in COMPLEXITY_CLASSES:
        return None, ['unknown COMPLEXITY_CLASS']
    if not isinstance(comps, list) or any(not contract.text(c) or len(c) > MAX_COMPONENT_TEXT for c in comps):
        return None, ['COMPONENTS shape']
    norm = [tn.normalize_text(c) for c in comps]
    if len(set(norm)) != len(norm):
        return None, ['duplicate component']
    lo, hi = COMPONENT_COUNT[cls]
    if not lo <= len(comps) <= hi:
        return None, [cls + ' needs ' + (str(lo) if lo == hi else str(lo) + '-' + str(hi)) + ' components']
    return comps, []


def _check_components(card, ctx, slot):
    return _components(card)[1]


def _check_main_effect_baseline(card, ctx, slot):
    comps, errors = _components(card)
    if errors or card.get('COMPLEXITY_CLASS') not in (INTERACTION, COMPOSITE):
        return []
    baseline = tn.normalize_text(card.get('BASELINE_OR_NULL') or '')
    missing = [c for c in comps if tn.normalize_text(c) not in baseline]
    return ['BASELINE_OR_NULL does not name component ' + missing[0]] if missing else []


CHECKS = {**contract.CHECKS, 'SCHEMA_FIELDS': _check_schema_fields, 'COMPONENTS': _check_components,
          'MAIN_EFFECT_BASELINE': _check_main_effect_baseline}


def card_violations(card, contexts, slot=None):
    """All V03 intake violations as [{'RULE','DETAIL'}]. Critic-enforced rules are not checked here."""
    if not isinstance(card, dict):
        return [{'RULE': 'SCHEMA_FIELDS', 'DETAIL': 'card is not an object'}]
    out = []
    for rule in RULE_IDS:
        if rule in CRITIC_ENFORCEMENT:
            continue
        try:
            details = CHECKS[rule](card, contexts, slot)
        except Exception as e:  # noqa: BLE001 - content never aborts intake
            details = ['check error ' + type(e).__name__]
        out += [{'RULE': rule, 'DETAIL': d} for d in details]
    return out


def validate_card_v03(card, contexts, slot=None):
    violations = card_violations(card, contexts, slot)
    if violations:
        raise ContractError('; '.join(v['RULE'] + ': ' + v['DETAIL'] for v in violations))
    return card


def fixture_components(slot):
    """Synthetic components for infrastructure fixtures (not research)."""
    n = COMPONENT_COUNT[slot['COMPLEXITY_CLASS']][0]
    return ['Synthetic component ' + slot['CANDIDATE_ID'] + '-' + str(k + 1) for k in range(n)]
