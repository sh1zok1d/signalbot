# MARKET-01 OI_EXPANSION_WEAK_CONTINUATION — outcome-blind prereg design

- **Status:** `PREREG_DESIGN_RESOLVED_BY_AUTHOR_DECISIONS / HISTORICAL_BLOCKER_RECORD`
- **Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`
- **Unit type:** design / blocker record; **not** the live preregistration
- **Live preregistration (unfrozen):** `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md` and `.json`
- **Parent feasibility:** `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_DATA_FEASIBILITY.md`
- **Feasibility commit:** `901f96eaa551e2591a6212a14ddd4488f5528e8e`
- **Date:** 2026-09-17
- **Outcome inspection:** **NO**
- **Prereg materialized:** **YES** (separate document; freeze is still required)
- **Prereg ready:** **YES** (semantics bound; `MARKET_01_FREEZE_REQUIRED = YES`)
- **MARKET-01 executed:** **NO**
- **B2-06 execution authorized:** **NO**
- **V4 created:** **NO**

This file is the **historical blocker record** of the design unit that
stopped because existing primitives could not bind matching, V3 mapping,
robustness, or the support floor. That unit's body below is preserved.

Current scientific authority for MARKET-01 is the outcome-blind
preregistration, not this design file:

- `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md`
- `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json`

Author decisions that resolved the blockers (do not re-litigate here):

1. `BLOCKER_BASELINE_MATCHING_SEMANTICS` → stratified two-group
   comparison on impulse magnitude × `PRE_VOL_60` tertiles (max 9
   strata; historical 30-day tertiles before impulse start).
2. `V3_CONFIRMATORY_ESTIMAND_NOT_MAPPABLE_TO_TWO_GROUP_REVERSAL_CONTRAST`
   → MARKET-01 does **not** use V3. Primary estimand is stratified OLS
   `reversal_return ~ candidate_indicator + stratum FE` with one-sided
   stationary bootstrap `B=999`, `alpha=0.05`.
3. `BLOCKER_ROBUSTNESS_SEMANTICS` → five frozen calendar eras, LOEO
   sign-stability plus candidate-share `<= 0.50`; robustness may only
   downgrade a primary `DETECTED`.
4. Support floor → `TOTAL>=100`, `CANDIDATE>=30`, `BASELINE>=30`,
   `USABLE_STRATA>=3` with both groups `>=5` per usable stratum.

This file is **not** a freeze. The prereg remains unfrozen until a
separate freeze unit.

The original blocked-unit narrative follows unchanged so the stop is
auditable. Where it says `MARKET_01_PREREG_READY = NO`, that was true
of **this design unit**. The live prereg supersedes those flags.

No MARKET outcomes, 2025/2026 partitions, V3 RESULT reinterpretation,
threshold search, or B2-06 execution occurred.

---

## 1. Research identity

```text
MARKET-01_OI_EXPANSION_WEAK_CONTINUATION
```

First real-market study of the MARKET phase. Market-relationship study,
not a trading strategy. No entries, exits, stops, take-profits, fees,
Sharpe, position sizing, or PnL.

"Absorption", "crowding", and leverage accumulation are possible
mechanism interpretations only. They are not observed facts and are not
encoded as proven.

---

## 2. Data authorities (bound; unchanged)

**Price:** `CORE_BTC_BINANCE_V0` snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`

- Binance USD-M perpetual `BTCUSDT`
- 1m klines, `HISTORICAL_COMPARABLE` / official archive
- `open_time_ms` = bar start
- `available_at = bar_end_exclusive = open_time + 60s`
- Only closed bars are legal

**OI:** Vision `daily/metrics/BTCUSDT` `sum_open_interest` in snapshot
`5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`

- Native grain 5m
- `create_time` = bucket start
- `available_at = create_time + 5 minutes`
- Legal OI at `T`: latest observation with `available_at <= T` **and**
  staleness `<= 5 minutes`
- 631 missing native buckets remain `MISSING`; never filled
- Do not upsample OI to 1m
- Funding in the same snapshot remains unusable
- Using these OI rows does **not** unblock B2-06

**Common legal period:**
`[2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)`

**Decision grain:** UTC-epoch 5-minute boundaries.

Protected 2025 validation and 2026 OOS remain forbidden and unopened.
Price after `2025-01-01` is outside this study's common OI authority.

---

## 3. Temporal design (unambiguous; not a freeze)

```text
IMPULSE WINDOW          = 30 minutes   [t-30m, t]
STATE FORMATION WINDOW  = 30 minutes   [t, t+30m]
DECISION TIME T         = t+30m
OUTCOME WINDOW          = 60 minutes   [t+30m, t+90m]
FULL EPISODE SPAN       = 120 minutes
```

No information from the OUTCOME window may enter eligibility, impulse /
OI-expansion / weak-continuation classification, normalization, matching,
threshold selection, or support selection.

---

## 4. Candidate definition (unambiguous; not a freeze)

At impulse endpoint `t`:

```text
impulse_return = 30-minute log price return
D = sign(impulse_return)
```

`QUALIFYING_IMPULSE` iff `abs(impulse_return)` is at or above the rolling
historical 90th percentile of absolute 30-minute returns, using the
previous 30 calendar days ending **before** the candidate impulse window
starts, using only legally available closed price bars. Insufficient
normalization support → `EPISODE_NOT_ELIGIBLE`. No fallback threshold.

During `[t, t+30m]`:

```text
delta_oi = log(OI_end / OI_start)
```

using only legally available native OI. `OI_EXPANSION` iff `delta_oi` is
**strictly greater** than the rolling historical 75th percentile of
comparable 30-minute OI changes, with that history fully available
**before** STATE FORMATION starts. Missing, stale (>5m), non-finite, or
non-positive OI where log change requires positive values →
`EPISODE_NOT_ELIGIBLE`. Never fill. Never redraw.

```text
state_return = 30-minute log price return over STATE FORMATION
signed_continuation = D * state_return
continuation_ratio = signed_continuation / abs(impulse_return)
WEAK_CONTINUATION iff continuation_ratio <= 0.25
```

Negative `signed_continuation` satisfies weak continuation. It is **not**
observed absorption.

```text
CANDIDATE =
  QUALIFYING_IMPULSE
  AND OI_EXPANSION
  AND WEAK_CONTINUATION
```

Candidate identity is determined before the outcome window begins.

Exact-zero `impulse_return` is not a qualifying impulse (`D` undefined).

---

## 5. Primary outcome (unambiguous; not a freeze)

```text
outcome_return = log(P_end / P_start)   over [T, T+60m]
reversal_return = -D * outcome_return
```

Positive `reversal_return` = movement against the original impulse.
Single frozen horizon. No alternative horizons. Not PnL.

---

## 6. Overlap and missing data (unambiguous; not a freeze)

Once a qualifying impulse episode is accepted chronologically, no new
qualifying impulse episode may begin before that full 120-minute episode
ends. On conflict, keep the earliest chronologically eligible episode.
The same rule applies regardless of later candidate/baseline class.
Outcome must not influence overlap resolution.

Fail closed. Never interpolate native OI. Never treat missing OI as zero
change. Never extend staleness beyond 5 minutes. Any episode that needs
unavailable OI for state calculation, historical normalization, or legal
decision-time observation is `EPISODE_NOT_ELIGIBLE`. Exclusion counts
are later diagnostics and must not alter this design.

---

## 7. Baseline primitive — BLOCKER_BASELINE_MATCHING_SEMANTICS

Required comparison: CANDIDATE episodes versus qualifying IMPULSE
episodes that do **not** satisfy the complete candidate state, prevented
from winning merely by different **impulse magnitude** or **pre-state
trailing volatility**. Matching must not use future returns, outcome
variables, state-window future information, OI-expansion status,
weak-continuation status, funding, or post-decision information.

Inspected existing primitives; none implement that comparison without
changing their scientific semantics:

| Primitive | Why it does not bind |
|---|---|
| `paired_same_support_delta` / `weighted_same_support_delta` (`scripts/research/lib/research_harness.py`) | Requires **identical event-ID sets**. MARKET-01 baseline is a **disjoint** complement of candidate among qualifying impulses. Same-support nested pairing is a different estimand. |
| H01/H03/H05 `matched-random` | Matches calendar month (and, for H03/H05, direction). Does **not** match impulse magnitude and trailing volatility. Changing match keys would change those primitives' frozen semantics. |
| B2-03 `baseline_stratum_id` (`W\|DIRECTION\|DISPLACEMENT_MAG_STATE\|VOL_STATE`) plus nested OLS | Frozen as **incremental nested-AE training strata**, not as a two-group matcher of disjoint candidate vs non-candidate reversal means. Reusing tertile labels for a two-sample test would change B2-03's estimand. |
| B2-06 `eligible_decision_keys` / `crowding_inputs_ready` | Require funding; B2-06 remains blocked; MARKET-01 is independent of B2-06. |

Inventing a new mag×vol matcher, bin edges, or tertile rule in this unit
is forbidden.

`MARKET_01_PREREG_READY = NO`  
**Blocker ID:** `BLOCKER_BASELINE_MATCHING_SEMANTICS`

**Smallest author decision required:** freeze, outcome-blind, a two-group
comparability rule whose dimensions are only impulse magnitude and
pre-state trailing volatility, including exact binning/support handling —
or explicitly change the MARKET-01 estimand (not done here). This unit
will not invent that rule.

---

## 8. V3 mapping — incompatible (not reused)

V3 may be reused only where frozen semantics apply. They do not apply
to MARKET-01's two-group reversal contrast.

Frozen V3 confirmatory identity (`evaluate_v3_world` /
`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md`):

- estimand `theta = E[d*_t | S_t=1]` with Clark-West nested OLS
  (`BASE=(1,X1,X2)`, `CAND=(1,X1,X2,feature)` via
  `expanding_era_predictions`);
- full chronological scored time axis split into **equal-width synthetic
  eras**; `n_scored` must be divisible by 4;
- overlay-with-baseline-fallback-outside-support is **forbidden**;
  Clark-West "does not transfer without independent re-derivation"
  (V3 prereg §4);
- `simulate_dgp` world object, not market episodes.

MARKET-01 would require feeding sparse, overlap-purged episode
`reversal_return` values and a disjoint two-group contrast into that
machine. That would silently change the frozen estimand. V3 is not
modified. V4 is not created.

V3 `DETECTED`/`PASS` remains research evidence and is **not** by itself
a robust market edge. `NONSTATIONARY_TRAP_PROTECTION =
INADEQUATE_ON_FROZEN_TRAP_DGP` remains explicit.
`V3_METHODOLOGY_CLAIMABLE = NO`.

`MARKET_01_PREREG_READY = NO`  
**Incompatibility ID:** `V3_CONFIRMATORY_ESTIMAND_NOT_MAPPABLE_TO_TWO_GROUP_REVERSAL_CONTRAST`

**Smallest author decision required:** freeze a MARKET-01 confirmatory
test identity that is **not** V3 (V3 cannot consume this comparison
exactly), using an existing non-V3 primitive if one can be bound without
transferring consumed H01/H03 MPIE thresholds — or change the MARKET-01
estimand to the nested-OLS regular-time-axis object V3 actually tests.
This unit will not do either.

---

## 9. Robustness primitive — BLOCKER_ROBUSTNESS_SEMANTICS

Required principle: aggregate positive evidence must **not** automatically
become `ROBUST_CANDIDATE` if the measured effect is materially
concentrated in one temporal/regime segment. Robustness may downgrade
interpretation. It may never rescue `NO_EVIDENCE`, failed primary
evidence, insufficient support, or non-identifiability.

Inspected existing primitives; none provide an unambiguous MARKET-01
mechanical criterion:

| Primitive | Why it does not bind |
|---|---|
| V3 `era_effects` / synthetic `E2..E5` | Equal-width slices of the frozen synthetic DGP, diagnostic, not a calendar/regime veto. Applying them to BTC calendar time would change V3 era meaning. |
| H01 `positive in at least 4 of 5 yearly blocks` | Consumed H01 promotion threshold. MARKET-01 legal overlap is `[2020-09-01, 2025-01-01)` (partial 2020 + 2021–2024), so “five years” is not the same partition. Copying the 4/5 count would transfer/invent a threshold. |
| `EDGE_RESEARCH_PROTOCOL.md` §12 | Requires honest scoping of localized evidence; does **not** freeze a mapping into `DETECTED_BUT_NOT_ROBUST` vs `ROBUST_CANDIDATE`. |

No new regime framework is designed here.

`MARKET_01_PREREG_READY = NO`  
**Blocker ID:** `BLOCKER_ROBUSTNESS_SEMANTICS`

**Smallest author decision required:** freeze a prospective, mechanical
concentration/downgrade rule on a specified chronological partition of
`[2020-09-01, 2025-01-01)`, including what “materially concentrated”
means, without using MARKET outcomes.

---

## 10. Support / identifiability (partial; not a freeze)

Fail-closed `EPISODE_NOT_ELIGIBLE` for missing/stale/invalid OI or
insufficient 30-day normalization support is bound as design intent.

V3 `support_count >= 50` is a synthetic-world `S_t=1` floor on a regular
time axis. It does **not** transfer as a MARKET-01 episode-count floor
without changing V3 support semantics.

Same-support pairing (`paired_same_support_delta`) does not apply to the
disjoint candidate/baseline groups (see §7).

A complete support/identifiability floor for confirmatory decision
therefore remains **unbound** until authors bind confirmatory identity.

---

## 11. Final classification mapping — not fully bound

Intended taxonomy (not mechanically mapped, because §7–§9 are blocked):

```text
NO_EVIDENCE
NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT
DETECTED_BUT_NOT_ROBUST
ROBUST_CANDIDATE
```

`ROBUST_CANDIDATE` would not mean validated alpha, a profitable strategy,
a production signal, permission to trade, or automatic OOS promotion.
Protected validation/OOS remains untouched.

This unit does not fill the mapping gap.

---

## 12. Explicit non-actions

- No MARKET-01 preregistration freeze, ARM, or execution.
- No calculation of `reversal_return` on candidate/baseline episodes.
- No V3 run on MARKET data.
- No threshold or window alteration (`90th` / `75th` / `0.25`;
  `30m` / `30m` / `60m`).
- No B2-06 unblock; no funding use.
- No V3 scientific modification; no V4.
- No new generic matcher, confirmatory test, or regime framework.

---

## 13. Next step (this design unit; now satisfied)

This design unit required author decisions on:

1. `BLOCKER_BASELINE_MATCHING_SEMANTICS`
2. `V3_CONFIRMATORY_ESTIMAND_NOT_MAPPABLE_TO_TWO_GROUP_REVERSAL_CONTRAST`
3. `BLOCKER_ROBUSTNESS_SEMANTICS`

Those decisions are now bound in the live preregistration. Next required
project step: **separate MARKET-01 prereg freeze**. Not this file.
