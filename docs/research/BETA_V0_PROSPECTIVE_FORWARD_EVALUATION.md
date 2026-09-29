# Beta V0 prospective forward evaluation (prereg-like product/research sidecar)

**Evidence label:** `PROSPECTIVE_PRE_REGISTERED_FORWARD_EVALUATION / OWNER_UNBLINDED`
**Frozen:** 2026-09-25, before any real-user launch. No beta data exists yet.
**Eligible event version:** `BETA_EVENT_RULES_V1`, `rules_digest 2e0afa4785675e7a3777627f45647f76268a7cdad3e0639c078ee5ccc7605f44`, state schema 1, outcome version `BETA_OUTCOME_V1`.

**Version transition note (before any beta data was collected).** The state tape moved to schema 2 with the temporal-context amendment. The rule thresholds are unchanged. Eligible events are now `BETA_EVENT_RULES_V1` under `rules_digest 9e9d2c631a1abfdb710dc2147835b3a0ccd4620512d3a0d6828140c96de17210`, state schema 2. Nothing was recorded under the schema-1 digest above.

The owner sees beta outcomes live, which is why this is labeled owner-unblinded. It is **never** called independent confirmation merely because the data arrived after launch. Everything else observed in beta outcomes is exploratory unless separately preregistered.

## Q1 (primary). Does a TRIGGERED event precede a larger absolute 4h range than matched non-event controls?

- **Unit:** each TRIGGERED episode of one event family (analysed separately per family, no pooling across families). The anchor is its trigger decision boundary.
- **Outcome:** `realized_range_pct` at horizon `4h` from `beta_episode_outcomes` (latest revision, status `COMPLETE`). The same statistic is computed for controls from the tape and 1m bars with identical composite rules.
- **Controls (from the frozen state tape only):**
  - Candidates are LIVE tape buckets with `evaluation_fresh` and all core families usable.
  - A control bucket must not be within ±4h of any open or triggered episode of any type.
  - For each event, up to 5 controls are drawn from the same UTC hour-of-day ±1h and from the same 30d-percentile tercile of the previous 1h realized range, measured strictly before the anchor.
  - Ties are broken by nearest calendar time.
  - Controls are sampled without replacement.
- **Statistic:** the median over events of (event range − mean of its matched controls' ranges). A one-sided sign test on the per-event differences gives the direction; a 95% bootstrap CI (events resampled, 10,000 draws, seed 20260925) gives the magnitude.
- **Minimum sample and stopping:** analyse a family only once it has 30 or more TRIGGERED episodes with complete 4h outcomes. Stop at the first of 60 episodes or 12 weeks. There is no interim look at the statistic. Only the counts are monitored.
- **Reading:** a positive CI excluding 0 is "descriptively associated with larger subsequent absolute range". It is not a direction claim and not a trading edge.

## Q2 (secondary)

The same design, applied to the absolute 1h range.

## Analysis-code identity

Not yet implemented. The analysis script and its sha256 must be frozen and recorded here **before** any family reaches its minimum sample. Changing Q1/Q2 afterwards creates a new evaluation. It never rescues this one.

## Boundaries

- Protected 2025/2026 research data is not used.
- No threshold tuning is motivated by these outcomes.
- The result cannot promote any rule into a predictive claim without a separate promotion gate.

## Amendment — 2026-09-28: Q1/Q2 superseded before any statistic was inspected

**Status:** `SUPERSEDED_BEFORE_INSPECTION`. The text above is kept unchanged as the historical preregistration.

- **Live collection had started.** Production beta collection (state tape, detector episodes, forward outcomes) began before this amendment. This document's earlier line "No beta data exists yet" was true when it was frozen on 2026-09-25; it is no longer true.
- **Nothing was inspected.** As of this amendment, no Q1 or Q2 statistic, no matched-control comparison, no per-event difference, no sign test and no bootstrap interval has been computed or looked at. The analysis script was never written or frozen. No interim Q1 result exists that could have been used for anything.
- **Why Q1/Q2 are superseded.** Product development now intends to show users descriptive historical follow-up statistics for past comparable events: absolute realized range after previous events, an ordinary same-time baseline, and a volatility-matched baseline in the spirit of Q1 (`docs/BETA_HISTORICAL_FOLLOW_UP_V0.md`). That exposure would happen before this preregistration's stopping rule (30–60 TRIGGERED episodes per family, or 12 weeks). Numbers derived from the same observations would be visible to the owner and to users during the observation window.
- **Consequence.** Observations collected after this decision cannot be claimed as an untouched realization of the original Q1/Q2 preregistration. The original evaluation is therefore closed as superseded, not completed. It is neither passed nor failed.
- **No tuning happened.** No detector threshold, streak, duration, gating rule or event definition was changed because of any outcome. `BETA_EVENT_RULES_V1` and its rules digest are unchanged by this amendment.
- **Future confirmation.** Any future confirmatory evaluation needs a new prospective contract, frozen before its data exists, with a new future observation window. It must also state explicitly how it handles the product's own display of historical follow-up statistics.
- **Not done here.** Q1 was not computed while writing this amendment.
