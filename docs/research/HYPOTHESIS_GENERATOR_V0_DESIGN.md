# Hypothesis Generator V0 — Design (frozen, not implemented)

**Status:** `FROZEN_NOT_IMPLEMENTED` · **Mode:** `SHADOW_ONLY`
**Base:** `origin/main` `547693ce9d725d7aa6f61b107472cd8c2083ad4f`
**Machine-readable record:** `docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json` (authoritative)

## Purpose

Reduce the active human effort needed to produce high-quality,
mechanistically distinct, falsifiable research cards. Target: about 70–80%
less human discovery effort without lowering scientific quality. It is not
an alpha generator and not a trader; it proposes research questions.

In shadow mode nothing it proposes is executed, promoted, allowed to open
protected data, allowed to change research contracts, allowed to acquire
data, or allowed to make trading/product claims.

## Blind generation

The generator must search mechanism space, not chase previous positives.
There is no role-agnostic "full governance context": every role gets
exactly the artifacts its row in the role context matrix allows (below).

### `BLIND_MECHANISM_MAP_V0` (generator view)

Derived from `MECHANISM_MEMORY_V0`:

- **Whitelisted fields only:** `ID`, `MECHANISM`, `INFORMATION_SOURCE`,
  `FUNCTION`, `TARGET_FAMILY`.
- **Excluded fields:** evidence class, what was tested, what it
  deprioritizes, what remains open, rescue warnings, post-hoc residuals,
  data state, generation.
- **Sanitization overrides** where a whitelisted field still leaks state:
  D2's information source (mentions replication), D1's mechanism
  ("reclassified"), D4's function ("lead-lag deferred"), D6's information
  source and function ("unpinned" / "pinned" source). A contract test
  rejects historical state or blocker language in any projected row.
- **Every row carries the same neutral constant:**
  `REGION_STATE = PRIOR_WORK_SIGNATURE`. It says only that the signature
  exists in prior work — not whether it was executed, blocked, deferred,
  null, promising or confirmed.
- **Generator-side rule:** avoid exact duplicates of prior-work signatures
  and cosmetic parameter, window, threshold or horizon relabels of them.
  Whether a near region is closed or still open is decided by the novelty
  critic, not the generator.

```
GENERATOR_SEES_EXECUTION_STATUS = false
GENERATOR_SEES_OUTCOME_LABELS   = false
```

Why those fields are excluded: measured on current memory, rescue
warnings carry outcome vocabulary in 10/30 entries and are written
differently for positive and null cards; family cooldowns reveal which
families produced positives. A uniform `CONSUMED` label would also have
been wrong: it would tell the generator that blocked regions (B2-06, D6,
D8, D4 lead-lag) are closed and suppress exactly the data-blocked demand
Stream B exists to measure.

The generator also receives the family taxonomy A–J (names only),
`DATA_CATALOG_V0`, the schema and data-status taxonomy, and generic
methodological lessons without card attribution. It never receives
classification labels, gate results, p-values, effect sizes or any numeric
result, replication/confirmation status, family statuses, past rejection
reasons, profitability, outcome-ranked families, or
`GOVERNANCE_REGION_AUTHORITY_V0` in any form.

### Structural provenance guard (primary protection)

Every field in generator context must have an allowlisted provenance entry
`SOURCE_ARTIFACT, SOURCE_FIELD, TRANSFORM, OUTPUT_FIELD`. The allowlist
covers the five memory fields above, the `REGION_STATE` constant, the data
catalog, family names only, the schema/taxonomy and the generic lessons.

- Nothing from `STATUS_EVIDENCE_CLASS`, `WHAT_WAS_ACTUALLY_TESTED`,
  `WHAT_THE_RESULT_DEPRIORITIZES_OR_CLOSES`, `WHAT_REMAINS_OPEN`,
  `NEIGHBOR_RESCUE_WARNING`, `POSTHOC_RESIDUALS_IF_ANY`, any `*_RESULT`
  artifact, `discovery_results/**` or the governance authority may enter,
  except through an explicitly reviewed, outcome-neutral transform recorded
  in the design (none in V0).
- The implementation unit materializes a tracked
  `docs/research/BLIND_MECHANISM_MAP_V0.json` with a SHA256 digest; the
  provider receives that artifact, never raw memory.
- **Fail closed:** if memory gains or changes an entry the materialized map
  does not cover, generation refuses to run until the map is regenerated
  and reviewed.
- A context field without an allowlisted provenance entry is a hard fail.

**Context scanner (backstop only).** Before every call, the fully
assembled context (map, catalog, prompt, few-shot examples) is scanned for
outcome and governance-state vocabulary and result-like numbers; a hit
stops the call. Passing the scanner is not proof of blindness — the
provenance guard is. Few-shot examples are synthetic. Residual risk — that
a prior region's existence or wording hints at its outcome — is accepted
and recorded.

### `GOVERNANCE_REGION_AUTHORITY_V0` (not generator context)

A machine-readable authority used by the novelty critic (and by the red
team only for a specific frozen anti-rescue row). One row per memory entry;
a memory entry without a row fails closed.

Row fields only: `SIGNATURE_ID, MECHANISM, FUNCTION, STATE,
ANTI_RESCUE_SCOPE, BLOCKER_CLASS_IF_ANY,
BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY`. No p-values, effect sizes, gate
results, promising/null labels, yearly outcomes, profitability or
prototype status.

| State | Meaning |
|---|---|
| `CONSUMED` | frozen function executed or otherwise used; outcome not recorded |
| `DEFERRED_OR_BLOCKED` | defined but not executed because of a named blocker; region not closed |
| `PARTIAL_OR_MIXED` | sub-signatures carry different states; adjudicate per sub-signature |

Novelty decision table (candidate's relation to the nearest signature):

| Relation | `CONSUMED` | `DEFERRED_OR_BLOCKED` |
|---|---|---|
| exact duplicate | reject | defer (blocker unresolved) |
| parameter neighbor | reject | reject |
| functional relabel | reject | defer (blocker unresolved) |
| resolves the blocker | human review | allow → feasibility |
| orthogonal mechanism | allow | allow |

`PARTIAL_OR_MIXED` applies the sub-signature's state. No row closes a
family or an information class. Rows are written symmetrically; outcome-
derived family cooldowns are not encoded (humans may still apply them,
logged).

Current rows: 24 `CONSUMED`; `DEFERRED_OR_BLOCKED` for B2-06 and MARKET-04
(point-in-time semantics), D1 (null model cannot generate the observable),
D6 (source not pinned), D8 (insufficient control support, frozen
thresholds kept); D4 `PARTIAL_OR_MIXED` — rolling 90d correlation
`CONSUMED`, 1-day lead-lag `DEFERRED_OR_BLOCKED` (null destroys the common
factor; needs a common-factor-preserving null).

**Stream assignment:** `EXECUTABLE_NOW` = allow + red team pass + all data
ready. `HIGH_VALUE_DATA_BLOCKED` = allow or allow→feasibility + red team
pass + any observable feasibility-required or data-blocked. Everything else
is not a stream. So a distinct funding/OI candidate near B2-06 lands in
Stream B, a distinct event-response mechanism near D8 is allowed, another
pinned external mechanism near D6 is allowed, and D4 rolling-correlation
neighbors are rejected while D4 lead-lag stays open to a blocker
resolution.

## Roles and context matrix

| Role | Allowed | Forbidden (besides raw memory, results, labels, magnitudes, prototype/null identity, full history) | Does |
|---|---|---|---|
| Generator | blind map, data catalog, schema, data-status taxonomy, generic methodology | governance authority, critic outputs | proposes cards in the frozen schema; no success estimates, no self-grading |
| Novelty critic | blind map, governance authority, generic anti-rescue rules, current batch signatures, candidate | — | duplicate, neighbor rescue, cosmetic novelty, batch overuse, blocker resolution; each verdict cites the signature and table cell |
| Feasibility critic | candidate, data catalog, taxonomy, blocker requirements, protected-data rules | — | confirms data status, names missing observables exactly, point-in-time and provenance, cost; writes data-gap rows |
| Red team | candidate, methodology checklist, protected-data rules; governance row only when adjudicating a frozen anti-rescue rule | — | lookahead/leakage, outcome-dependent selectors, impossible causality, confounding, hidden search surface, p-hacking freedom |
| Selector | sanitized critic outputs, data status, selection judgments | governance authority, blind map | ordinal ranking by mechanism distance × information gain × feasibility × cheapness; shortlist ≤5 for humans |
| Human | full research history | — | approves/rejects with logged reasons, adjudicates novelty, authorizes data and execution, program decisions |

Sanitized critic outputs carry verdicts and judgments only; the governance
state a novelty verdict cited is stripped before the selector sees it.
Full research history is reachable only by the human role.

## Candidate schema (frozen)

`CANDIDATE_ID, NAME, MECHANISM_FAMILY, MECHANISM, CAUSAL_OR_STRUCTURAL_STORY,
INFORMATION_SOURCE, OBSERVABLE, FUNCTION, PRIMARY_TARGET, HORIZON,
BASELINE_OR_NULL, FALSIFIER, NEAREST_TESTED_MECHANISM,
MECHANISM_DISTANCE_ARGUMENT, WHY_NOT_A_RESCUE, SEARCH_SURFACE,
MAIN_CONFOUNDERS, NO_LOOKAHEAD_RULE, DATA_REQUIRED, DATA_STATUS,
MISSING_OBSERVABLES, DATA_GAP_CLASS, EXPECTED_IMPLEMENTATION_COST,
WHAT_POSITIVE_WOULD_TEACH, WHAT_NULL_WOULD_ELIMINATE,
EXPECTED_INFORMATION_GAIN, PROTECTED_DATA_REQUIREMENT`

Forbidden: `EXPECTED_PROBABILITY_OF_SUCCESS`.

## Data status and two streams

| Status | Meaning |
|---|---|
| `DATA_READY` | all observables in tracked, snapshot-bound, restorable datasets |
| `FEASIBILITY_REQUIRED` | plausible free source, unverified; must list what to verify |
| `DATA_BLOCKED_MISSING_OBSERVABLE` | no known source |
| `DATA_BLOCKED_PROVENANCE` | source exists but can't be pinned/reproduced |
| `DATA_BLOCKED_POINT_IN_TIME_SEMANTICS` | publication time or revision history unproven |
| `DATA_BLOCKED_COST` | paid or disproportionate engineering |

Existing repo labels map onto these (e.g. B2-06 / MARKET-04 →
point-in-time; D6 → provenance). Requiring 2025/2026 data is a hard fail,
not a status.

- **Stream A — `EXECUTABLE_NOW`:** data-ready candidates passing all critics.
- **Stream B — `HIGH_VALUE_DATA_BLOCKED`:** candidates passing novelty and
  red team but blocked by data. Kept, not discarded; each writes a
  `DATA_GAP_LEDGER_V0` row: missing data class and observable, mechanism
  region, information gain, number of **mutually distinct** candidates
  blocked, duplicate-demand flag, acquisition cost, provenance risk, and
  whether it unlocks distinct mechanism space. No numbers are preset.

**Acquisition priority (later, ordinal only):**
(unlocked distinct mechanism space × aggregate information gain × expected
reuse) ÷ (acquisition cost × provenance risk × maintenance cost). Considered
only after a full adjudicated shadow batch, never on near-duplicate demand,
always with explicit human authorization. Nothing is acquired now.

`DATA_CATALOG_V0` seed: CORE BTC and ETH (USD-M perpetual 1m), Binance
perp/OKX spot 5m, BitMEX pre-2020 5m, Binance spot USDT daily panel, Binance
spot BTC 1h, FOMC calendar, DST calendars (all data-ready); OI/funding
snapshots (point-in-time blocked); anything 2025/2026 (forbidden).

## Shadow batch

- Target 40 candidates (bounds 25–50), generated in rounds with a
  family/source slot plan, not one idea per call.
- At most 5 per existing family; at least 8 slots for new-family attempts;
  at least 6 information-source classes; data-blocked ideas explicitly
  welcome.
- Selector shortlist of at most 5 for human adjudication.

## Evaluating the generator

Per-candidate ordinal dimensions, kept separate (no single opaque score):
novelty, mechanism distance, non-rescue, falsifiability, data specificity,
no-lookahead quality, confounding awareness, search-surface discipline,
null information gain, implementation boundedness.

Batch metrics: duplicate rate, rescue-violation rate, hard-fail rate,
family/source coverage, Stream A/B split, critic–human agreement (novelty
and feasibility), human active minutes and cost per accepted candidate.
There is no timed historical human baseline; the first real campaign logs
human minutes and any comparison with past sprints is labelled an estimate.

**Anti-Goodhart:** downstream classifications of executed candidates are
never a generator reward and never enter generator or selector context.
Never scored: expected alpha, probability of a positive result.

**Hard fails:** scanner hit; generator-context field without allowlisted
provenance; success-probability field; protected-data requirement;
lookahead; novelty verdict reject under the decision table; missing
falsifier or baseline; unbounded search surface; trading/alpha/product
claim; blocked status without a named missing observable; off-catalog
source claimed as data-ready.

## LLM architecture, budget, reproducibility

- Provider-neutral adapter: `complete(role, prompt_version, context,
  parameters) → raw text + usage`. Deterministic mock provider is
  required; real adapters sit behind the same interface. Roles may use
  different models/providers.
- Zero-cost mock mode required. Real-LLM hard cap: **USD 30** for the first
  shadow campaign, all roles; the guard checks estimated cost before every
  call. Records calls, provider, model, tokens, estimated cost, yield,
  rejection reasons.
- Run ledger: `RUN_ID, PROMPT_VERSION, CONTEXT_DIGEST, MODEL_PROVIDER,
  MODEL_ID, MODEL_PARAMETERS, RAW_RESPONSE_SHA256, PARSED_CARD,
  CRITIC_OUTPUTS, FINAL_DECISION, HUMAN_MUTATIONS`. Human edits are
  recorded as explicit mutations (field, before, after, reason).

## Next unit

`HYPOTHESIS_GENERATOR_V0_IMPLEMENTATION_AND_SHADOW_HARNESS` — infrastructure
only: blind-context builder (provenance allowlist, overrides, materialized
map with digest, scanner), governance region authority, schema
validator, provider interface and mock, generator, three critics, selector,
data-gap ledger, run ledger, budget guard, shadow batch runner. No market
scientific execution.

## Pre-outcome amendment 1

Amends PR #204 head `fd364b3`, before any generator exists or any output is
observed: neutral `PRIOR_WORK_SIGNATURE` state replaces the uniform
`CONSUMED` label; `GOVERNANCE_REGION_AUTHORITY_V0` added; explicit role
context matrix replaces the full-governance-context path; structural
provenance guard made primary with the scanner as backstop. Maturity
decision, batch size, budget cap and all boundary flags are unchanged.
