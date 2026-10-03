# C025-R1 design repair

Owner-authorized manual escalation of GV0V03L40 / C025. The original card is unchanged. Original critic judgments stay REJECT.

```
SOURCE_CARD = C025
DESIGN_VERSION = C025-R1
SELECTION_PIPELINE_OVERRIDDEN = true
OVERRIDE_REASON = Owner-authorized scientific audit of C025 after questioning critic rejection; original critic judgments remain immutable.
ORIGINAL_CARD_CHANGED = false
R1_REASON = PRE_OUTCOME_NO_LOOKAHEAD_REPAIR
NOVELTY_VERDICT = REJECT
FEASIBILITY_VERDICT = REJECT
RED_TEAM_VERDICT = REJECT
RED_TEAM_FAILED_CHECKS = CAUSALITY, CONFOUNDING_ADDRESSED, NO_LOOKAHEAD
```

## Lookahead defect

The original null says: "Bursts with another burst inside the outcome window are excluded." Whether another burst occurs after T is future information. That rule is not executed.

C025-R1 admits an eligible burst only when no previously accepted event falls in the preceding 60 minutes. The outcome window is then fixed. A later burst may be flagged as contamination. It cannot drop the event, and the primary result is not recomputed after dropping contaminated events.

## Claim

CLAIM_TYPE = INCREMENTAL. TARGET_CLASS = UNCONDITIONAL. COMPLEXITY_CLASS = ATOMIC.

Primary claim: at matched high-volume BTC perpetual bursts, strong taker one-sidedness is associated with greater subsequent impact-per-volume persistence than a two-sided burst.

Allowed reading: consistent with maker inventory loading. Forbidden reading: maker inventory constraints caused the effect.

## Frozen primary cell

```
ONE_SIDE_THETA = 0.70
VOLUME_QUANTILE = 0.999
W_MINUTES = 30
TWO_SIDED_MAX = 0.30
```

The other 11 generated cells are not confirmatory and were not estimated.

BURST(t) compares quote volume at t with the linear quantile of the preceding 43200 minutes. ONE_SIDE(t) = 2 * abs(taker-buy quote / quote - 0.5). The 1m log return is log(close/open) of that minute. PRE_IMPACT uses [t-60m, t) only. POST_IMPACT was not computed.

## Stop

The count-only pass, before any post-T target, found one admitted one-sided event and 879 admitted two-sided events (2895 raw bursts, 1251 neither-arm). Every predeclared matching collapse leaves a single one-sided event. GV0R02 V2 returns `INFORMATIONALLY_WEAK` with blocker `MDE_TOO_LARGE` (effective N 0.994, stress MDE 5.62, stress power 0.035, bar 0.30 SD).

No preregistration, no execution permit, and no outcome were opened. Theta, quantile, and horizon were not changed.
