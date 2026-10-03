# Divergence program — owner decisions V3

**Date:** 2026-10-02
**Decided by:** owner, after `DIVERGENCE_FULL_HISTORY_RESEARCH_V0`
**Supersedes:** nothing in V1 or V2. It accepts the full-history result and authorizes a new research object.
**Result accepted:** `DIVERGENCE_FULL_HISTORY_RESEARCH_V0_REPORT.md` (freeze `c122040`, validation `fca3ab5`, stage 2 `b100619`)

```
DIVERGENCE_FULL_HISTORY_RESEARCH_V0         = ACCEPTED
REGULAR_DIVERGENCE_INSIDE_SUPPORT           = no large practical edge shown
VALIDATION_A_MINUS_B                        = +0.011 [-0.087, +0.109]; rules out the targeted +15 pp
POOLED_A_MINUS_B                            = small, about +1-3 pp
CONFIRMATORY_SEED_FOR_A_MINUS_B_GE_15PP     = not to be created
REINTERPRETATION_AS_DIVERGENCE_WORKS        = forbidden
REVERSAL_SELLER_EXHAUSTION_THEME            = open (not closed)
NEXT_UNIT                                   = SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0 (feasibility only)
RSI_GRADIENT_SUPPORT_CANDIDATE              = recorded as a separate candidate; not primary; no unit authorized
SEED_CREATION                               = not authorized
E1_PROTECTION                               = absolute
PR_303_MERGE                                = not authorized
```

## `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0`

This is a **new research object**. It is not a continuation or a rescue of SEED-0001, and it is not a re-analysis of the divergence result.

**Question.** Within an already-present support state, does a pre-specified state of weakening selling pressure and non-expanding open interest carry useful information about subsequent reversal and trading outcomes, independently of classical oscillator divergence?

**Motivation, not evidence.** The exploratory observation was about +4 pp. It was found on already-opened data and is not prior confirmatory evidence.

**Scope: feasibility only.**
- No new protected outcome is opened.
- No variant is selected by outcome performance.
- No SEED is created.

**Candidate state.** A precise point-in-time definition is frozen before use. It must express all of these:
- price makes or approaches a new local low;
- aggressive selling weakens relative to the prior downswing or a local baseline;
- OI does not expand materially, and may contract;
- support is present;
- no oscillator-divergence flag is required.

Each threshold and transformation must be justified. Several defensible formulations are carried as separate variants.

**Primary candidate estimand: `E − S`.**
- E = support + the frozen exhaustion state.
- S = support without it.
- MACD and RSI divergence flags appear only as descriptive or mechanistic covariates, never in the inclusion rule.

**Effect sizes.** Power is reported at 3, 5, 7.5 and 10 pp, together with MDE80. The decision focuses on whether an effect of about 4–5 pp can be measured in a realistic time; if not, the unit says so explicitly. 15 pp is no longer the relevant scale.

**Data surfaces.** Already exposed, and usable as discovery: 2023–2024, and the opened six-symbol 2025-01-01..2026-08-15 surface.
- **Allowed uses:** detector construction, count estimation, dependence estimation, feasibility and descriptive mechanism work.
- **Not allowed:** presenting them as pristine validation for this hypothesis.
- **E1-RUN-001** is absolutely protected. It is never reached directly or through feature lookbacks, baselines, detector windows, outcome horizons or auxiliary joins.
- **Clean confirmation.** Prospective data after a new freeze is the only clean independent confirmation surface, unless another protected source is explicitly identified.

**Panel.** The panel is BTC, ETH, SOL, BNB, DOGE and XRP. It is not expanded merely to increase nominal N. Any expansion needs a fixed eligibility rule and its own dependence analysis.

**Dependence (lessons from the divergence panel).**
- Symbols are strongly cross-correlated, and simultaneous episodes are not independent replications.
- Weekly and common-market clustering is modelled, and overlapping outcome windows are accounted for.
- **Reported:** nominal N, effective clustered information, unique decision times, decision dates, common-market clusters, and symbol and epoch concentration.

**Feasibility questions to answer:**
1. How frequent is the exhaustion state?
2. How frequent is support-only?
3. What is the expected primary sample under honest clustering?
4. What is MDE80?
5. Can 4–5 pp be tested in a realistic horizon?
6. How much prospective data would that need?
7. Does a binary state throw away too much information?
8. Would a continuous selling-pressure/OI score improve efficiency materially, without unacceptable researcher degrees of freedom?

**Continuous score rules.** Feasibility only. The transformation is defined before any clean outcome, and is not selected by outcome performance.

## `RSI_GRADIENT_SUPPORT_CANDIDATE`

**Basis.** The full-history exploratory finding that, inside support-only episodes, larger continuous RSI14/RSI21 deltas between pivots go with a higher +1R rate (about +3.8 pp per SD). It was found on data that includes the validation slice.

**Status.**
- Recorded as a separate candidate only. It is not promoted to primary.
- It may receive its own future feasibility unit if warranted.
- It is not combined with the selling-exhaustion state into one optimized model.

## Documentation-policy correction

Project-level status documents stated that all of 2025/2026 was unopened or sealed. That is no longer accurate. The minimum status lines are corrected to:

- **Opened.** The 2025-01-01..2026-08-15 surface (exclusive read horizon) was opened on 2026-10-02 for the divergence/support research program (`DIVERGENCE_FULL_HISTORY_RESEARCH_V0`). It covers the six USD-M perpetuals BTC, ETH, SOL, BNB, DOGE and XRP: 1m klines, bookDepth and OI metrics.
- **No longer pristine OOS** for hypotheses generated from divergence, support or mechanism research.
- **Still usable** as previously exposed historical data for estimation and feasibility.
- **E1-RUN-001** stays protected and unopened: the holdout `[2026-08-16, 2026-08-25 17:20)`, and every byte at or after 2026-08-15.
- **Not globally spent.** This is not a claim that all of 2025/2026 is spent for every unrelated research family. Whether this surface can serve as OOS for an unrelated family is decided per family by the owner. Other venues, symbols and observables of 2025/2026 have not been opened by this program.

Historical records that said "unopened" at their own date are not rewritten.
