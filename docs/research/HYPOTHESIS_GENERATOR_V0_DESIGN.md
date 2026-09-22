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
It works from `BLIND_GENERATOR_CONTEXT`; governance works from
`FULL_GOVERNANCE_CONTEXT`.

### `BLIND_MECHANISM_MAP_V0`

Derived from `MECHANISM_MEMORY_V0`:

- **Whitelisted fields only:** `ID`, `MECHANISM`, `INFORMATION_SOURCE`,
  `FUNCTION`, `TARGET_FAMILY`.
- **Excluded fields:** evidence class, what was tested, what it
  deprioritizes, what remains open, rescue warnings, post-hoc residuals,
  data state, generation.
- **Sanitization overrides** where a whitelisted field still leaks (today:
  D2's information source, which mentions replication).
- **Every entry gets the same state:** `REGION_STATE = CONSUMED`,
  regardless of outcome.
- **One uniform transformation rule** for all consumed signatures: no
  parameter/threshold/window/horizon/lag/clock variants, no observable
  substitution within the same function, no alternate strata/null/
  refractory/bootstrap, no composition of consumed signatures, no relabel.

Why those fields are excluded: measured on current memory, rescue
warnings carry outcome vocabulary in 10/30 entries and are written
differently for positive and null cards; family cooldowns reveal which
families produced positives. Those stay in governance.

The generator also receives the family taxonomy A–J (names only),
`DATA_CATALOG_V0`, the schema and data-status taxonomy, the protected-data
rule, previously considered candidate signatures **without** selection or
rejection reasons, and generic methodological lessons without card
attribution.

It never receives classification labels, gate results, p-values, effect
sizes or any numeric result, replication/confirmation status, family
statuses, past rejection reasons, profitability, or outcome-ranked
families.

**Context scanner (hard fail).** Before every call, the fully assembled
context (map, catalog, prompt, few-shot examples) is scanned for outcome
vocabulary and result-like numbers. A hit stops the call. Few-shot
examples are synthetic. The scanner is a backstop, not the main
protection: rescue warnings use ordinary words ("D7 positive does not
authorize…"), so the denylist includes words like `positive`/`negative`
as well as label vocabulary. Residual risk — that a consumed region's existence
or wording hints at its outcome — is accepted and recorded.

### Governance context

Governance may read full memory, rotation rules and results to enforce
frozen anti-rescue and consumed-region rules and scientific integrity. It
may **not** score a candidate as more or less likely to work because it
resembles a past positive or null card.

## Roles

| Role | Sees | Does |
|---|---|---|
| Generator | blind context | proposes cards in the frozen schema; no success estimates, no self-grading |
| Novelty critic | blind map + frozen anti-rescue rules | duplicate, neighbor rescue, cosmetic novelty, batch overuse, equivalent target — each verdict cites the consumed signature or rule |
| Feasibility critic | data catalog, taxonomy, protected rule | confirms data status, names missing observables exactly, point-in-time and provenance, cost; writes data-gap rows |
| Red team | card + methodology checklist | lookahead/leakage, outcome-dependent selectors, impossible causality, confounding, hidden search surface, p-hacking freedom |
| Selector | critic outputs + data status only | ordinal ranking by mechanism distance × information gain × feasibility × cheapness; shortlist ≤5 for humans |
| Human | everything | approves/rejects with logged reasons, adjudicates novelty, authorizes data and execution, program decisions |

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

**Hard fails:** scanner hit; success-probability field; protected-data
requirement; lookahead; identical to a consumed signature; forbidden
transformation of one; missing falsifier or baseline; unbounded search
surface; trading/alpha/product claim; blocked status without a named
missing observable; off-catalog source claimed as data-ready.

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
only: blind-context builder (whitelist, overrides, scanner), schema
validator, provider interface and mock, generator, three critics, selector,
data-gap ledger, run ledger, budget guard, shadow batch runner. No market
scientific execution.
