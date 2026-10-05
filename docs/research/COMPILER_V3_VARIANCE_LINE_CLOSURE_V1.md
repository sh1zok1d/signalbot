# Compiler V3 variance / estimator line — closure record V1

**Status:** `CLOSED (owner decision, 2026-10-05) / APPEND-ONLY / NO RESULT CHANGED`
**Successor model:** `EVIDENCE_AND_CLAIMS_DECISION_V1.md`

## 1. Decision

The owner closed the compiler V3 variance research line on 2026-10-05. It consisted of the variance-floor gate, the variance-model redesign and the exposed-variance estimator calibration.

- **No Official Run 2**, no new floor, model, estimator, grid, amendment, binding or authorization, and no "repair" of either official result.
- **The two official results stand exactly as recorded.** Nothing in them is recomputed, rescored or reinterpreted.
- **Why it closed.** At the sample sizes this project actually has, the line tried to guarantee two things in advance, before any outcome:
  - near-absolute coverage safety (a 99 % upper bound with a miss target of 1 %);
  - practical utility (the bound within 1.5× of the truth for at least 80 % of cases).

  Under the frozen requirements those two cannot hold together. This is a **negative methodological result**. It is not evidence that any market structure is absent, and it rescores no market unit.

## 2. What the line established

| Unit | Official result | What it says |
|---|---|---|
| Variance-floor validation (`COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md`, Official Run 1, 2026-10-04) | `VARIANCE_MODEL_REDESIGN_REQUIRED` | Floors 0.60 / 0.75 fail SAFETY at `k = 1`; 1.00 fails UTILITY at `k = 0.5`; no floor selected. |
| Redesign (`COMPILER_V3_VARIANCE_MODEL_REDESIGN_DESIGN_V1.md`, design only) | `NEXT_VALIDATION_POSSIBLE = NO` (`REDESIGN_BLOCKED_REQUIREMENTS_JOINTLY_UNSATISFIABLE`) | Identification theorem: two frozen cells hand the compiler identical inputs and require opposite verdicts, so no function of compile-time inputs satisfies both bars. |
| Exposed-variance estimator calibration (`COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_SPEC_V1.md`, amendments V1–V4, Official Run 1, 2026-10-05) | `ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT` | Every required class (TWO_SAMPLE, PAIRED_UNITS, CLUSTERED, RARE_EVENT) is `CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT`; no candidate A/B/C is eligible anywhere; reference D never misses coverage and never passes utility. |

**The arithmetic behind the estimator result was recorded in its own spec before the run** (§6, "preregistered analytic expectation"). Under ideal independent Gaussian data with the exact chi-square bound:
- `P(U ≤ 1.5·VAR_TRUE)` is about 0.35 at 49 df, 0.68 at 99 df and 0.96 at 199 df;
- utility needed the lower confidence bound of that probability to be at least 0.80.

The declared realistic ranges (CLUSTERED G ≤ 40, RARE_EVENT n_e ≤ 100) sit below that information, so utility could not pass there for any estimator. Amendment V1 set coverage PASS at `cp_upper ≤ MISS_TARGET = 0.01`, so a bound whose true miss rate equals the target cannot pass. Only an over-conservative bound can, and that bound fails utility.

## 3. What is kept

All artifacts stay in the tree unchanged:
- specs, grids, manifests, amendments, bindings, authorizations, snapshots, completion records, results, aggregations, provenance deviation;
- the code under `scripts/research/compiler_v3_variance_floor/` and `scripts/research/compiler_v3_estimator_calibration/`;
- their tests.

They are the audit trail. They were merged into this branch from `research/hypothesis-evaluation-contract-v2-draft` at `8909f50` without edits. The checkpoints under gitignored `data/` are not in git, as before.

The lesson worth carrying forward is a sentence, not a gate:

> At ≤ 100 effective units, a design cannot be certified in advance as both 99 %-safe and 1.5×-useful. A design reports its amount of information and its uncertainty instead.

## 4. What changes for routing

- **Nothing may start from this line.** That includes Official Run 2, a calibration rerun, a "variance model validation" unit, compiler V3 implementation of contract V2 draft §5, and ledger schema V2 as a compiler prerequisite.
- **The GV0R02 compiler V0–V2 stay reproducible and untouched.** Their information numbers (MDE, unit counts) may still be computed and reported, but as **amount-of-information fields**, not as a pass/fail gate before a unit may run (`EVIDENCE_AND_CLAIMS_DECISION_V1.md` §3).
- **Contract V2 draft.** `HYPOTHESIS_EVALUATION_CONTRACT_V2_DRAFT.md` is not adopted and will not be adopted as written. Its useful core is carried into `EVIDENCE_AND_CLAIMS_DECISION_V1.md`: tracks, evidence fields separate from decision fields, the rare-event accumulation idea and the exposure ledger. Its certification machinery is dropped: §4 bar-function compilation, §5 compiler V3 requirement, §7 tranche machinery and §8.3a closed registries. The draft file is kept as history with a pointer.
- **Atlas.** The compiler is methodology, not a market unit, so no atlas unit or surface changes.
