# GV0R01-C012 outcome-blind design and power

The within-stratum label permutation in this file is historical. It failed the pre-outcome global-invariance gate and is superseded for inference by `GV0R01_C012_INFERENCE_AMENDMENT.json`. The claim, events, controls, endpoint, alpha, and falsifiers are unchanged. No outcome was opened.

`STATUS = PREREGISTRATION_CANDIDATE`
`OUTCOME_BLIND_GATE = EXECUTION_JUSTIFIED`
`EXECUTION_AUTHORIZED = false`
`NEXT_UNIT = GV0R01_C012_ONE_SHOT_EXECUTION`

This unit freezes the C012 design and its ex-ante power. It does not execute C012. No BTC series was opened, no pre-release return was computed, and protected 2025/2026 values stay sealed. Generator V0 memory was not modified.

Machine contract: `GV0R01_C012_OUTCOME_BLIND_DESIGN.json`. Power block: `GV0R01_C012_POWER.json`. Builder: `scripts/research/gv0r01_c012_design.py`.

## Claim

Anticipation of a scheduled FOMC statement or CPI release produces a signed drift in the Binance BTCUSDT perpetual over the 24 hours ending one minute before the release, relative to the same year, weekday and UTC hour on weeks with no such release.

The null is equality of the two means. The alternative is two-sided. The sign is not pre-specified. This is the card's claim (`GV0R01_STREAM_B_FEASIBILITY_TRIAGE.json`, C012). It is not a trading rule.

## Primary specification

One primary variant: `FOMC_AND_CPI` with `PRE_WINDOW_H = 24`.

That choice uses only calendar facts. The event set is the set named in the card. The window is the longest card horizon for which every canonical CPI event is `SAFE_FOR_W24`. The other five card variants are computed later as a descriptive grid and cannot change the classification.

`PRE_RET_24 = ln(close at T-1min) - ln(close at T-1min-24h)` from the pinned `CORE_BTC_BINANCE_V0` 1m close, snapshot `717d37a4…`. No bar at or after T enters.

The primary endpoint is `DELTA_24`, the mean event return minus the mean of 1:1 matched controls. Matching is inside `YEAR x WEEKDAY x UTC_HOUR`, without replacement, seed 12012, using the existing stratified sampler. Inference is a two-sided stratified label permutation, 5000 draws, seed 12012, alpha 0.05. The 95% interval uses the permutation-null standard deviation and does not replace the p-value.

Three conjunctive falsifiers, taken from the card:

1. The permutation does not reject.
2. The yearly mean difference shares the pooled sign in fewer than 3 of 5 years.
3. The same contrast on the 24 hours before the primary window is significant in the same direction, or more than half of events have no control within 0.25 log-return on that prior window.

## Calendar

| Family | N | Clock |
|---|---|---|
| CPI, all `VERIFIED_PREANNOUNCED` | 60 | 08:30 America/New_York, so 12:30Z (EDT) or 13:30Z (EST) |
| FOMC, inherited from `D11_FOMC_OFFICIAL_V0` | 39 | 14:00 ET, so 18:00Z or 19:00Z |
| Primary set | 99 | 19, 20, 20, 20, 20 by year 2020–2024 |

Rescheduled CPI events: 0. Unresolved CPI events: 0. Digest `760ed2c5…`.

Same-family 24h windows do not overlap (minimum gaps 647h and 984h). Two CPI–FOMC pairs overlap, both 5.5h apart: `BLS_CPI_REF_2020_05` with `FOMC_20200610`, and `BLS_CPI_REF_2024_05` with `FOMC_20240612`. Both events stay in the primary set. A sensitivity that drops the later event of each pair cannot change the classification. The 99 events fall in 94 ISO weeks.

Eleven CPI events have a pre-cutoff evidence gap above 30 days. They stay in the primary set. Sensitivity `S_GAP` repeats the endpoint without them and cannot change the classification.

Every occupied stratum has more same-weekday calendar slots than events, so 1:1 matching is possible on the calendar. Bar completeness is an execution check under the missing-data rule (drop and count; missing rate above 5%, or any year left with fewer than 4 events, is `INCONCLUSIVE_DISCOVERY`). No winsorization and no outlier deletion.

## Dependence and power

The nominal count is 99. It is not 99 independent draws. The planning sample is the 94 ISO weeks, then divided by 2 as a stated variance-inflation stress (`n_eff = 47`). Five years are the sign-stability gate, not the sample size.

No C012 return was used. The 24h BTC log-return standard deviation is a stated scenario range, 0.02 / 0.04 / 0.06, not a fit.

| Sample | n | MDE (sigma) | Power at 0.50 sigma | Power at 0.25 sigma |
|---|---|---|---|---|
| Nominal events | 99 | 0.282 | 0.999 | 0.701 |
| ISO-week clusters | 94 | 0.289 | 0.998 | 0.679 |
| Variance inflation 2 | 47 | 0.409 | 0.929 | 0.403 |

The frozen MDE formula is `(z_{1-α/2} + z_{0.80}) / sqrt(n_eff)`. It is the two-sided 80% detectable size of a mean of `n_eff` observations, in units of the standard deviation of those observations. The figures 0.82%, 1.63% and 2.45% are that standardized MDE multiplied by the stated standard deviation of an individual 24h log return (0.02, 0.04, 0.06). They are not the standard deviation of an event-minus-control paired difference, and the variance inflation is already inside `n_eff = 47` rather than a second scaling. Because the endpoint is a difference of two equal-sized means, an independent equal-variance reading makes the standard error larger by `sqrt(2)` than a one-sample mean of the same `n_eff`. The frozen gate compares 0.409 sigma with the 0.50 bar under the formula as written. This note does not change that formula, the bar, or the gate.

`TARGET_POWER = 0.80` refers to that primary mean test only. The five-year sign rule is falsifier F2. It is required for `PROMISING_PROTOTYPE` and was not given its own power calculation. A 0.25-sigma drift remains unpowered (about 0.40 under the stress). The planning MDE, 0.409 sigma, is under the 0.50 bar, so the gate is `EXECUTION_JUSTIFIED`.

A drift of 0.25 sigma is not powered (power about 0.40 under the stress). A later null would not rule one out. Alpha is not relaxed and no subgroup is added to change that.

## Gate

`EXECUTION_JUSTIFIED`. Execution of this candidate is still not authorized. A later unit may run it only under this contract. Realized returns cannot move the gate.

## What remains

Scientific choices for the primary endpoint are frozen: event set, window, transform, matching, seeds, alpha, falsifiers, missingness, outliers, and the descriptive grid. The execution unit still has to apply those rules to the pinned 1m file. It does not get to choose a variant.

## Validation

`python3 -m scripts.research.gv0r01_c012_design` prints `VALID`. `tests/research/test_gv0r01_c012_design.py` and the CPI archive tests passed (32).
