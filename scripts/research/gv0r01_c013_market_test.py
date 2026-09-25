"""GV0R01-C013 market test: preflight and guarded one-shot execution.

    python -m scripts.research.gv0r01_c013_market_test preflight
    python -m scripts.research.gv0r01_c013_market_test execute

`preflight` is offline and computes no target. `execute` refuses unless every
preflight check passes, including an owner execution permit bound to the exact
prereg digest, a clean worktree for the scientific paths, restored local panel
bytes that match the frozen object ledger, and an absent result file. The
result is written once with exclusive create.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from scripts.research import gv0r01_c013_market_test_lib as L

REPO = Path(__file__).resolve().parents[2]
PREREG_REL = 'docs/research/GV0R01_C013_MARKET_TEST_PREREG.json'
LEDGER_REL = 'docs/research/SCIENTIFIC_TEST_LEDGER.json'
PERMIT_REL = 'docs/research/GV0R01_C013_MARKET_TEST_EXECUTION_PERMIT.json'
RESULT_REL = 'docs/research/GV0R01_C013_MARKET_TEST_RESULT.json'
DATASET_DOCS_REL = 'docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0'
IMPLEMENTATION_FILES = (
    'scripts/research/gv0r01_c013_market_test_lib.py',
    'scripts/research/gv0r01_c013_market_test.py',
    'scripts/research/discovery_sprint_04/d13_panel.py',
    'scripts/research/discovery_sprint_04/d13_acquire.py',
    'scripts/research/discovery_sprint_04/d13.py',
    'scripts/research/discovery_sprint_04/common.py',
)
SEED_LABEL = b'GV0R01-C013|MARKET_TEST_V1|PERMUTATION_NULL'


class PreflightRefused(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def derived_seed() -> int:
    return int(hashlib.sha256(SEED_LABEL).hexdigest()[:16], 16)


def load_prereg(repo: Path = REPO) -> dict[str, Any]:
    return json.loads((repo / PREREG_REL).read_text(encoding='utf-8'))


def ledger_entry(repo: Path, test_family_id: str) -> dict[str, Any] | None:
    ledger = json.loads((repo / LEDGER_REL).read_text(encoding='utf-8'))
    hits = [e for e in ledger['TESTS'] if e['TEST_FAMILY_ID'] == test_family_id]
    if len(hits) > 1:
        raise PreflightRefused('TEST_FAMILY_ID_NOT_UNIQUE')
    return hits[0] if hits else None


def git_dirty_paths(repo: Path, paths: list[str]) -> list[str] | None:
    try:
        out = subprocess.run(['git', 'status', '--porcelain', '--', *paths], cwd=repo,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [line for line in out.splitlines() if line.strip()]


def preflight(repo: Path = REPO, *, mode: str = 'preflight') -> dict[str, Any]:
    """Every check the one-shot needs. Computes no target and opens no market bytes
    except, in execute mode, the ledger-bound local byte verification."""

    checks: dict[str, Any] = {}
    fail: list[str] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks[name] = {'OK': bool(ok), 'DETAIL': detail}
        if not ok:
            fail.append(name)

    prereg_path = repo / PREREG_REL
    prereg_sha = sha256_file(prereg_path)
    prereg = load_prereg(repo)
    prm = prereg['PARAMS']
    entry = ledger_entry(repo, prm['TEST_FAMILY_ID'])
    check('LEDGER_ENTRY_PRESENT', entry is not None)
    check('PREREG_DIGEST_MATCHES_LEDGER', bool(entry) and entry.get('PREREG_SHA256') == prereg_sha, prereg_sha)
    check('TEST_FAMILY_ID_UNUSED', bool(entry) and entry.get('STATUS') == 'PREREGISTERED_NOT_EXECUTED'
          and entry.get('RESULT_SHA256') is None, entry and entry.get('STATUS'))
    impl = {rel: sha256_file(repo / rel) for rel in IMPLEMENTATION_FILES}
    check('IMPLEMENTATION_DIGESTS_MATCH', impl == prereg['IMPLEMENTATION_FILE_SHA256'], impl)
    check('SEED_FROZEN', int(prm['SEED']) == derived_seed(), prm['SEED'])
    check('PERMUTATIONS_FROZEN', int(prm['PERMUTATIONS']) == 1000, prm['PERMUTATIONS'])
    check('TIME_RANGE_FROZEN', (prm['FIRST_DECISION_DATE'], prm['LAST_DECISION_DATE'], prm['LEGAL_LAST_BAR_DATE'])
          == ('2020-01-06', '2024-12-29', '2024-12-31'))
    check('PROTECTED_EXCLUDED', date.fromisoformat(prm['LEGAL_LAST_BAR_DATE']).year < 2025
          and prereg['PROTECTED_DATA_RULE']['PROTECTED_2025_2026_OPEN_AUTHORIZED'] is False)
    check('NUMPY_VERSION_MATCHES', np.__version__ == prereg['NUMPY_VERSION'], np.__version__)
    check('RESULT_ABSENT', not (repo / RESULT_REL).exists())
    data = prereg['DATASET']
    docs = repo / DATASET_DOCS_REL
    from scripts.research.discovery_sprint_04 import d13_panel
    ledger = d13_panel.load_object_ledger(repo=repo)
    check('FILE_LEDGER_DIGEST_MATCHES', d13_panel.file_ledger_digest(ledger) == data['FILE_LEDGER_DIGEST'])
    for name, rel in (('OBJECT_LEDGER_SHA256', 'object_ledger.json'), ('EXCLUSION_LISTS_SHA256', 'EXCLUSION_LISTS.json'),
                      ('UNIVERSE_IDENTITY_SHA256', 'UNIVERSE_IDENTITY.json')):
        check(name + '_MATCHES', sha256_file(docs / rel) == data[name])
    excl = json.loads((docs / 'EXCLUSION_LISTS.json').read_text(encoding='utf-8'))
    check('EXCLUSION_LIST_DIGEST_MATCHES', excl['EXCLUSION_LIST_DIGEST'] == data['EXCLUSION_LIST_DIGEST'])
    dirty = git_dirty_paths(repo, list(IMPLEMENTATION_FILES) + [PREREG_REL, LEDGER_REL, DATASET_DOCS_REL])
    check('SCIENTIFIC_PATHS_CLEAN', dirty == [], dirty)
    if mode == 'execute':
        permit_path = repo / PERMIT_REL
        permit = json.loads(permit_path.read_text(encoding='utf-8')) if permit_path.exists() else None
        check('EXECUTION_PERMIT_BOUND', bool(permit) and permit.get('PREREG_SHA256') == prereg_sha
              and permit.get('TEST_FAMILY_ID') == prm['TEST_FAMILY_ID'] and permit.get('EXECUTION_AUTHORIZED') is True)
        try:
            v = d13_panel.verify_local_bytes_against_ledger(repo=repo)
            check('LOCAL_BYTES_MATCH_LEDGER', v.get('IDENTITY_OK') is True, v.get('VERIFIED_N'))
        except Exception as e:  # missing or mismatched bytes are a refusal, not a crash
            check('LOCAL_BYTES_MATCH_LEDGER', False, type(e).__name__ + ':' + str(e)[:200])
    return {'MODE': mode, 'OK': not fail, 'FAILURES': fail, 'CHECKS': checks, 'PREREG_SHA256': prereg_sha,
            'TARGETS_COMPUTED': False}


def load_real_panel(repo: Path, *, permit_checked: bool) -> tuple[L.Panel, frozenset[str]]:
    """Ledger-bound OHLCV loader. Refuses unless the execute preflight passed."""

    if not permit_checked:
        raise PreflightRefused('REAL_PANEL_REQUIRES_EXECUTE_PREFLIGHT')
    from scripts.research.discovery_sprint_04 import d13_acquire, d13_panel
    rows: dict[str, dict[int, tuple[float, ...]]] = {}
    raw = repo / d13_panel.RAW_REL
    for key in d13_panel.scientific_file_keys(repo=repo):
        d13_panel.refuse_protected_object(key)
        sym = d13_acquire.OBJECT_RE.match(key).group(1)
        with zipfile.ZipFile(raw / key) as zf:
            text = zf.read(zf.namelist()[0]).decode('utf-8')
        recs = list(csv.reader(io.StringIO(text)))
        if recs and recs[0] and recs[0][0].lower().replace('﻿', '').startswith('open'):
            recs = recs[1:]
        bucket = rows.setdefault(sym, {})
        for rec in recs:
            if len(rec) < 8:
                continue
            open_ms = d13_panel.normalize_open_ms(int(rec[0]))
            vals = tuple(float(rec[i]) for i in (1, 2, 3, 4, 7))
            if open_ms in bucket and bucket[open_ms] != vals:
                raise L.C013IntegrityError(f'CONFLICTING_DUPLICATE_DAY:{sym}:{open_ms}')
            bucket[open_ms] = vals
    excl = json.loads((repo / DATASET_DOCS_REL / 'EXCLUSION_LISTS.json').read_text(encoding='utf-8'))
    return L.build_panel(rows, last_day=date(2024, 12, 31)), frozenset(excl['EXCLUDED_SYMBOLS'])


def execute(repo: Path = REPO) -> dict[str, Any]:
    pf = preflight(repo, mode='execute')
    if not pf['OK']:
        raise PreflightRefused('PREFLIGHT_FAILED:' + ','.join(pf['FAILURES']))
    prereg = load_prereg(repo)
    panel, excluded = load_real_panel(repo, permit_checked=True)
    identity = {'PREREG_SHA256': pf['PREREG_SHA256'], 'IMPLEMENTATION_FILE_SHA256': prereg['IMPLEMENTATION_FILE_SHA256'],
                'DATASET': prereg['DATASET'], 'PREFLIGHT_FAILURES': pf['FAILURES']}
    result = L.run_all(panel, prereg['PARAMS'], excluded=excluded, identity=identity, identity_ok=True)
    with open(repo / RESULT_REL, 'xb') as f:
        f.write(L.canonical_bytes(result))
    return {'RESULT_PATH': RESULT_REL, 'CLASSIFICATION': result['EVALUATION']['CLASSIFICATION']}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='GV0R01-C013 market test (one-shot; permit-gated)')
    ap.add_argument('command', choices=['preflight', 'execute'])
    a = ap.parse_args(argv)
    if a.command == 'preflight':
        out = preflight(REPO)
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0 if out['OK'] else 2
    print(json.dumps(execute(REPO), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
