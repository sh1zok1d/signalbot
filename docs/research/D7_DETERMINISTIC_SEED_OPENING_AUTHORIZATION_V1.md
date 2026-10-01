# D7 deterministic-seed opening authorization

Mechanical review after the seed-source amendment commit was visible on GitHub, and before any protected target read.

Amendment commit `b603f55d7b12492bf813abac1537aa21f85932e4`, tree `094f8123a5bf629a6a4ec7ed2991c6b6f1dbe605`, branch `cursor/d7-deterministic-seed-amendment-v1-c58d`. GitHub's API returned HTTP 200 for that commit at `2026-10-01T08:46:42Z`. Commit statuses were empty.

Changed files in that commit:

- `docs/DOCUMENTATION_INDEX.md`
- `docs/RESEARCH_LEDGER.md`
- `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.md`
- `docs/research/D7_CONFIRMATORY_SEED_SOURCE_AMENDMENT_V1.json`
- `docs/research/D7_CONFIRMATORY_SEED_SOURCE_AMENDMENT_V1.md`
- `scripts/research/d7_confirmatory_target_opening_v1.py`
- `scripts/research/d7_deterministic_fixed_seed_v1.py`
- `tests/research/test_d7_deterministic_fixed_seed_v1.py`

The canonical BitMEX gzip and the frozen statistical modules are not in that list. No primary result file exists.

```
SEED_SOURCE_AMENDMENT_COMMITTED = true
TARGET_WAS_UNOPENED_AT_AMENDMENT_COMMIT = true
CONFIRMATORY_SEED_DIGEST = 5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e
STATISTICAL_PROCEDURE_CHANGED = false
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
```

Focused tests `tests/research/test_d7_deterministic_fixed_seed_v1.py` and `tests/research/test_d7_nist_beacon_verifier_v1.py`: 21 passed. The verifier blob remains `bed8a2aa33599b7ce4c0915eb410ad7413747b1d`.

```
D7_DETERMINISTIC_SEED_OPENING_AUTHORIZED
```

This review does not open the target, generate the confirmatory bootstrap stream, or compute theta.
