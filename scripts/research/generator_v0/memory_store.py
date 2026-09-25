"""Append-only Generator V0 memory chain, deterministic replay and atomic publish.

Authority model
  The event chain under docs/research/generator_v0_memory/ is the historical
  authority. Event 0 is the immutable LEGACY_BOOTSTRAP; every later event binds one
  append-only delta. The current memory is whatever deterministic replay of
  bootstrap + deltas yields under the frozen design rules. HEAD.json names the chain
  head and is the single publish point (one os.replace). Snapshot directories are
  immutable versioned copies of replayed state; mirrors and context pins are derived
  caches, verified against the head snapshot and never trusted on their own.

Two kinds of memory
  FULL memory (MECHANISM_MEMORY + ATTEMPT_RECORDS) may hold pipeline dispositions,
  blockers and, later, scientific results. The blind generator projection only ever
  exposes the design's WHITELISTED_FIELDS plus REGION_STATE=PRIOR_WORK_SIGNATURE, so
  no disposition or outcome can reach GENERATOR through this module.
"""
from __future__ import annotations
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
from .context import ContractError, canonical, digest, project

SCHEMA_VERSION = 'GENERATOR_V0_MEMORY_CHAIN_V1'
STORE = 'docs/research/generator_v0_memory'
HEAD_FILE = STORE + '/HEAD.json'
GENESIS = 'GENESIS'
EVENT_TYPES = ('LEGACY_BOOTSTRAP', 'CAMPAIGN_FINALIZATION', 'MARKET_TEST_RESULT')
# MARKET_TEST_RESULT attaches one frozen experiment result to FULL memory
# (MEMORY.MARKET_TEST_RESULTS, keyed by TEST_FAMILY_ID) of an existing signature. It
# adds no entry, row or attempt, so the blind projection and the governance authority
# cannot change. No event type is reserved any more.
RESERVED_EVENT_TYPES = ()
MARKET_TEST_RESULTS_KEY = 'MARKET_TEST_RESULTS'
SNAPSHOT_FILES = {
    'MEMORY': 'MECHANISM_MEMORY_V0.json',
    'BLIND_MAP': 'BLIND_MECHANISM_MAP_V0.json',
    'AUTHORITY': 'GOVERNANCE_REGION_AUTHORITY_V0.json',
    'ATTEMPTS': 'ATTEMPT_RECORDS.json',
}
MIRRORS = {
    'MEMORY': 'docs/research/MECHANISM_MEMORY_V0.json',
    'BLIND_MAP': 'docs/research/BLIND_MECHANISM_MAP_V0.json',
    'AUTHORITY': 'docs/research/GOVERNANCE_REGION_AUTHORITY_V0.json',
}
# Keys of the design's governance section that are rules, not rows. ROWS never come
# from the design: they are a projection of accumulated memory.
DESIGN_ONLY_GOVERNANCE_KEYS = ('ROWS', 'ROWS_SOURCE')
EVENT_FIELDS = ('SCHEMA_VERSION', 'EVENT_TYPE', 'SEQUENCE', 'CAMPAIGN_ID', 'SOURCE_ARTIFACT_IDENTITY', 'SOURCE_SHA256',
                'PREVIOUS_EVENT_HASH', 'MEMORY_DELTA_SHA256', 'RULES_DIGEST', 'FINALIZER_CODE_DIGEST',
                'RESULTING_MEMORY_DIGEST', 'RESULTING_BLIND_MAP_DIGEST', 'RESULTING_AUTHORITY_DIGEST',
                'RESULTING_ATTEMPTS_DIGEST', 'SUMMARY', 'EVENT_HASH')
CODE_FILES = ('memory_store.py', 'memory_finalizer.py')


def pretty(obj):
    """The only byte serialization used for store files, mirrors and pins."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def read_canonical(path):
    """Parse a store file and refuse non-canonical bytes (so bytes <-> semantics are 1:1)."""
    try:
        raw = Path(path).read_bytes()
    except OSError as e:
        raise ContractError('memory store file missing or unreadable: ' + str(path)) from e
    try:
        obj = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as e:
        raise ContractError('memory store file is not JSON: ' + str(path)) from e
    if pretty(obj) != raw:
        raise ContractError('memory store file is not canonical: ' + str(path))
    return obj, raw


def event_hash(event):
    return digest({k: v for k, v in event.items() if k != 'EVENT_HASH'})


def code_digest():
    here = Path(__file__).resolve().parent
    return digest({name: sha256_bytes((here / name).read_bytes()) for name in CODE_FILES})


# ----------------------------------------------------------------------------- state and projections

def design_governance_header(design):
    gov = design['GOVERNANCE_REGION_AUTHORITY_V0']
    return {k: copy.deepcopy(v) for k, v in gov.items() if k not in DESIGN_ONLY_GOVERNANCE_KEYS}


def rows_by_id(rows):
    out = {}
    for row in rows:
        for rid in [row['SIGNATURE_ID']] + [s['SIGNATURE_ID'] for s in row.get('SUB_SIGNATURES', [])]:
            if rid in out:
                raise ContractError('duplicate governance signature id: ' + rid)
        out[row['SIGNATURE_ID']] = row
        for sub in row.get('SUB_SIGNATURES', []):
            out[sub['SIGNATURE_ID']] = sub
    return out


def views(state, design):
    """Deterministic projections of FULL state. Fails closed on any coverage break."""
    memory = state['MEMORY']
    header = design_governance_header(design)
    rows = state['ROWS']
    rows_by_id(rows)
    top = [r['SIGNATURE_ID'] for r in rows]
    if set(top) != set(memory['ENTRIES']) or len(top) != len(set(top)):
        raise ContractError('governance coverage: every memory entry needs exactly one row')
    fields = set(header['ROW_FIELDS'])
    for r in rows:
        if set(r) - {'SUB_SIGNATURES'} != fields or r['STATE'] not in header['STATES']:
            raise ContractError('governance row shape/state: ' + r['SIGNATURE_ID'])
    attempt_ids = [a['ATTEMPT_ID'] for a in state['ATTEMPTS']]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ContractError('duplicate attempt record id')
    blind = project(memory, design)
    authority = {**header, 'ROWS': copy.deepcopy(rows)}
    return {'MEMORY': copy.deepcopy(memory), 'BLIND_MAP': blind, 'AUTHORITY': authority,
            'ATTEMPTS': copy.deepcopy(state['ATTEMPTS'])}


def view_digests(v):
    return {'RESULTING_MEMORY_DIGEST': digest(v['MEMORY']), 'RESULTING_BLIND_MAP_DIGEST': digest(v['BLIND_MAP']),
            'RESULTING_AUTHORITY_DIGEST': digest(v['AUTHORITY']), 'RESULTING_ATTEMPTS_DIGEST': digest(v['ATTEMPTS'])}


def genesis_state(delta):
    if delta.get('KIND') != 'LEGACY_BOOTSTRAP':
        raise ContractError('event 0 must bind a LEGACY_BOOTSTRAP delta')
    return {'MEMORY': copy.deepcopy(delta['LEGACY_MEMORY']), 'ROWS': copy.deepcopy(delta['LEGACY_GOVERNANCE_ROWS']),
            'ATTEMPTS': []}


def apply_delta(state, delta):
    """Mechanical, append-only merge. Existing entries, rows and attempts are never rewritten."""
    kind = delta.get('KIND')
    if kind in RESERVED_EVENT_TYPES:
        raise ContractError(kind + ' is a reserved event type and is not implemented')
    if kind == 'MARKET_TEST_RESULT':
        return _apply_market_test_result(state, delta)
    if kind != 'CAMPAIGN_FINALIZATION':
        raise ContractError('unknown delta kind: ' + str(kind))
    new = copy.deepcopy(state)
    entries = new['MEMORY']['ENTRIES']
    known_rows = rows_by_id(new['ROWS'])
    for sid, entry in delta['ADD_ENTRIES'].items():
        if sid in entries or sid in known_rows or entry.get('ID') != sid:
            raise ContractError('delta would rewrite or collide with existing signature: ' + sid)
        entries[sid] = copy.deepcopy(entry)
    new['ROWS'].extend(copy.deepcopy(delta['ADD_ROWS']))
    known_attempts = {a['ATTEMPT_ID'] for a in new['ATTEMPTS']}
    for a in delta['ATTEMPTS']:
        if a['ATTEMPT_ID'] in known_attempts:
            raise ContractError('duplicate attempt id: ' + a['ATTEMPT_ID'])
        known_attempts.add(a['ATTEMPT_ID'])
        new['ATTEMPTS'].append(copy.deepcopy(a))
    meta = delta['MEMORY_METADATA']
    for group, ids in meta['COVERAGE'].items():
        if group in new['MEMORY']['COVERAGE']:
            raise ContractError('coverage group already exists: ' + group)
        new['MEMORY']['COVERAGE'][group] = list(ids)
    for key in ('STATUS', 'DATE'):
        if meta.get(key) is not None:
            new['MEMORY'][key] = meta[key]
    return new


def _apply_market_test_result(state, delta):
    """Append result records only. Entries, rows and attempts must stay untouched."""
    if delta.get('ADD_ENTRIES') != {} or delta.get('ADD_ROWS') != [] or delta.get('ATTEMPTS') != []:
        raise ContractError('MARKET_TEST_RESULT may not add entries, rows or attempts')
    results = delta.get('ADD_MARKET_TEST_RESULTS')
    if not isinstance(results, dict) or len(results) != 1:
        raise ContractError('MARKET_TEST_RESULT binds exactly one test family')
    new = copy.deepcopy(state)
    memory = new['MEMORY']
    known = memory.setdefault(MARKET_TEST_RESULTS_KEY, {})
    attempts = {a['ATTEMPT_ID']: a for a in new['ATTEMPTS']}
    for tf, record in results.items():
        if tf in known or record.get('TEST_FAMILY_ID') != tf:
            raise ContractError('test family already attached or mis-keyed: ' + str(tf))
        sid = record.get('SIGNATURE_ID')
        if sid not in memory['ENTRIES']:
            raise ContractError('market test result for unknown signature: ' + str(sid))
        attempt = attempts.get(record.get('HYPOTHESIS_ID'))
        if attempt is None or attempt.get('SIGNATURE_ID') != sid:
            raise ContractError('hypothesis is not the attempt that generated signature ' + str(sid))
        known[tf] = copy.deepcopy(record)
    return new


# ----------------------------------------------------------------------------- chain reading and verification

def store_dir(root):
    return Path(root) / STORE


def event_path(root, seq, ehash):
    return store_dir(root) / 'events' / '{:06d}-{}.json'.format(seq, ehash)


def delta_path(root, dsha):
    return store_dir(root) / 'deltas' / (dsha + '.json')


def snapshot_dir(root, seq, ehash):
    return store_dir(root) / 'snapshots' / '{:06d}-{}'.format(seq, ehash[:16])


def read_head(root):
    path = Path(root) / HEAD_FILE
    if not path.exists():
        return None
    head, _ = read_canonical(path)
    if set(head) != {'SCHEMA_VERSION', 'HEAD_EVENT_HASH', 'SEQUENCE'} or head['SCHEMA_VERSION'] != SCHEMA_VERSION:
        raise ContractError('memory HEAD shape')
    return head


def load_event(root, seq, ehash):
    ev, _ = read_canonical(event_path(root, seq, ehash))
    if tuple(sorted(ev)) != tuple(sorted(EVENT_FIELDS)) or ev['SCHEMA_VERSION'] != SCHEMA_VERSION:
        raise ContractError('event shape at sequence ' + str(seq))
    if ev['EVENT_HASH'] != ehash or event_hash(ev) != ehash or ev['SEQUENCE'] != seq:
        raise ContractError('event hash mismatch at sequence ' + str(seq))
    return ev


def load_delta(root, dsha):
    path = delta_path(root, dsha)
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise ContractError('memory delta missing: ' + dsha) from e
    if sha256_bytes(raw) != dsha:
        raise ContractError('delta digest mismatch: ' + dsha)
    obj, _ = read_canonical(path)
    return obj


def chain(root, head=None):
    """Events from genesis to head, following PREVIOUS_EVENT_HASH links backwards."""
    head = head if head is not None else read_head(root)
    if head is None:
        raise ContractError('memory chain has no HEAD')
    out = []
    seq, ehash = head['SEQUENCE'], head['HEAD_EVENT_HASH']
    while True:
        ev = load_event(root, seq, ehash)
        out.append(ev)
        if seq == 0:
            if ev['PREVIOUS_EVENT_HASH'] != GENESIS or ev['EVENT_TYPE'] != 'LEGACY_BOOTSTRAP':
                raise ContractError('chain does not start at LEGACY_BOOTSTRAP')
            break
        seq, ehash = seq - 1, ev['PREVIOUS_EVENT_HASH']
    return list(reversed(out))


def replay(root, design, events):
    """Rebuild FULL state and projections from bootstrap + deltas only; check every event's digests."""
    state = None
    per_event = []
    campaigns = set()
    for ev in events:
        if ev['EVENT_TYPE'] not in EVENT_TYPES:
            raise ContractError('unsupported event type: ' + ev['EVENT_TYPE'])
        if ev['CAMPAIGN_ID'] in campaigns:
            raise ContractError('campaign finalized twice in chain: ' + ev['CAMPAIGN_ID'])
        campaigns.add(ev['CAMPAIGN_ID'])
        delta = load_delta(root, ev['MEMORY_DELTA_SHA256'])
        if (delta.get('CAMPAIGN_ID') != ev['CAMPAIGN_ID'] or delta.get('SOURCE_SHA256') != ev['SOURCE_SHA256']
                or delta.get('KIND') != ev['EVENT_TYPE']):
            raise ContractError('delta does not match its event at sequence ' + str(ev['SEQUENCE']))
        state = genesis_state(delta) if ev['SEQUENCE'] == 0 else apply_delta(state, delta)
        v = views(state, design)
        if view_digests(v) != {k: ev[k] for k in view_digests(v)}:
            raise ContractError('replayed state does not match event digests at sequence ' + str(ev['SEQUENCE']))
        per_event.append(v)
    return state, per_event


def check_snapshot(root, ev, v):
    sdir = snapshot_dir(root, ev['SEQUENCE'], ev['EVENT_HASH'])
    manifest, _ = read_canonical(sdir / 'MANIFEST.json')
    if manifest != snapshot_manifest(ev, v):
        raise ContractError('snapshot manifest mismatch at sequence ' + str(ev['SEQUENCE']))
    for key, name in SNAPSHOT_FILES.items():
        obj, raw = read_canonical(sdir / name)
        if obj != v[key]:
            raise ContractError('snapshot file differs from replayed state: ' + name)
    return sdir


def snapshot_manifest(ev, v):
    return {'SCHEMA_VERSION': SCHEMA_VERSION, 'EVENT_HASH': ev['EVENT_HASH'], 'SEQUENCE': ev['SEQUENCE'],
            'FILES': {name: sha256_bytes(pretty(v[key])) for key, name in SNAPSHOT_FILES.items()}}


def published(root, design, all_snapshots=False):
    """The verified current memory: chain hashes + links + deltas + replay + head snapshot."""
    events = chain(root)
    _, per_event = replay(root, design, events)
    checked = range(len(events)) if all_snapshots else [len(events) - 1]
    for i in checked:
        check_snapshot(root, events[i], per_event[i])
    return {'HEAD': events[-1], 'EVENTS': events, 'VIEWS': per_event[-1]}


def published_at(root, design, event_ref):
    """A historical verified memory version (by EVENT_HASH, sequence number, or 'LEGACY_BOOTSTRAP')."""
    events = chain(root)
    if event_ref == 'LEGACY_BOOTSTRAP':
        idx = 0
    elif isinstance(event_ref, int):
        idx = event_ref
    else:
        matches = [i for i, e in enumerate(events) if e['EVENT_HASH'] == event_ref]
        if len(matches) != 1:
            raise ContractError('unknown memory event: ' + str(event_ref))
        idx = matches[0]
    if not 0 <= idx < len(events):
        raise ContractError('memory event out of range')
    _, per_event = replay(root, design, events[:idx + 1])
    check_snapshot(root, events[idx], per_event[idx])
    return {'HEAD': events[idx], 'EVENTS': events[:idx + 1], 'VIEWS': per_event[idx]}


def mirror_bytes(v):
    return {key: pretty(v[key]) for key in MIRRORS}


def mirrors_current(root, v):
    return [key for key, rel in MIRRORS.items()
            if not (Path(root) / rel).exists() or (Path(root) / rel).read_bytes() != pretty(v[key])]


# ----------------------------------------------------------------------------- atomic writes and publish

def _fsync_dir(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.tmp')
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def place_immutable(src, dst):
    """Move a staged file into its content-addressed location. Identical bytes already
    there (a retry after a crash) are accepted; different bytes are a hard failure."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    if dst.exists():
        if dst.read_bytes() != data:
            raise ContractError('immutable memory file already exists with different bytes: ' + str(dst))
        src.unlink()
        return
    os.replace(src, dst)
    _fsync_dir(dst.parent)


@contextlib.contextmanager
def exclusive_lock(root):
    import fcntl
    sdir = store_dir(root)
    sdir.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(sdir / '.finalize.lock'), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            raise ContractError('another memory finalization holds the lock') from e
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def build_event(event_type, seq, campaign_id, identity, source_sha, previous, delta_sha, rules_digest, v, summary):
    ev = {'SCHEMA_VERSION': SCHEMA_VERSION, 'EVENT_TYPE': event_type, 'SEQUENCE': seq, 'CAMPAIGN_ID': campaign_id,
          'SOURCE_ARTIFACT_IDENTITY': identity, 'SOURCE_SHA256': source_sha, 'PREVIOUS_EVENT_HASH': previous,
          'MEMORY_DELTA_SHA256': delta_sha, 'RULES_DIGEST': rules_digest, 'FINALIZER_CODE_DIGEST': code_digest(),
          **view_digests(v), 'SUMMARY': summary}
    ev['EVENT_HASH'] = event_hash(ev)
    return ev


def publish(root, design, delta, event, v, fault=None):
    """Stage -> validate -> place immutable files -> ONE atomic HEAD switch -> derived caches.

    `fault` is a test hook: fault(point) may raise to simulate a crash at that point.
    Before 'HEAD_SWITCH' nothing authoritative has changed."""
    fault = fault or (lambda _p: None)
    root = Path(root)
    sdir = store_dir(root)
    staging = sdir / '.staging' / event['EVENT_HASH']
    if staging.exists():
        for p in sorted(staging.rglob('*'), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
    (staging / 'snapshot').mkdir(parents=True)
    delta_bytes = pretty(delta)
    (staging / 'delta.json').write_bytes(delta_bytes)
    (staging / 'event.json').write_bytes(pretty(event))
    for key, name in SNAPSHOT_FILES.items():
        (staging / 'snapshot' / name).write_bytes(pretty(v[key]))
    (staging / 'snapshot' / 'MANIFEST.json').write_bytes(pretty(snapshot_manifest(event, v)))
    fault('BEFORE_STAGING_VALIDATION')
    # Validate staged bytes, not in-memory objects.
    staged_delta, _ = read_canonical(staging / 'delta.json')
    staged_event, _ = read_canonical(staging / 'event.json')
    if sha256_bytes(delta_bytes) != event['MEMORY_DELTA_SHA256'] or staged_delta != delta or staged_event != event:
        raise ContractError('staged delta/event mismatch')
    if event_hash(staged_event) != staged_event['EVENT_HASH']:
        raise ContractError('staged event hash mismatch')
    for key, name in SNAPSHOT_FILES.items():
        obj, _ = read_canonical(staging / 'snapshot' / name)
        if obj != v[key]:
            raise ContractError('staged snapshot mismatch: ' + name)
    fault('AFTER_STAGING_BEFORE_PUBLISH')
    place_immutable(staging / 'delta.json', delta_path(root, event['MEMORY_DELTA_SHA256']))
    place_immutable(staging / 'event.json', event_path(root, event['SEQUENCE'], event['EVENT_HASH']))
    target = snapshot_dir(root, event['SEQUENCE'], event['EVENT_HASH'])
    for name in list(SNAPSHOT_FILES.values()) + ['MANIFEST.json']:
        place_immutable(staging / 'snapshot' / name, target / name)
    # Full verification of the chain as it WILL be published, before the switch.
    new_head = {'SCHEMA_VERSION': SCHEMA_VERSION, 'HEAD_EVENT_HASH': event['EVENT_HASH'], 'SEQUENCE': event['SEQUENCE']}
    events = chain(root, new_head)
    _, per_event = replay(root, design, events)
    check_snapshot(root, events[-1], per_event[-1])
    fault('BEFORE_HEAD_SWITCH')
    atomic_write(root / HEAD_FILE, pretty(new_head))           # <- the single publish point
    fault('AFTER_HEAD_BEFORE_DERIVED_CACHES')
    write_derived_caches(root, per_event[-1])
    for p in sorted(staging.rglob('*'), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    staging.rmdir() if staging.exists() else None
    return new_head


# ----------------------------------------------------------------------------- derived caches (mirrors + pins)

PINS = 'docs/research/GENERATOR_V0_CONTEXT_PINS.json'
PINNED_STATIC = ('docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json', 'docs/research/HETEROGENEOUS_FAMILY_ROTATION_V3.json')


def pins_expected(root):
    root = Path(root)
    paths = list(PINNED_STATIC) + list(MIRRORS.values()) + [HEAD_FILE]
    return {p: sha256_bytes((root / p).read_bytes()) for p in sorted(paths)}


def write_derived_caches(root, v):
    """Mirrors are byte copies of the head snapshot; pins are a runtime drift cache.
    Neither is historical authority: that is the event chain."""
    root = Path(root)
    for key, data in mirror_bytes(v).items():
        atomic_write(root / MIRRORS[key], data)
    atomic_write(root / PINS, pretty(pins_expected(root)))
