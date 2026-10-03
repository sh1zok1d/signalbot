# SEED-0001 regular divergence — outcome-blind feasibility report

**Status:** `FEASIBILITY_COMPLETE / OUTCOMES_NOT_OPENED`
**Date:** 2026-10-02
**Verdict (frozen rule):** `INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR`
**Machine record:** `SEED0001_FEASIBILITY_REPORT.json`
**Prereg:** `SEED0001_REGULAR_DIVERGENCE_PREREG.json`, SHA256 `c6f02ecb…`, frozen in commit `8e213d3` before any data download

```
OUTCOMES_COMPUTED                 = false (no future return, +1R/-1R, +2R/-1R, MFE/MAE or post-decision price)
PROTECTED_2025_2026_BYTES_FETCHED = false
DEFINITIONS_CHANGED_AFTER_COUNTS  = false
PIT_TRUNCATION_AUDIT              = 30/30 identical (BTC), 30/30 identical (ETH)
OUTCOME_OPENING_AUTHORIZED        = false
NEXT_UNIT                         = OWNER_DECISION (see "What this means")
```

## Data

| Object | Result |
|---|---|
| 1m klines 2022-11..2024-12, BTCUSDT and ETHUSDT | 52/52 months verified against the published checksum and against the pinned CORE inventories (BTC via the C012 manifest, ETH via the `CORE_ETH_BINANCE_V0` inventory). 19,008 complete 1h bars per symbol, 0 incomplete. |
| bookDepth 2023-01-01..2024-12-31 | BTC: 728/731 days, missing in the archive 2023-02-08, 2023-02-09, 2024-04-18. ETH: 729/731, missing 2023-02-08, 2023-02-09. Median 120 snapshots per hour. 98.5% (BTC) and 98.6% (ETH) of hours from 2023 have a value. |

The dataset manifest is `docs/research_data/SEED0001_BINANCE_UM_1H_BOOKDEPTH_V0/DATASET_MANIFEST.json`, digest `21c4bd48…`. It pins every object's SHA256. Raw bytes are not committed.

## Funnel

| Step | BTC | ETH |
|---|---:|---:|
| swing lows with T in the decision window | 1794 | 1791 |
| not a pronounced decline | 344 | 357 |
| not a lower low | 682 | 665 |
| **population** | **768** | **769** |
| risk width < 0.25 ATR | 5 | 5 |
| support hour missing | 7 | 9 |
| book baseline immature | 13 | 19 |
| **eligible** | **743** | **736** |

## Arms

| Arm | BTC episodes | BTC dates | 2023H1 / H2 / 2024H1 / H2 | week clusters | ETH episodes | ETH dates |
|---|---:|---:|---|---:|---:|---:|
| **A** support + divergence | **36** | **33** | 10 / 6 / 9 / 11 | 24 | **32** | **27** |
| B support only | 259 | 199 | 74 / 49 / 68 / 68 | 81 | 264 | 213 |
| C divergence only | 63 | 62 | 14 / 22 / 16 / 11 | 44 | 48 | 46 |
| D neither | 385 | 306 | 82 / 126 / 85 / 92 | 97 | 392 | 299 |

ETH A by half-year: 10 / 6 / 3 / 13.

**Structure (BTC).**
- **Divergence is the rare component.** It holds in 13.3% of eligible episodes, while support holds in 39.7%.
- **Family counts:** 468 episodes with no divergent family, 176 with one, 68 with two and 31 with all three.
- **Shares by family:** RSI 19.9%, MACD 21.5%, CVD 13.1%.

A is rare because the two conditions rarely coincide, and A is not concentrated in one half-year.

## Dependence and clustering (BTC)

| | Value |
|---|---|
| weekly clusters (the frozen inference clusters), G | 101; mean 7.4 episodes, max 14 |
| A episodes in distinct weeks | 24 weeks, at most 3 A episodes per week |
| 48h overlap chains (descriptive) | 71 chains, mean size 10.5, max 42, singletons 9.9% |
| A episodes sharing a 48h chain with another episode | 36 of 36 |
| 48h windows crossing a week boundary | 167 of 743 (22%) |

Decline episodes come in long overlapping runs, so the effective N is far below 743. Weekly clusters cover most overlap, though 22% of windows straddle a week boundary. The chain-clustered sensitivity (S4) would have 71 clusters.

## Attainable alpha

- **Holm thresholds:** 0.025 and 0.05, two-sided.
- **Reference:** t with 100 degrees of freedom. The critical t is 2.28 at step 1 and 1.98 at step 2.
- **No discrete floor.** The p-value floor does not bind, so alpha is attainable. A sits in only 24 weekly clusters, and C in 44.

## Covariate support (outcome-blind)

- **Max |SMD|, A vs B or A vs C:** 0.61 for BTC (log RV24, A vs C) and 0.63 for ETH (time-of-day sine, A vs C). Both are under the 1.0 limit, so support passes.
- **A vs B and A vs C:** A has a somewhat deeper decline (0.36–0.38 SD) and, against B, a more buy-leaning pre-decision flow (0.30 SD). The adjustment set exists for exactly these imbalances.

## Power (frozen procedure, synthetic outcomes on the real layout)

The power profile is `SEED0001_BINARY_POWER_PROFILE_V1`: Holm conjunction of P1 and P2, both positive, 2000 replicates.

| BTC | δ = 0.05 | 0.075 | **0.10** | 0.15 | 0.20 | 0.25 | 0.30 | MDE (80%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BASE (weekly shock, ICC 0.10) | 0.04 | 0.06 | **0.12** | 0.23 | 0.43 | 0.68 | 0.85 | **0.30** |
| STRESS (week × arm shock, ICC 0.25) | 0.03 | 0.07 | **0.10** | 0.22 | 0.41 | 0.64 | 0.84 | **0.30** |

ETH (descriptive): the MDE is 0.325 in both profiles, and power at 0.10 is 0.09.

**What the numbers mean.** The minimum meaningful effect is a 10 pp risk difference. At that size, the retrospective conjunction has about 10% power. It would reliably detect only a gap of about 30 pp in the +1R-before-−1R rate between A and both comparators.

**Planning extrapolation** (not part of the frozen rule). The same function on k stacked copies of the BTC layout gives:

| A episodes | STRESS power at 10 pp |
|---:|---:|
| 108 | 0.25 |
| 216 | 0.53 |
| 324 | 0.74 |
| 432 | 0.86 |

That is about 10× the 2023–2024 sample. At about 18 A episodes a year, it is roughly two decades of BTC data. A 20 pp effect would need about 108 A episodes (power 0.88), about 6 years.

**Heterogeneity assessability (V1 §4).** `NOT_ASSESSABLE`: the power is 0.05 for both contrasts, on the smallest epochs 2023H2 and 2024H1. Under V1 this cannot fail the card. It is not evidence of stability.

## Prospective planning (frozen stop: 30 A episodes or 2028-10-05)

**Method.** The chronological prefix of the 2023–2024 layout, as a structural stand-in, with one-sided Holm.

| Stop | A / B / C / D | weeks | power at 0.10 (BASE / STRESS) | power at 0.20 | MDE |
|---|---|---:|---|---|---:|
| 30 A | 30 / 223 / 58 / 331 | 85 | 0.16 / 0.15 | 0.53 / 0.47 | 0.30 |
| 20 A (minimum) | 20 / 155 / 43 / 249 | 63 | 0.14 / 0.13 | 0.39 / 0.36 | 0.325–0.35 |

**What the numbers mean.**
- **Time to the stop.** At the 2023–2024 rate, 30 A episodes take about 20 months, so the deadline is not expected to bind.
- **Power.** A confirmation at this stop is also low-powered against a 10 pp effect. It can confirm only a large effect, and a miss there is mostly uninformative.

## Compiler V1 checks

- **Definitions:** no blocker.
- **Protected window:** `PROTECTED_SURFACE_DECISION_REQUIRED` on the replication surface, as expected. The prospective start is inside 2026, matching the owner's rule that the protected segment needs a separate decision.
- **Inference class:** pass D is not applicable. The V0 inference-class enum has no model-based cluster-robust class, so power was computed directly.

## Verdict

The frozen rule applies in order, first match winning:
1. **Floor:** BTC A = 36 < 40, so the verdict is `INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR`. The dates (33 ≥ 30) would have passed.
2. **Power, independently:** STRESS power at 0.10 is 0.096 < 0.80. The card would also be `INFORMATIONALLY_WEAK` above the floor.

Nothing in the definitions was changed after the counts, and none may be.

## What this means (owner decision needed; nothing here is authorized)

**Fact.** Under its frozen definitions, the faithful 1h BTC test cannot answer the 10 pp question:
- **Retrospective:** 2023–2024 is below the floor and about 10% powered.
- **Prospective:** the frozen stop at 30 A episodes is about 15% powered.

**Opening outcomes now** would spend the 2023–2024 surface on a look that cannot support the claim, and it is not recommended. The definitions are not weakened, and ETH is not pooled.

**Options for a separate owner decision:**
1. **Close the retrospective leg.** Close `TF-SEED0001-RD-RETRO1` as `INCONCLUSIVE_SAMPLE` without opening outcomes. Prospective counting continues under the frozen stop, knowing it can confirm only a large effect, about 30 pp.
2. **Accept a large-effect test.** Restate, in a new card, the claim as a large effect, with the bar set from cost and product grounds and not from these counts. The retrospective look would then be honest about only detecting about 30 pp.
3. **Track B.** The long-history flow surrogate (2020–2024 and BitMEX / spot 2017–2019 for confirmation) as a separate card labelled `SURROGATE`. It has far more episodes, but it is not the owner's observable.
4. **Other timeframes as separate cards.** 4h and 1D will have fewer episodes still.

## Files

| File | Role |
|---|---|
| `scripts/research/seed0001_feasibility.py` | Runner: guarded acquisition, parsing, count pass. SHA256 in the JSON. |
| `docs/research/SEED0001_FEASIBILITY_REPORT.json` | Full machine record. |
| `docs/research/seed0001/EPISODES_{BTCUSDT,ETHUSDT}.csv` | The frozen eligible episode sets, pre-decision fields only. Digests: BTC `3f90eefc…`, ETH `080b99d6…`. The future evaluator must reproduce them exactly. |
| `docs/research_data/SEED0001_BINANCE_UM_1H_BOOKDEPTH_V0/DATASET_MANIFEST.json` | Source objects and SHA256s. |
