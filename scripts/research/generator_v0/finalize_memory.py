"""Operator CLI for the Generator V0 memory finalizer. Offline; never contacts a provider.

  python -m scripts.research.generator_v0.finalize_memory --verify
  python -m scripts.research.generator_v0.finalize_memory --rebuild
  python -m scripts.research.generator_v0.finalize_memory --dry-run --campaign-id GV0R01 --run-journal path/run.sqlite
  python -m scripts.research.generator_v0.finalize_memory --apply   --campaign-id GV0R01 --run-journal path/run.sqlite
  python -m scripts.research.generator_v0.finalize_memory --apply   --campaign-id GV0CAL --calibration-export docs/research/GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.json
  python -m scripts.research.generator_v0.finalize_memory --dry-run --market-test-result docs/research/GV0R01_C013_MARKET_TEST_RESULT.json
  python -m scripts.research.generator_v0.finalize_memory --apply   --market-test-result docs/research/GV0R01_C013_MARKET_TEST_RESULT.json

--market-test-result attaches one executed, ledger-closed scientific test to FULL memory
(MARKET_TEST_RESULT event). Its unit id is derived from TEST_FAMILY_ID; --campaign-id is
not used. The blind map, governance authority and attempt records never change.

--bootstrap-from-commit is a one-time migration command: it creates the LEGACY_BOOTSTRAP
event from the pre-GV0CAL memory at a Git commit and refuses once a chain exists. After
bootstrap, verification never consults Git.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from .context import ROOT, ContractError, DESIGN, read
from . import memory_finalizer as fin
from . import memory_store as store

LEGACY_MEMORY_PATH = 'docs/research/MECHANISM_MEMORY_V0.json'
LEGACY_AUTHORITY_PATH = 'docs/research/GOVERNANCE_REGION_AUTHORITY_V0.json'


def _git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def bootstrap_from_commit(root, commit):
    mem_raw = _git(root, 'show', commit + ':' + LEGACY_MEMORY_PATH)
    auth_raw = _git(root, 'show', commit + ':' + LEGACY_AUTHORITY_PATH)
    memory, authority = json.loads(mem_raw), json.loads(auth_raw)
    header = store.design_governance_header(read(Path(root) / DESIGN))
    if {k: v for k, v in authority.items() if k != 'ROWS'} != header:
        raise ContractError('legacy authority header differs from the frozen design rules')
    provenance = {'KIND': 'LEGACY_MEMORY_AT_COMMIT', 'COMMIT': _git(root, 'rev-parse', commit).decode().strip(),
                  'MEMORY_PATH': LEGACY_MEMORY_PATH, 'MEMORY_SHA256': hashlib.sha256(mem_raw).hexdigest(),
                  'MEMORY_GIT_BLOB': _git(root, 'rev-parse', commit + ':' + LEGACY_MEMORY_PATH).decode().strip(),
                  'AUTHORITY_PATH': LEGACY_AUTHORITY_PATH, 'AUTHORITY_SHA256': hashlib.sha256(auth_raw).hexdigest(),
                  'AUTHORITY_GIT_BLOB': _git(root, 'rev-parse', commit + ':' + LEGACY_AUTHORITY_PATH).decode().strip(),
                  'NOTE': 'Pre-GV0CAL mechanism memory and governance rows, carried verbatim. No scientific reinterpretation.'}
    ev = fin.bootstrap(root, memory, authority['ROWS'], provenance)
    return {'STATUS': 'BOOTSTRAPPED', 'EVENT_HASH': ev['EVENT_HASH'], 'MEMORY_ENTRY_COUNT': len(memory['ENTRIES']),
            'GOVERNANCE_ROW_COUNT': len(authority['ROWS'])}


def main(argv=None):
    p = argparse.ArgumentParser(description='Generator V0 memory finalizer (offline)')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--verify', action='store_true')
    mode.add_argument('--rebuild', action='store_true')
    mode.add_argument('--bootstrap-from-commit')
    p.add_argument('--campaign-id')
    src = p.add_mutually_exclusive_group()
    src.add_argument('--run-journal', type=Path)
    src.add_argument('--calibration-export', type=Path)
    src.add_argument('--market-test-result', type=Path)
    p.add_argument('--scientific-test-ledger', type=Path, default=Path(fin.SCIENTIFIC_TEST_LEDGER))
    p.add_argument('--root', type=Path, default=ROOT)
    a = p.parse_args(argv)
    try:
        if a.verify:
            out = fin.verify(a.root)
        elif a.rebuild:
            out = fin.rebuild(a.root)
        elif a.bootstrap_from_commit:
            out = bootstrap_from_commit(a.root, a.bootstrap_from_commit)
        elif a.market_test_result:
            if a.campaign_id:
                p.error('--market-test-result derives its unit from TEST_FAMILY_ID; do not pass --campaign-id')
            rel = lambda x: str(x.resolve().relative_to(a.root.resolve())) if x.is_absolute() else str(x)
            source = fin.source_from_market_test_result(a.root, rel(a.market_test_result), rel(a.scientific_test_ledger))
            out = fin.finalize_market_test_result(a.root, source, apply=a.apply)
        else:
            if not a.campaign_id or not (a.run_journal or a.calibration_export):
                p.error('--dry-run/--apply need --campaign-id and one source')
            design = read(a.root / DESIGN)
            source = (fin.source_from_run_journal(a.run_journal, a.campaign_id) if a.run_journal
                      else fin.source_from_calibration_export(a.calibration_export, a.campaign_id, design))
            out = fin.finalize(a.root, source, apply=a.apply)
    except ContractError as e:
        print(json.dumps({'STATUS': 'FAILED_CLOSED', 'ERROR': str(e)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out.get('STATUS') != 'CHAIN_VERIFIED_DERIVED_CACHE_DRIFT' else 3


if __name__ == '__main__':
    sys.exit(main())
