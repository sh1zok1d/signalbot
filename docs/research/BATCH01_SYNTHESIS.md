# Signalbot R2 Batch01 Synthesis and Closeout

**Date:** 2026-08-28  
**Status:** `BATCH01_CLOSED / 0_OF_5_PROMOTED`

## Scope and evidence boundary

R2 Batch01 comprised five preregistered development-only mechanism families on
`CORE_BTC_BINANCE_V0`:

1. H01 — compression -> volatility expansion;
2. H02 — failed breakout -> mean reversion;
3. H03 — extreme impulse -> continuation/exhaustion;
4. H04 — trend pullback -> continuation;
5. H05 — taker imbalance -> subsequent return.

All five development claims are closed without promotion. 2025 validation and
2026 OOS remain untouched for H01-H05. No Batch01 result authorizes opening
those windows to rescue a rejected claim.

## Family-level result

| Family | Development result | Interpretation |
|---|---|---|
| H01 | `H01_KILL / REJECTED` | Compression predicted lower, not higher, subsequent realized volatility. Reverse volatility persistence is `POSTHOC_UNTESTED`. |
| H02 | `H02_KILL` | Closing back inside a range did not establish a failed-breakout-specific mean-reversion mechanism; the successful-breakout control was stronger. |
| H03 | `H03_REJECTED_SPECIFIC_CLAIM` | Mixed/null surface with sign instability across horizons, thresholds, direction and years; no robust continuation or exhaustion candidate. |
| H04 | `H04_REJECTED_SPECIFIC_CLAIM` | Some controlled local effects existed, but not as a broad robust parameter neighborhood. Moderate-depth/local patterns remain `POSTHOC_UNTESTED`. |
| H05 | `H05_REJECTED_SPECIFIC_CLAIM` | Raw directional asymmetry existed, but MPIE and structural incremental gates were 0/45 on both preregistered orientations. |

Canonical aggregate result:

```
BATCH01_PRIMARY_FAMILIES = 5
BATCH01_PROMOTED_FAMILIES = 0
BATCH01_2025_VALIDATION = UNTOUCHED
BATCH01_2026_OOS = UNTOUCHED
```

## Cross-hypothesis synthesis

Batch01 does not show that crypto has no predictable structure. It shows that
the five tested formulations did not earn promotion under the project's
incremental-information standard.

The recurring failure mode is important: a feature can look predictive in raw
conditional outcomes while adding little or no information once compared with
simpler descriptions of the same market state. Batch01 therefore rejects the
practice of promoting a detector merely because `P(Y|X)` or an average
conditional return looks favorable.

For future work, the relevant question is:

> Does this feature add stable information beyond a simpler causal market-state
> baseline on the same support?

This is stronger than asking whether the feature is correlated with what
happens next.

## E1 / VPS detector closeout

The earlier VPS/E1 development run evaluated three frozen Stage-5 detector
families:

- `TREND_PULLBACK`;
- `COMPRESSION_BREAKOUT`;
- `CONFIRMED_BREAKOUT`.

Their chronological holdout was never opened.

Batch01 did **not** rerun the exact E1 detector code and therefore is not treated
as a mathematical replication of E1. The closeout decision instead combines:

1. the already-consumed E1 development evidence, which did not justify
   promotion of any of the three current formulations; and
2. the broader multi-year Batch01 mechanism evidence, which did not provide a
   new reason to rescue those formulations.

Canonical project status:

```
E1_TREND_PULLBACK = RETIRED_CURRENT_FORMULATION
E1_COMPRESSION_BREAKOUT = RETIRED_CURRENT_FORMULATION
E1_CONFIRMED_BREAKOUT = RETIRED_CURRENT_FORMULATION
E1_HOLDOUT = UNOPENED_AND_NOT_SPENT
```

`RETIRED_CURRENT_FORMULATION` does not mean that every possible future
trend, compression or breakout hypothesis is disproved. Any materially new
formulation must receive a new hypothesis identity, preregistration and clean
evaluation path. The frozen E1 holdout must not be opened merely to rescue the
retired formulations.

## Post-hoc quarantine

The following remain hypothesis-generation material only:

- H01 reverse volatility-persistence pattern;
- H04 local/moderate-depth controlled pattern;
- H05 BUY/SELL asymmetry and horizon-dependent sign behavior;
- any simplified child derived from E1 development.

All are `POSTHOC_UNTESTED`. None is a validated edge and none may be
back-filled into Batch01 as a pass.

## Decision for the next program

Do not continue mechanically to H06.

The next engineering task is:

`V2_RESEARCH_HARNESS_V1`

Minimum inherited controls:

- same-support candidate/control comparisons;
- mandatory dataset identity/provenance before outcome reads;
- deterministic fail-closed promotion evaluation;
- adversarial tests for no-lookahead and support/comparator semantics.

After that harness is independently checked, design Batch02 around distinct
information families rather than additional transformations of the same price
state. One H04-derived child may be considered only if explicitly labeled as a
post-hoc child with a new clean evaluation path.

```
BATCH01 = CLOSED
BATCH02 = NOT_STARTED
H06 = NOT_AUTHORIZED
NEXT_ENGINEERING_STAGE = V2_RESEARCH_HARNESS_V1
NEXT_RESEARCH_DESIGN_STAGE = BATCH02_DESIGN
```
