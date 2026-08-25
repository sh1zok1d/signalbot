# E1-RUN-001 — Final Pre-Holdout Freeze

Status: **FROZEN BEFORE ANY HOLDOUT OUTCOME READ**  
Date: 2026-08-25  
Holdout: `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`

This is an append-only prospective amendment recorded after development candidate/control/ablation outcomes were consumed and while the chronological holdout remains unopened. The original `docs/E1_DETECTOR_SEPARATION_PREREG.md` remains unchanged as the historical preregistration artifact. This file freezes the final holdout reporting, delay and economic-friction stress rules. No detector threshold or production Stage-3/4/5 rule may change for E1-RUN-001.

## 1. Holdout is opened once

Before the first holdout future-price query:

1. regenerate the already-preregistered FULL and ablation/simple-baseline candidate populations on the holdout decision grid using only information available at each T;
2. record outcome-free counts/directions/overlap;
3. fail closed if frozen FULL holdout counts do not reproduce the previously recorded candidate census (`TP=105`, `CB=17`, `FB=19`);
4. freeze the candidate artifact;
5. only then run one holdout outcome evaluation.

After holdout outcomes are opened, no parameter, family definition, baseline definition, horizon, delay, cost grid, matching rule, or verdict criterion may be changed inside E1-RUN-001.

## 2. Variants to report on holdout

Report every already-preregistered variant; do not select a development winner and test only that winner.

TREND_PULLBACK:

- `TP_FULL`
- `TP_NO_4H`
- `TP_NO_1H`
- `TP_NO_CONTEXT`

COMPRESSION_BREAKOUT:

- `CB_FULL`
- `CB_NO_TAKER`
- `CB_SIMPLE_COMPRESSION_BREAKOUT`
- `CB_ORDINARY_RANGE_BREAKOUT`

CONFIRMED_BREAKOUT:

- `FB_FULL`
- `FB_NO_CONTEXT`
- `FB_DUMB_48H_LEVEL_BREAKOUT`

`FB_NO_CONTEXT` and `FB_DUMB_48H_LEVEL_BREAKOUT` are one Stage-5 population and one evidence item; the alias is shown for preregistration traceability only.

## 3. Outcome reporting

No primary horizon is selected after development. Report all frozen horizons equally:

- 15m
- 30m
- 1h
- 2h
- 4h

For every population report:

- raw N;
- LONG/SHORT N;
- terminal directional-return mean and median;
- positive share;
- median MFE and MAE;
- path completeness;
- 30m and 60m time-gap cluster counts;
- UTC-day concentration.

Do not turn raw qualification count into an independence claim.

## 4. Nested ablation rule

For a gate-removal ablation, FULL is a subset of the ablated population. Therefore report three objects:

- `FULL`;
- `ABLATION_ALL`;
- `ADDED_ONLY = ABLATION_ALL \ FULL` on exact `(T,direction)` identity.

The value of a removed gate is judged primarily by the behavior of `ADDED_ONLY` relative to FULL, not by pretending FULL and ABLATION_ALL are independent samples.

## 5. Matched-random controls on holdout

The development matching rule is reused unchanged with fixed seed `20260825`.

For each evaluated population independently:

- match within `(variant/family, UTC day)`;
- preserve the candidate direction;
- choose legal decision boundaries with complete/reference-usable data;
- exclude that population's own candidate times;
- sample without replacement where feasible;
- report any unmatched rows explicitly rather than relaxing the rule silently.

FULL-family comparisons retain the original family matched-random interpretation. Simplified variants must also beat their own matched-random control before they can support a final `SIMPLIFY` verdict rather than merely showing that FULL was worse.

## 6. Direction inversion

For each FULL family, report same-T direction inversion exactly as on development. This remains a negative control, not a candidate alternative strategy.

A family whose inverted direction is materially and consistently better than its frozen direction is evidence against the directional hypothesis, not permission to flip the production signal inside E1-RUN-001.

## 7. Same-day time-shift control

To complete the preregistered time-shift diagnostic without outcome-driven offset selection:

- apply a fixed `+6h` (`72` x 5m boundaries) circular shift within the same UTC calendar day to every FULL-family candidate T;
- preserve family and direction;
- do not search for a better offset;
- candidate-time collisions are allowed and their overlap share is reported;
- shifted rows still require complete/reference-usable outcome paths.

This diagnostic asks whether exact qualification timing matters beyond coarse same-day regime exposure.

## 8. Historical delay stress

Only the resolution-supported delays from the original preregistration are allowed:

- `0s` (contract-point result already represented by P_T);
- `+60s`;
- `+120s`.

No 15s/30s synthetic result is allowed.

For a delay `d`:

- delayed entry reference is the Binance 1m close at the end of the minute reaching `T+d`;
- the terminal endpoint remains the original frozen horizon `T+h`, so delay shortens the actionable path instead of granting an extra h minutes;
- MFE/MAE for the delay diagnostic are measured from delayed entry through the original `T+h` endpoint;
- rows with missing delayed-entry/path data are reported incomplete.

Delay stress is reported for FULL families and for any simplified variant that otherwise qualifies for a possible `SIMPLIFY` verdict.

## 9. Economic-friction stress

E1 is a detector-separation study, not an execution backtest. Primary statistics remain gross directional returns.

As a generic economic-sensitivity check, subtract the following fixed total round-trip friction from terminal directional return:

- `0 bps`
- `5 bps`
- `10 bps`
- `20 bps`

These are scenario stresses, not claims about a specific exchange/account fee schedule. No fee grid is tuned to the observed outcomes. MFE/MAE remain raw path diagnostics.

## 10. Uncertainty / concentration

Report dependence rather than pretending iid observations:

- nominal row N;
- 30m and 60m time-gap cluster N;
- per-UTC-day result table;
- UTC-day block bootstrap of the mean directional return with fixed seed `20260825` and `10,000` resamples, 95% percentile interval.

The bootstrap interval is descriptive; no single p-value threshold decides E1.

## 11. Final family-verdict logic

Original allowed verdict vocabulary remains:

- `SURVIVES`
- `SIMPLIFY`
- `DEMOTE_TO_BASELINE`
- `KILL`
- `INCONCLUSIVE_SAMPLE`

Apply it prospectively as follows.

### SURVIVES

Requires the frozen FULL family to show reasonably stable positive separation from its matched/random/time-shift controls across multiple horizons, without dependence on one UTC day, and without a simpler preregistered variant clearly matching or improving it.

### SIMPLIFY

Requires FULL not to earn its extra complexity **and** at least one preregistered simpler variant to reproduce materially better/stabler holdout separation than FULL and its own matched-random control. Merely being "less negative than FULL" is insufficient.

### DEMOTE_TO_BASELINE

Use when the family is useful mainly as a descriptive price-structure baseline but does not demonstrate incremental information from its added context/flow machinery.

### KILL

Use when the frozen directional hypothesis is adverse/indistinguishable from controls on holdout, especially if inversion performs better, or when neither FULL nor preregistered simpler variants show meaningful positive separation.

### INCONCLUSIVE_SAMPLE

Use only where the untouched family holdout remains too small/unstable to distinguish the above outcomes. Small N must not be converted into a favorable verdict.

## 12. Global Level-0 decision

The original global fail condition remains unchanged:

> If all three frozen Stage-5 families fail to separate from simple/matched controls and the full variants do not beat simpler price-only/ablated versions, stop downstream V2 lifecycle/product expansion and conduct a hypothesis review rather than adding features or tuning thresholds.

Development currently places FB near `KILL`, TP near `SIMPLIFY/KILL`, and CB near `SIMPLIFY/INCONCLUSIVE`; these are development-only priors. The sealed holdout decides the final E1 verdict under the rules above.
