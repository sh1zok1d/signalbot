# Discovery Sprint 01 — Final Pre-Execution Correction (D3, D4)

**Unit:** `DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4`
**Unit type:** `OUTCOME_BLIND_PRE_EXECUTION_CORRECTION`
**Date:** 2026-09-21
**Reviewed commit:** `355a1657aac288fe75b272df1845fd9b5cfcac3f`
**Scope:** D3 and D4 only. D1, D2, D5, D6 unchanged from
`DISCOVERY_SPRINT_01_RED_TEAM_REVIEW`.
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4.json`

No Discovery Sprint 01 card was executed. No candidate performance was
inspected. Protected 2025/2026 remains unopened. No MARKET-07 was
created.

## D3 — direction / native-path null semantics

### Issue 1: direction alignment contradicted `UNCONDITIONAL_DESIGN`

`MAX_ADVERSE_EXCURSION_24h` / `TIME_TO_MAX_ADVERSE_EXCURSION` were
direction-aligned using `BTC_SIDE(t)` — a real, historically informative
quantity (sign of the prior 24h return), not a neutral label. Orienting
"adverse" by it risks smuggling in the same directional-predictability
structure D1/D2/MARKET-01/02/05/06 already test (momentum or mean
reversion), which would then masquerade as "path morphology."

**Options considered:**

- **A** (condition on real, legally-known `BTC_SIDE(t)`, shared by real
  and surrogate): rejected — even shared identically, a real directional-
  predictability effect would make real direction-aligned excursions
  systematically differ from the null for reasons unrelated to path
  shape, reintroducing the exact risk flagged.
- **B** (generate surrogate pre-history to derive a surrogate `BTC_SIDE`):
  rejected — needs a second, undecided bootstrap design for a synthetic
  48h sequence, and risks duplicating D1's state-persistence question.
- **C** (remove direction alignment; genuinely unconditional, unsigned
  path morphology): **selected**, outcome-blind, on structural grounds —
  no `BTC_SIDE` computation needed at all, cannot smuggle in directional
  predictability by construction, matches the card's own label exactly.

**Corrected functional definitions** (replacing the direction-aligned
ones; `ev.btc_side_from_ret` is no longer used by D3):

- `MAX_UPSIDE_EXCURSION_24h` = max over the 288 forward bars of
  `(high - entry_open) / entry_open`.
- `MAX_DOWNSIDE_EXCURSION_24h` = max over the 288 forward bars of
  `(entry_open - low) / entry_open`.
- `TIME_TO_MAX_EXCURSION` = bar offset (0-287) at which
  `max(MAX_UPSIDE_EXCURSION_24h, MAX_DOWNSIDE_EXCURSION_24h)` occurs.
- `PATH_ASYMMETRY` = `MAX_UPSIDE_EXCURSION_24h / MAX_DOWNSIDE_EXCURSION_24h`.

### Issue 2: time-of-day confound in the F3 null

The prior (first-round) `5m_RETURN_POOLED_CIRCULAR_BLOCK_BOOTSTRAP` null
pools blocks from anywhere in history, ignoring time-of-day. Every
MARKET-06 decision point starts at the **same fixed UTC clock time**
(`00:05:00Z`, per the frozen `is_forbidden_decision` check). That means
bar-offset `k` corresponds to the *identical* UTC time-of-day on every
single observation — `TIME_TO_MAX_EXCURSION` isn't merely correlated
with time-of-day, it **is** a time-of-day statistic. Ordinary, mundane
intraday volatility seasonality (e.g. session-overlap hours) would
concentrate the real empirical distribution at specific bar-offsets,
while a time-of-day-blind null would smear that out — a near-certain
confound. This is a structural argument from the frozen decision-grid
design, not an outcome inspection; irrelevance could not be demonstrated
(the opposite could be, structurally).

**Resolution: preserve time-of-day/UTC-slot structure in the bootstrap.**

Corrected null: `5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP`.
Partition the 288 bar-offsets into 24 fixed 1-hour slots of 12
consecutive bar-offsets each (slot `i` = bar-offsets `[12i, 12i+11]`,
each a fixed UTC hour since every window starts at `00:05Z`). For each
surrogate day and each of the 24 slot positions **independently**, draw
the replacement 12-bar block — with replacement — only from the pool of
real historical blocks that occurred **at that same slot position**
across the discovery interval; never mix blocks across slots.

This preserves everything the original null preserved (5m-return
marginal, short-range ≤1h autocorrelation/clustering) **plus** the
marginal UTC time-of-day volatility profile, while still destroying
date-specific conditioning and cross-slot (>1h) dependency, matching the
original intent. Block length (12), replicates (1000), and seed
(`D3_NULL_SURROGATE_SEED = 20260921103`) are unchanged; companion
stability checks (block lengths 6 and 24) are retained, each also
slot-stratified (`288/6=48` and `288/24=12` slots, both exact).

### Issue 3: edge cases frozen

- **`PATH_ASYMMETRY` zero-denominator handling:** if
  `MAX_DOWNSIDE_EXCURSION_24h == 0`, `PATH_ASYMMETRY` is undefined for
  that row and the row is excluded from that functional's distribution
  only (not from the other two); the exclusion count is reported.
- **`TIME_TO_MAX_EXCURSION` tie handling:** earliest bar-offset wins
  (consistent with D6's tie-handling convention elsewhere in this
  sprint).
- **Entry/reference convention:** `entry_open =
  ev.get_perp_bar_opening_at(perp, t_ms).open`, reused verbatim from the
  frozen MARKET-06 entry convention (the same reference
  `ev.arithmetic_mae` already uses).

**D3 status after correction: `EXECUTABLE_DISCOVERY_SPEC`.**

## D4 — lead-lag null still destroyed too much

The first-round `INDEPENDENT_BLOCK_BOOTSTRAP` fix for `LEAD_LAG_1DAY`
destroys not only the true `BTC(t)→ETH(t+1)` cross-lag but also ordinary
same-time common-factor dependence (shared crypto-market-wide moves) —
not the target being tested. A null this weak makes almost any
contemporaneous co-movement masquerade as lead-lag evidence. No
outcome-blind demonstration exists that it preserves the relevant
non-target cross-asset structure — it demonstrably does not, by
construction.

**Preferred minimal resolution applied** (no complex new lead-lag model
invented merely to keep both functionals):

- `ROLLING_CORRELATION_90D`: **retained**, unchanged — paired-vector
  `BLOCK_BOOTSTRAP_PAIRED_RETURNS` (block length 20 days), cleanly
  specified, separately justified as a longer-horizon test.
- `LEAD_LAG_1DAY`: **`DEFERRED_FROM_SPRINT_01`**. Its definition is
  retained in the spec as historical record, not deleted.

**D4 status after correction: `EXECUTABLE_DISCOVERY_SPEC`, scoped to
`ROLLING_CORRELATION_90D` only** for Sprint 01 execution. The
`PROMISING_PROTOTYPE_EVALUATION_FIELDS` OR-clause referencing
`|LEAD_LAG_1DAY|` no longer applies.

## Final report

```
D1_STATUS = BLOCKED_PENDING_PRE_OUTCOME_FIX
D2_STATUS = EXECUTABLE_DISCOVERY_SPEC
D3_STATUS = EXECUTABLE_DISCOVERY_SPEC
D4_STATUS = EXECUTABLE_DISCOVERY_SPEC (ROLLING_CORRELATION_90D only)
D4_ROLLING_CORRELATION_STATUS = EXECUTABLE_DISCOVERY_SPEC
D4_LEAD_LAG_STATUS = DEFERRED_FROM_SPRINT_01
D5_STATUS = EXECUTABLE_DISCOVERY_SPEC
D6_STATUS = DEFERRED

EXECUTION_AUTHORIZED_CARDS = D2, D3, D4 (ROLLING_CORRELATION_90D only), D5
BLOCKED_OR_DEFERRED        = D1 (blocked, pending D1_NULL_ADEQUACY_GATE execution),
                              D4 LEAD_LAG_1DAY (deferred from Sprint 01),
                              D6 (deferred, pending replacement benchmark)

SCIENTIFIC_OUTCOMES_COMPUTED   = false
CANDIDATE_PERFORMANCE_INSPECTED = false
PROTECTED_2025_OPENED          = false
PROTECTED_2026_OPENED          = false
MARKET_07_CREATED              = false

NEXT_UNIT = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5,
            gated separately on D1_NULL_ADEQUACY_GATE_EXECUTION,
            D4_LEAD_LAG_REPLACEMENT_NULL_OR_PERMANENT_DEFERRAL,
            and D6_REPLACEMENT_BENCHMARK_SELECTION
```
