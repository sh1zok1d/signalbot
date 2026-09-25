# Beta V0 prospective forward evaluation (prereg-like product/research sidecar)

**Evidence label:** `PROSPECTIVE_PRE_REGISTERED_FORWARD_EVALUATION / OWNER_UNBLINDED`
**Frozen:** 2026-09-25, before any real-user launch. No beta data exists yet.
**Eligible event version:** `BETA_EVENT_RULES_V1`, `rules_digest 2e0afa4785675e7a3777627f45647f76268a7cdad3e0639c078ee5ccc7605f44`, state schema 1, outcome version `BETA_OUTCOME_V1`.

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
