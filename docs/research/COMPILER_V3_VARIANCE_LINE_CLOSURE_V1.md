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

## 5. Latent rerun path found while closing (recorded, code untouched)

`scripts/research/compiler_v3_variance_floor/engine.py::official_run` guards the one-shot rule by refusing when `docs/research/COMPILER_V3_VARIANCE_FLOOR_VALIDATION_RESULT.json` exists. The official result was committed as `…_RESULT_V1.json`, and the run authorization exists. So the guard no longer stops a second run.

The suite's `test_official_run_refuses_without_authorized_binding` was written before the authorization existed. On the merged tree it **started the official run** in this session's validation. The process was stopped within minutes, before it wrote anything; the tree was verified clean.

**Repair, tests only.** The test now points the authorization at an absent file. Two pre-run assertions that became false after the run are replaced by post-run checks:
- the authorization binds the binding;
- the V1 result exists;
- in the estimator suite, the committed C-table equals the sealed digest.

`engine.py` and `freeze.py` are digest-bound by the execution binding, so they are **not** edited.

**Rule:** `--official` must never be invoked again for this line. Any future code change to the guard is a new binding, which this closure forbids, so the rule is procedural.

## 6. Operational tombstone (owner, 2026-10-05; replaces the procedural-only rule of §5)

The closed line is now hard-refused at the entry layer. Its frozen code and records are not edited:
- **Registry:** `docs/research/CLOSED_RESEARCH_LINES_V1.json`.
- **Guard:** `scripts/research/closed_lines.py`, installed from the two packages' `__init__.py`. No execution binding covers those two files.

**Programmatic calls refuse before any original code runs:**
- `compiler_v3_variance_floor.engine.official_run`;
- `compiler_v3_estimator_calibration.engine.run_cal` / `run_eval` with `official=True`;
- `cal_official.execute`, `eval_official.execute` and `eval_resume.execute`.

The refusal exception subclasses each module's own refusal type.

**CLI calls refuse before the module runs:**
- `python -m …variance_floor.engine --official`;
- `…estimator_calibration.run --official`;
- every `cal_official` step;
- every `eval_official` / `eval_resume` step except `verify-binding` / `verify-authorization`.

**What stays verifiable:** the bound files keep their recorded digests (`verify_execution_binding`, `executor_digest`), and the historical artifacts stay valid. Tests are in `tests/research/test_closed_research_lines.py`. Each refusal test replaces the original behind the guard with a tripwire, so a broken guard fails the test instead of running anything.

**Override:** only `docs/research/COMPILER_V3_VARIANCE_LINE_REOPEN_AUTHORIZATION_V1.json` lifts the refusal. It must carry `LINE_ID`, `OWNER_AUTHORIZED: true`, the entry points it opens and an existing owner decision record. It does not exist, and creating it is a new owner decision.
