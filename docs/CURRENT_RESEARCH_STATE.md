## GV0V03L40 C033 V1 feasibility — 2026-10-02

`MEMORY_CAMPAIGN_ID = GV0V03L40`
`SOURCE_RUN_ID = ladder-40-card-v03-r02-derived-critics-v2`
`C033_PLANNING_VALIDATION = PASS`
`GV0R02_SCHEMA = GV0R02_SCHEMA_V1`
`GV0R02_POLICY = GV0R02_POLICY_V1`
`FEASIBILITY_STATUS = FEASIBLE_FOR_PREREGISTRATION`
`C033_NEXT = PREREGISTRATION_DESIGN`
`EXECUTION_AUTHORIZED = false`
`TOTAL_ALL4_EVENTS = 0`
`NOMINAL_N = 1383`
`MARKET_OUTCOMES_OPENED = false`
`PROTECTED_2025_2026_OPENED = false`
`LLM_CALLS = 0`

C033 is the only shortlist card in this planning unit. The primary cell is `SHOCK_SIGMA = 3`, `TAKER_BAND = p1_p99`, `POST_WINDOW_H = 6`. The compiler screen on the thinned eligible-shock sample is feasible. The all-four joint label occurs zero times in 2020–2024. That count is recorded and the design was not repaired after the compile. No preregistration is executed here. C005, C024, C031 and C037 stay blocked. Record: `docs/research/GV0V03L40_C033_V1_FEASIBILITY.md`.

## Beta V0.3 — market briefing and analogue gate — 2026-10-02

`BETA_SURFACE = MARKET_BRIEFING (CHANGE_PRODUCT under the frozen exit criteria)`
`BETA_V0_3_P1 = CONTRACT_RECORDED / NOT_IMPLEMENTED`
`HISTORICAL_ANALOGUE_GATE_V1 = FROZEN_BEFORE_IMPLEMENTATION / NOT_ACTIVE`
`PREDICTIVE_PRODUCT_FROZEN = true, except outcome-aware historical analogue summaries under their gate`
`DETECTOR_RULES_CHANGED = false`
`NEXT_UNIT = BETA_V0_3_P1 implementation (read-model projections first)`

**Why.** Two days of owner use: the 5m events are noise and unactionable, and the 3-push cap is used up by about 11:00. The frozen beta criteria name this `CHANGE PRODUCT`.

**What is new.** The surface becomes a briefing built on rolling 1h / 4h / 24h windows ending at the last closed 5m bucket (`docs/BETA_V0_3_MARKET_BRIEFING.md`):
- `/catchup` and "since your last view";
- a Market State block;
- decomposed significance with venue agreement;
- "I don't know" lines;
- one morning brief and quiet pushes.
  - `/catchup` and push both come from 1h briefing episodes.
  - The legacy 5m detector is evidence in Details only and never a push source.

**Analogues.** "Что было после похожих" may show direction medians only under `docs/BETA_HISTORICAL_ANALOGUE_GATE_V1.md`:
- a matched-control baseline in the same card, N and spread;
- a display floor (30 events / 15 dates) separate from an inferential minimum of at least 30 independent date clusters;
- a mandatory verdict from a frozen, Holm-corrected, date-clustered test;
- a null calibration with at least 1000 pseudo-event replicates, accepted when the Clopper–Pearson upper bound is at most 0.07;
- materiality floors to be set before event outcomes, from controls only;
- live and historical cohorts never pooled, the historical one being a declared Binance proxy through a frozen mapping;
- directional labels never;
- 2025/2026 sealed.

The permission is narrow: historical conditional statistics are allowed; a prediction engine is not.

## Generator V0 — r02 paused; all V03 critics resumable; derived continuation — 2026-10-02

`LADDER40_V03_R02 = PAUSED_UNCERTAIN_CALL / IMMUTABLE_SOURCE_FOR_DERIVED_CONTINUATION`
`OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1 = IMPLEMENTED (offline; no LLM call)`
`DERIVED_RUN = ladder-40-card-v03-r02-derived-critics-v1 (DERIVED_IMPORTED_REVALIDATED)`
`DERIVED_CONTINUATION_LIVE_AUTHORIZED = false`
`SCIENTIFIC_DESIGN_CHANGED = false`
`V02_ROUTING_CHANGED = false`
`MEMORY_FINALIZER = NOT_RUN`
`PROTECTED_2025_2026_OPENED = false`
`MARKET_OUTCOMES_TESTED = false`

This is the current generator routing. It is an infrastructure repair, not a scientific result.

**What r02 was.** The owner-authorized V03 ladder on Message Batches. All four generator rounds completed (USD 2.192768; 30 valid, 10 hard fail). The synchronous feasibility call for C024 then timed out after dispatch with no response id. State `UNCERTAIN`, reservation USD 0.005302. Source charged total USD 3.659239. The source journal is frozen. PR #299 is the durable checkpoint (`bb13d8f26a93713fa6fb956703c5207486b6a570`). A byte-identical copy is `docs/research/generator_v0_ladder40_v03_r02/run.sqlite` (SHA256 `ffa179220d12986520c214f7a1ad1cfecd084848f9de0158fcd43476d9447a37`). C024 was not reconciled.

**The fix.** `OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1`. On the V03 ladder only, feasibility and the selector move from synchronous Chat Completions to background Responses. Model, effort, output cap, prompt and schema stay the same. Every paid V03 role is now resumable. V02 routes are unchanged.

**Continuation.** `ladder-40-card-v03-r02-derived-critics-v1` imports the four generator rounds and none of the critic judgments. Those stay prior attempts. All 30 valid cards are to be reviewed again under the new routing. Starting lineage charge is the full r02 spend, USD 3.659239. Cap remains USD 9.789228, so USD 6.129989 is left. The offline remaining-work bound does not fit: base USD 14.518795, stress USD 29.035834, `FITS_BASE = false`, `FITS_STRESS = false`. The cap was not raised. Live calls are not authorized.

Record: `docs/research/GENERATOR_V0_V03_RESUMABLE_CRITICS_AND_DERIVED_CONTINUATION.{md,json}`.

## Generator V0 — r01 frozen, resumable Anthropic transport — 2026-10-02

`LADDER40_V03_R01 = INFRASTRUCTURE_FAILED_FROZEN`
`ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1 = IMPLEMENTED (offline; no LLM call)`
`SCIENTIFIC_DESIGN_CHANGED = false`
`MEMORY_FINALIZER = NOT_RUN`
`PROTECTED_2025_2026_OPENED = false`
`MARKET_OUTCOMES_TESTED = false`
`LINEAGE_CAP_USD = 12.000000 (r01 + r02 combined)`
`R01_CONSERVATIVE_CHARGE_USD = 2.210772`
`R02_INITIAL_CAP_USD = 9.789228`
`R02_LIVE_EXECUTION_AUTHORIZED = false`
`NEXT_UNIT = LADDER40_V03_R02 (identical V03 design; needs a fresh owner live authorization)`

**What r01 was.**
- The owner-authorized `ladder-40-card` on `GENERATOR_CONTRACT_V03` with a USD 12 cap. Cursor ran it with OpenAI `DIRECT`.
- It stopped on its first call. The synchronous Anthropic Messages POST for `generation:0` held the connection until the 1800 s client timeout.
- The call is `UNCERTAIN`: no message id, a USD 2.210772 reservation, no cards and no shortlist.
- Record: `docs/research/GENERATOR_V0_LADDER40_V03_R01_PAUSE.{md,json}`. Journal snapshot: `docs/research/generator_v0_ladder40_v03_r01/run.sqlite` (SHA256 `72b7aaa7…`).

**Owner decision on r01.**
- It is a technically failed run, frozen: no `UNKNOWN` reconcile, no replay and no resume.
- The exact cost is recorded later as an offline `BILLED` reconcile, when the Anthropic console shows it.

**Budget lineage (owner decision 2026-10-02).** r01 and r02 share one ceiling of USD 12.000000; r02 is not a fresh USD 12.
- **r01 charge.** r01 is charged its full reservation, USD 2.210772, until exact provider billing evidence exists. The r02 cap is therefore USD 9.789228 (12.000000 - 2.210772).
- **A lower exact r01 cost is never reclaimed automatically.** Raising the r02 cap needs a new, recorded owner decision, and it must keep r01 billed + r02 authorized <= USD 12.000000.
- **Recording the budget does not authorize the paid run.** Details: `docs/research/GENERATOR_V0_ANTHROPIC_RESUMABLE_TRANSPORT.md`, section "r02 budget lineage".

**The fix.** `ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1`, record `docs/research/GENERATOR_V0_ANTHROPIC_RESUMABLE_TRANSPORT.{md,json}`.
- **Message Batches.** The ladder GENERATOR goes through a one-request Message Batch:
  - the `custom_id` is journaled before the create POST;
  - the batch id is journaled at acceptance, and the call is then only polled;
  - a lost create acknowledgement is found again by `custom_id`;
  - a poll failure leaves the call `PENDING`, never `UNCERTAIN`.
- **External checkpoints.** The journal is checkpointed outside the machine at acceptance, after every round and stage, and on every stop. A checkpoint target is mandatory for a live V03 run.
- **Price.** Batch price is half of standard. The generator reservation is about USD 1.105 per round. The fresh V03 worst case is USD 26.33 (USD 30.75 before), so the r02 cap of USD 9.789228 still needs `--accept-budget-stop`.
- **Unchanged.** V02 routes and `first-30-card` are byte-identical. The V03 design is unchanged: slot plan, prompts, schemas, models, effort, critics, the 2/2/1 shortlist and the budget-stop semantics.
- **Tests.** Offline crash/resume fault tests on fake transports and a fake clock: 25 new tests plus the rehearsal on the batch route.

## Generator V0 Cursor DIRECT transport amendment — 2026-10-02

`CURSOR_DIRECT_TRANSPORT = implementation/infrastructure amendment only`
`SCIENTIFIC_DESIGN_CHANGED = false`
`LIVE_LLM_CALLS = 0`

For the V03 `ladder-40-card` path, an explicit `--openai-network-mode DIRECT` is now respected for Cursor/local environments with direct API credentials. Without the flag, `ladder-40-card` still defaults to `CLOUD_PROXY`; `first-30-card` still forces `CLOUD_PROXY`. The mode is recorded in transport/run identity, so resume across modes fails closed. No model, prompt, schema, route, ladder, critic, shortlist, budget, or scientific rule changed.

Record: `docs/research/GENERATOR_V0_CURSOR_DIRECT_TRANSPORT.{md,json}`.

## Generator V0 pre-campaign hardening — 2026-10-02

`MEMORY_FINALIZER_V03 = IMPLEMENTED (validates and copies ladder fields; V02 unchanged)`
`V03_BUDGET_STOP = INCOMPLETE_BUDGET_STOP (no shortlist; same-run resume only)`
`LLM_CALLS = 0`
`NEXT_UNIT = GENERATOR_V0_FRESH_SHADOW_CAMPAIGN (waits for owner live authorization and provider keys)`

**Finalizer.** The memory finalizer now accepts V03 campaigns: the red-team check `RUNG_CONSISTENT` and the card fields `COMPLEXITY_CLASS` and `COMPONENTS`. It copies them verbatim and never re-evaluates them. A rung failure maps to `METHOD_RUNG_INCONSISTENT`. V02 deltas and the rules digest are unchanged.

**Budget stop.** A V03 budget stop before all 40 slots and reviews complete gives `INCOMPLETE_BUDGET_STOP`.
- There is no official shortlist. The partial journal is kept and cannot be finalized.
- Only the same run may resume, with identical identity; the cap may change only through a recorded extension.
- After a full resume, the 2/2/1 shortlist is built once.

**Campaign plan.**
- 40 slots split 16/14/7/3; shortlist 2/2/1.
- Hard cap USD 12 with `accept-budget-stop`.
- 125 logical calls, at most 245 attempts.
- Offline worst case USD 30.75, or USD 61.50 with retries; expected spend about USD 7–8.
- No design changes after the first live call.

Record: `docs/research/GENERATOR_V0_PRE_CAMPAIGN_HARDENING.{md,json}`.

## Generator complexity ladder amendment (V03) — 2026-10-02

`GENERATOR_CONTRACT_V03 = IMPLEMENTED (offline)`
`V02_BYTE_IDENTICAL = true`
`LLM_CALLS = 0`
`MARKET_OUTCOMES_OPENED = false`
`NEXT_UNIT = GENERATOR_V0_FRESH_SHADOW_CAMPAIGN (paid; owner budget, roles and call counts required)`

The generator now goes from simple to complex.
- **Slots.** Each of 40 slots carries a `COMPLEXITY_CLASS`, assigned before any LLM call: 16 atomic, 14 conditional, 7 interaction, 3 composite. The model copies the class and never chooses it.
- **Card contract V03.** It adds `COMPLEXITY_CLASS` and `COMPONENTS`. Interaction and composite baselines must name every component, so main effects are controlled; components need not work on their own.
- **Critics.** The red team checks rung consistency. The novelty critic scores an indicator-threshold card low ("simplicity is not banality").
- **Shortlist.** Seats are 2 atomic, 2 conditional and 1 complex. An unfilled seat passes down the ladder, never up.
- **V02.** Schemas, prompts, digests and mock campaign results are byte-identical to `main`.
- **Entry point.** `ladder-40-card`.
- **Before memory ingestion of the ladder campaign:** the memory finalizer must be extended. It refuses V03 red-team checks, failing closed.

Record: `docs/research/GENERATOR_V0_COMPLEXITY_LADDER_AMENDMENT.{md,json}`.

## Generator feasibility contract mapped to V1 — 2026-10-02

`GENERATOR_CONTRACT_VERSION = GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1`
`GENERATOR_CARD_SCHEMA_CHANGED = false`
`LLM_CALLS = 0`
`MARKET_OUTCOMES_OPENED = false`
`COMPLEXITY_LADDER = ATOMIC / CONDITIONAL / INTERACTION / COMPOSITE (planning contract + shortlist quota 2/2/1)`
`NEXT_UNIT = GENERATOR_V0_COMPLEXITY_LADDER_AMENDMENT, then GENERATOR_V0_FRESH_SHADOW_CAMPAIGN (owner budget decision required)`

A shortlisted card becomes a V1 planning object through `scripts/research/generator_v0/feasibility_contract_v1.py`, which emits `GV0R02_SCHEMA_V1` proposals.
- **The planning object carries the V1 design decisions:** claim type, target class, variable roles, 1–3 primary cells, practical bar, surfaces within the frozen era roles, and epochs.
- **The contract checks shape only.** The V1 compiler stays the single adjudicator of the V1 rules.
- **Unchanged:** the generator card (`GENERATOR_CONTRACT_V02`, `CANDIDATE_SCHEMA_FROZEN`), its prompt, and the V0 planning contract.

**Complexity ladder (owner decision).** Generation goes from simple to complex, and simple mechanisms build the library of tested base effects.
- **Planning rungs.** The planning object declares its rung. For interaction and composite claims, each component's main effect is controlled in the baseline, the joint term is the mechanism, and the claim is its incremental effect. The components need not be supported on their own: A ≈ 0, B ≈ 0 and A × B ≠ 0 is valid.
- **Shortlist quota.** 2 atomic, 2 conditional, 1 complex. An unfilled seat passes down the ladder, never up.
- **Simplicity is not banality.** An indicator threshold is a weak atomic card.
- **Generation itself is a separate amendment** to the frozen generator design, made before the campaign: rung-assigned slots, card contract V03, the novelty-critic rule and the quota in the runner.

Record: `docs/research/GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING.md`.

After that amendment comes a paid LLM campaign under `docs/AGENT_RUNTIME_PROTOCOL.md`: a fresh shadow run with a new run ID. It needs the owner's absolute budget cap and the allowed roles and call counts before any live call.

## TWAP V1 closed — owner decision — 2026-10-02

`TWAP_V1 = CLOSED`
`TWAP_SEALED_RUN_V1 = MECHANISM_SUPPORTED_PRICE_EFFECT_NOT_SUPPORTED (merged #287 at becb6cd)`
`RERUN_AUTHORIZED = false`
`NEARBY_VARIANTS_AUTHORIZED = false (no K, duration, tolerance, horizon or floor rescue; no "early TWAP" re-detection)`
`PRODUCT_DIRECTIONAL_CLAIM = NONE`
`NEXT_UNIT = GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING`

The owner closed the TWAP branch after reviewing the sealed run. The closure covers only the narrow region tested: a regular-slice spot BTCUSDT footprint under this detector at the 10 bps scale. It does not close algorithmic execution as a mechanism family. A new execution-family card would need its own seed, novelty check and V1 design freeze, and must not be a variant of this one.

The compiler side of the V1 mapping is done (`GV0R02_SCHEMA_V1 = IMPLEMENTED`). The remaining route is:
1. Generator-side feasibility-contract mapping to V1.
2. A fresh Generator V0 shadow campaign under a new run ID with a capped budget.
3. A shortlist of at most 5.
4. GV0R02 feasibility.
5. New preregistrations.

## TWAP sealed end-to-end run V1 — 2026-10-02

`TWAP_SEALED_RUN_V1 = MECHANISM_SUPPORTED_PRICE_EFFECT_NOT_SUPPORTED`
`SPEC = docs/research/TWAP_SEALED_SPEC_V1.json (frozen at 5a0cd66 before outcomes)`
`RERUN_AUTHORIZED = false`
`NEARBY_VARIANTS_AUTHORIZED = false`
`PROTECTED_2025_2026_OPENED = false`
`NEXT_UNIT = OWNER_DECISION_AFTER_TWAP_SEALED_RUN_V1`

On the discovery period 2020–2024, the detected spot BTCUSDT TWAP footprint keeps showing in same-side flow after detection: 1.26 times matched controls. Independent replication of that statement is insufficient, and H1 was not opened on the replication surface. No side-aligned price statement is supported, at 1 h, at 6 h or after the end:
- H2_1h: +5.0 bps, Holm p 0.17, below the 10 bps floor;
- H2_6h: −0.4 bps;
- H3: +0.5 bps.

Replication 2017–2019 has too little support (19 < 100). The owner decides the next unit; the generator feasibility-contract mapping remains queued. Record: `docs/research/TWAP_SEALED_RUN_V1_RESULT.md`.

## GV0R02 compiler mapped to V1 — 2026-10-01

`GV0R02_SCHEMA_V1 = IMPLEMENTED`
`V0_COMPILER_CHANGED = false`
`MARKET_OUTCOMES_OPENED = false`
`NEXT_UNIT = GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING`

`scripts/research/gv0r02_feasibility_compiler_v1.py` adds the V1 definition checks, Holm-adjusted power over primary cells, a replication power screen, the protected-window check and heterogeneity assessability. The V0 passes run unchanged underneath.
- **Golden cases.** C012, C004 and C020 keep their V0 statuses under V1, and the positive control stays feasible.
- **Record:** `docs/research/GV0R02_FEASIBILITY_COMPILER_V1_MAPPING.md`.

## Hypothesis evaluation contract V1 adopted — 2026-10-01

`HYPOTHESIS_EVALUATION_CONTRACT_V1 = ADOPTED`
`ADOPTED_TEXT_COMMIT = 0db19833adcfa97feac754c3a2108b86122469c5`
`RETROACTIVE = false`
`NEXT_UNIT = GV0R02_COMPILER_AND_GENERATOR_CONTRACT_V1_MAPPING`

The owner adopted `docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1.md` with the pre-adoption amendments A1 (fixed stopping rule for prospective replication) and A2 (no stability claim from heterogeneity tests). It governs every card registered from now on. It supersedes the scoped profile of the decision-layer program.

Route:
1. GV0R02 compiler mapping to V1.
2. Generator feasibility-contract mapping.
3. A fresh Generator V0 shadow run under a new run ID with a capped budget.
4. A shortlist of at most 5.
5. Feasibility.
6. One or two preregistrations.
7. One-shot discovery.
8. Time-disjoint confirmation.

The TWAP footprint card stays separate: its feasibility is outcome-blind and continues, and it will be the first `INCREMENTAL` card preregistered under V1.

## D7 campaign closed; evaluation contract V1 reviewed — 2026-10-01

`D7_CAMPAIGN_CLOSED = true`
`HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW = COMPLETE`
`V1_STATUS = READY_FOR_OWNER_ADOPTION`
`HISTORICAL_VERDICTS_CHANGED = false`
`NEXT_UNIT = OWNER_ADOPTION_OF_HYPOTHESIS_EVALUATION_CONTRACT_V1`

**D7 is closed.** Discovery on Binance, confirmation on BitMEX (`b4efa972…`), and one beta claim. No rerun, no second seed, and no D7 child cards. The record notes the claim's scope: persistence beyond within-bucket volatility and relative volume was not tested.

**The review replayed 19 recorded objects under V1.** Results:
- no failure turns into support;
- C013 would be `HETEROGENEOUS_UNEXPLAINED`: its sign genuinely reverses in 2023–24;
- D12 is not downgraded: its concentration is within noise;
- D7 and D11 have an incomplete nuisance baseline.

**Calibration fixes.** Three over-strict draft rules were found on recorded data and fixed:
- a hard 0.5 epoch-share rule, which rejects 33–84% of constant effects at these sample sizes, is replaced by a calibrated heterogeneity test;
- a `CONTEXT_DESCRIPTIVE` claim type is added for non-directional context;
- prospective replication is allowed.

The red team found ten possible new false-positive paths, each closed by a rule in the contract.

**After adoption:**
1. GV0R02 compiler and generator contract mapping.
2. A fresh generator shadow campaign with a new run ID.

The TWAP footprint feasibility unit is outcome-blind and continues. Its preregistration will be the first card under V1.

Records:
- `docs/research/D7_CAMPAIGN_CLOSE_V1.{md,json}`
- `docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.{md,json}`
- `docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1.md`

## Decision-layer research program V0 — owner decision — 2026-10-01

`BETA_SCOPE_FROZEN_AS_IS = true`
`FIRST_MECHANISM = TWAP_EXECUTION_FOOTPRINT`
`DELTA_DIRECTION_ARM = DROPPED (H05_REJECTED_SPECIFIC_CLAIM)`
`GLOBAL_EVALUATION_REVIEW = STILL_PENDING`
`MARKET_OUTCOMES_OPENED = false`
`NEXT_UNIT = TWAP_FOOTPRINT_OUTCOME_BLIND_FEASIBILITY`

The owner froze the beta as it is. The next research builds evidence for a future decision layer: statistical statements about what followed a detected situation, direction included. A statement is shown only after independent confirmation and a separate promotion gate.

- **Closed arm.** Net taker flow → return is H05, already rejected. It is not re-tested in any form. A TWAP claim must be incremental over matched net flow.
- **Scoped review.** The owner authorized a scoped evaluation profile for this program only. It replaces `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW` for this program. The global review stays pending for everything else.

Record: `docs/research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md`.

## GV0R03 generator feasibility contract — 2026-09-25

`GENERATOR_CONTRACT_VERSION = GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V0`
`COMPILER_MAPPING_STATUS = MECHANICAL_COPY`
`NEW_HYPOTHESES_GENERATED = false`
`LLM_CALLS = 0`
`MARKET_OUTCOMES_OPENED = false`
`NEXT_UNIT = NONE_AUTHORIZED_AFTER_GV0R03_CONTRACT`

Future candidates must carry the planning object in `scripts/research/generator_v0/feasibility_contract.py`. The transform copies it into a `GV0R02_SCHEMA_V0` proposal. It does not score feasibility. `GENERATOR_CONTRACT_V02` card rules are unchanged. Golden cases and the positive control are unchanged.

## GV0R02 feasibility compiler positive control — 2026-09-25

`POSITIVE_CONTROL_EXECUTED = true`
`POSITIVE_CONTROL_STATUS = FEASIBLE_FOR_PREREGISTRATION`
`NEGATIVE_MUTATION_STATUS = INFORMATIONALLY_WEAK`
`MARKET_OUTCOMES_OPENED = false`
`GENERATOR_MODIFIED = false`
`NEXT_UNIT = NONE_AUTHORIZED_AFTER_POSITIVE_CONTROL`

The synthetic planning fixture `GV0R02_POSITIVE_CONTROL_SYNTHETIC` passes `compile_proposal` under the unchanged `GV0R02_POLICY_V0` profile. Reducing only its nominal observation count to 36 returns `INFORMATIONALLY_WEAK` with blocker `MDE_TOO_LARGE`. Golden C012, C004, and C020 were not edited. This is not a market hypothesis and it does not authorize a generator run.

## GV0R02 feasibility compiler implemented — 2026-09-25

`FEASIBILITY_COMPILER_IMPLEMENTED = true`
`GOLDEN_C012 = PASS`
`GOLDEN_C004 = PASS`
`GOLDEN_C020 = PASS`
`MARKET_OUTCOMES_OPENED = false`
`POSITIVE_CONTROL_EXECUTED = false`
`NEXT_UNIT = GV0R02_FEASIBILITY_COMPILER_POSITIVE_CONTROL`

The compiler screens a pre-candidate proposal under `GV0R02_SCHEMA_V0`. It does not decide that a hypothesis is true. Golden C012 is `INFORMATIONALLY_WEAK`, C004 is `INFERENCE_SUPPORT_INSUFFICIENT`, and C020 is a placebo reference test that is `INFORMATIONALLY_WEAK`. The positive control was not run. Code: `scripts/research/gv0r02_feasibility_compiler.py`.

## GV0R02 feasibility compiler design — 2026-09-25

`FEASIBILITY_COMPILER_IMPLEMENTED = false`
`GENERATOR_MODIFIED = false`
`NEXT_UNIT = GV0R02_OUTCOME_BLIND_FEASIBILITY_COMPILER_IMPLEMENTATION`

The compiler is a cheap outcome-blind screen before preregistration. It does not decide that a hypothesis is true and it is not implemented in this unit. Binance 2020–2024 stays discovery, BitMEX 2016–2019 stays a historical replication candidate, and 2025–2026 stays protected. C012, C004, and C020 remain closed and are the golden cases. Contract: `docs/research/GV0R02_FEASIBILITY_COMPILER_DESIGN.md`.

## GV0R01-C020 closed — reference test, informationally weak — 2026-09-25

`C020_STATUS = CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK_REFERENCE_TEST`
`C020_EXECUTION_AUTHORIZED = false`
`EXACT_RANDOMIZATION_CLAIM_STATUS = NOT_JUSTIFIED`
`OBSERVED_ASSIGNMENT_IN_REFERENCE_SUPPORT = false`
`SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING = 0`
`NEXT_UNIT = GV0R02_OUTCOME_BLIND_FEASIBILITY_COMPILER_DESIGN`

The frozen pseudo-holiday procedure compares NYSE closure dates with dates drawn outside holiday weeks. The observed assignment is not in that reference set, so it is not an exact randomization orbit. The number `1.647e-59` is the resolution of the full reference set. The operational Monte Carlo floor is `1/1001`. Validity requires the closure dates to be exchangeable with that reference distribution under the null for calendar factors other than participant removal. The failed power gate is unchanged: stress power at `log(0.90)` is 0.40. No BTC value was opened and no C020 test was run. The old candidate queue is not continued, and the feasibility compiler is not implemented here. C012, C004, and C020 are the later acceptance cases for that compiler. Record: `docs/research/GV0R01_C020_CLOSE.json`.

## GV0R01-C020 outcome-blind design — 2026-09-25

`OUTCOME_BLIND_GATE_RESULT = EXECUTION_INFORMATIONALLY_WEAK`
`PRIMARY_EVENT_COUNT = 47`
`ALPHA_ATTAINABLE = true`
`MARKET_DATA_OPENED_FOR_C020 = false`
`C020_PRIMARY_TEST_EXECUTED = false`
`NEXT_UNIT = NO_C020_EXECUTION_AUTHORIZED`

The lead arm is the 47 point-in-time verified NYSE full weekday closures. The US session is NYSE regular hours, 09:30–16:00 America/New_York, converted with the statutory DST calendar. The endpoint is the mean of log(US-session quote-volume share / mean share on same-weekday controls at ±2 weeks). Exact pseudo-holiday support reaches alpha 0.05. The execution bar, frozen before power, is log(0.90). At that bar the base synthetic power is 0.79 and the stress power is 0.40, so one-shot execution is not justified. F2 and F3 are vetoes and are not power-calibrated. China and early-close arms stay non-decisive. No BTC price or volume was opened. Record: `docs/research/GV0R01_C020_OUTCOME_BLIND_DESIGN.json`.

## GV0R01-C020 holiday calendars pinned — 2026-09-25

`STATUS = HOLIDAY_CALENDARS_PINNED`
`NYSE_ROLE = PRIMARY_EVENT_DEFINITION`
`CN_STATE_COUNCIL_ROLE = CONTROL_CONTAMINATION_EXCLUSION_AND_NON_DECISIVE_EXTENSION`
`US_OPM_ROLE = OTHER_FALSIFIER_SPECIFICITY`
`MARKET_DATA_OPENED_FOR_C020 = false`
`NEXT_UNIT = GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER_CONTINUATION`

Discovery years 2020–2024 only. NYSE full weekday closures are 47, all `VERIFIED_PREANNOUNCED`, and are distinct from 9 early closes. One NYSE dash (2021 Juneteenth, no weekday closure) and the OPM 2021 Juneteenth observed date remain `UNRESOLVED_PUBLICATION_TIMING` and are not lead-arm inputs. China non-working and compensating-working dates are separate. No session bound, endpoint, or power was frozen. Record: `docs/research/GV0R01_C020_HOLIDAY_CALENDAR_PIN.json`.

## GV0R01-C020 design blocked on unpinned holiday calendars — 2026-09-25

`C020_DEFINITION_STATUS = UNAMBIGUOUS`
`OUTCOME_BLIND_GATE_RESULT = BLOCKED_BY_MISSING_INPUT`
`MARKET_DATA_OPENED_FOR_C020 = false`
`NEXT_UNIT = GV0R01_C020_HOLIDAY_CALENDAR_PINNING`

The card is a holiday natural experiment on BTC session volume shares. NYSE, China State Council and US OPM calendars are required with publication dates and are not pinned. No third-party holiday list was substituted. No price or volume value was opened. Inference and power were not reached. Record: `docs/research/GV0R01_C020_DESIGN_BLOCK.json`.

## GV0R01-C004 closed outcome-blind — 2026-09-25

`C004_STATUS = CLOSED_OUTCOME_BLIND_INFERENCE_SUPPORT_INSUFFICIENT`
`C004_EXECUTED = false`
`C004_MARKET_OUTCOMES_OPENED = false`
`PRIMARY_LABEL_ORBIT_SIZE = 16`
`MIN_ATTAINABLE_EXACT_P = 0.0625`
`ALPHA_ATTAINABLE = false`
`SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING = 0`
`NEXT_CANDIDATE_FOR_DESIGN = GV0R01-C020`
`NEXT_UNIT = GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER`

The dependence-valid label orbit has 16 configurations, so the exact one-sided floor is 1/16 = 0.0625, above alpha 0.05. Rejection is impossible under that frozen test. The synthetic power gate also fails. No BTC or ETH price was opened and no primary test was run. The 2000-draw Monte Carlo was power planning only. The permutation group was not widened and alpha was not changed. A different design needs a new research-object id. The remaining ready zero-cost Stream-B candidate is C020. Record: `docs/research/GV0R01_C004_CLOSE.json`.

## GV0R01-C004 outcome-blind design — informationally weak — 2026-09-25

`C004_DEFINITION_STATUS = UNAMBIGUOUS`
`OUTCOME_BLIND_GATE_RESULT = EXECUTION_INFORMATIONALLY_WEAK`
`MARKET_DATA_OPENED_FOR_C004 = false`
`NEXT_UNIT = NO_C004_EXECUTION_AUTHORIZED`

The GV0R01-C004 claim is a lower ETH residual-variance share in the 60 minutes after a scheduled FOMC statement. CPI is not in the primary event set. Beta-window overlap makes one dependence component of 76 windows. The graph-preserving label orbit has size 16, so a 5% test is not attainable. No price file was opened. Record: `docs/research/GV0R01_C004_OUTCOME_BLIND_DESIGN.json`.

## GV0R01-C012 closed outcome-blind — 2026-09-25

`C012_STATUS = CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK`
`C012_EXECUTED = false`
`C012_MARKET_OUTCOMES_OPENED = false`
`SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING = 0`
`NEXT_CANDIDATE_FOR_DESIGN = GV0R01-C004`
`NEXT_UNIT = GV0R01_C004_OUTCOME_BLIND_DESIGN_AND_POWER`

The amended permutation is structurally valid and fails the frozen 0.50 single-window-SD power bar (stress MDE 0.6093023255813953). No BTC price was opened and no primary test was run. C012 has no evidence for or against anticipatory drift. The failure is ex-ante information content. No further C012 inference amendment is authorized. A different design needs a new research-object id.

The next object is C004, from the Stream-B feasibility ranking after C012 is removed. C004's core FOMC arm is already point-in-time resolved and it needs one free source, which the pinned BLS CPI calendar already supplies. C020 remains behind it. C006, C014 and C016 stay blocked. Record: `docs/research/GV0R01_C012_CLOSE.json`.

## GV0R01-C012 inference amendment — outcome-blind, not powered — 2026-09-25

`AMENDED_POWER_GATE_RESULT = INFERENCE_AMENDMENT_VALID_BUT_INFORMATIONALLY_WEAK`
`STRUCTURAL_INVARIANCE_STATUS = PASS`
`MARKET_DATA_OPENED_FOR_C012 = false`
`C012_PRIMARY_TEST_EXECUTED = false`
`NEXT_UNIT = NO_EXECUTION_AUTHORIZED`

The primary randomization group is now `G_C012_TOPO`, the stratum-preserving automorphisms of the frozen 198-node overlap graph. The label orbit has size `3204454418600404451328000000000`. Under variance inflation 2, the synthetic 80% MDE is about 0.61 single-window SD units, above the 0.50 bar. Execution is not authorized. Record: `docs/research/GV0R01_C012_INFERENCE_AMENDMENT.json`.

## GV0R01-C012 one-shot stopped before prices — dependence defect — 2026-09-25

`RUN_STATUS = BLOCKED_INFERENCE_DEPENDENCE_DEFECT`
`GLOBAL_PERMUTATION_INVARIANCE_STATUS = NOT_ESTABLISHED`
`MARKET_DATA_OPENED_FOR_C012 = false`
`C012_PRIMARY_TEST_EXECUTED = false`
`NEXT_UNIT = GV0R01_C012_OUTCOME_BLIND_INFERENCE_AMENDMENT`

Identity checks on the frozen design, preflight, and discovery manifest passed. The complete overlap graph of the 198 frozen windows has 177 components and maximum size 2. 240 allowed within-stratum label swaps exchange observations whose outside-stratum overlap neighbors differ (154 observations). Within-stratum separation does not establish exchangeability of the complete statistic. No price value was opened. The primary test was not run. Record: `docs/research/GV0R01_C012_DEPENDENCE_BLOCK.json`.

## C012 discovery-period BTC months pinned — 2026-09-25

`STATUS = DISCOVERY_MARKET_BYTES_PINNED`
`MARKET_DATA_OPENED_FOR_C012 = false`
`NEXT_UNIT = GV0R01_C012_ONE_SHOT_EXECUTION`

The 60 monthly Binance BTCUSDT 1m objects for 2020-01 through 2024-12 are on disk and match snapshot `717d37a4…`. No 2025 or 2026 object was fetched. No C012 return was computed. Manifest: `docs/research_data/C012_DISCOVERY_BTC_1M_V0/MANIFEST.json`, digest `78e3f54a…`.

## GV0R01-C012 one-shot execution blocked before prices — 2026-09-25

`PREFLIGHT_STATUS = PASS`
`RUN_STATUS = BLOCKED_MARKET_BYTES_ABSENT`
`MARKET_DATA_OPENED = false`
`NEXT_UNIT = GV0R01_C012_ONE_SHOT_EXECUTION`

The calendar preflight committed at `61ce003` assigns a control to all 99 events with no reuse. Within each stratum the windows are at least 7 days apart, so the frozen within-stratum permutation is compatible with that assignment. The pinned `CORE_BTC_BINANCE_V0` 1m months are not on disk. The snapshot identity runs through 2026-08, so the full materializer was not started. No price file was opened and no return was computed.

## GV0R01-C012 outcome-blind design and power — 2026-09-25

`C012_DESIGN = PREREGISTRATION_CANDIDATE`
`OUTCOME_BLIND_GATE = EXECUTION_JUSTIFIED`
`EXECUTION_AUTHORIZED = false`
`NEXT_UNIT = GV0R01_C012_ONE_SHOT_EXECUTION`

This section supersedes `NEXT_UNIT = GV0R01_C012_OUTCOME_BLIND_DESIGN_AND_POWER` below.

The primary specification is singular: FOMC and CPI, 24h window ending one minute before the release, two-sided stratified permutation against year/weekday/UTC-hour controls. The other five card variants cannot decide. The universe is 60 CPI events plus 39 pinned FOMC events. Both overlapping pairs and all 11 long-gap CPI events stay in.

No BTC series was opened and no pre-release return was computed. The planning MDE at `n = 94/2` is 0.409 sigma, under the pre-set 0.50-sigma bar, so the gate justifies a later execution. This unit does not authorize it. A 0.25-sigma drift is not powered.

Record: `docs/research/GV0R01_C012_OUTCOME_BLIND_DESIGN.{md,json}` and `docs/research/GV0R01_C012_POWER.json`.

## BLS CPI release-schedule archive V0 pinned — 2026-09-25

`BLS_CPI_CALENDAR_V0 = DURABLY_PINNED`
`C012_CPI_BLOCKER_RESOLVED = true`
`C004_CPI_BLOCKER_RESOLVED = true`
`NEXT_UNIT = GV0R01_C012_OUTCOME_BLIND_DESIGN_AND_POWER`

This section supersedes `NEXT_UNIT = GV0R01_C012_CPI_CALENDAR_ACQUISITION_AND_OUTCOME_BLIND_DESIGN` below. It also supersedes that section's note that the sandbox refuses `bls.gov` and `web.archive.org`: both hosts were reachable in this run.

`BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0` holds the point-in-time CPI release schedule for 2020–2024:

- **Coverage.** 60 events, all `VERIFIED_PREANNOUNCED` and safe for 6h, 12h and 24h windows. There are no reschedules and no unresolved events.
- **Sources.** The authority is the first-party BLS schedule page, dated by Wayback captures whose bytes match the CDX digest. UTC is derived from the frozen `STATUTORY_DST_CALENDARS`.
- **Content.** Schedule metadata only: no CPI values, no market data, and protected 2025/2026 values stay unopened.

The dataset resolves only the CPI calendar observable, and C012 and C004 may reference it later. Neither has been designed, preregistered or powered.

Record: `docs/research/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0_ACQUISITION.{md,json}`. Dataset: `docs/research_data/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0/`.

## Post-C013 program decision — GV0R01 Stream-B feasibility triage — 2026-09-25

`C013_PROGRAM_STATE = PROMISING_PROTOTYPE / CONFIRMATION_DEFERRED_LOW_POWER`
`NEXT_CANDIDATE_FOR_DESIGN = GV0R01-C012`
`RUN_GV0R02_NEXT = false`
`NEXT_UNIT = GV0R01_C012_CPI_CALENDAR_ACQUISITION_AND_OUTCOME_BLIND_DESIGN`

This section supersedes `NEXT_UNIT = POST_GV0R01_C013_CONFIRMATION_FEASIBILITY_PROGRAM_DECISION` below.

C013 is parked pending an adequate independent surface. There is no underpowered confirmation and no rescue, and 2025/2026 stay sealed.

The six GV0R01 Stream-B candidates were triaged outcome-blind:
- **Ready after free public acquisition:** C004, C012 and C020 (official calendars).
- **Blocked on point-in-time semantics:** C006 and C014 (DVOL non-revision cannot be evidenced from the free source).
- **Blocked on expensive data:** C016 (the card's spread control needs paid L2 history).

C012 (pre-announcement BTC drift before scheduled FOMC and CPI releases) is next, chosen on feasibility only:
- its FOMC arm is already point-in-time resolved;
- it needs one free source, the BLS CPI schedule archive;
- it declares the smallest search surface;
- it is BTC-only, which allows a pre-2020 confirmation route.

Its design must plan confirmation power before any discovery run. This sandbox refuses `bls.gov` and `web.archive.org`, so they must be allowed in the environment network settings for the CPI pinning.

Record: `docs/research/GV0R01_STREAM_B_FEASIBILITY_TRIAGE.{md,json}`.

## GV0R01-C013 independent confirmation — feasibility decided, not executable — 2026-09-25

`FRESH_SURFACE_DECISION = WAIT_FOR_MORE_FRESH_DATA`
`CONFIRMATION_FEASIBILITY = UNDERPOWERED_ON_EVERY_AVAILABLE_OR_FORESEEABLE_FRESH_SURFACE`
`CONFIRMATION_PREREG_CREATED = false`
`EXECUTION_AUTHORIZED = false`
`NEXT_UNIT = POST_GV0R01_C013_CONFIRMATION_FEASIBILITY_PROGRAM_DECISION`

This section supersedes `NEXT_UNIT = GV0R01_C013_INDEPENDENT_CONFIRMATION_DESIGN` below.

The outcome-blind confirmation design for GV0R01-C013 (discovery `PROMISING_PROTOTYPE`, not a validated edge) found no adequately powered fresh surface.

- **Method.** Power was planned from exposed 2020–2024 material only, by resampling whole exposed years to preserve dependence.
- **Why power is low.** The discovery's year-level heterogeneity dominates. Yearly means are negative in 2020–2022 and positive in 2023–2024, with a between-year sd of about 2.5× the effect.
- **Power at the discovery effect.** Statistical + direction power is 0.60 for 2025 only, 0.52 for 2025 plus the available 2026 prefix, and 0.69 for full 2025–2026. The target is 0.80, which needs about 9 independent years. Attenuated effects are lower still.
- **Alternative surface.** Pre-2019-12 Binance spot history cannot support an N=50 universe.

2025 and 2026 remain sealed and unspent; only metadata was listed and no payload was opened. No confirmation test is registered, and `TF-GV0R01-C013-CONF1` is reserved only. The owner decides the program next, for example parking C013 as unconfirmable for now. There is no parameter, horizon, sign or regime rescue.

Record: `docs/research/GV0R01_C013_CONFIRMATION_FEASIBILITY_AND_DESIGN.{md,json}`, with power in `docs/research/GV0R01_C013_CONFIRMATION_POWER.json`.

## GV0R01-C013 result ingested into full scientific memory — 2026-09-25

`MARKET_TEST_RESULT_EVENT = IMPLEMENTED`
`GV0R01_C013_RESULT_MEMORY_INGESTION = COMPLETE`
`NEXT_UNIT = GV0R01_C013_INDEPENDENT_CONFIRMATION_DESIGN` (unchanged)

The memory chain is now `LEGACY_BOOTSTRAP → GV0CAL → GV0R01 → GV0R01C013MT1`. The head is `853ef4514460a18b5aa16bf3fff86ece027c52e4b58d92dfbf98034f1fde9373`. Memory holds 57 signatures, 35 attempt records and 1 market result.

The immutable C013 discovery result (`TF-GV0R01-C013-MT1`, `PROMISING_PROTOTYPE`, result SHA256 `036016c4…`) is attached to full **human** scientific memory under `MECHANISM_MEMORY_V0.MARKET_TEST_RESULTS`. It is not a validated edge. Independent confirmation has not been designed or executed.

The blind generator map and the governance authority are byte-for-byte unchanged and outcome-neutral. GV0R01-C013 stays `PRIOR_WORK_SIGNATURE` for the generator, and its governance row stays `CONSUMED`. No market data were read, no outcome was computed, and no provider was called. See `docs/research/GENERATOR_V0_MEMORY_FINALIZER.md` §8.

## GV0R01-C013 one-shot market test — executed — 2026-09-25

`GV0R01_C013_MARKET_TEST = EXECUTED_ONCE`
`CLASSIFICATION = PROMISING_PROTOTYPE` (discovery tier; not a validated edge)
`RERUN_AUTHORIZED = false`
`NEXT_UNIT = GV0R01_C013_INDEPENDENT_CONFIRMATION_DESIGN`

This section supersedes `NEXT_UNIT = GV0R01_C013_MARKET_TEST_EXECUTION_AUTHORIZATION` below.

The frozen one-shot test `TF-GV0R01-C013-MT1` ran once under the owner permit committed in `386bc10`. The result is `docs/research/GV0R01_C013_MARKET_TEST_RESULT.json` (SHA256 `036016c403f83e4c63b2e006379551a0f595e8803cb55a0ef8f27a19ce3a1062`).

- All six frozen gates passed: statistical, direction, temporal, control, dependence and adjacency.
- Primary K5/H1/N50: pooled weekly-mean Spearman −0.0199, permutation p 0.002 (the 1000-draw floor).
- Controlled statistic −0.0535, p 0.002. Newey–West t −2.48. Adjacency −0.0214.
- Yearly means are negative in 2020–2022 and positive in 2023–2024. The temporal gate passed exactly at 3 of 5.
- Coverage: 1820/1820 valid days, 260 valid weeks. Missing-target rate 0.03%.
- The seven secondary variants are descriptive only and cannot change the classification.

This is discovery evidence only. It requires independent confirmation, which has **not** been designed or executed. No trading or profitability claim is made. Protected 2025/2026 remain unopened. Generator V0 memory is unchanged: the result enters full memory only through a later deterministic `MARKET_TEST_RESULT` event, and the generator's blind map stays outcome-neutral.

Record: `docs/research/GV0R01_C013_MARKET_TEST_OUTCOME.{md,json}`. Ledger: `docs/research/SCIENTIFIC_TEST_LEDGER.json` (`EXECUTED`; search family `SF-GENERATOR_V0-GV0R01` has 1 executed test out of 30 generated cards).

## GV0R01-C013 first market test — preregistration frozen — 2026-09-25

`GV0R01_C013_MARKET_TEST_DESIGN = FROZEN`
`EXECUTION_AUTHORIZED = false`
`MARKET_TEST_EXECUTED = false`
`NEXT_UNIT = GV0R01_C013_MARKET_TEST_EXECUTION_AUTHORIZATION`

This section supersedes `NEXT_UNIT = FIRST_MARKET_TEST_DESIGN_FOR_GV0R01` below.

The first market test for GV0R01-C013 ("Persistence of intraday wick morphology across the Binance spot USDT cross-section") is frozen as a one-shot discovery-tier preregistration: `docs/research/GV0R01_C013_MARKET_TEST_PREREG.{json,md}`, prereg SHA256 `49dff57b3e068d999c9c4467fb5117de9d73ad564425bf737df727a1096f7625`, test family `TF-GV0R01-C013-MT1`.

- Primary variant: K=5 trailing CLV, H=1 residual wick target, top-50 universe on the Sprint 04 panel, decision days 2020-01-06..2024-12-29.
- Primary statistic: weekly-mean Spearman correlation.
- Null: 1000 within-date quote-volume-tercile permutations.
- Direction: negative (persistence).
- Gates: the card's three falsifiers, plus dependence (HAC) and adjacency gates that only narrow support.

The deterministic harness is `scripts/research/gv0r01_c013_market_test{,_lib}.py`, tested on synthetic panels only. It is registered in the new global `docs/research/SCIENTIFIC_TEST_LEDGER.json` before any outcome. No C013 outcome was computed. Protected 2025/2026 remain unopened. Execution requires an explicit owner permit bound to the prereg digest.

## Generator V0 first 30-card run GV0R01 — 2026-09-25

`GENERATOR_V0_FIRST_30_CARD_RUN = COMPLETE`
`CAMPAIGN_ID = GV0R01`
`CAMPAIGN_STATUS = PENDING_HUMAN_REVIEW`
`MEMORY_FINALIZATION = COMPLETE`
`NEXT_UNIT = FIRST_MARKET_TEST_DESIGN_FOR_GV0R01`

This section supersedes the Generator V0 `NEXT_UNIT` / `NEXT_ACTION` entries below.

The first real 30-card campaign ran on the frozen routed architecture:
- 3 generator POSTs;
- 30 novelty, 30 feasibility and 30 red-team calls;
- 0 selector LLM calls;
- 93 calls, all complete, none unresolved;
- USD 5.091486 spent under the USD 10.00 hard cap.

All 30 cards were valid and reviewed. Stream A (`EXECUTABLE_NOW`) is C013. Stream B (`HIGH_VALUE_DATA_BLOCKED`) is C004, C006, C012, C014, C016 and C020. The deterministic shortlist is C013, C014, C006, C012, C016.

The journal is sealed and archived at `docs/research/generator_v0_gv0r01/run.sqlite` (SHA256 `de22f7c2aeb0487842a2477e5a2f44e3df7a9cbf007785cfaf213cbcd648be62`). It is registered in `GENERATOR_V0_SEALED_RUNS.json`.

Memory Finalizer V1 applied event `416b22fabd1663be9094bce18c5bce2a8b3d062b0b01525a25395d195788bead` (current memory head, chain `LEGACY_BOOTSTRAP → GV0CAL → GV0R01`):
- 30 attempt records;
- 22 new signatures (1 `CONSUMED`, 21 `DEFERRED_OR_BLOCKED`);
- 4 links to prior signatures and 4 batch links;
- 57 memory entries and 35 attempt records in total.

C013 (`GV0R01-C013`, "Persistence of intraday wick morphology across the Binance spot USDT cross-section") is the sole current GV0R01 `EXECUTABLE_NOW` research candidate after generator and critic governance. Its market outcome remains completely untested. It is **not** a validated market hypothesis, and no card has been executed. The other GV0R01 signatures are durable prior work and must not be regenerated with cosmetic changes. Protected 2025/2026 remain unopened. `MARKET_OUTCOMES_TESTED = false`.

Record: `docs/research/GENERATOR_V0_FIRST_30_CARD_RUN_GV0R01.{md,json}`.

## Generator V0 first 30-card production-path repair — 2026-09-24

`FIRST_30_PRODUCTION_PATH_REPAIRED = true`
`NEXT_UNIT = GENERATOR_V0_FIRST_30_CARD_RUN`
`NEXT_ACTION = FIRST_30_CARD_RUN_AFTER_INDEPENDENT_REVERIFY`

Offline repair of three execution defects. No live call and no scientific change. Memory Finalizer V1 is unchanged.

- `GENERATOR_CONTENT_ATTEMPTS = 1` (`GENERATOR_CONTENT_RETRIES = 0`). A size-30 campaign has `MAX_GENERATOR_POSTS = 3`. Critics still use `MAX_CONTENT_ATTEMPTS = 2`. The budget reservation is unchanged.
- First 30-card selector: `SELECTOR_LLM_CALLS = 0`, `SELECTOR_AUTHORITY = DETERMINISTIC_ORDINAL_ORDER`, advisory `NOT_CALLED` / `deterministic-only first 30-card run`. Other sizes keep the historical advisory call.
- Cloud Agent OpenAI: `OPENAI_NETWORK_MODE = CLOUD_PROXY`, chosen explicitly by `first-30-card`. Transport is `CloudProxyOpenAITransport`. No `OPENAI_API_KEY`. Anthropic still requires `SIGNALBOT_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY`. `HTTPS_PROXY` does not select the mode.

Record: `docs/research/GENERATOR_V0_FIRST_30_PRODUCTION_PATH_REPAIR.{md,json}`.

## Generator V0 memory finalizer V1 — 2026-09-24

`MEMORY_FINALIZER_V1 = ACTIVE`
`NEXT_UNIT = GENERATOR_V0_FIRST_30_CARD_RUN`

Mechanism memory is now an append-only event chain (`docs/research/generator_v0_memory/`): `LEGACY_BOOTSTRAP` (`54afd1ed229cca6785586534102df3b6fb5129e736def4f5df726225b16773e8`, the 30 pre-GV0CAL entries verbatim from `d4b28de`) then `GV0CAL` (`358f06d4e2d1f7d1657c89544fc702d7dffe7bf6c1ec920ceab4228f7a50c3ad`, head at that time), derived deterministically from the calibration export. GV0CAL governance is unchanged: C001/C002/C005 `CONSUMED`, C003/C004 `DEFERRED_OR_BLOCKED` with the same blocker classes. Governance rows are no longer embedded in the frozen design; the mirrors and context pins are derived caches. After the first 30-card run, finalize it with `python -m scripts.research.generator_v0.finalize_memory` in the same VM. No provider call, no market outcome, no protected data. Canonical record: `docs/research/GENERATOR_V0_MEMORY_FINALIZER.{md,json}`.

## Generator V0 calibration-memory ingestion — 2026-09-24

`CALIBRATION_MEMORY_INGESTION_COMPLETE = true` (manual workflow superseded by the memory finalizer above; kept as its golden source)
`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_FIRST_30_CARD_RUN`

All five durable calibration cards are now represented in mechanism memory before the first 30-card generation. Stable prior IDs are `GV0CAL-C001`–`GV0CAL-C005`. The generator sees only outcome-neutral prior-work signatures. The novelty critic sees C001/C002/C005 as consumed prior signatures and C003/C004 as deferred/blocked methodological regions with explicit blocker-resolution requirements. No market outcomes were tested; protected 2025/2026 remain unopened. The architecture freeze is unchanged.

Canonical record: `docs/research/GENERATOR_V0_CALIBRATION_MEMORY_INGESTION.{json,md}`.

## Generator V0 first 30-card architecture freeze — 2026-09-24

`NEXT_UNIT = GENERATOR_V0_FIRST_30_CARD_RUN`  
`NEXT_ACTION = FIRST_30_CARD_RUN_AFTER_OPERATIONAL_PERSISTENCE_REVIEW`

This section supersedes older Generator V0 `NEXT_UNIT` / `NEXT_ACTION` entries below.

The live transport repair/calibration cycle is closed for the first campaign:
- Anthropic Opus generator completed live;
- background Sol NOVELTY completed live;
- Luna FEASIBILITY completed live;
- background Sol RED_TEAM completed live;
- the five-card critic calibration completed all final chains.

The first full campaign is frozen at 30 cards: three 10-card Opus rounds, no generator retry. Routed authority remains `scripts/research/generator_v0/routing.py`. Cloud OpenAI runtime binding is `scripts/research/generator_v0/cloud_openai_transport.py` under `docs/AGENT_RUNTIME_PROTOCOL.md`.

No further precautionary smoke/calibration cycles are required before the first 30-card run. Reopen transport/routing only for a concrete execution defect or explicit owner amendment. Calibration/smoke evidence has no scientific status; protected 2025/2026 remain unopened.

Canonical record: `docs/research/GENERATOR_V0_FIRST_30_CARD_ARCHITECTURE_FREEZE.{md,json}`.

## Generator V0 background RED_TEAM transport — 2026-09-24

`NEXT_UNIT = GENERATOR_V0_BACKGROUND_RED_TEAM_SMOKE`.
The critic-only continuation of the five-card cost calibration (recovered Opus generator round, USD 0.892012, 10/10 admitted, cards C001-C005) completed C001 background NOVELTY (USD 0.029376) and C001 FEASIBILITY (USD 0.000415), then stopped on C001 synchronous Sol `RED_TEAM` HTTP 502 `UNCERTAIN`. That call was reconciled UNKNOWN at its full reservation (USD 0.098806; no response_id or usage existed). By owner authorization only the RED_TEAM transport now uses background Responses; model, effort, prompt, schema, token cap and every other role are unchanged. No live call in this amendment; the calibration is not complete. See `docs/research/GENERATOR_V0_BACKGROUND_RED_TEAM_TRANSPORT_AMENDMENT.md`.

## Generator V0 background novelty transport — 2026-09-24

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_BACKGROUND_NOVELTY_INDEPENDENT_REVIEW` (superseded by the RED_TEAM transport amendment above).
The final compact re-smoke completed (Opus, Luna and Sol; new spend USD 0.962547). The five-card cost calibration then stopped twice on ambiguous non-JSON HTTP 502s from routed Sol `NOVELTY_CRITIC` (one reconciled UNKNOWN, one still UNCERTAIN). Only that role's transport now uses background Responses (one create POST, then GET polling by response_id). Model, effort, prompt, schema and every other role are unchanged. No live call in this amendment; the calibration is not complete. See `docs/research/GENERATOR_V0_BACKGROUND_NOVELTY_TRANSPORT_AMENDMENT.md`.

## Generator V0 re-smoke guard — 2026-09-24

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_FINAL_RE_SMOKE_REVIEW` (performed; see above).
The Anthropic synchronous timeout is 1800 s. The re-smoke ledger carries historical spend USD 0.713332 inside an absolute cap of USD 3.10, and `run_resmoke` allows one Anthropic GENERATOR POST with no content retry and no transport replay. No live call in this follow-up. See `docs/research/GENERATOR_V0_ANTHROPIC_OUTPUT_CAP_AMENDMENT.md`.

## Generator V0 Anthropic GENERATOR output-cap amendment — 2026-09-24

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_OUTPUT_CAP_INDEPENDENT_REVIEW` (accepted; see the re-smoke guard below).
The live compact re-smoke was accepted by Anthropic (HTTP 200) but stopped at `max_tokens` after 32,768 output tokens (17,396 thinking), cost USD 0.713332, one POST, no critic calls. By owner decision only the routed Anthropic GENERATOR output cap rises to 100,000; model, effort, round size, candidate count, compact projection and V02 rules are unchanged, and the legacy OpenAI cap stays 32,768. Every generator call key changes. Failed attempts now record only `wire_sha256`. The next re-smoke fits the USD 3.10 absolute smoke ceiling (3.038724 incl. history). No live call in this repair. See `docs/research/GENERATOR_V0_ANTHROPIC_OUTPUT_CAP_AMENDMENT.md`.

## Generator V0 Anthropic compact GENERATOR projection — 2026-09-24

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_ANTHROPIC_RE_SMOKE` (performed; see the output-cap amendment above).
The first Anthropic smoke was rejected with HTTP 400 "compiled grammar is too large" at cost USD 0. The Anthropic GENERATOR request now uses a compact array wire format with one shared card schema. Intake enforces the exact keyed slot schema and V02 rules before any card is VALID or reaches a critic. No scientific change and no real API call. See `docs/research/GENERATOR_V0_ANTHROPIC_COMPACT_PROJECTION.md`.

## Generator V0 outcome-blind multi-provider routing — 2026-09-24

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_MULTI_PROVIDER_ROUTING_READY_FOR_INDEPENDENT_REVIEW` (verified; see the compact projection above).
PR #214 was verified `READY_FOR_PROVIDER_SMOKE_TEST`. This unit adds an infrastructure-only routing layer:
- GENERATOR → Anthropic `claude-opus-5-5` (effort high);
- NOVELTY_CRITIC and RED_TEAM → OpenAI `gpt-6-sol` (high);
- FEASIBILITY_CRITIC and the advisory SELECTOR → OpenAI `gpt-6-luna` (low / none).

Recorded as an outcome-blind routing amendment; scientific stages and contracts are unchanged. No real API call, no live shadow. See `docs/research/GENERATOR_V0_MULTI_PROVIDER_ROUTING_AMENDMENT.md`.

## Generator V0 final narrow repair (after re-verification) — 2026-09-23

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_FINAL_NARROW_REPAIR_READY_FOR_FINAL_RE_VERIFICATION` (verified READY_FOR_PROVIDER_SMOKE_TEST; see the routing amendment above).
The final narrow offline repair covers three residual classes:
- abbreviated cross-year ranges;
- imperative trade language;
- the fail-closed budget gate moved into `run_campaign`, so it no longer depends on the CLI.

Completion state is `READY_FOR_FINAL_RE-VERIFICATION`, not a provider smoke test or live shadow. See `docs/research/GENERATOR_V0_LIMITED_REPAIR.md`.

## Generator V0 limited offline repair (after PR #215 verification) — 2026-09-23

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_LIMITED_REPAIR_READY_FOR_RE_VERIFICATION` (re-verified; see the final narrow repair above).
Limited offline repair of the five blockers found by the independent
verification (PR #215):
- keyed novelty prompt/schema/parser contract;
- sealed journals refused inside `Ledger`;
- dispatch state machine so a possibly-POSTed call is never re-sent without evidence;
- Unicode-normalized structural temporal/protected/trade checks;
- budget preflight for fresh and derived journals, with a scenario table and no run shape chosen.
Completion state is `READY_FOR_RE-VERIFICATION`, not a provider smoke test or live shadow. No paid call, no protected data, no scientific outcome; v6/v7 sealed and untouched. See `docs/research/GENERATOR_V0_LIMITED_REPAIR.md`.

## Generator V0 pre-live repair (offline) — 2026-09-23

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_PRE_LIVE_REPAIR_READY_FOR_INDEPENDENT_REVIEW` (reviewed by PR #215; see the limited repair above).
Offline repair of the audit findings behind the v4–v7 one-failure-per-run
history: per-card quarantine instead of campaign aborts, a single V02 rule
contract (prompt and validator derived from one table), decoding-level
schemas, explicit provider failure classes with reconcile, an advisory
selector, and lineage-cumulative spend (a derive from v7 keeps USD 4.946750
charged). Completion state is `READY_FOR_INDEPENDENT_REVIEW`, not ready for a
live shadow. No paid call, no protected data, no scientific outcome; v6/v7
sealed and untouched. See `docs/research/GENERATOR_V0_PRE_LIVE_REPAIR.md`.

---

## Generator V0 first-shadow-v7 fail-closed — 2026-09-23

`NEXT_UNIT = GENERATOR_V0_FIRST_SHADOW_V7_FAIL_CLOSED`.
Live first-shadow-v7 ran generation:3 under the USD 17.100000 absolute
ceiling, then fail-closed on `ambiguous protected range`. New spend
USD 1.167200; cumulative USD 4.946750. Critics and selector were not
started. Cards table remains empty. No scientific outcome. Protected
2025/2026 remain unopened. `first-shadow-v6` and `first-shadow-v7` are
sealed. Do not resume v7. Do not extend LEGAL_RANGE or the C033 exclusion
parser from observed generation:3 wrappers. Frozen design/historical
records retain their historical labels.

---

# Signalbot — Current Research State

**Status date:** 2026-09-23
**Status:** `ACTIVE / CANONICAL ROUTING INDEX`  
**Main integration baseline before this status commit:** `ea024cfee63b1dd7c917ec81b6dd39838b2fecd5`

This file is the compact answer to “what controls the project now?”. Frozen preregistrations/results remain authoritative for reproducing their own experiments; this file controls current routing only.

## Program state

| Unit | Current state | Canonical reference |
|---|---|---|
| MARKET-01 | `NO_EVIDENCE`, consumed, no rerun | `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json` |
| MARKET-02 | `NO_EVIDENCE`, consumed, no rerun | result lineage head `70f9489bd4fed905255b6791adcd23dc1e7d5dfa` |
| MARKET-03 | `REPRODUCED_DIRECTION` historical external reproduction; not internal validated alpha | RESULT `9c360a19a8e35ba0e7638fd125a0e6ae32f15846` |
| MARKET-04 / 04H | `BLOCKED_OBSERVABLE / NOT_TESTED`; not rejected | adjudication `e8d77b3b5c016582304db55c6ff2dacff92f0210` |
| MARKET-05 | `MARKET_05_NO_EVIDENCE`, consumed, no rerun | RESULT `828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b` |
| Forward observability | collector implementation frozen; authoritative collection not started by repo cleanup | `4158403b942c3ac0e2af3fb602f074f0064690fd` |
| MARKET-06 | `MARKET_06_NO_EVIDENCE`, one canonical shot consumed, no rerun | RESULT `80c7d19f622cc7b5576154de59dbb9cdf85d4dcf` |

MARKET-06 sealed identity:

- run identity: `f3aa51372594d710a8f705d761d857f8385d0b848fb0ed59a36b27a16ce25c22`;
- RESULT payload SHA256: `67f6f14c9221d3d0be2c130938f6ff8588aadc6eabc52126dd00a5fbbedd2a53`;
- classification: `MARKET_06_NO_EVIDENCE`;
- pooled relative MAE improvement: `-0.03756596483364705`, CI95 `[-0.0644801374915513, -0.014898013948610516]`;
- 2023: `-0.02814838672162434`; 2024: `-0.045320425619876925`;
- G1=true; G2-G6=false;
- protected 2025/2026 unopened.

Program-level correction is sealed in `docs/research/MARKET_PROGRAM_UPDATE_POST_M06.*`: MARKET-01 is **not** in the exact M05/M06 cell. The exact cell is repeated-null / low-priority-for-now; the broader short-horizon BTC conditional scalar-prediction family is low-priority / saturated-for-now as a search-priority judgement.

## Exact next unit

```
PREVIOUS_ROUTING            = POST_SPRINT04_AUTOMATION_MATURITY_DECISION
PREVIOUS_ROUTING_SUPERSEDED = true
R_A_CURRENT_STATUS          = DISCOVERY_SPRINT_01_D1
MARKET_07_CREATED           = false
NEXT_UNIT                   = GENERATOR_V0_MULTI_PROVIDER_ROUTING_READY_FOR_INDEPENDENT_REVIEW
NEXT_ACTION                 = INDEPENDENT_REVIEW_OF_MULTI_PROVIDER_ROUTING_NO_LIVE_RUN
POST_SPRINT04_AUTOMATION_MATURITY_DECISION = HYPOTHESIS_GENERATOR_V0_INFRA_READY
HYPOTHESIS_GENERATOR_V0_DESIGN = FROZEN_NOT_IMPLEMENTED
GENERATOR_MODE              = SHADOW_ONLY
SPRINT05_CREATED            = false
D12_CONFIRMATION_EXECUTED   = false
POST_SPRINT03_PROGRAM_DECISION = DECIDED
HETEROGENEOUS_FAMILY_ROTATION_V1 = FROZEN_HISTORICAL_SPRINT_02_POLICY
HETEROGENEOUS_FAMILY_ROTATION_V2 = FROZEN_HISTORICAL_SPRINT_03_POLICY
HETEROGENEOUS_FAMILY_ROTATION_V3 = FROZEN
DISCOVERY_SPRINT_04 = CANONICAL_SCIENTIFIC_EXECUTION_CONSUMED
DISCOVERY_SPRINT_04_INTERNAL_CARDS = 2
D12_NAME                    = PARTICIPATION_CLOCK_ANCHORING_DST_NATURAL_EXPERIMENT
D12_FAMILY                  = J_PARTICIPANT_CLOCK_ANCHORING_NEW
D12_EXECUTED                = true
D12_STATUS                  = PROMISING_PROTOTYPE
D12_CLASSIFICATION          = PROMISING_PROTOTYPE
D12_RESULT_PAYLOAD_SHA256   = 73299c8d8313c7c73f423bb83565a45e3c17da6a534dbc8dc8fbf12f943b6feb
D13_NAME                    = CROSS_SECTIONAL_WEEKLY_RELATIVE_RETURN_STRUCTURE
D13_FAMILY                  = H_TRUE_CROSS_SECTIONAL_PANEL
D13_DATA_STATUS             = CANONICAL_SCIENTIFIC_EXECUTION_CONSUMED
D13_EXECUTED                = true
D13_STATUS                  = NO_USEFUL_STRUCTURE
D13_CLASSIFICATION          = NO_USEFUL_STRUCTURE
D13_RESULT_PAYLOAD_SHA256   = c18f7de5821d8ee808732e0278afa53f622bb977d77f1ec71ee7423c96f5effd
D13_N                       = 82
D13_NO_POST_T_CLOSE_SELECTED_N = 0
D14                         = NOT_SELECTED
D11_CONFIRMATION_SELECTED_NOW = false
POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED = true
AUTOMATIC_SPRINT05          = false
DISCOVERY_SPRINT_02 = D7_EXECUTED_D8_DEFERRED
DISCOVERY_SPRINT_02_INTERNAL_CARDS = 2
DISCOVERY_SPRINT_03 = CANONICAL_SCIENTIFIC_EXECUTION_CONSUMED
DISCOVERY_SPRINT_03_INTERNAL_CARDS = 3
SPRINT03_SELECTION_INCOMPLETE = false
SPRINT04_HYPOTHESES_SELECTED = true
D7_STATUS                   = PROMISING_PROTOTYPE
D8_STATUS                   = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
D9_STATUS                   = NO_USEFUL_STRUCTURE
D10_STATUS                  = NO_USEFUL_STRUCTURE
D11_STATUS                  = PROMISING_PROTOTYPE
D9_CHOSEN_ESTIMAND          = RELATIVE_RESOLUTION_ATTRIBUTION
D9_PRIMARY_LOCATION_STATISTIC = MEDIAN_PERP_RESOLUTION_SHARE
D9_ALGEBRAIC_IDENTIFICATION_FIXED = true
D9_SCIENTIFIC_CLAIM_MAY_ESTABLISH = CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION
D9_SHARE_NOT_CLIPPED        = true
D10_FIXED_PRE_EVENT_BETA    = true
D10_REGRESSION_SPECIFICATION = NO_INTERCEPT_OLS
D11_FOMC_ONLY               = true
D11_OFFICIAL_SOURCE_PINNED  = true
MANDATE_V1_ON_MAIN          = true
D7_IMPLEMENTATION_STATUS    = EXECUTED_ONE_SHOT
D8_IMPLEMENTATION_STATUS    = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
D7_EXECUTION_AUTHORIZED     = true
D7_ONE_SHOT_RUNNER_BYTES_BOUND = true
PROVENANCE_MODEL            = AUTHORITY_PARENT_PLUS_FILE_HASHES
D7_EXECUTED                 = true
D7_CONFIRMATION_CANDIDATE   = true
D7_CONFIRMATION_SELECTED_NOW = false
D8_EXECUTION_AUTHORIZED     = false
D8_EXECUTED                 = false
D9_EXECUTED                 = true
D9_CLASSIFICATION           = NO_USEFUL_STRUCTURE
D9_SCIENTIFIC_OUTCOME_COMPUTED = true
D10_EXECUTED                = true
D10_CLASSIFICATION          = NO_USEFUL_STRUCTURE
D11_EXECUTED                = true
D11_CLASSIFICATION          = PROMISING_PROTOTYPE
D12_EXECUTED                = true
D12_CLASSIFICATION          = PROMISING_PROTOTYPE
D13_EXECUTED                = true
D13_CLASSIFICATION          = NO_USEFUL_STRUCTURE
D7_RERUN_PERFORMED          = false
DATA_IDENTITY_MODE          = TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION
D7_SELECTOR_N               = 4545
D7_SELECTOR_DIGEST_FROZEN   = true
SCIENTIFIC_OUTCOMES_COMPUTED = true
THIS_UNIT_SCIENTIFIC_OUTCOMES_COMPUTED = true
SPRINT03_SCIENTIFIC_OUTCOMES_COMPUTED = true
SPRINT04_SCIENTIFIC_OUTCOMES_COMPUTED = true
RESEARCH_DATA_DURABILITY_V1_REQUIRED = true
D2_DECOMPOSITION_DESIGN_STATUS = FROZEN
D2_DECOMPOSITION_IMPLEMENTATION_REVIEW = PASS
D2_DECOMPOSITION_SCIENTIFIC_KERNEL_READY = true
D2_DECOMPOSITION_CANONICAL_ORCHESTRATION_READY = true
D2_DECOMPOSITION_PERMIT_VERIFIER_READY = true
D2_DECOMPOSITION_EXACT_SELECTOR_IDENTITY_IMPLEMENTED = true
D2_DECOMPOSITION_IMPLEMENTATION_REVIEW_CANONICAL_SELECTOR_DIGEST_FROZEN = false
D2_DECOMPOSITION_SELECTOR_IDENTITY_AUTHORITY = FROZEN
D2_DECOMPOSITION_CANONICAL_SELECTOR_DIGEST_FROZEN = true
D2_DECOMPOSITION_SELECTOR_IDENTITY_AUTHORITY_CREATED = true
D2_DECOMPOSITION_EXECUTION_READY   = false
D2_DECOMPOSITION_EXECUTION_AUTHORIZED = true
D2_DECOMPOSITION_EXECUTION_PERMIT_CREATED = true
D2_DECOMPOSITION_ONE_SHOT = true
D2_DECOMPOSITION_RERUN_AUTHORIZED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = true
RESULT_CREATED = true
D2_DECOMPOSITION_CLASSIFICATION_ASSIGNED = D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT
D2_DECOMPOSITION_ONE_SHOT_CONSUMED = true
D2_PROGRAM_CLASS            = INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE
BINANCE_2025_2026_DECISION  = KEEP_SEALED
PRODUCT_BUILD_FROZEN        = true
HYPOTHESIS_GENERATION_POLICY = HETEROGENEOUS_FAMILY_ROTATION_V3
PROTECTED_2025_OPENED       = false
PROTECTED_2026_OPENED       = false
INTERNAL_DISCOVERY_CARDS_EXECUTED = 10
INTERNAL_PROMISING_PROTOTYPES     = 4
INTERNAL_DISCOVERY_WARNING        = null
INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED = false
FULL_DISCOVERY_CARDS_COMPLETED    = 5
PARTIAL_COMPONENT_OUTCOMES_OBSERVED = 1
PARTIAL_COMPONENT_OUTCOMES        = D2/RULE_2/DISLOCATION_ABSTENTION
D2_RULE_2_DISCOVERY_OUTCOME_OBSERVED = true
D2_RULE_2_GATE_PASS               = false
D2_RULE_2_REPLAY_EXACT_MATCH      = true
POST_OUTCOME_DESIGN_CHANGES       = false
D1_STATUS                         = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH
D2_DISCOVERY_STATUS               = PROMISING_PROTOTYPE
CONFIRMATION_FEASIBILITY          = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION
2025_OPEN_AUTHORIZED              = false
2026_OPEN_AUTHORIZED              = false
ARM_CREATED                       = false
D2_OUTCOME_COMPUTED_ON_BITMEX     = true
D2_BITMEX_CLASSIFICATION          = D2_BITMEX_REPLICATION_SUPPORTED
D2_BITMEX_ADJUDICATION_CLASS      = REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH
D2_BITMEX_CONSTRUCTED_ELIGIBLE_N  = 1067
D2_BITMEX_FROZEN_ELIGIBLE_N       = 1069
CORRECTED_EXPECTED_N              = 1067
ORIGINAL_RUN_CLASSIFICATION       = D2_BITMEX_REPLICATION_INVALID
ORIGINAL_RERUN_AUTHORIZED         = false
CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE = true
D2_REPLICATION_STATUS             = SUPPORTED_ON_INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_SURFACE
RERUN_AUTHORIZED                  = false
PROTECTED_2025_PRICE_VALUES_INSPECTED = false
PROTECTED_2026_PRICE_VALUES_INSPECTED = false
```

Post-Sprint 03 program decision (`docs/research/POST_SPRINT03_PROGRAM_DECISION.{json,md}`):
D9/D10 consumed `NO_USEFUL_STRUCTURE` (no rescue), D11 consumed
`PROMISING_PROTOTYPE`; D7/D11 confirmation not selected now because the
bottleneck is mechanism-space coverage. All three prototypes are
volatility/activity-level structures, so Sprint 04 selects no
volatility-level card. Policy is `HETEROGENEOUS_FAMILY_ROTATION_V3`
(new family J). Sprint 04 (`docs/research/DISCOVERY_SPRINT_04.{json,md}`)
selects D12 (participation-clock anchoring, DST natural experiment,
existing CORE BTC) and D13 (first true cross-sectional panel, weekly
relative return, bounded free Binance Vision acquisition). D14 not
selected. After Sprint 04 execution a post-Sprint 04 automation maturity
decision is required; there is no automatic Sprint 05.

Post-Sprint 04 automation maturity decision
(`docs/research/POST_SPRINT04_AUTOMATION_MATURITY_DECISION.{json,md}`):
`HYPOTHESIS_GENERATOR_V0_INFRA_READY`. No Sprint 05. Four prototypes but
two effective classes (D2/D7/D11 second-moment/activity; D12 participation
timing). Datasets are not expanded ahead of the generator; its data-gap
ledger measures demand first. Generator V0 design is frozen, not built
(`docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.{json,md}`): shadow-only,
blind to outcomes, provider-neutral, mock mode required, USD 30 cap for
the first real campaign.

Discovery Sprint 01 first attempt (`37921089ce289cd9bcbcebb123724a3e033dcdc3`)
is preserved as blocked: D2/D3/D4 rolling/D5 were
`BLOCKED_MISSING_LOCAL_DATA`; D2 RULE_2 was a partial component outcome
(`GATE_PASS=false`), not a completed card.

After restoring frozen CORE BTC/ETH 2020-2024 only, the same
implementation `26d8f7066533bcae7138d5a1952783f2a16f3c39` was retried.
Preflight BTC/ETH/M06 all present. D2 RULE_2 replayed exactly. Retry
classifications: D2 `PROMISING_PROTOTYPE` (RULE_1 gate pass; RULE_2
still fails), D3/D4/D5 `NO_USEFUL_STRUCTURE`. Adaptive discovery only;
not confirmatory. Protected 2025/2026 unopened. MARKET-07 not created.
No post-outcome design changes.

D1 was then adjudicated for `D1_NULL_ADEQUACY_GATE` and **deferred**:
the frozen daily GARCH null cannot generate the 288×5m `ev.rv_btc_24h`
observable used by `RV_20`, and no already-frozen mapping exists. The
gate was not executed. Independently, gate statistics remain
underspecified. `D1_STATUS = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`.
Deferred D1 is not counted as executed. D6 remains `DEFERRED`.
D4 `LEAD_LAG_1DAY` remains `DEFERRED_FROM_SPRINT_01`.

Result records: `docs/research/discovery_results/`.
Adjudication record: `docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.{json,md}`.

D2 RULE_1 (`RV_ABSTENTION`) was then taken through
`D2_CONFIRMATION_FEASIBILITY_AND_DESIGN` without opening 2025/2026
prices or creating MARKET-07/ARM. Calendar 2025 is the proposed first
independent confirmation surface; 2026 remains a second reserved
surface. Metadata-only 2025 monthly source/canonical hashes are bound.
A 2020-2024 power calculation at the predeclared 20% true effect
returned year-cycled `ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011`
(joint pass probability `0.006` is diagnostic only; practical-gate
power `~0.499` at the exact 20% boundary is expected and is not
underpower evidence). Primary prospective criterion is statistical
power `>= 0.80`. `CONFIRMATION_FEASIBILITY = UNDERPOWERED_SINGLE_YEAR_2025`.
IID two-year power `0.903` is superseded. Authoritative
year-matched whole-year-block plus contiguous partial-block power
gives `POWER_N728 = 0.64 < 0.80` and `POWER_N1092 = 1.0`.
`MIN_REQUIRED_FRESH_DECISION_ROWS = 1092`.
`POTENTIAL_FUTURE_SURFACE = MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE`.
`AUTHORIZED_TO_OPEN = false`. `2025_OPEN_AUTHORIZED = false`.
Do not consume 2025+2026. Full calendar 2026 is not currently available.
Record: `docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.{json,md}`.

`D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY` then tested whether the
same frozen RULE_1 / RV_ABSTENTION mechanism can be replicated on pre-2020
BitMEX XBTUSD without waiting for future Binance data and without opening
2025/2026. Refined year-matched power on exposed 2020-2024 only gives
`MIN_REQUIRED_FRESH_DECISION_ROWS = 815` (point-estimate power `0.801`).
Official BitMEX 5m buckets yield `BITMEX_PRE2020_ELIGIBLE_N = 1069` legal
decision rows whose 24h outcomes finish before 2020-01-01. Contract
compatibility is `SCIENTIFICALLY_COMPARABLE_CROSS_VENUE` (price-path MAE,
not inverse PnL). No D2 outcome was computed on BitMEX.
`CONFIRMATION_FEASIBILITY = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION`.
A later BitMEX result, if executed, is
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`, not exact Binance
confirmation. Protected 2025/2026 remain sealed.
Record: `docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.{json,md}`.

`D2_BITMEX_REPLICATION_PREREG_FREEZE` then froze the outcome-blind
replication contract without executing it. Evidence class
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`. Rule, target,
clock, year-matched comparator, 10000-replicate seed `20260921125`,
statistical `MU_RULE > CONTROL_P95`, and practical
`DELTA >= 0.20 * UNCONDITIONAL_MEAN` are bound. Mechanical census
reproduced `N=1069`, first `2017-01-24T00:05:00Z`, last
`2019-12-30T00:05:00Z`. Classification unassigned. No BitMEX D2 outcome.
Protected 2025/2026 unopened. MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_PREREG.{json,md}`.

`D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW` then
replaced the firewalled stub evaluator with a reviewed execution
implementation without computing BitMEX outcomes. Timestamp census still
reproduces `N=1069`. Execution remains unauthorized: no permit exists.
`IMPLEMENTATION_REVIEW = PASS`. `EXECUTION_READY = true`.
`EXECUTION_AUTHORIZED = false`.
Record: `docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.{json,md}`.

`D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION` then created the immutable
permit and executed once. Timestamp census still matches frozen
`N=1069` / `2017-01-24T00:05:00Z` / `2019-12-30T00:05:00Z` /
years `341/364/364`. Constructed eligible rows after frozen
`construct_discovery_row` were `N=1067` (years `341/363/363`). The
sample-identity gate therefore classified
`D2_BITMEX_REPLICATION_INVALID`. Primary MU_RULE / control metrics were
not computed. This is not `NOT_SUPPORTED` and not a rescue. No rerun.
Protected 2025/2026 unopened. MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_RESULT.{json,md}`.

`D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION` then identified the two
dropped timestamp-complete decisions as predeclared `BTC_RET_24H_EQ_0`
ineligibility. Class
`REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH`. Original INVALID
run preserved. No D2 effect computed. Corrected eligible N=1067; first/last
T unchanged. Original rerun unauthorized. A new integrity-repair lineage
is scientifically permissible; no permit yet.
Record: `docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.{json,md}`.

`D2_BITMEX_REPLICATION_CORRECTED_ONE_SHOT_EXECUTION` then created the
integrity-repair permit and executed once under NEW_RUN_IDENTITY
`8e3e9ecfadc18f71dae800cd16d0b0b36845c17710a108a0258c833af0420b43`.
Corrected identity passed: constructed `N=1317`, warmup `250`, eligible
`N=1067` (years `341/363/363`), first `2017-01-24T00:05:00Z`, last
`2019-12-30T00:05:00Z`. The two `BTC_RET_24H_EQ_0` rows remain excluded.
Original INVALID run preserved; primary metrics were computed only after
the amended identity gate. Classification
`D2_BITMEX_REPLICATION_SUPPORTED`. Evidence label
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED`. This is
not `EXACT_BINANCE_CONFIRMATION`, `PROVEN_ALPHA`, or
`VALIDATED_TRADING_EDGE`. No rerun. Protected 2025/2026 unopened.
MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.{json,md}`.

`PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED` then classified D2
as `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`. Discovery claim and
independent pre-2020 BitMEX replication claim are supported. Market-mechanism,
trading-edge, and product claims are not. Protected 2025/2026 remain sealed.
Hypothesis generation now rotates across families A–I; D2 neighbors are
forbidden. Product build remains frozen. MARKET-07 not created.
Record: `docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.{json,md}`.
That unit's next step was
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`
then froze an outcome-blind post-replication mechanism-decomposition
contract without executing it. Selector remains frozen D2 / RULE_1 /
`RV_ABSTENTION`. Primary target is `ADVERSE_SHARE = MAE_SIDE /
(MAE_SIDE + MAE_OPPOSITE)` on the same 24h path, versus year×SIDE-matched
rate-matched random abstention (`N=10000`, seed `20260922131`). A
pre-outcome correction replaced year-only matching with
`YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION` so candidate LONG/SHORT
composition cannot confound `ADVERSE_SHARE`. Evidence
class is `POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY`, not
independent confirmation. BitMEX 2017-2019 is not reused for this new
target. Protected 2025/2026 unopened. MARKET-07 not created. No real
decomposition outcome.
Record: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.{json,md}`.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`
then implemented that frozen design and reviewed it adversarially
**without executing the decomposition**. The design was not redesigned:
selector, SIDE, target, comparator, strata, seed, gates, thresholds and
classification order are imported from the frozen design module, not
reimplemented. The one new mechanical part is future-path reconstruction —
`DiscoveryRow` stores `future_closes` only, so the evaluator re-walks the
exact 288 5m `PerpBar` path and calls frozen `arithmetic_mae` twice on
that one shared sequence, cross-checking recomputed `MAE_SIDE`
bit-for-bit against the frozen `DiscoveryRow.severity`. Target
ineligibility (`TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE`, no
epsilon) never rebuilds the selector and is reported per year. Twenty
red-team failure classes (F1-F20) returned `NOT_CONFIRMED`; PASS is
justified by implemented/tested machinery, not by a hardcoded table.
Integrity repair closed dormant canonical orchestration, tracked-permit
authority verification, exact ordered selector-identity machinery, and
the inherited D2 NumPy linear P95 method. `IMPLEMENTATION_REVIEW = PASS`,
`SCIENTIFIC_KERNEL_READY = true`, `CANONICAL_ORCHESTRATION_READY = true`,
`PERMIT_VERIFIER_READY = true`, `EXACT_SELECTOR_IDENTITY_IMPLEMENTED = true`,
`CANONICAL_SELECTOR_DIGEST_FROZEN = false`, `EXECUTION_READY = false`,
`EXECUTION_AUTHORIZED = false`. The canonical route now requires a tracked
selector-identity authority (permit-bound SHA256) and compares the
reconstructed ordered digest to that frozen digest before any
ADVERSE_SHARE / PATH_SCALE evaluation. The authority artifact was **not**
created in the implementation-review unit.
Record: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REVIEW.{json,md}`.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE`
then reconstructed the frozen RULE_1 / RV_ABSTENTION identity from legal
CORE BTC 2020-2024 and wrote the tracked authority
`docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_SELECTOR_IDENTITY.json`.
Constructed N=1791 / years 334,364,364,364,365; abstain N=163 / years
10,48,32,23,50. No ADVERSE_SHARE, PATH_SCALE, permit, or RESULT was
computed. Distinguish:

```
IMPLEMENTATION_REVIEW_AT_TIME: CANONICAL_SELECTOR_DIGEST_FROZEN = false
CURRENT STATE: SELECTOR_IDENTITY_AUTHORITY = FROZEN
CURRENT STATE: CANONICAL_SELECTOR_DIGEST_FROZEN = true
```

The evaluator module constant remains `false` (review-unit truth). Current
lifecycle truth is the verified authority.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION` commit 1 then
wrote the tracked execution permit
`docs/research/D2_EXCESS_PATH_RISK_EXECUTION_PERMIT.json` (exactly
`EV.tracked_permit_expected_authority`) and the outcome-blind one-shot
runner `scripts/research/d2_excess_path_risk_one_shot.py`. Evaluator-module
`EXECUTION_AUTHORIZED` remains `false` (review-era). Tracked-permit
`EXECUTION_AUTHORIZED = true`.

The exact permit commit `29f83a102bd8ece2b078f65ef69a578a52812c7c` was then
executed once. Canonical RESULT:
`docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.{json,md}`.
Evaluator classification (not reinterpreted):
`D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`.
`STATISTICAL_GATE = false`, `PRACTICAL_GATE = false`,
`TEMPORAL_GATE = true`, `PATH_SCALE_MATERIALLY_ELEVATED = true`.
No rerun. 2025/2026 remain sealed. BitMEX 2017-2019 was not reused for
this target. MARKET-07 was not created. D2 program class remains
`INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE` from the independent
pre-2020 BitMEX surface; this decomposition does not promote a robust
excess-alignment claim and does not authorize 2025/2026 open.

```
SELECTOR_IDENTITY_AUTHORITY = FROZEN
EXECUTION_PERMIT_CREATED = true
EXECUTION_AUTHORIZED = true
ONE_SHOT = true
RERUN_AUTHORIZED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = true
RESULT_CREATED = true
CLASSIFICATION = D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT
RESULT_PAYLOAD_SHA256 =
  53ce2e20064671f5ae26c9174e77e52986fba8619263b3015143dce4aa874b81
NEXT_ACTION = CONTINUE_ORTHOGONAL_FAMILY_ROTATION
NEXT_UNIT = HETEROGENEOUS_FAMILY_ROTATION_V1
```

`HETEROGENEOUS_FAMILY_ROTATION_V1` was then frozen and applied as
`DISCOVERY_SPRINT_02_HETEROGENEOUS_CARD_DEFINITION`: exactly two internal
cards, D7 `KLINE_FLOW_IMPACT_STATE` (family E, kline proxy only) and D8
`ENDOGENOUS_SHOCK_RECOVERY` (family G). Neither card is executed.
F remains `DEFERRED_BLOCKER_UNRESOLVED`; H `DEFERRED_DATA_LIMITATION`;
I `DEFERRED_SOURCE_NOT_PINNED`. Record:
`docs/research/HETEROGENEOUS_FAMILY_ROTATION_V1.{json,md}` and
`docs/research/DISCOVERY_SPRINT_02.{json,md}`.
D8 primary control is `RETURN_SHOCK_MATCHED_NON_HIGH_ACTIVITY_CONTROL`
(same P99 return-shock gate; fails only P90 volume). Recovery clock is
frozen at `EVENT_DECISION_T = H+1h` with a strict
`EVENT_DECISION_T + 6h < 2025-01-01T00:00:00Z` bound. D7 unchanged.

Sprint 02 feasibility/implementation then ran selector/support census
only on legal CORE BTC 2020-2024. D7 is `OUTCOME_BLIND_READY`. D8 is
`DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` (event support passed; 1:1
return-shock controls did not). No scientific outcomes. An outcome-blind
integrity pass then formalized
`DATA_IDENTITY_MODE = TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION`
(runtime snapshot manifest is not required), froze D7 selector identity
`N=4545` / digest `8794fece…`, and recorded D8 as final non-executable
for this card (`NOT D8_NO_USEFUL_STRUCTURE`; recovery unevaluated).
Record: `docs/research/DISCOVERY_SPRINT_02_FEASIBILITY.{json,md}` and
`docs/research/DISCOVERY_SPRINT_02_IMPLEMENTATION_REVIEW.{json,md}`.
`NEXT_UNIT = DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION` (D7-only).
The D7 one-shot scientific execution route was then executed once from
execution root `0f22d46ab0ee41be78cb45de39842c8a5684b54e`. Canonical
RESULT `docs/research/DISCOVERY_SPRINT_02_D7_RESULT.{json,md}` classified
`D7_PROMISING_PROTOTYPE` (`STATISTICAL_GATE`, `PRACTICAL_GATE`, and
`TEMPORAL_GATE` all true; yearly delta positive in 2020–2024). Evidence
label remains `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`. Not
independent confirmation, proven alpha, a validated trading edge, or an
order-book liquidity claim. No rerun. D8 remains
`DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` and is not a negative scientific
result. Protected 2025/2026 unopened. MARKET-07 not created.

`POST_D7_PROGRAM_UPDATE_AND_DISCOVERY_SPRINT_03_SELECTION` then recorded
those counters (`INTERNAL_DISCOVERY_CARDS_EXECUTED = 5`,
`INTERNAL_PROMISING_PROTOTYPES = 2`) and froze
`HETEROGENEOUS_FAMILY_ROTATION_V2`. A pre-outcome amendment (this
status) keeps D7/D8 routing, rebases onto `origin/main` `35511b3`
(`SIGNALBOT_MANDATE_V1` canonical), and expands Sprint 03 to **three**
orthogonal internal cards after `MECHANISM_MEMORY_V0`:

- D9 `VENUE_DISLOCATION_RESOLUTION_STRUCTURE` (family H; `DATA_READY`;
  estimand A `RELATIVE_RESOLUTION_ATTRIBUTION` / `CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION`;
  unclipped SHARE; old `-s*(rp+rs)` imbalance rejected);
- D10 `BTC_ETH_RESIDUAL_SHOCK_PERSISTENCE` (family D; `DATA_READY`;
  frozen pre-event `beta_t` reused at t+1);
- D11 `SCHEDULED_FOMC_EVENT_VOL_RESPONSE` (family G;
  `ACQUIRABLE_FREE_HISTORICAL`; official FOMC calendar only).

`SPRINT03_SELECTION_INCOMPLETE = false`. Family E remains in cooldown.
D7 remains a confirmation candidate but is **not** selected for
confirmation now. `RESEARCH_DATA_DURABILITY_V1` is required (CORE BTC
bytes live in gitignored `artifacts/` without a verified object-storage
restore path) and is **not** implemented in this unit.

The Sprint 03 canonical scientific execution then ran once from
`EXECUTION_ROOT = e2852f57ee946ec8380f09fa4cf834579c40f872`
(`EXPECTED_TREE = 8805ee7d39b29c267589e7f9400384ebdb1f66ca`).
Classifications (frozen predicates; not rescued):

- D9 `NO_USEFUL_STRUCTURE`
- D10 `NO_USEFUL_STRUCTURE`
- D11 `PROMISING_PROTOTYPE`

Counters: `INTERNAL_DISCOVERY_CARDS_EXECUTED = 8`,
`INTERNAL_PROMISING_PROTOTYPES = 3`. Sprint 04 hypotheses are **not**
selected here. D7 was not rerun. D8 was not executed. MARKET-07 was not
created. Protected 2025/2026 remain sealed.
`NEXT_UNIT = DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION`.

### SPRINT03_INFORMATION_GAIN

D9 `NO_USEFUL_STRUCTURE`:

- WHAT_THIS_RESULT_SUPPORTS: the frozen SHARE-on-closing-extremes
  formulation did not pass the discovery gate.
- WHAT_THIS_RESULT_DEPRIORITIZES: this SHARE formulation. Do not rescue
  with clipping or leadership relabel.
- WHAT_REMAINS_OPEN: orthogonal families already recorded. Not
  PRICE_DISCOVERY_LEADERSHIP.

D10 `NO_USEFUL_STRUCTURE`:

- WHAT_THIS_RESULT_SUPPORTS: the frozen residual-persistence formulation
  did not pass the discovery gate.
- WHAT_THIS_RESULT_DEPRIORITIZES: this residual-persistence formulation.
  Do not add post-hoc refractory or block bootstrap. Does not validate
  MARKET-05.
- WHAT_REMAINS_OPEN: orthogonal families already recorded.

D11 `PROMISING_PROTOTYPE`:

- WHAT_THIS_RESULT_SUPPORTS: a discovery-stage unsigned BTC 6h RV
  elevation after scheduled FOMC announcements. Worth considering for
  later confirmation. Not validated alpha, not a trading edge, not a
  confirmed mechanism, not causal proof.
- WHAT_THIS_RESULT_DEPRIORITIZES: does not rescue D8. Does not authorize
  CPI/NFP/ECB substitution.
- WHAT_REMAINS_OPEN: independent confirmation; N=39 is the frozen
  scheduled-FOMC family size.

Do not alter hypothesis-generation philosophy from one result. Do not
create neighbor-rescue hypotheses.

### SPRINT04_INFORMATION_GAIN

The Sprint 04 canonical scientific execution ran once from
`EXECUTION_ROOT = d2a62da6e5c907def603a258505b9cc1f92ae3a5`
(`EXPECTED_TREE = 3c5c5262db5c1313c8d5c712c0d1658f32da0edb`) after the
tracked permit commit. Classifications (frozen predicates; not rescued):

- D12 `PROMISING_PROTOTYPE`
- D13 `NO_USEFUL_STRUCTURE`

Counters: `INTERNAL_DISCOVERY_CARDS_EXECUTED = 10`,
`INTERNAL_PROMISING_PROTOTYPES = 4`. D7 was not rerun. D8 was not
executed. D7/D11 confirmation was not executed. MARKET-07 was not
created. Protected 2025/2026 remain sealed.
`AUTOMATIC_SPRINT05 = false`.
`NEXT_UNIT = POST_SPRINT04_AUTOMATION_MATURITY_DECISION`.

D12 `PROMISING_PROTOTYPE`:

- WHAT_THIS_RESULT_SUPPORTS: BTC Binance 2020-2024 intraday quote-volume
  timing exhibits the frozen US-clock anchoring pattern
  (`MEAN_A = 0.1335535649302866`; `MC_P = 9.999000099990002e-05`;
  practical and temporal gates true). Worth considering for later
  confirmation. Not validated alpha, not a trading edge, not a confirmed
  mechanism, not causal proof.
- WHAT_THIS_RESULT_DEPRIORITIZES: does not identify participants, ETFs,
  equity-session causality, direction, trading alpha, or volatility.
  Does not rescue D11. EU diagnostic `MEAN_A = -0.17392447104949169`
  does not promote or demote D12 (`EU_DIAGNOSTIC_AFFECTS_CLASSIFICATION
  = false`).
- WHAT_REMAINS_OPEN: independent confirmation. Do not try W=5/W=7,
  another volume field, trade count, selected UTC hours, or EU as
  primary.

D13 `NO_USEFUL_STRUCTURE`:

- WHAT_THIS_RESULT_SUPPORTS: the frozen 1-week liquid Binance spot USDT
  panel relative-return formulation did not pass the discovery gate.
  Observed pooled sign is REVERSAL (`MEAN_WEEKLY_IC =
  -0.027440631083253317`; `POOLED_IC_SIGN = -1`). Statistical and
  temporal gates true; practical gate false because the same-sign
  top-vs-bottom quintile spread
  (`SIGNED_TOP_BOTTOM_SPREAD = -0.007875047071699056`) is below the
  friction floor `0.004`.
- WHAT_THIS_RESULT_DEPRIORITIZES: this 1-week frozen-panel formulation.
  Do not pick the larger of momentum vs reversal. Do not try 2w/4w,
  skip-week, top 50/100, alternate exclusions, winsorization, vol
  scaling, sector filter, beta-neutralization, or another exchange.
- WHAT_REMAINS_OPEN: orthogonal families already recorded. Residual
  weekly IC serial dependence remains a declared discovery-stage
  limitation, not a rescue path.

Do not automatically create Sprint 05. Do not build the hypothesis
generator in this unit. The next unit must decide
`HYPOTHESIS_GENERATOR_V0_INFRA_READY` vs `AT_MOST_ONE_FINAL_SPRINT05`.

All six Discovery Sprint 01 cards (D1-D6) were converted to frozen
`EXECUTABLE_DISCOVERY_SPEC` records (none deferred) by
`DISCOVERY_SPRINT_01_SPEC_COMPILATION`, recorded in
`docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`. That unit
is an outcome-blind spec freeze, not a confirmatory lifecycle: no ARM, no
claim/reservation, no one-shot execution authority. At compilation time
no discovery outcome had been computed. The first partial batch is
preserved as blocked; the CORE-restore retry completed D2-D5 as recorded
in the next-unit box above.

**Superseded by `DISCOVERY_SPRINT_01_RED_TEAM_REVIEW`** (reviewed commit
`7bb92b0bd6238693164b6592c0711fa4c15fc9fe`,
`docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.{json,md}`), which
checked whether each frozen spec was actually mechanically executable, not
merely well-worded. Seven suspected defects (F1-F7) were reviewed
outcome-blind: F1, F2, F3, F4, F6 were confirmed and fixed (per-rule legal
intervals + bound cross-venue dataset authority for D2/D5's
dislocation-based rule; an explicit base exposure schedule for D2/D5; a
corrected native-5m-granularity null for D3, replacing a mechanically
broken daily-granularity reuse; a corrected split null for D4's lead-lag
vs. rolling-correlation functionals; a corrected variance-level RV_20
formula for D1). F5 found D1's null defensibility had been asserted, not
verified -- a `D1_NULL_ADEQUACY_GATE` (non-target summary statistics only)
is now defined but not yet executed. F7 found D6's external benchmark has
at most one testable historical episode given `CORE_BTC_BINANCE_V0`'s
2020 start versus the source's 2013/2017/2021 claims, judged
diagnostically insufficient.

**Superseded again by `DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4`**
(reviewed commit `355a1657aac288fe75b272df1845fd9b5cfcac3f`,
`docs/research/DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4.{json,md}`),
D3 and D4 only; D1, D2, D5, D6 unchanged from the red-team review above.
D3's excursion functionals were direction-aligned via `BTC_SIDE(t)`,
contradicting its own `UNCONDITIONAL_DESIGN` label and risking
smuggled-in directional-predictability structure; redefined as genuinely
unsigned (`MAX_UPSIDE_EXCURSION_24h`, `MAX_DOWNSIDE_EXCURSION_24h`,
`TIME_TO_MAX_EXCURSION`, `PATH_ASYMMETRY`). D3's null was also found to
ignore UTC time-of-day -- since every MARKET-06 decision point shares the
same fixed UTC decision time, bar-offset structurally equals
time-of-day, making `TIME_TO_MAX_EXCURSION` a near-certain seasonality
confound -- corrected to a time-of-day-stratified block bootstrap. D4's
`INDEPENDENT_BLOCK_BOOTSTRAP` lead-lag null was found to also destroy
ordinary same-time common-factor dependence, not just the tested cross-lag;
`LEAD_LAG_1DAY` is now `DEFERRED_FROM_SPRINT_01` (no complex replacement
null invented), `ROLLING_CORRELATION_90D` retained unchanged.

**Superseded once more by `DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX`**
(reviewed commit `475072d22f4c4631836ca7d38ccdc5da6ce59222`,
`docs/research/DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX.{json,md}`),
D3, D4's practical-threshold semantics, and D5 only; D1 and D6 unchanged.
D3's real functionals used 5m HIGH/LOW while its surrogate only ever
produced a close-to-close path -- a real/null observable mismatch, fixed
(without inventing synthetic high/low) by redefining D3 as CLOSE-PATH
morphology: `MAX_UPSIDE_CLOSE_24H`, `MAX_DOWNSIDE_CLOSE_24H`,
`TIME_TO_MAX_ABS_CLOSE_EXCURSION` (exactly 3 functionals; `PATH_ASYMMETRY`
removed, since the original card allowed at most 2-3 and it is derivative
of the other two anyway). D4's `ROLLING_CORRELATION_90D` practical gate
made mathematically exact: `PRACTICAL_EXCESS_RANGE =
OBSERVED_CORRELATION_RANGE - NULL_RANGE_MEDIAN >= 0.15`. D5's
"beats best component" check corrected to compare against
`COMPONENT_A_DELTA_FOR_D5` / `COMPONENT_B_DELTA_FOR_D5` (both evaluated
on D5's exact common interval `2022-02-01 -> 2025-01-01`), not D2
RULE_1's unrestricted full-2020-2024 result.

**Current per-card status:** `D1 = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`
(adequacy gate not executed); `D2 = PROMISING_PROTOTYPE` (adaptive
discovery; RULE_1 only; corrected independent pre-2020 BitMEX replication
classified `D2_BITMEX_REPLICATION_SUPPORTED`; program class
`INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`; original INVALID run
preserved; not exact Binance confirmation and not a validated trading
edge);
`D3 = NO_USEFUL_STRUCTURE`; `D4
ROLLING_CORRELATION_90D = NO_USEFUL_STRUCTURE` (`LEAD_LAG_1DAY` still
deferred); `D5 = NO_USEFUL_STRUCTURE`; `D6 = DEFERRED`;
`D7 = PROMISING_PROTOTYPE` (adaptive discovery; family E cooldown; not
selected for confirmation now); `D8 = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`
(not a negative scientific result; not counted as executed);
`D9 = NO_USEFUL_STRUCTURE` (family H venue-structure; consumed one-shot;
SHARE-on-closing-extremes did not pass discovery gates; do not rescue);
`D10 = NO_USEFUL_STRUCTURE` (family D; consumed one-shot; residual
persistence did not pass discovery gates; do not add post-hoc refractory);
`D11 = PROMISING_PROTOTYPE` (family G; consumed one-shot; unsigned
scheduled-FOMC 6h RV; N=39; not D8 rescue; not a FOMC trading strategy);
`D12 = PROMISING_PROTOTYPE` (family J; consumed one-shot; US-clock
quote-volume anchoring on CORE BTC; EU diagnostic does not classify;
not participant identity, ETF/equity causality, direction, or D11 rescue);
`D13 = NO_USEFUL_STRUCTURE` (family H true panel; consumed one-shot;
observed pooled IC sign REVERSAL; practical gate failed vs friction
floor 0.004; do not pick the larger of momentum vs reversal).
First blocked Sprint 01 attempt preserved. D2–D5 and D7 scientific bytes
unchanged. Sprint 03 implementation freeze bytes unchanged. Sprint 04
scientific implementation hashes unchanged after the permit commit.

The orthogonal-region selection is recorded in
`docs/research/MARKET_NEXT_HYPOTHESIS_SELECTION.{json,md}` (commit
`a711086c36eb7129fc3f0660732049de93dd1629`) and remains a valid historical
record: R-A was chosen because it materially changes the FUNCTION axis
(scalar outcome prediction -> state detection), does not rescue
MARKET-05/06, and is feasible with existing point-in-time price data. That
selection is **preserved, not retracted**.

A later, separate program-level decision recorded in
`docs/research/HYPOTHESIS_DISCOVERY_PIPELINE_V2.{json,md}` and
`docs/research/DISCOVERY_SPRINT_01.{json,md}` **supersedes only the
routing** that followed from a711086 (i.e. turning R-A directly into the
next confirmatory research unit). Signalbot has strong
falsification/validation machinery but `INTERNAL_PROMISING_PROTOTYPES = 0`
across MARKET-01/02/05/06; MARKET-03 is external reproduction, not internal
discovery. R-A is therefore reclassified as `DISCOVERY_SPRINT_01 / D1 =
STRUCTURAL_STATE_DETECTION`: it is explored first as one of six cheap,
outcome-inspecting, non-evidentiary discovery cards (D1-D6), not
immediately preregistered as a confirmatory hypothesis. R-A's null-model
risk (surrogate/null must preserve lower-order structure, chosen
outcome-blind) carries over unchanged into card D1.

a711086's statement that R-B and R-F "need a fresh evaluation surface that
does not exist" is now scoped to **confirmatory** use only.
`DISCOVERY_FEASIBILITY != CONFIRMATORY_FEASIBILITY`: both may be explored
under adaptive discovery on historically exposed 2020-2024 data (cards D2
and D5 respectively), but any resulting pattern remains exploratory and
requires an independent future confirmation surface, and D5 (R-F) carries
an explicitly recorded HIGH rescue/multiple-testing risk. R-C is still the
most orthogonal region but has no panel data and no listing/delisting
reconstruction (see the `CROSS_SECTIONAL_PANEL_FEASIBILITY` sidecar in
`DISCOVERY_SPRINT_01`). R-D and R-E remain forward-collection only.

Do not create MARKET-07. `DISCOVERY_SPRINT_01_CARD_EXECUTION` must stop and
require a program-level decision if, after 6-10 materially orthogonal
internal discovery cards, `INTERNAL_PROMISING_PROTOTYPES == 0`.

### Historical surface exposure

2020-2024 is a **historically exposed/adapted program research surface**:
H01/H02 and further H/BATCH work adapted on 2020-02-01 -> 2025-01-01 with
outcome inspection allowed, and MARKET-01/02/05/06 consumed confirmatory
windows inside it. A chronological split inside 2020-2024 must be called
"chronological held-out evaluation on historically exposed research data",
never out-of-sample or independent confirmation. The earlier claim that
2020-2021 was unconsumed is retracted.

## Hard boundaries

- no MARKET-05 or MARKET-06 rescue, sign flip, venue swap, threshold tweak, horizon tweak, or rerun;
- no opening protected 2025/2026 merely to search for a survivor;
- no V4;
- B2-06 remains blocked;
- product build remains frozen until evidence justifies a concrete restart.

For detailed history use `docs/RESEARCH_LEDGER.md`; for immutable experiment semantics use each experiment's frozen artifacts.
