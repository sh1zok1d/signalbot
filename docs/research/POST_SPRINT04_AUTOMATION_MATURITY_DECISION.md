# Post-Sprint 04 Automation Maturity Decision

**Unit:** `POST_SPRINT04_AUTOMATION_MATURITY_DECISION`
**Date:** 2026-09-22
**Base:** `origin/main` `547693ce9d725d7aa6f61b107472cd8c2083ad4f` (tree `10565a58136205d0cb40ade097341bd25c21a529`)
**Machine-readable record:** `docs/research/POST_SPRINT04_AUTOMATION_MATURITY_DECISION.json`

No outcome computed, no data acquired, no card created, no result
artifact modified.

## Decision

```
MATURITY_DECISION = HYPOTHESIS_GENERATOR_V0_INFRA_READY
INTERNAL_DISCOVERY_CARDS_EXECUTED = 10
INTERNAL_PROMISING_PROTOTYPES     = 4
AUTOMATIC_SPRINT05 = false
SPRINT05_CREATED   = false
NEXT_UNIT = HYPOTHESIS_GENERATOR_V0_IMPLEMENTATION_AND_SHADOW_HARNESS
```

Design: `docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.{json,md}`.

## Why A, not B

1. **What the generator is judged on.** Generator V0 is evaluated on
   novelty, mechanism distance, falsifiability, data specificity and
   information gain — never on how often its cards later turn out
   promising. What it needs from history is coverage of mechanism regions,
   anti-rescue lineage, blocked-data examples and card-schema examples.
   Ten executed cards plus ~20 legacy H/B2/MARKET entries in structured
   memory provide that.
2. **Every example class the critics need already exists:** clean nulls in
   six distinct regions, prototypes, a replication that survived (D2 on
   BitMEX), statistical-but-not-practical structure (D13), and four
   different kinds of blockers (D1 method, D6 provenance, D8 support,
   B2-06/MARKET-04 publication-time semantics).
3. **No region is required for a valid evaluation.** The one region
   previously named B-eligible — forward expectations (options) — has no
   executed card, but the generator can still propose and critique options
   mechanisms. They land in the data-blocked stream, and the data-gap
   ledger then measures how much distinct mechanism space options would
   actually unlock. Running one options card first would spend a dataset
   acquisition before demand is measured, without changing whether the
   generator can be evaluated.
4. **Remaining weaknesses are carried, not blocking:** prototype
   concentration, D12 unreplicated, and no timed human-effort baseline are
   evidence-strength and KPI-measurement issues.

Option B regions considered and rejected: forward expectations (options),
true order-book liquidity, a second-moment distinctness diagnostic, and
derivatives crowding/funding/basis (still blocked on publication-time
semantics).

## Assessments

**Mechanism diversity — sufficient for V0, positive diversity thin.**
Eight families executed (A, C, D, E, G, H, J and the D5 composition).
Four prototypes, but only **two effective classes**: D2, D7 and D11 are
all second-moment / activity-level structures and are treated as one class
until shown distinct; D12 (timing of participation, not its level) is the
second. D12 is itself adaptive discovery on 10 transitions, largest in
2023–2024 and negative in 2022 — a prototype, not a robust mechanism.
Never-executed information classes: options, L2 depth, derivatives
positioning with proven publication time, on-chain, external macro.

**Negative evidence — sufficient.** Internal clean-null regions: D3, D4,
D5, D9, D10, D13, plus the legacy directional/scalar-prediction regions.
D13 is the statistical-but-not-practical example.

**Anti-rescue memory — sufficient but outcome-asymmetric.** Rescue
warnings and family cooldowns are written differently for positive and
null cards, so passed raw they leak outcomes. Measured on
`MECHANISM_MEMORY_V0`: `NEIGHBOR_RESCUE_WARNING` contains outcome
vocabulary in 10/30 entries, `WHAT_WAS_ACTUALLY_TESTED` in 16/30, and D2's
information-source text mentions replication. The generator therefore gets
a symmetric transformation rule; specific rules stay in governance.

**Data-feasibility memory — sufficient** to seed a data-status taxonomy
and data catalog (Sprint 03/04 pools, funding/premium adjudications,
dataset authorities).

**Card schema — mature but fragmented** across three generations (Pipeline
V2, Sprint 03, Sprint 04); consolidated into one frozen V0 schema.

**Automation risks:** outcome leakage through memory or human-written
prompts; LLM pull toward literature-famous effects; mode collapse and
cosmetic novelty; hallucinated data sources; the same model generating and
grading; Goodhart on prototype rate; rubber-stamping; and no timed human
baseline for the 70–80% effort KPI. Each has a mitigation in the design.

## Data expansion: generator first

Do not expand datasets ahead of the generator. Evidence: acquisitions made
ahead of a concrete card have been expensive and provenance-fragile
(funding/premium semantics still unproven after two audits), while
card-driven bounded acquisitions worked (D11 calendar, D13 panel). If most
high-value proposals turn out data-blocked, that is itself the finding the
data-gap ledger exists to produce.

## Erratum recorded, not rewritten

`DISCOVERY_SPRINT_04.json` D12 `ALLOWED_CLAIM` says "Binance BTCUSDT spot",
but `CORE_BTC_BINANCE_V0` is the Binance USD-M BTCUSDT **perpetual**
(`docs/CORE_BTC_BINANCE_V0_CONTRACT.md`). Consumed artifacts are not
rewritten; any claim or confirmation must name the perpetual.

## Boundary

```
NEW_DATA_ACQUIRED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
SPRINT05_CREATED = false
D14_CREATED = false
GENERATOR_BUILT = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
D7_CONFIRMATION_EXECUTED = false
D11_CONFIRMATION_EXECUTED = false
D12_CONFIRMATION_EXECUTED = false
```
