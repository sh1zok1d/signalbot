# E1-RUN-001 — exposed fixed-prereg execution: classification and provenance (before execution)

**Status:** `AUTHORIZED (owner, 2026-10-03) / CLASSIFIED_BEFORE_EXECUTION / NOT_EXECUTED — BLOCKED_ENVIRONMENT`
**Recorded:** 2026-10-03, before any E1 outcome exists or is read.
**Machine-readable twin:** `E1_RUN_001_EXPOSED_FIXED_PREREG_EXECUTION_V1.json`

This is an append-only governance record. It changes nothing in the E1 preregistration, in `docs/e1/`, in the evaluator or in any frozen rule. It fixes, before execution, how the result will be read, and it records why the run could not happen in this session.

## 1. Evidence class (fixed before execution)

```
E1_RUN_001_EVIDENCE_CLASS = EXPOSED_FIXED_PREREG_SUPPORTING_EVIDENCE
PRISTINE_CONFIRMATION = NO
INDEPENDENT_REPLICATION = NO
PREREG_FROZEN_BEFORE_P4 = YES
OUTCOME_SURFACE_PREVIOUSLY_EXPOSED = YES (P4; erratum Amendment 1)
```

**Interpretation, fixed in advance (owner instruction, 2026-10-03):**

| Class | Reading |
|---|---|
| PASS | Supporting evidence only. The mechanism is not promoted to CONFIRMED on E1 alone; confirmation needs a new independent, time-disjoint or prospective surface. |
| FAIL | Real negative evidence against the frozen hypothesis. No rescue on this surface, no parameter change, no neighbouring threshold. |
| INCONCLUSIVE | Not optimized. It may be used only to plan a future independent test, and is counted as neither PASS nor FAIL. |

**Mapping from the frozen verdict vocabulary.** The vocabulary is fixed in `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md` §11 and applied per family (TREND_PULLBACK, COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT). The mechanical verdict is always reported in its own words.

| Frozen verdict | Class |
|---|---|
| `SURVIVES` | PASS for that FULL family |
| `KILL` | FAIL for that family |
| `DEMOTE_TO_BASELINE` | FAIL for the family's added context/flow machinery. The price-structure baseline is only descriptive. |
| `INCONCLUSIVE_SAMPLE` | INCONCLUSIVE |
| `SIMPLIFY` | PASS only for the named simpler preregistered variant, and FAIL for the components it removes. **This row needs owner confirmation before execution**, because the owner's three classes do not name it. |

The global Level-0 rule (§12) applies unchanged.

**Context recorded before execution.**
- The three Stage-5 formulations were marked `RETIRED_CURRENT_FORMULATION` on 2026-08-28 (`docs/RESEARCH_LEDGER.md`). Executing E1 does not revive them.
- The result is evidence about those frozen formulations only.
- E1 has no single primary p-value. The evaluator reports per-family, per-horizon distributions with UTC-day block-bootstrap intervals, and §10 states: "no single p-value threshold decides E1".

## 2. Provenance gate — PASS

| Check | Evidence |
|---|---|
| A. Hypothesis before P4 | Preregistration `1e33880` (2026-08-25T17:02:09Z) is 34 days before P4 (`as_of 2026-09-29T15:03:00Z`; P4 record commits `5aa0ae5`, `b0868f6`, 2026-09-29T16:38:54Z). |
| B. Elements frozen before P4 | Primary hypothesis and families: prereg `1e33880`, final form `adc69ca` (2026-08-25T19:33:04Z). The additions after `1e33880` are append-only split records made before outcomes (§11.1–11.2). |
| | Grid and split: `76661b6`, `3c96c8c`; holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)`. |
| | Controls: `c401758`. Ablations: `b9588bf`. Ablation reporting: `067f864`. |
| | Final reporting, delay, friction, bootstrap and verdict logic: `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`, `09648f5`. |
| | Coverage gate: `3fe16c8`, `f3a6019` (strengthened timestamp-only preflight). |
| | Evaluator and one-shot rule: `f093fc3`, freeze record `a9c3833` (2026-08-25T21:34:07Z). |
| C. No change after P4 | No commit after 2026-09-29T15:03Z touches any of the following: `docs/E1_DETECTOR_SEPARATION_PREREG.md`, `docs/e1/`, the evaluator, `scripts/research/v2_e1_holdout_outcome_coverage_preflight.py`, `scripts/research/v2_e1_holdout_ablation_inventory_vps.py`, or any `analytics/` or `scripts/research/v2_e1_*` module the evaluator imports. |
| | Of the 72 repository modules the evaluator reaches, only seven changed after its freeze: `storage/db.py`, `beta/access.py`, `beta/config.py`, `beta/models.py`, `beta/oi_asof.py`, `beta/state_tape.py`, `storage/beta_v0_store.py`. |
| | `storage/db.py` changed once, on 2026-09-25 (before P4), and only by adding two methods. Those methods import the beta modules lazily, and no E1 script calls them. |
| | **CONTRACT_CHANGED_AFTER_P4 = NO** |
| D. P4 not used for any choice | Every threshold, horizon, variant, sample, direction and stopping rule was frozen by 2026-08-26, 34 days before P4 existed. |
| E. Evaluator not run before | No result artifact exists in the repository, and every E1 record states the holdout outcomes unopened. The one-shot `.OPENED` marker lives on the VPS and cannot be inspected from here. The evaluator refuses to start if that marker or the output artifact exists (freeze record, Preconditions). |
| F. Sealed artifacts not opened | No sealed E1 result artifact exists in the repository. Repository level only; VPS state is checked by the evaluator's own preconditions. |

```
E1_PREREG_COMMIT = 1e33880 (final frozen form adc69ca)
E1_PREREG_TIMESTAMP = 2026-08-25T17:02:09Z (final form 2026-08-25T19:33:04Z)
E1_PREREG_SHA256 = 3c12e4da94fa11bd3f95c87f3f942efb2fecc680cc806333b78189dc740b894b (at 1e33880)
                   8353e74566104cae3caaccd21fff7a349f2ec6a94e7e2184514891884cb4a740 (final form = current file)
P4_EXPOSURE_RECORD_COMMIT = 5aa0ae5 (summary b0868f6)
P4_EXPOSURE_TIMESTAMP = 2026-09-29T15:03:00Z
CONTRACT_CHANGED_AFTER_P4 = NO
PROVENANCE_GATE = PASS
```

## 3. Execution identity

| Item | Value |
|---|---|
| Runner | `scripts/research/v2_e1_final_holdout_evaluator.py` |
| Runner SHA-256 | `e96d1b53bd60116ef600afbb50f43e022a5fc927f45195e5a79a44153722667f`, identical at `f093fc3`, at the freeze record `a9c3833` and now |
| Preflight | `scripts/research/v2_e1_holdout_outcome_coverage_preflight.py`, last changed `8bfe908` (2026-08-25T21:30:25Z) |
| Frozen dataset | Signalbot live archive (`source = 'live'`), BTCUSDT perpetual, the single `calculation_version` / `feature_schema_version` identity of the frozen inventory |
| Frozen grid | holdout 5m decision grid `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`; FULL populations `TP=105`, `CB=17`, `FB=19` |
| Frozen spec | E1-RUN-001: prereg `adc69ca` + `E1_RUN_001_PRE_HOLDOUT_FREEZE.md` (`09648f5`) + evaluator freeze `a9c3833` |
| Input artifacts | the outcome-free `holdout_ablation_inventory.json` and a strengthened preflight artifact with `ready_for_single_holdout_outcome_open = true`. Both live in `artifacts/` on the VPS (not tracked in git). |

## 4. Execution status — NOT_EXECUTED (BLOCKED_ENVIRONMENT)

This session runs in a cloud container. That rules out execution here:
- No database DSN for the Signalbot live archive is available. The only local PostgreSQL is an empty test instance.
- The VPS `artifacts/` directory (inventory and preflight) is absent; it is not tracked in git.
- There is no SSH access to the VPS.

The evaluator was therefore not started, no holdout row was read, no outcome exists, and the one-shot marker was not consumed. Nothing was repaired, and no alternative was run.

**Owner-run procedure (frozen commands only).** The owner runs this on the VPS checkout of this branch, inside the repository root.

1. **Verify identity.**
   - `sha256sum scripts/research/v2_e1_final_holdout_evaluator.py` must print `e96d1b53…667f`.
   - `git status` must be clean.
2. **Derive the DSN without printing it**, as in `docs/E1_VPS_RUNBOOK.md`:

   `DSN="$(python -c 'from common.config import _build_postgres_dsn; print(_build_postgres_dsn())')"`
3. **Rerun the strengthened timestamp-only preflight.** It reads timestamps only:

   ```
   python scripts/research/v2_e1_holdout_outcome_coverage_preflight.py --dsn "$DSN" --input artifacts/e1/holdout_ablation_inventory.json > artifacts/e1/holdout_outcome_coverage_preflight.json
   ```

   Exit code `0` means READY. Exit code `2` means not ready: stop there and do not open.
4. **Run the single evaluator, once.** Use the `calculation_version` recorded in the inventory artifact:

   ```
   python scripts/research/v2_e1_final_holdout_evaluator.py --dsn "$DSN" --input artifacts/e1/holdout_ablation_inventory.json --preflight artifacts/e1/holdout_outcome_coverage_preflight.json --output artifacts/e1/final_holdout_result.json --calculation-version '<from inventory>'
   ```
5. **If anything fails after the `.OPENED` marker is reserved, it is a holdout-open incident.** Report it and do not rerun (freeze record).
6. **Commit the result artifact unchanged, then apply §1:**
   - the immutable `final_holdout_result.json`, plus its SHA-256;
   - each family verdict, applied with the frozen §11 logic;
   - the class from §1;
   - the atlas update for unit `E1-RUN-001`: `execution = COMPLETED`, `surface_pristine = NO`, `prior_exposure = P4`, the evidence class, and the mechanical verdict;
   - an atlas event.
