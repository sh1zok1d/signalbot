"""Generator V0 memory finalizer V1: completed campaign -> append-only memory event.

Deterministic, offline. No LLM decides what is written: every disposition, link,
blocker class, state and text field below is a fixed function of the structured
campaign record and the frozen design. See docs/research/GENERATOR_V0_MEMORY_FINALIZER.md.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from .context import ContractError, canonical, digest, read, DESIGN
from . import memory_store as store

FINALIZER_VERSION = 'GENERATOR_V0_MEMORY_FINALIZER_V1'
CAMPAIGN_ID_RE = re.compile(r'^[A-Z][A-Z0-9]{2,15}$')
CANDIDATE_ID_RE = re.compile(r'^C[0-9]{3}$')
RESERVED_CAMPAIGN_IDS = ('LEGACY',)
ATTEMPT_CARD_FIELDS = ('CANDIDATE_ID', 'NAME', 'MECHANISM_FAMILY', 'INFORMATION_SOURCE', 'MECHANISM',
                       'CAUSAL_OR_STRUCTURAL_STORY', 'OBSERVABLE', 'FUNCTION', 'PRIMARY_TARGET', 'HORIZON',
                       'BASELINE_OR_NULL', 'FALSIFIER', 'DATA_STATUS', 'DATA_REQUIRED', 'EXPECTED_INFORMATION_GAIN')
RED_TEAM_CHECKS = ('NO_LOOKAHEAD', 'CAUSALITY', 'FALSIFIABLE', 'BOUNDED_SEARCH', 'CONFOUNDING_ADDRESSED', 'NO_TRADING_CLAIM')
ORTHOGONAL = 'ORTHOGONAL_MECHANISM'
LINK_RELATIONS = ('EXACT_DUPLICATE', 'PARAMETER_NEIGHBOR', 'FUNCTIONAL_RELABEL', 'RESOLVES_BLOCKER')
VERDICT_PRECEDENCE = ('REJECT', 'HUMAN_REVIEW', 'DEFER_BLOCKER_UNRESOLVED', 'ALLOW_TO_FEASIBILITY', 'ALLOW')

# Ordered, first match wins. The set is the RED_TEAM checks that must all be false.
RED_TEAM_BLOCKER_RULES = (
    (('NO_LOOKAHEAD',), 'METHOD_LOOKAHEAD_VIOLATION'),
    (('CAUSALITY', 'CONFOUNDING_ADDRESSED'), 'METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING'),
    (('CAUSALITY',), 'METHOD_CAUSAL_IDENTIFICATION_INADEQUATE'),
    (('CONFOUNDING_ADDRESSED',), 'METHOD_CONFOUNDING_CONTROL_INADEQUATE'),
    (('FALSIFIABLE',), 'METHOD_FALSIFIER_INADEQUATE'),
    (('BOUNDED_SEARCH',), 'METHOD_UNBOUNDED_SEARCH_SURFACE'),
    (('NO_TRADING_CLAIM',), 'METHOD_TRADING_CLAIM_OUT_OF_SCOPE'),
)
BLOCKER_REQUIREMENTS = {
    'METHOD_LOOKAHEAD_VIOLATION': 'A predeclared design must use only information observable at or before the decision time before this signature can advance.',
    'METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING': 'A predeclared design must separately identify the proposed mechanism from correlated timing, venue and calendar structure and address its causal interpretation before this signature can advance.',
    'METHOD_CAUSAL_IDENTIFICATION_INADEQUATE': 'A predeclared design must state and support an identification strategy for the proposed causal pathway before this signature can advance.',
    'METHOD_CONFOUNDING_CONTROL_INADEQUATE': 'A predeclared design must control the correlated calendar, volatility, liquidity and contemporaneous event structure that confound this signature before it can advance.',
    'METHOD_FALSIFIER_INADEQUATE': 'A predeclared design must state an explicit falsifier and null before this signature can advance.',
    'METHOD_UNBOUNDED_SEARCH_SURFACE': 'A predeclared design must bound and declare its search surface before this signature can advance.',
    'METHOD_TRADING_CLAIM_OUT_OF_SCOPE': 'A redesign must remove the trading claim and state a research-only estimand before this signature can advance.',
    'DATA_LEGAL_RANGE_NOT_SATISFIED': 'A redesign must restrict every required range to legal, non-protected history inside the catalog bounds before this signature can advance.',
    'DATA_READY_CLAIM_NOT_CONFIRMED': 'The claimed catalog observables must be confirmed as supported, point-in-time and provenance-complete before this signature can advance.',
    'DATA_STATUS_DISAGREEMENT_REQUIRES_HUMAN_REVIEW': 'A human must adjudicate the disagreement between the generated and the critic data status before this signature can advance.',
    'DATA_FEASIBILITY_REQUIRED': 'The required observables must be sourced with point-in-time semantics and archive provenance before this signature can advance.',
}
DATA_BLOCKED_REQUIREMENT = 'The data blocker {status} must be resolved with point-in-time semantics and archive provenance before this signature can advance.'
ANTI_RESCUE_SCOPE = {
    'CONSUMED': 'exact duplicate; parameter/threshold/window/horizon/clock neighbors; observable substitution within the same function; functionally equivalent relabel',
    'DEFERRED_OR_BLOCKED': 'the same signature while its named blocker is unresolved; parameter/threshold/window/horizon/clock neighbors or cosmetic relabels that evade the blocker',
}
# Text-field scrub rules for new signatures. Blind rows must pass the frozen generator
# denylist (read from the design at run time) and the blind state-language rules;
# governance rows must stay outcome-free. Any matching token is replaced by OMITTED.
OMITTED = '(omitted)'
SCRUB_PATTERNS = (
    (r'\bCONSUMED\b|DEFERRED|BLOCKED|PARTIAL_OR_MIXED|\bEXECUTED\b|PROMISING|CONFIRMED', re.IGNORECASE),
    (r'unpinned|\bpinned\b|unauthori[sz]ed|deferred|blocked|consumed|not executed|not tested|not run'
     r'|insufficient (?:control|support)|insufficient|publication latency|unresolved|replicat|promising'
     r'|prototype|rejected|no useful structure|no evidence|reclassified', re.IGNORECASE),
    (r'p[-_ ]?value|effect size|prototype|promising|profit|\bgate\b|\b20[12]\d\b|\d\.\d', re.IGNORECASE),
    (r'\bPASS\b|\bFAIL\b', 0),
)
# MARKET_TEST_RESULT: one executed scientific test family -> one full-memory record.
SCIENTIFIC_TEST_LEDGER = 'docs/research/SCIENTIFIC_TEST_LEDGER.json'
TEST_FAMILY_ID_RE = re.compile(r'^TF-([A-Z0-9]+(?:-[A-Z0-9]+)*)$')
DISCOVERY_CLASSIFICATIONS = ('PROMISING_PROTOTYPE', 'NO_USEFUL_STRUCTURE', 'INCONCLUSIVE_DISCOVERY', 'INVALID_DISCOVERY')
RESULT_GATES = ('STATISTICAL_GATE', 'DIRECTION_GATE', 'TEMPORAL_GATE', 'CONTROL_GATE', 'DEPENDENCE_GATE', 'ADJACENCY_GATE')
MARKET_RESULT_INTERPRETATION = ('Frozen classification of one preregistered test, copied verbatim. Not a validated edge; '
                                'no trading, cost or profitability claim. Full human memory only; never generator-visible.')
MARKET_TEST_RESULT_RULES = {
    'UNIT_ID': 'TEST_FAMILY_ID without the TF- prefix and without hyphens (must satisfy CAMPAIGN_ID_RE)',
    'SIGNATURE': 'the SIGNATURE_ID of the attempt record whose ATTEMPT_ID equals HYPOTHESIS_ID',
    'CLASSIFICATIONS': list(DISCOVERY_CLASSIFICATIONS), 'GATES': list(RESULT_GATES),
    'INTERPRETATION': MARKET_RESULT_INTERPRETATION, 'APPENDS_ONLY': 'MEMORY.MARKET_TEST_RESULTS[TEST_FAMILY_ID]',
}
FINALIZER_RULES = {
    'VERSION': FINALIZER_VERSION, 'CAMPAIGN_ID_RE': CAMPAIGN_ID_RE.pattern, 'CANDIDATE_ID_RE': CANDIDATE_ID_RE.pattern,
    'STABLE_ID': 'CAMPAIGN_ID + "-" + CANDIDATE_ID', 'RESERVED_CAMPAIGN_IDS': list(RESERVED_CAMPAIGN_IDS),
    'RED_TEAM_BLOCKER_RULES': [[list(k), v] for k, v in RED_TEAM_BLOCKER_RULES], 'BLOCKER_REQUIREMENTS': BLOCKER_REQUIREMENTS,
    'DATA_BLOCKED_REQUIREMENT': DATA_BLOCKED_REQUIREMENT, 'ANTI_RESCUE_SCOPE': ANTI_RESCUE_SCOPE,
    'SCRUB_PATTERNS': [[p, f] for p, f in SCRUB_PATTERNS], 'OMITTED': OMITTED, 'ATTEMPT_CARD_FIELDS': list(ATTEMPT_CARD_FIELDS),
    'SIGNATURE_FIELDS': {'MECHANISM': 'NAME', 'FUNCTION': 'FUNCTION', 'INFORMATION_SOURCE': 'INFORMATION_SOURCE + ": " + DATA_REQUIRED datasets',
                         'TARGET_FAMILY': 'PRIMARY_TARGET'},
    'MARKET_TEST_RESULT': MARKET_TEST_RESULT_RULES,
}


# GENERATOR_CONTRACT_V03 (complexity ladder) extension. Applies only to V03 campaigns;
# FINALIZER_RULES and every V02 delta, digest and disposition are unchanged.
GENERATOR_CONTRACT_V03 = 'GENERATOR_CONTRACT_V03'
LADDER_CARD_FIELDS = ('COMPLEXITY_CLASS', 'COMPONENTS')
ATTEMPT_CARD_FIELDS_V03 = ATTEMPT_CARD_FIELDS + LADDER_CARD_FIELDS
RED_TEAM_CHECKS_V03 = RED_TEAM_CHECKS + ('RUNG_CONSISTENT',)
# Appended after every V02 rule: a V02 failure keeps its V02 class first.
RED_TEAM_BLOCKER_RULES_V03 = RED_TEAM_BLOCKER_RULES + ((('RUNG_CONSISTENT',), 'METHOD_RUNG_INCONSISTENT'),)
BLOCKER_REQUIREMENTS_V03 = {
    'METHOD_RUNG_INCONSISTENT': 'A redesign must state the candidate at its assigned complexity rung (one mechanism for a simple rung; a joint term over controlled component main effects for an interaction or composite rung) before this signature can advance.',
}
FINALIZER_RULES_V03 = {
    'CONTRACT': GENERATOR_CONTRACT_V03, 'ATTEMPT_CARD_FIELDS_ADDED': list(LADDER_CARD_FIELDS),
    'RED_TEAM_CHECKS_ADDED': ['RUNG_CONSISTENT'],
    'RED_TEAM_BLOCKER_RULES_ADDED': [[['RUNG_CONSISTENT'], 'METHOD_RUNG_INCONSISTENT']],
    'BLOCKER_REQUIREMENTS_ADDED': BLOCKER_REQUIREMENTS_V03,
    'COPY_RULE': 'COMPLEXITY_CLASS, COMPONENTS and every critic output are validated for shape and copied verbatim; never re-evaluated or rewritten',
}


def design_rules(design):
    b = design['BLIND_GENERATOR_CONTEXT']
    return {'BLIND_GENERATOR_CONTEXT': b, 'GOVERNANCE_HEADER': store.design_governance_header(design),
            'DATA_STATUS_TAXONOMY': design['DATA_STATUS_TAXONOMY']}


def rules_digest(design, contract=None):
    if contract == GENERATOR_CONTRACT_V03:
        return digest({'DESIGN_RULES': design_rules(design), 'FINALIZER_RULES': FINALIZER_RULES,
                       'FINALIZER_RULES_V03': FINALIZER_RULES_V03})
    return digest({'DESIGN_RULES': design_rules(design), 'FINALIZER_RULES': FINALIZER_RULES})


def stable_id(campaign_id, candidate_id):
    if not isinstance(campaign_id, str) or not CAMPAIGN_ID_RE.fullmatch(campaign_id) or campaign_id in RESERVED_CAMPAIGN_IDS:
        raise ContractError('invalid CAMPAIGN_ID: ' + repr(campaign_id))
    if not isinstance(candidate_id, str) or not CANDIDATE_ID_RE.fullmatch(candidate_id):
        raise ContractError('invalid CANDIDATE_ID: ' + repr(candidate_id))
    return campaign_id + '-' + candidate_id


def scrub(text, design):
    """Replace every whole token that matches a forbidden pattern. Deterministic."""
    if not isinstance(text, str):
        raise ContractError('signature text must be a string')
    patterns = [re.compile(design['BLIND_GENERATOR_CONTEXT']['CONTEXT_SCANNER']['DENYLIST_REGEX'], re.IGNORECASE)]
    patterns += [re.compile(p, f) for p, f in SCRUB_PATTERNS]
    for _ in range(1000):
        hit = next((m for pat in patterns for m in [pat.search(text)] if m), None)
        if hit is None:
            return ' '.join(text.split())
        start, end = hit.start(), hit.end()
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] in '_-.'):
            start -= 1
        while end < len(text) and (text[end].isalnum() or text[end] in '_-.'):
            end += 1
        text = text[:start] + OMITTED + text[end:]
    raise ContractError('scrub did not converge')


# ----------------------------------------------------------------------------- source adapters

def _normalize_review(card, novelty, feasibility, red_team, stream, review_state, prior_basis, ladder=False):
    fields = ATTEMPT_CARD_FIELDS_V03 if ladder else ATTEMPT_CARD_FIELDS
    return {'CANDIDATE_ID': card['CANDIDATE_ID'], 'CARD': {k: copy.deepcopy(card[k]) for k in fields},
            'REVIEW_STATE': review_state, 'NOVELTY': novelty, 'FEASIBILITY': feasibility, 'RED_TEAM': red_team,
            'STREAM': stream, 'PRIOR_RELATIONS_BASIS': prior_basis}


def source_from_calibration_export(path, campaign_id, design):
    """GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.json. It records novelty verdicts but not
    per-signature relation values. Under the frozen decision table only ORTHOGONAL_MECHANISM
    yields ALLOW for every state, so an ALLOW verdict proves every prior relation was
    orthogonal; any other verdict cannot be linked from this source and fails closed."""
    path = Path(path)
    raw = path.read_bytes()
    doc = json.loads(raw.decode('utf-8'))
    if doc.get('UNIT') != 'GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT':
        raise ContractError('not a Generator V0 calibration export')
    if doc.get('NO_SCIENTIFIC_STATUS') is not True or doc.get('MARKET_OUTCOMES_TESTED') is not False or doc.get('PROTECTED_DATA_OPENED') is not False:
        raise ContractError('calibration export boundary flags')
    table = design['GOVERNANCE_REGION_AUTHORITY_V0']['NOVELTY_DECISION_TABLE']
    allow_relations = {rel for state, t in table.items() if isinstance(t, dict) for rel, v in t.items() if v == 'ALLOW'}
    if allow_relations != {ORTHOGONAL}:
        raise ContractError('frozen table no longer proves ALLOW => orthogonal')
    if doc['DETERMINISTIC_SELECTOR'].get('NEAR_DUPLICATE_EXCLUSIONS') != []:
        raise ContractError('calibration export batch duplicates cannot be linked without relation values')
    ids = [c['CARD']['CANDIDATE_ID'] for c in doc['CARDS']]
    candidates = []
    for c in doc['CARDS']:
        card, cr = c['CARD'], c['CRITICS']
        if cr['NOVELTY']['VERDICT'] != 'ALLOW':
            raise ContractError('calibration export verdict other than ALLOW cannot be linked: ' + card['CANDIDATE_ID'])
        if sorted(c['NOVELTY_BATCH_RELATION_IDS']) != sorted(i for i in ids if i != card['CANDIDATE_ID']):
            raise ContractError('calibration export batch coverage: ' + card['CANDIDATE_ID'])
        novelty = {'VERDICT': 'ALLOW', 'PRIOR_RELATIONS': [], 'BATCH_RELATIONS': [
            {'CANDIDATE_ID': o, 'RELATION': ORTHOGONAL} for o in sorted(c['NOVELTY_BATCH_RELATION_IDS'])]}
        feas = {k: copy.deepcopy(cr['FEASIBILITY'][k]) for k in ('VERDICT', 'DATA_STATUS', 'CHECKS')}
        red = {k: copy.deepcopy(cr['RED_TEAM'][k]) for k in ('VERDICT', 'CHECKS')}
        candidates.append(_normalize_review(card, novelty, feas, red, c['STREAM'], 'REVIEWED', 'DERIVED_FROM_ALLOW_VERDICT_UNDER_FROZEN_TABLE'))
    return {'CAMPAIGN_ID': campaign_id, 'SOURCE_KIND': 'GENERATOR_V0_CALIBRATION_EXPORT',
            'SOURCE_ARTIFACT_IDENTITY': {'KIND': 'GENERATOR_V0_CALIBRATION_EXPORT', 'PATH': path.name, 'UNIT': doc['UNIT'],
                                         'SOURCE_HEAD': doc.get('SOURCE_HEAD'), 'GENERATOR_CALL_KEY': doc['GENERATOR']['CALL_KEY'],
                                         'CARD_IDS': ids},
            'SOURCE_SHA256': hashlib.sha256(raw).hexdigest(), 'SOURCE_DATE': doc.get('DATE'),
            'CANDIDATES': candidates, 'INVALID_OUTPUTS': []}


def _check_ladder_card(card):
    """Shape of the V03 ladder fields, against the frozen ladder. Validates; never rewrites."""
    from .complexity import COMPLEXITY_CLASSES, COMPONENT_COUNT
    cls, comps = card.get('COMPLEXITY_CLASS'), card.get('COMPONENTS')
    if cls not in COMPLEXITY_CLASSES:
        raise ContractError('V03 card without a valid COMPLEXITY_CLASS: ' + str(card.get('CANDIDATE_ID')))
    lo, hi = COMPONENT_COUNT[cls]
    if (not isinstance(comps, list) or not all(isinstance(x, str) and x.strip() for x in comps)
            or not lo <= len(comps) <= hi or len(set(comps)) != len(comps)):
        raise ContractError('V03 card COMPONENTS shape: ' + str(card.get('CANDIDATE_ID')))


def source_from_campaign_payload(payload, campaign_id, identity):
    """A completed runner campaign result (results.key='campaign'), as persisted in run.sqlite."""
    if payload.get('STATUS') != 'PENDING_HUMAN_REVIEW':
        raise ContractError('campaign is not complete (status ' + str(payload.get('STATUS')) + ')')
    ladder = payload.get('CONTRACT') == GENERATOR_CONTRACT_V03
    reviews = {r['CANDIDATE_ID']: r for r in payload['REVIEWS']}
    candidates = []
    for card in payload['CANDIDATES']:
        if ladder:
            _check_ladder_card(card)
        elif any(k in card for k in LADDER_CARD_FIELDS):
            raise ContractError('ladder fields on a non-V03 campaign card: ' + card['CANDIDATE_ID'])
        r = reviews.get(card['CANDIDATE_ID'])
        if r is None:
            raise ContractError('admitted candidate without a review record: ' + card['CANDIDATE_ID'])
        if r['STATE'] == 'REVIEW_FAILED':
            candidates.append(_normalize_review(card, None, None, None, 'NOT_A_STREAM', 'REVIEW_FAILED', 'NONE', ladder))
            continue
        n, f, t = r['NOVELTY'], r['FEASIBILITY'], r['RED_TEAM']
        candidates.append(_normalize_review(
            card, {'VERDICT': n['VERDICT'], 'PRIOR_RELATIONS': copy.deepcopy(n['PRIOR_RELATIONS']), 'BATCH_RELATIONS': copy.deepcopy(n['BATCH_RELATIONS'])},
            {k: copy.deepcopy(f[k]) for k in ('VERDICT', 'DATA_STATUS', 'CHECKS')}, {k: copy.deepcopy(t[k]) for k in ('VERDICT', 'CHECKS')},
            r['STREAM'], 'REVIEWED', 'RECORDED_NOVELTY_RELATIONS', ladder))
    invalid = [{'CANDIDATE_ID': h['CANDIDATE_ID'], 'ROUND': h.get('ROUND'), 'RULES': sorted({x.get('RULE') for x in h.get('REASONS', [])} - {None})}
               for h in payload.get('HARD_FAILS', [])]
    source = {'CAMPAIGN_ID': campaign_id, 'SOURCE_KIND': 'GENERATOR_V0_RUN_JOURNAL', 'SOURCE_ARTIFACT_IDENTITY': identity,
              'SOURCE_SHA256': digest(payload), 'SOURCE_DATE': None, 'CANDIDATES': candidates, 'INVALID_OUTPUTS': invalid}
    if ladder:
        source['GENERATOR_CONTRACT'] = GENERATOR_CONTRACT_V03
    return source


def source_from_run_journal(path, campaign_id):
    db = sqlite3.connect('file:{}?mode=ro'.format(Path(path).resolve()), uri=True)
    try:
        row = db.execute("SELECT payload FROM results WHERE key='campaign'").fetchone()
        cfg = db.execute("SELECT value FROM meta WHERE key='config'").fetchone()
    finally:
        db.close()
    if row is None:
        raise ContractError('run journal has no completed campaign result')
    payload = json.loads(row[0])
    config = json.loads(cfg[0]) if cfg else {}
    identity = {'KIND': 'GENERATOR_V0_RUN_JOURNAL', 'RUN_ID': config.get('RUN_ID'),
                'SEMANTIC_RESULT_DIGEST': payload.get('SEMANTIC_RESULT_DIGEST')}
    return source_from_campaign_payload(payload, campaign_id, identity)


def market_test_unit_id(test_family_id):
    m = TEST_FAMILY_ID_RE.fullmatch(test_family_id or '')
    unit = m.group(1).replace('-', '') if m else ''
    if not CAMPAIGN_ID_RE.fullmatch(unit) or unit in RESERVED_CAMPAIGN_IDS:
        raise ContractError('invalid TEST_FAMILY_ID for a memory unit: ' + repr(test_family_id))
    return unit


def _json_file(root, rel, *, canonical_bytes=False):
    path = Path(root) / rel
    try:
        raw = path.read_bytes()
        obj = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ContractError('unreadable scientific authority: ' + str(rel)) from e
    if canonical_bytes and store.pretty(obj) != raw:
        raise ContractError('scientific result is not canonical JSON: ' + str(rel))
    return obj, hashlib.sha256(raw).hexdigest()


def _one(items, key, value, what):
    hits = [x for x in items if x.get(key) == value]
    if len(hits) != 1:
        raise ContractError(what + ' must appear exactly once: ' + str(value))
    return hits[0]


def source_from_market_test_result(root, result_rel, ledger_rel=SCIENTIFIC_TEST_LEDGER):
    """Immutable scientific authorities -> normalized, cross-verified MARKET_TEST_RESULT source.

    Fail-closed on every cross-link. Binds the specific ledger entry (not the whole,
    growing ledger file). The signature is resolved against published memory."""
    root = Path(root)
    result, result_sha = _json_file(root, result_rel, canonical_bytes=True)
    ledger, _ = _json_file(root, ledger_rel)
    ev = result.get('EVALUATION') or {}
    tf, hyp = result.get('TEST_FAMILY_ID'), result.get('HYPOTHESIS_ID')
    unit = market_test_unit_id(tf)
    if result.get('PROTECTED_2025_2026_OPENED') is not False:
        raise ContractError('result does not attest protected 2025/2026 unopened')
    entry = _one(ledger.get('TESTS', []), 'TEST_FAMILY_ID', tf, 'scientific test ledger entry')
    if entry.get('STATUS') != 'EXECUTED':
        raise ContractError('ledger entry is not EXECUTED: ' + str(entry.get('STATUS')))
    if entry.get('RESULT_SHA256') != result_sha or entry.get('RESULT_PATH') != str(result_rel):
        raise ContractError('ledger result digest/path does not match the result file')
    if entry.get('CLASSIFICATION') != ev.get('CLASSIFICATION') or ev.get('CLASSIFICATION') not in DISCOVERY_CLASSIFICATIONS:
        raise ContractError('ledger classification does not match the frozen result classification')
    if entry.get('HYPOTHESIS_ID') != hyp:
        raise ContractError('ledger hypothesis does not match the result')
    if entry.get('RERUN_AUTHORIZED') is not False:
        raise ContractError('ledger entry must record RERUN_AUTHORIZED = false')
    prereg, prereg_sha = _json_file(root, entry['PREREG_PATH'])
    permit, permit_sha = _json_file(root, entry['EXECUTION_PERMIT_PATH'])
    if not (prereg_sha == entry.get('PREREG_SHA256') == (result.get('IDENTITY') or {}).get('PREREG_SHA256') == permit.get('PREREG_SHA256')):
        raise ContractError('prereg digest disagrees across ledger, result identity and permit')
    if (permit.get('EXECUTION_AUTHORIZED') is not True or permit.get('RERUN_AUTHORIZED') is not False
            or permit.get('TEST_FAMILY_ID') != tf or permit.get('HYPOTHESIS_ID') != hyp
            or permit.get('PROTECTED_2025_2026_AUTHORIZED') is not False):
        raise ContractError('execution permit does not authorize exactly this one-shot test')
    if prereg.get('HYPOTHESIS_ID') != hyp or prereg.get('TEST_FAMILY_ID') != tf:
        raise ContractError('prereg identity does not match the result')
    sf_id = entry.get('SEARCH_FAMILY_ID')
    if not (sf_id == prereg.get('SEARCH_FAMILY_ID') == permit.get('SEARCH_FAMILY_ID')):
        raise ContractError('search family disagrees across ledger, prereg and permit')
    family = _one(ledger.get('SEARCH_FAMILIES', []), 'SEARCH_FAMILY_ID', sf_id, 'search family')
    executed = sum(1 for t in ledger['TESTS'] if t.get('SEARCH_FAMILY_ID') == sf_id and t.get('STATUS') == 'EXECUTED')
    if family.get('EXECUTED_TESTS') != executed or executed < 1:
        raise ContractError('search family EXECUTED_TESTS does not include this execution')
    design = read(root / DESIGN)
    pub = store.published(root, design)
    attempt = next((a for a in pub['VIEWS']['ATTEMPTS'] if a['ATTEMPT_ID'] == hyp), None)
    if attempt is None or not attempt.get('SIGNATURE_ID'):
        raise ContractError('hypothesis did not generate a canonical signature in memory: ' + str(hyp))
    sid = attempt['SIGNATURE_ID']
    if sid not in pub['VIEWS']['MEMORY']['ENTRIES']:
        raise ContractError('unknown signature: ' + str(sid))
    identity = {'KIND': 'SCIENTIFIC_MARKET_TEST_RESULT', 'TEST_FAMILY_ID': tf, 'SEARCH_FAMILY_ID': sf_id,
                'HYPOTHESIS_ID': hyp, 'SIGNATURE_ID': sid, 'RESULT_PATH': str(result_rel), 'RESULT_SHA256': result_sha,
                'PREREG_PATH': entry['PREREG_PATH'], 'PREREG_SHA256': prereg_sha,
                'EXECUTION_PERMIT_PATH': entry['EXECUTION_PERMIT_PATH'], 'EXECUTION_PERMIT_SHA256': permit_sha,
                'EXECUTION_PERMIT_COMMIT': entry.get('EXECUTION_PERMIT_COMMIT'),
                'LEDGER_PATH': str(ledger_rel), 'LEDGER_ENTRY_DIGEST': digest(entry)}
    if not isinstance(identity['EXECUTION_PERMIT_COMMIT'], str) or not re.fullmatch(r'[0-9a-f]{40}', identity['EXECUTION_PERMIT_COMMIT']):
        raise ContractError('ledger entry lacks the pre-outcome permit commit')
    return {'UNIT_ID': unit, 'SOURCE_KIND': 'SCIENTIFIC_MARKET_TEST_RESULT', 'SOURCE_ARTIFACT_IDENTITY': identity,
            'SOURCE_SHA256': digest(identity), 'RESULT': result, 'LEDGER_ENTRY': entry, 'PREREG': prereg}


def build_market_test_record(source):
    """Deterministic full-memory record: copied fields only, no operator prose."""
    r, e, idn = source['RESULT'], source['LEDGER_ENTRY'], source['SOURCE_ARTIFACT_IDENTITY']
    ev, prim = r['EVALUATION'], r['PRIMARY']
    pv = source['PREREG']['PARAMS']['PRIMARY_VARIANT']
    if (prim['K'], prim['H'], prim['N']) != (pv['K'], pv['H'], pv['N']):
        raise ContractError('result primary variant differs from the prereg')
    if set(ev['GATES']) != set(RESULT_GATES):
        raise ContractError('result gate set differs from the frozen gates')
    return {
        'TEST_FAMILY_ID': idn['TEST_FAMILY_ID'], 'SEARCH_FAMILY_ID': idn['SEARCH_FAMILY_ID'],
        'HYPOTHESIS_ID': idn['HYPOTHESIS_ID'], 'SIGNATURE_ID': idn['SIGNATURE_ID'],
        'PREREG_PATH': idn['PREREG_PATH'], 'PREREG_SHA256': idn['PREREG_SHA256'],
        'EXECUTION_PERMIT_PATH': idn['EXECUTION_PERMIT_PATH'], 'EXECUTION_PERMIT_COMMIT': idn['EXECUTION_PERMIT_COMMIT'],
        'RESULT_PATH': idn['RESULT_PATH'], 'RESULT_SHA256': idn['RESULT_SHA256'], 'RESULT_SCHEMA': r['SCHEMA'],
        'CLASSIFICATION': ev['CLASSIFICATION'], 'EVIDENCE_TIER': source['PREREG']['EVIDENCE_TIER']['TIER'],
        'PRIMARY_TEST_COUNT': e['PRIMARY_TEST_COUNT'], 'SECONDARY_TEST_COUNT': e['SECONDARY_TEST_COUNT'],
        'MULTIPLICITY_METHOD': e['MULTIPLICITY_METHOD'],
        'DATASET_ID': r['IDENTITY']['DATASET']['DATASET_ID'], 'DATASET_SNAPSHOT_ID': r['IDENTITY']['DATASET']['SNAPSHOT_ID'],
        'PRIMARY_VARIANT': {'K': prim['K'], 'H': prim['H'], 'N': prim['N']},
        'PRIMARY': {'POOLED': prim['POOLED'], 'P_TWO_SIDED': prim['NULL']['P_TWO_SIDED'], 'VALID_DAYS': prim['VALID_DAYS'],
                    'VALID_WEEKS': prim['VALID_WEEKS'], 'MISSING_TARGET_RATE': prim['MISSING_TARGET_RATE'],
                    'YEARLY': copy.deepcopy(prim['YEARLY'])},
        'CONTROLLED': {'POOLED': prim['CONTROLLED']['POOLED'], 'P_TWO_SIDED': prim['CONTROLLED']['NULL']['P_TWO_SIDED']},
        'GATES': {g: ev['GATES'][g] for g in RESULT_GATES},
        'HAC_T': ev.get('HAC_T'), 'YEARS_SHARING_POOLED_SIGN': copy.deepcopy(ev.get('YEARS_SHARING_POOLED_SIGN')),
        'ADJACENCY_POOLED': r['ADJACENCY_DIAGNOSTIC']['POOLED'],
        'SECONDARY_CAN_CHANGE_CLASSIFICATION': ev['SECONDARY_CAN_CHANGE_CLASSIFICATION'],
        'PROTECTED_2025_2026_OPENED': r['PROTECTED_2025_2026_OPENED'],
        'RERUN_AUTHORIZED': e['RERUN_AUTHORIZED'], 'LEDGER_STATUS': e['STATUS'],
        'INTERPRETATION': MARKET_RESULT_INTERPRETATION,
    }


def build_market_delta(state, source):
    unit = source['UNIT_ID']
    record = build_market_test_record(source)
    return {'KIND': 'MARKET_TEST_RESULT', 'FINALIZER_VERSION': FINALIZER_VERSION, 'CAMPAIGN_ID': unit,
            'SOURCE_KIND': source['SOURCE_KIND'], 'SOURCE_ARTIFACT_IDENTITY': source['SOURCE_ARTIFACT_IDENTITY'],
            'SOURCE_SHA256': source['SOURCE_SHA256'], 'ADD_ENTRIES': {}, 'ADD_ROWS': [], 'ATTEMPTS': [],
            'ADD_MARKET_TEST_RESULTS': {record['TEST_FAMILY_ID']: record},
            'SUMMARY': {'MARKET_TEST_RESULTS_ADDED': 1, 'TEST_FAMILY_ID': record['TEST_FAMILY_ID'],
                        'SIGNATURE_ID': record['SIGNATURE_ID'], 'MEMORY_ENTRY_COUNT': len(state['MEMORY']['ENTRIES']),
                        'ATTEMPT_RECORD_COUNT': len(state['ATTEMPTS'])}}


# ----------------------------------------------------------------------------- deterministic dispositions

def _failed(checks):
    return sorted(k for k, v in checks.items() if v is False)


def _route(n_verdict, f, r):
    if r['VERDICT'] != 'PASS' or f['VERDICT'] != 'PASS':
        return 'NOT_A_STREAM'
    s = f['DATA_STATUS']
    if n_verdict == 'ALLOW' and s == 'DATA_READY':
        return 'EXECUTABLE_NOW'
    if n_verdict == 'ALLOW_TO_FEASIBILITY' and not f.get('CHECKS', {}).get('BLOCKER_RESOLVED', False):
        return 'NOT_A_STREAM'
    if n_verdict in ('ALLOW', 'ALLOW_TO_FEASIBILITY') and s != 'DATA_READY':
        return 'HIGH_VALUE_DATA_BLOCKED'
    return 'NOT_A_STREAM'


def blockers_for(f, r, ladder=False):
    """All blockers of a distinct signature, primary first. Structured checks only."""
    out = []
    failed_red = _failed(r['CHECKS'])
    if set(r['CHECKS']) != set(RED_TEAM_CHECKS_V03 if ladder else RED_TEAM_CHECKS):
        raise ContractError('RED_TEAM checks shape')
    if failed_red:
        for need, cls in (RED_TEAM_BLOCKER_RULES_V03 if ladder else RED_TEAM_BLOCKER_RULES):
            if set(need) <= set(failed_red):
                out.append({'CLASS': cls, 'SOURCE': 'RED_TEAM', 'FAILED_CHECKS': failed_red})
                break
        else:
            raise ContractError('unmapped RED_TEAM failure: ' + ','.join(failed_red))
    if f['VERDICT'] == 'REJECT':
        cls = 'DATA_LEGAL_RANGE_NOT_SATISFIED' if f['CHECKS'].get('LEGAL_RANGE') is False else 'DATA_READY_CLAIM_NOT_CONFIRMED'
        out.append({'CLASS': cls, 'SOURCE': 'FEASIBILITY', 'FAILED_CHECKS': _failed(f['CHECKS'])})
    elif f['VERDICT'] == 'HUMAN_REVIEW':
        out.append({'CLASS': 'DATA_STATUS_DISAGREEMENT_REQUIRES_HUMAN_REVIEW', 'SOURCE': 'FEASIBILITY', 'FAILED_CHECKS': _failed(f['CHECKS'])})
    elif f['VERDICT'] != 'PASS':
        raise ContractError('unknown feasibility verdict: ' + str(f['VERDICT']))
    if f['DATA_STATUS'] != 'DATA_READY':
        cls = f['DATA_STATUS'] if f['DATA_STATUS'].startswith('DATA_BLOCKED_') else 'DATA_FEASIBILITY_REQUIRED'
        out.append({'CLASS': cls, 'SOURCE': 'FEASIBILITY_DATA_STATUS', 'FAILED_CHECKS': _failed(f['CHECKS'])})
    return out


def requirement_text(blockers):
    primary = blockers[0]['CLASS']
    text = BLOCKER_REQUIREMENTS.get(primary) or BLOCKER_REQUIREMENTS_V03.get(primary) or DATA_BLOCKED_REQUIREMENT.format(status=primary)
    others = [b['CLASS'] for b in blockers[1:]]
    if others:
        text += ' Also unresolved for this signature: ' + ', '.join(others) + '.'
    return text


def _prior_leaf_rows(state):
    return {k: r for k, r in store.rows_by_id(state['ROWS']).items() if r['STATE'] != 'PARTIAL_OR_MIXED'}


def _norm(x):
    return re.sub(r'[^a-z0-9]+', ' ', x.lower()).strip()


def build_delta(state, source, design):
    """Pure: current published FULL state + normalized source -> append-only delta."""
    campaign = source['CAMPAIGN_ID']
    stable_id(campaign, 'C001')
    ladder = source.get('GENERATOR_CONTRACT') == GENERATOR_CONTRACT_V03
    if source.get('GENERATOR_CONTRACT') not in (None, GENERATOR_CONTRACT_V03):
        raise ContractError('unknown generator contract in source')
    table = design['GOVERNANCE_REGION_AUTHORITY_V0']['NOVELTY_DECISION_TABLE']
    leaves = _prior_leaf_rows(state)
    from .schema import signature
    cands = sorted(source['CANDIDATES'], key=lambda c: c['CANDIDATE_ID'])
    ids = [c['CANDIDATE_ID'] for c in cands]
    if len(ids) != len(set(ids)):
        raise ContractError('duplicate candidate id in source')
    by_id = {c['CANDIDATE_ID']: c for c in cands}
    for c in cands:
        stable_id(campaign, c['CANDIDATE_ID'])
        if c['CARD']['CANDIDATE_ID'] != c['CANDIDATE_ID']:
            raise ContractError('card identity mismatch: ' + c['CANDIDATE_ID'])
    # Batch links: a non-orthogonal relation in either direction, or an identical
    # deterministic signature, links the later ID to the earlier one (runner rule).
    batch_link = {}
    for c in cands:
        if c['REVIEW_STATE'] != 'REVIEWED':
            continue
        for rel in c['NOVELTY']['BATCH_RELATIONS']:
            other = rel['CANDIDATE_ID']
            if other not in by_id:
                raise ContractError('batch relation to unknown candidate: ' + other)
            if rel['RELATION'] != ORTHOGONAL:
                later, earlier = max(c['CANDIDATE_ID'], other), min(c['CANDIDATE_ID'], other)
                batch_link.setdefault(later, set()).add((earlier, rel['RELATION'] if c['CANDIDATE_ID'] == later else rel['RELATION'] + '_REVERSE'))
    for i, a in enumerate(cands):
        for b in cands[i + 1:]:
            if signature(a['CARD']) == signature(b['CARD']):
                batch_link.setdefault(b['CANDIDATE_ID'], set()).add((a['CANDIDATE_ID'], 'IDENTICAL_DETERMINISTIC_SIGNATURE'))
    add_entries, add_rows, attempts, canonical_of = {}, [], [], {}
    counts = {'ATTEMPT_RECORDS': 0, 'NEW_CANONICAL_SIGNATURES': 0, 'LINKS_TO_PRIOR_SIGNATURES': 0,
              'LINKS_TO_BATCH_ATTEMPTS': 0, 'REVIEW_INCOMPLETE': 0, 'INVALID_OUTPUTS': len(source['INVALID_OUTPUTS'])}
    for c in cands:
        aid = stable_id(campaign, c['CANDIDATE_ID'])
        record = {'ATTEMPT_ID': aid, 'CAMPAIGN_ID': campaign, 'CANDIDATE_ID': c['CANDIDATE_ID'], 'CARD': c['CARD'],
                  'REVIEW_STATE': c['REVIEW_STATE'], 'PRIOR_RELATIONS_BASIS': c['PRIOR_RELATIONS_BASIS'],
                  'NO_SCIENTIFIC_STATUS': True, 'MARKET_TESTS': [], 'SIGNATURE_ID': None,
                  'PRIOR_LINKS': [], 'BATCH_LINKS': [], 'BLOCKERS': [], 'STREAM': c['STREAM'], 'CRITICS': None}
        counts['ATTEMPT_RECORDS'] += 1
        if c['REVIEW_STATE'] == 'REVIEW_FAILED':
            record['DISPOSITION'] = 'REVIEW_INCOMPLETE_NO_SIGNATURE'
            counts['REVIEW_INCOMPLETE'] += 1
            attempts.append(record)
            continue
        n, f, r = c['NOVELTY'], c['FEASIBILITY'], c['RED_TEAM']
        record['CRITICS'] = {'NOVELTY': {'VERDICT': n['VERDICT']},
                             'FEASIBILITY': {'VERDICT': f['VERDICT'], 'DATA_STATUS': f['DATA_STATUS'], 'FAILED_CHECKS': _failed(f['CHECKS'])},
                             'RED_TEAM': {'VERDICT': r['VERDICT'], 'FAILED_CHECKS': _failed(r['CHECKS'])}}
        prior_links, prior_verdicts = [], []
        for rel in n['PRIOR_RELATIONS']:
            sid, relation = rel['SIGNATURE_ID'], rel['RELATION']
            if sid not in leaves:
                raise ContractError('novelty relation to unknown prior signature: ' + sid)
            if relation == ORTHOGONAL:
                continue
            if relation not in LINK_RELATIONS:
                raise ContractError('unknown novelty relation: ' + relation)
            prior_links.append({'SIGNATURE_ID': sid, 'RELATION': relation, 'BASIS': 'NOVELTY_CRITIC'})
            prior_verdicts.append(table[leaves[sid]['STATE']][relation])
        # The novelty role's deterministic exact-duplicate override (roles._novelty).
        for sid, leaf in sorted(leaves.items()):
            if _norm(c['CARD']['MECHANISM']) == _norm(leaf['MECHANISM']) and _norm(c['CARD']['FUNCTION']) == _norm(leaf['FUNCTION']):
                if not any(l['SIGNATURE_ID'] == sid for l in prior_links):
                    prior_links.append({'SIGNATURE_ID': sid, 'RELATION': 'EXACT_DUPLICATE', 'BASIS': 'DETERMINISTIC_EXACT_MATCH'})
                    prior_verdicts.append(table[leaf['STATE']]['EXACT_DUPLICATE'])
        blinks = sorted(batch_link.get(c['CANDIDATE_ID'], ()))
        expected = next((v for v in VERDICT_PRECEDENCE if v in prior_verdicts), 'ALLOW')
        if blinks:
            if n['VERDICT'] != 'REJECT':
                raise ContractError('batch-linked candidate must carry the REJECT verdict: ' + c['CANDIDATE_ID'])
        elif n['VERDICT'] != expected:
            raise ContractError('novelty verdict inconsistent with its relations: ' + c['CANDIDATE_ID'])
        stream_expected = _route('REJECT' if blinks else n['VERDICT'], f, r)
        if c['STREAM'] != stream_expected:
            raise ContractError('recorded stream inconsistent with critic verdicts: ' + c['CANDIDATE_ID'])
        record['PRIOR_LINKS'] = sorted(prior_links, key=lambda l: (l['SIGNATURE_ID'], l['RELATION']))
        record['BATCH_LINKS'] = [{'ATTEMPT_ID': stable_id(campaign, e), 'RELATION': rel} for e, rel in blinks]
        if prior_links:
            relations = {l['RELATION'] for l in prior_links}
            record['DISPOSITION'] = ('LINKED_PRIOR_BLOCKER_RESOLUTION_PROPOSAL' if relations == {'RESOLVES_BLOCKER'}
                                     else 'LINKED_PRIOR_DUPLICATE_OR_NEIGHBOR')
            counts['LINKS_TO_PRIOR_SIGNATURES'] += 1
        elif blinks:
            record['DISPOSITION'] = 'LINKED_BATCH_DUPLICATE_OR_NEIGHBOR'
            target = canonical_of.get(blinks[0][0])
            record['BATCH_LINKS'][0]['CANONICAL_SIGNATURE_ID'] = target
            counts['LINKS_TO_BATCH_ATTEMPTS'] += 1
        else:
            sid = aid
            blockers = blockers_for(f, r, ladder)
            state_name = 'DEFERRED_OR_BLOCKED' if blockers else 'CONSUMED'
            if (state_name == 'CONSUMED') != (c['STREAM'] == 'EXECUTABLE_NOW'):
                raise ContractError('consumed state must equal the EXECUTABLE_NOW stream: ' + c['CANDIDATE_ID'])
            datasets = []
            for d in c['CARD']['DATA_REQUIRED']:
                if d['DATASET'] not in datasets:
                    datasets.append(d['DATASET'])
            sig = {'MECHANISM': scrub(c['CARD']['NAME'], design), 'FUNCTION': scrub(c['CARD']['FUNCTION'], design),
                   'INFORMATION_SOURCE': scrub(c['CARD']['INFORMATION_SOURCE'] + ': ' + ', '.join(datasets), design),
                   'TARGET_FAMILY': scrub(c['CARD']['PRIMARY_TARGET'], design)}
            primary = blockers[0]['CLASS'] if blockers else None
            add_rows.append({'SIGNATURE_ID': sid, 'MECHANISM': sig['MECHANISM'], 'FUNCTION': sig['FUNCTION'], 'STATE': state_name,
                             'ANTI_RESCUE_SCOPE': ANTI_RESCUE_SCOPE[state_name], 'BLOCKER_CLASS_IF_ANY': primary,
                             'BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY': requirement_text(blockers) if blockers else None})
            verdicts = 'novelty {}, feasibility {}, red team {}'.format(n['VERDICT'], f['VERDICT'], r['VERDICT'])
            failed = _failed(r['CHECKS'])
            add_entries[sid] = {
                'ID': sid, **sig, 'GENERATION': 'GENERATOR_V0_CAMPAIGN_' + campaign,
                'DATA_STATE': f['DATA_STATUS'] + '; generated candidate; market outcomes not tested; protected 2025/2026 unopened',
                'STATUS_EVIDENCE_CLASS': ('PIPELINE_BLOCKED_' + primary if primary else 'PIPELINE_SURVIVOR') + '_NO_SCIENTIFIC_STATUS',
                'WHAT_WAS_ACTUALLY_TESTED': 'Generator V0 pipeline only: ' + verdicts
                    + ('; red team failed checks: ' + ', '.join(failed) if failed else '') + '. No market outcomes were tested.',
                'WHAT_THE_RESULT_DEPRIORITIZES_OR_CLOSES': ('Exact duplicate, cosmetic relabel, and parameter/window/horizon neighbors of this already-generated mechanism signature.'
                    if not primary else 'Exact duplicate, cosmetic relabel, and parameter/window/horizon neighbors that leave the ' + primary + ' blocker unresolved.'),
                'WHAT_REMAINS_OPEN': ('Market-outcome testing only if later selected under a separate frozen research contract; orthogonal mechanisms remain open.'
                    if not primary else 'A materially redesigned candidate that explicitly resolves ' + primary + '; orthogonal mechanisms remain open.'),
                'NEIGHBOR_RESCUE_WARNING': ('Do not regenerate the same mechanism through threshold/window/horizon changes, observable substitution within the same function, or functional relabeling.'
                    if not primary else 'Do not regenerate the same mechanism or parameter/window/horizon neighbors unless the named blocker is explicitly resolved: ' + primary + '.'),
                'POSTHOC_RESIDUALS_IF_ANY': None}
            # Exactly the frozen memory-entry schema (design WHITELISTED + EXCLUDED fields).
            # Campaign identity, disposition, blockers and MARKET_TESTS live on the attempt record.
            if set(add_entries[sid]) != set(design['BLIND_GENERATOR_CONTEXT']['WHITELISTED_FIELDS']) | set(design['BLIND_GENERATOR_CONTEXT']['EXCLUDED_FIELDS']):
                raise ContractError('memory entry schema drift')
            record['DISPOSITION'] = 'NEW_SIGNATURE_' + state_name
            record['SIGNATURE_ID'] = sid
            record['BLOCKERS'] = blockers
            canonical_of[c['CANDIDATE_ID']] = sid
            counts['NEW_CANONICAL_SIGNATURES'] += 1
        if record['SIGNATURE_ID'] is None and prior_links:
            canonical_of[c['CANDIDATE_ID']] = record['PRIOR_LINKS'][0]['SIGNATURE_ID']
        elif record['SIGNATURE_ID'] is None and blinks:
            canonical_of[c['CANDIDATE_ID']] = canonical_of.get(blinks[0][0])
        attempts.append(record)
    for inv in source['INVALID_OUTPUTS']:
        stable_id(campaign, inv['CANDIDATE_ID'])
    delta = {'KIND': 'CAMPAIGN_FINALIZATION', 'FINALIZER_VERSION': FINALIZER_VERSION, 'CAMPAIGN_ID': campaign,
             'SOURCE_KIND': source['SOURCE_KIND'], 'SOURCE_ARTIFACT_IDENTITY': source['SOURCE_ARTIFACT_IDENTITY'],
             'SOURCE_SHA256': source['SOURCE_SHA256'], 'ADD_ENTRIES': add_entries, 'ADD_ROWS': add_rows,
             'ATTEMPTS': attempts, 'INVALID_OUTPUTS': source['INVALID_OUTPUTS'],
             'MEMORY_METADATA': {'COVERAGE': {'GENERATOR_V0_' + campaign: sorted(add_entries)} if add_entries else {},
                                 'STATUS': 'EXTENDED_THROUGH_' + campaign, 'DATE': source.get('SOURCE_DATE')},
             'SUMMARY': counts}
    if ladder:
        delta['GENERATOR_CONTRACT'] = GENERATOR_CONTRACT_V03
    return delta


# ----------------------------------------------------------------------------- finalize / verify / rebuild

def _design(root):
    return read(Path(root) / DESIGN)


def verify_generator_boundary(root, v, design):
    """The generator-visible projection must pass the frozen scanner and carry only neutral fields."""
    blind = design['BLIND_GENERATOR_CONTEXT']
    allowed = set(blind['WHITELISTED_FIELDS']) | set(blind['PER_ENTRY_ADDED_FIELD'])
    for key, row in v['BLIND_MAP'].items():
        if set(row) != allowed or row['REGION_STATE'] != blind['REGION_STATE_VALUE']:
            raise ContractError('blind projection shape: ' + key)
    if re.search(blind['CONTEXT_SCANNER']['DENYLIST_REGEX'], canonical(v['BLIND_MAP']), re.IGNORECASE):
        raise ContractError('blind projection trips the frozen generator scanner')


def verify(root, all_snapshots=True):
    design = _design(root)
    pub = store.published(root, design, all_snapshots=all_snapshots)
    verify_generator_boundary(root, pub['VIEWS'], design)
    drift = store.mirrors_current(root, pub['VIEWS'])
    pins_ok = (Path(root) / store.PINS).exists() and read(Path(root) / store.PINS) == store.pins_expected(root)
    ids = [a['ATTEMPT_ID'] for a in pub['VIEWS']['ATTEMPTS']]
    return {'STATUS': 'VERIFIED' if not drift and pins_ok else 'CHAIN_VERIFIED_DERIVED_CACHE_DRIFT',
            'HEAD_EVENT_HASH': pub['HEAD']['EVENT_HASH'], 'SEQUENCE': pub['HEAD']['SEQUENCE'],
            'EVENTS': [{'SEQUENCE': e['SEQUENCE'], 'EVENT_TYPE': e['EVENT_TYPE'], 'CAMPAIGN_ID': e['CAMPAIGN_ID'], 'EVENT_HASH': e['EVENT_HASH']} for e in pub['EVENTS']],
            'MEMORY_ENTRY_COUNT': len(pub['VIEWS']['MEMORY']['ENTRIES']), 'ATTEMPT_RECORD_COUNT': len(ids),
            'MARKET_TEST_RESULT_COUNT': len(pub['VIEWS']['MEMORY'].get(store.MARKET_TEST_RESULTS_KEY, {})),
            'DUPLICATE_STABLE_IDS': len(ids) != len(set(ids)), 'MIRROR_DRIFT': drift, 'PINS_CURRENT': pins_ok,
            'DIGESTS': store.view_digests(pub['VIEWS'])}


def rebuild(root):
    """Replay bootstrap + deltas under frozen rules; compare with every published snapshot."""
    design = _design(root)
    events = store.chain(root)
    _, per_event = store.replay(root, design, events)
    for ev, v in zip(events, per_event):
        store.check_snapshot(root, ev, v)
    return {'STATUS': 'REBUILT_EQUALS_PUBLISHED', 'HEAD_EVENT_HASH': events[-1]['EVENT_HASH'],
            'DIGESTS': store.view_digests(per_event[-1])}


def bootstrap(root, legacy_memory, legacy_rows, provenance, fault=None):
    root = Path(root)
    design = _design(root)
    with store.exclusive_lock(root):
        if store.read_head(root) is not None:
            raise ContractError('memory chain already bootstrapped')
        delta = {'KIND': 'LEGACY_BOOTSTRAP', 'CAMPAIGN_ID': 'LEGACY', 'LEGACY_MEMORY': legacy_memory,
                 'LEGACY_GOVERNANCE_ROWS': legacy_rows, 'PROVENANCE': provenance,
                 'SOURCE_SHA256': digest({'MEMORY': legacy_memory, 'ROWS': legacy_rows})}
        v = store.views(store.genesis_state(delta), design)
        verify_generator_boundary(root, v, design)
        ev = store.build_event('LEGACY_BOOTSTRAP', 0, 'LEGACY', provenance, delta['SOURCE_SHA256'], store.GENESIS,
                               store.sha256_bytes(store.pretty(delta)), rules_digest(design), v,
                               {'MEMORY_ENTRY_COUNT': len(legacy_memory['ENTRIES']), 'GOVERNANCE_ROW_COUNT': len(legacy_rows)})
        store.publish(root, design, delta, ev, v, fault)
        return ev


def _already_finalized(root, pub, unit, source_sha, apply):
    """Idempotence on the event unit (CAMPAIGN_ID field): same source -> no-op (repairing
    derived caches on apply); different source -> hard failure."""
    prior = [e for e in pub['EVENTS'] if e['CAMPAIGN_ID'] == unit]
    if not prior:
        return None
    if prior[0]['SOURCE_SHA256'] != source_sha:
        raise ContractError('unit ' + unit + ' already finalized from a different source; refusing to reinterpret')
    repaired = []
    if apply:
        repaired = store.mirrors_current(root, pub['VIEWS'])
        pins_ok = (root / store.PINS).exists() and read(root / store.PINS) == store.pins_expected(root)
        if repaired or not pins_ok:
            store.write_derived_caches(root, pub['VIEWS'])
            repaired = repaired or ['PINS']
    return {'STATUS': 'ALREADY_FINALIZED', 'CAMPAIGN_ID': unit, 'EVENT_HASH': prior[0]['EVENT_HASH'],
            'SOURCE_SHA256': source_sha, 'NEW_EVENT': False, 'DERIVED_CACHES_REPAIRED': repaired}


def finalize(root, source, apply=False, fault=None):
    """Dry run (apply=False) writes nothing. Apply stages, verifies and publishes one event."""
    root = Path(root)
    design = _design(root)
    lock = store.exclusive_lock(root) if apply else _nolock()
    with lock:
        pub = store.published(root, design)
        head = pub['HEAD']
        done = _already_finalized(root, pub, source['CAMPAIGN_ID'], source['SOURCE_SHA256'], apply)
        if done:
            return done
        state = {'MEMORY': pub['VIEWS']['MEMORY'], 'ROWS': pub['VIEWS']['AUTHORITY']['ROWS'], 'ATTEMPTS': pub['VIEWS']['ATTEMPTS']}
        delta = build_delta(state, source, design)
        new_state = store.apply_delta(state, delta)
        v = store.views(new_state, design)
        verify_generator_boundary(root, v, design)
        seq = head['SEQUENCE'] + 1
        ev = store.build_event('CAMPAIGN_FINALIZATION', seq, source['CAMPAIGN_ID'], source['SOURCE_ARTIFACT_IDENTITY'],
                               source['SOURCE_SHA256'], head['EVENT_HASH'], store.sha256_bytes(store.pretty(delta)),
                               rules_digest(design, source.get('GENERATOR_CONTRACT')), v, delta['SUMMARY'])
        report = {'STATUS': 'DRY_RUN' if not apply else 'FINALIZED', 'CAMPAIGN_ID': source['CAMPAIGN_ID'],
                  'SOURCE_SHA256': source['SOURCE_SHA256'], 'PREVIOUS_HEAD_EVENT_HASH': head['EVENT_HASH'],
                  'PROPOSED_EVENT_HASH': ev['EVENT_HASH'], 'SEQUENCE': seq, **delta['SUMMARY'],
                  'NEW_SIGNATURE_IDS': sorted(delta['ADD_ENTRIES']), 'RESULTING_DIGESTS': store.view_digests(v), 'NEW_EVENT': apply}
        if apply:
            store.publish(root, design, delta, ev, v, fault)
        return report


def finalize_market_test_result(root, source, apply=False, fault=None):
    """Append one MARKET_TEST_RESULT event. Dry run writes nothing. Fails closed unless the
    blind map, governance authority and attempt records are unchanged."""
    root = Path(root)
    design = _design(root)
    lock = store.exclusive_lock(root) if apply else _nolock()
    with lock:
        pub = store.published(root, design)
        head = pub['HEAD']
        unit = source['UNIT_ID']
        done = _already_finalized(root, pub, unit, source['SOURCE_SHA256'], apply)
        if done:
            done['TEST_FAMILY_ID'] = source['SOURCE_ARTIFACT_IDENTITY']['TEST_FAMILY_ID']
            return done
        tf = source['SOURCE_ARTIFACT_IDENTITY']['TEST_FAMILY_ID']
        if tf in pub['VIEWS']['MEMORY'].get(store.MARKET_TEST_RESULTS_KEY, {}):
            raise ContractError('test family already attached to memory: ' + tf)
        state = {'MEMORY': pub['VIEWS']['MEMORY'], 'ROWS': pub['VIEWS']['AUTHORITY']['ROWS'], 'ATTEMPTS': pub['VIEWS']['ATTEMPTS']}
        delta = build_market_delta(state, source)
        v = store.views(store.apply_delta(state, delta), design)
        verify_generator_boundary(root, v, design)
        before, after = store.view_digests(pub['VIEWS']), store.view_digests(v)
        for key in ('RESULTING_BLIND_MAP_DIGEST', 'RESULTING_AUTHORITY_DIGEST', 'RESULTING_ATTEMPTS_DIGEST'):
            if before[key] != after[key]:
                raise ContractError('MARKET_TEST_RESULT would change ' + key)
        seq = head['SEQUENCE'] + 1
        ev = store.build_event('MARKET_TEST_RESULT', seq, unit, source['SOURCE_ARTIFACT_IDENTITY'], source['SOURCE_SHA256'],
                               head['EVENT_HASH'], store.sha256_bytes(store.pretty(delta)), rules_digest(design), v, delta['SUMMARY'])
        report = {'STATUS': 'DRY_RUN' if not apply else 'FINALIZED', 'EVENT_TYPE': 'MARKET_TEST_RESULT', 'CAMPAIGN_ID': unit,
                  'TEST_FAMILY_ID': tf, 'SIGNATURE_ID': delta['SUMMARY']['SIGNATURE_ID'],
                  'SOURCE_SHA256': source['SOURCE_SHA256'], 'MEMORY_DELTA_SHA256': ev['MEMORY_DELTA_SHA256'],
                  'PREVIOUS_HEAD_EVENT_HASH': head['EVENT_HASH'], 'PROPOSED_EVENT_HASH': ev['EVENT_HASH'], 'SEQUENCE': seq,
                  'DIGESTS_BEFORE': before, 'RESULTING_DIGESTS': after,
                  'MEMORY_ENTRY_COUNT': len(v['MEMORY']['ENTRIES']), 'ATTEMPT_RECORD_COUNT': len(v['ATTEMPTS']),
                  'MARKET_TEST_RESULT_COUNT': len(v['MEMORY'][store.MARKET_TEST_RESULTS_KEY]), 'NEW_EVENT': apply}
        if apply:
            store.publish(root, design, delta, ev, v, fault)
        return report


class _nolock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
