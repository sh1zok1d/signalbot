# TWAP execution footprint — sealed end-to-end run V1 — RESULT

This is a one-shot execution of `DECISION_LAYER_RESEARCH_PROGRAM_V0.md` §8, run 2026-10-01/02 with no human approval between phases. The classification below comes from the frozen classifier and is not reinterpreted.

```
FINAL_STATUS = MECHANISM_SUPPORTED_PRICE_EFFECT_NOT_SUPPORTED
H1_POST_DETECTION_FLOW = PASS_DISCOVERY_ONLY (ratio 1.264, one-sided p < 0.0001; not replicated)
H2_1h = NOT_SUPPORTED (+5.0 bps, Holm p 0.17)
H2_6h = NOT_SUPPORTED (-0.4 bps, Holm p 1.0)
H3_POST_END_1h = NOT_SUPPORTED (+0.5 bps, Holm p 1.0)
REPLICATION = INFERENCE_INSUFFICIENT (support gate 19 < 100; no replication outcome computed)
RERUN_AUTHORIZED = false
PROTECTED_2025_2026_OPENED = false
```

## Identity

| Item | Value |
|---|---|
| Protocol | `docs/research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md` §8 (PRs #285, #286), SHA-256 recorded in the spec |
| Sealed spec | `docs/research/TWAP_SEALED_SPEC_V1.json`, SHA-256 `961c7578220df5341fc395da84835122acd978300167e5afc68e0b9fe1846df8` |
| Freeze commit | `5a0cd66acc539b7a2d1e1aebe4543ae64e325e2e`, pushed 2026-10-02 00:22 UTC, before the first scientific outcome |
| Code | `scripts/research/twap_footprint/` — SHA-256 per file in the spec; unchanged after the freeze |
| Data | Binance spot BTCUSDT `aggTrades`, 89 monthly zips, each checked against its `.CHECKSUM`; digests in `twap_sealed_run_v1/ingest_log.jsonl` and in the spec |
| Artifacts | `docs/research/twap_sealed_run_v1/` |

## Phase 0 — detector validation and feasibility (outcome-blind)

### Calibration on 2024-06 (structure only)

There were 200 injected synthetic TWAPs (seed 20261002) and 5 hour-preserving shuffles (seeds 20261003–20261007). The month covers 30.0 days.

| tau ms | K | min dur | real episodes | shuffled episodes | FP/day | FP ratio | recall | admissible |
|---|---|---|---|---|---|---|---|---|
| **250** | **20** | **15** | **6** | **0,0,0,0,0** | **0** | **0** | **1.000** | **yes — selected** |
| 250 | 20 | 30 | 0 | 0,0,0,0,0 | 0 | — | 0.915 | no (no real episode) |
| 250 | 40 | 15 | 3 | 0,0,0,0,0 | 0 | 0 | 0.940 | yes |
| 250 | 40 | 30 | 0 | 0,0,0,0,0 | 0 | — | 0.905 | no (no real episode) |
| 500 | 20 | 15 | 9 | 1,0,2,0,0 | 0.020 | 0.067 | 1.000 | yes |
| 500 | 20 | 30 | 3 | 1,0,1,0,0 | 0.013 | 0.133 | 0.915 | no (FP ratio) |
| 500 | 40 | 15 | 3 | 0,0,0,0,0 | 0 | 0 | 0.940 | yes |
| 500 | 40 | 30 | 1 | 0,0,0,0,0 | 0 | 0 | 0.905 | yes |

The frozen rule ranks by lowest FP/day (four tie at 0), then by highest recall. That selects 250 ms / 20 / 15 min. Real episode counts did not rank candidates. They did decide admissibility in one case: a candidate with 0 real episodes is inadmissible. See the post-run erratum.

**Limitation.** The specificity ratio rests on a small calibration denominator: 6 real episodes in 2024-06.

### Counts and gates

| | Discovery 2020-01 → 2024-12 | Replication 2017-08 → 2019-12 |
|---|---|---|
| `N_detected` | 2,179 | 23 |
| after the 6 h same-side refractory | 1,210 | 19 |
| `N_persistence_eligible` | **1,207** on 702 UTC days | **19** on 16 days |
| `N_end_identified` | 1,207 | 19 |
| `N_post_end_1h_complete` | 1,207 | 19 |
| 6 h window complete | 1,206 | 19 |
| by side (buy / sell) | 712 / 495 | 11 / 8 |
| by year | 2020: 93, 2021: 223, 2022: 281, 2023: 284, 2024: 326 | 2018: 4, 2019: 15 |
| exclusions | refractory 969, data gap 2, no 30-day reference 1 | refractory 4 |

Gate results:
- **Discovery support:** passes (≥ 300 on ≥ 100 days).
- **H3 support:** passes (1,207 ≥ 150).
- **Replication support:** fails (19 < 100), so replication is `INFERENCE_INSUFFICIENT` with no substitute surface.

Every exclusion is listed per episode in `exclusions_*.csv`.

**Episode shape**, persistence-eligible, outcome-blind (p10 / median / p90):
- total duration 17 / 29 / 99 min;
- period 2.2 / 10.5 / 71 s;
- slices 24 / 123 / 1,185.

Key types: quantity 629, notional 351, both 227.

**At the decision time the median remaining execution is 11 min.** 89% of episodes are declared ended within the first post-detection hour. By the time the detector can confirm a TWAP (≥ 20 slices and ≥ 15 min), most of it is already executed.

### Planned heterogeneity assessability (outcome-blind, frozen)

| Cell | Power | Status |
|---|---|---|
| H2_1h | 0.18 | `NOT_ASSESSABLE` |
| H2_6h | 0.06 | `NOT_ASSESSABLE` |
| H3 | 0.18 | `NOT_ASSESSABLE` |

The two smallest years hold 93 and 223 episodes. The test is not reached in any case, because no cell passes Holm and the floor.

### Implementation changes made before the freeze

None of these was motivated by any outcome; all are recorded in the spec.
1. **Memory-bounded chain builder.** The chain builder releases chains that can no longer be extended. Output was verified identical to the calibration-time builder on 2024-06, 2019-06 and 2018-01 (both tolerances) and on the whole replication surface (23/23 episodes).
2. **Per-month detection checkpoints.** The container restarted twice during ingest and detection; detection now resumes from per-month checkpoints.
3. **Control matching per anchor.** `match()` returns one control list per anchor, so anchors that share a minute no longer share controls.
4. **Heterogeneity blocks.** The 26-week blocks are implemented as calendar half-years. Each block then lies inside one epoch, so the observed statistic is the identity draw of the permutation null.
5. **Low-power rule.** A planned `NOT_ASSESSABLE` heterogeneity gate is not a failure, per §8 literally.
6. **Classifier and reporting.** A deterministic final classifier was added, and control counts are reported.

## Phase 2 — H1 mechanism gate

H1 compares same-side taker notional in `[t0, t0+60m)` with 5 matched controls per episode.

| N | days | controls / anchor | ratio | 95% CI | one-sided p | pass |
|---|---|---|---|---|---|---|
| 1,207 | 701 | 5.0 | **1.264** | 1.203 – 1.329 | < 0.0001 (1/10,001) | **yes** (p < 0.05 and ratio ≥ 1.10) |

**Reading.** On the discovery surface, same-side flow after detection is about 26% above matched controls. The matching covers hour, prior-hour RV, prior-hour net flow and prior-hour return sign.
- Part of this is mechanical: it includes the detected algorithm's own remaining slices. H1 therefore shows that the footprint persists in the flow, not that other participants join it.
- This is a discovery-surface result only. Independent replication is insufficient: H1 was never opened on the replication surface, where the support gate failed with 19 < 100. It is not a V1-level confirmed statement.

**Day counts.** Feasibility counts distinct UTC days of the qualifying print `T` (702). H1 and H2 bootstrap over the day of the anchor `t0`, the first minute boundary after `T` (701 for H1 and H2_1h, 700 for H2_6h). H3 bootstrap is over the day of `e0` (704). An episode near midnight can move to the next UTC day; no episode is lost between these counts.

## Phase 3 — price outcomes

Statistics are side-signed log returns minus the matched-control mean. Inference uses a day-block bootstrap with 10,000 draws (seed 20261002), two-sided, with Holm m = 3 and a 10 bps floor.

| Cell | N | days | mean | 95% CI | p | Holm p | floor | supported |
|---|---|---|---|---|---|---|---|---|
| H2_1h | 1,207 | 701 | **+5.0 bps** | −0.1 … +10.1 | 0.057 | 0.170 | no | **no** |
| H2_6h | 1,206 | 700 | **−0.4 bps** | −11.1 … +10.4 | 0.940 | 1.000 | no | **no** |
| H3 (post-end 1h) | 1,207 | 704 | **+0.5 bps** | −4.5 … +5.3 | 0.846 | 1.000 | no | **no** |

**Reading:**
- **H2_1h.** The 1-hour cell has a positive point estimate in the TWAP's direction. It is neither significant after Holm nor above the frozen 10 bps floor, and its CI upper bound only just reaches 10 bps. No direction statement is supported.
- **H2_6h.** At 6 h the estimate is zero.
- **H3.** There is no post-end reversal, so no temporary-impact fingerprint is detectable either.

No unregistered breakdown (by side, year, size or key type) was computed.

## Phase 4 — replication

Not run.
- The replication support gate failed (19 persistence-eligible episodes in 2017-08 → 2019-12, threshold 100).
- No discovery cell was supported, so phase 4 had no cell to replicate anyway.
- No replication flow or price outcome was computed.

## Final classification

`MECHANISM_SUPPORTED_PRICE_EFFECT_NOT_SUPPORTED`. It comes from the frozen classifier: H1 passes and no price cell is supported.

## What this closes, and what it does not

**Closed (narrow region).** The region is: a regular-slice TWAP footprint in Binance spot BTCUSDT `aggTrades`, detected point-in-time by this detector (≥ $1k prints, 250 ms tolerance, ≥ 20 slices, ≥ 15 min). For that footprint:
- excess side-aligned price drift over 1 h or 6 h beyond matched net flow, RV, hour and prior-return controls is not supported at the 10 bps scale in 2020–2024;
- a post-end 1 h reversal is not supported either.

This is a null on the price claim for this footprint, under this detector, at this scale. It is not a test of TWAP execution in general.

**Not closed:**
- other venues and instruments (USD-M perpetual, Coinbase, ETH);
- footprints this detector cannot see (randomized slices, iceberg/limit execution, slices under $1k);
- execution detected earlier in its life;
- smaller effects below 10 bps.

None of these is authorized by this result. Per the research rules, no nearby tolerance, K, duration, horizon or floor variant is to be generated from this outcome, and this run is not rerun.

**Product reading.** On the discovery period, a detected spot TWAP footprint keeps showing in same-side flow after detection. Independent replication of that statement is insufficient. There is no supported directional price statement at the frozen scale. If it is ever shown, it can only be descriptive context ("a regular-slice buyer has been active for N minutes"), never "price will move".

## Post-run erratum — protocol wording (2026-10-02)

This erratum records inexact wording in the frozen protocol. It does not change the sealed spec, any computed number or the classification.

**Selection rule.** §8 says "real episode counts are never a selection criterion". The same section also makes a candidate with 0 real episodes in 2024-06 inadmissible, because `FP_RATIO` would divide by zero. Real counts therefore did enter admissibility, in the zero case only.

**Effect on this run: none.** Two candidates were excluded only for having 0 real episodes: 250/20/30 (recall 0.915) and 250/40/30 (recall 0.905). Both have FP/day 0. Had they been admissible, the rule would still have selected 250/20/15, which has FP/day 0 and recall 1.000. A future protocol should state the zero-denominator rule as an explicit, separate admissibility condition.

**CI.** At the result commit the GitHub `CI` job is red, but no tests ran: the job got no runner (runner id 0), finished in 3 s and has no log. The `Full regression` run on `main` at this PR's base `b9c71c0` looks the same (2 s, no steps), as do the earlier runs listed from 2026-10-01. This is consistent with exhausted Actions minutes, not with failing tests. Validation is the local run listed in the PR.
