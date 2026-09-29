# PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0 — frozen pilot protocol

**Status:** `FROZEN_BEFORE_OUTCOMES / PILOT_ONLY / NOT_CONFIRMATORY`
**Frozen:** 2026-09-29, on base `main` `d47e6c8142c54afbe25be05db4609a670996a968`
**Machine-readable twin:** `price_oi_incremental_information_pilot_v0.json` (the runner refuses to start if its constants differ from it)

This is a fast kill-test on the existing Signalbot live archive. It is not historical validation, it is not confirmatory, and it makes no trading claim. Protected Binance 2025/2026 data is not used. No threshold, caliper, gate or endpoint below may be changed after outcomes are seen; a changed design is a new pilot identity.

## 1. What was already seen

The P4 owner-run record (`docs/audit/live_archive_price_oi_p4_followup_v0/`) was read before this protocol was written. It shows larger 1h/4h realized range after triggered `PRICE_OI_CONTRACTION` states than at ordinary same-time anchors. That comparison does not control for the extreme price move that defines the event. No outcome of the ablation below had been computed when this protocol was frozen.

The old frozen matched-baseline design is **not** reused or repaired. Its ±4h forward-looking exclusion, coarse prior-1h tercile and missing control for the event-defining move are exactly what this pilot avoids.

## 2. Question

Does the OI-contraction component add forward realized-range information beyond the extreme, persistent recent price move that already defines the event?

- **A (event):** the current `PRICE_OI_CONTRACTION_{DOWN,UP}` trigger, exactly.
- **B (control):** the same price condition, side, persistence, bucket timing, venue coverage, feature version and maturity, but OI is valid and **not** contracting.

If A and B have similar forward range after balancing the pre-anchor price/volatility profile, the event is mostly an extreme-price / volatility-clustering filter.

## 3. Scope

- Families are processed separately. DOWN and UP are never pooled.
- Rule-evaluation buckets: the frozen Phase A grid, `AUTHORIZED_BUCKETS = 12434` (2026-08-16T19:30Z–2026-09-25T12:40Z and 2026-09-25T13:05Z–2026-09-28T23:55Z). Percentile history starts 2026-07-17T19:30Z.
- 1m klines are read up to 2026-09-29T04:00Z (exclusive) only so that 4h outcome windows of anchors inside the grid can complete. No bucket outside the grid is evaluated.
- `source = 'live'` only. Read-only session. No production writes.

**Data gate (fail closed → `PILOT_DATA_BLOCKED`):** the grid must have 12434 buckets and the current-code reconstruction must yield exactly 25 triggered DOWN and 19 triggered UP episodes (the P4 counts). The P4 eligible counts (22 / 17) are reported for comparison but are not blocking, because the P4 outcome runner is not in the repository.

## 4. Predicates (current code, not paraphrased)

- **Event A** = `semantic_rule(cfg, family, bucket) == QUALIFIES` from `scripts/audit/live_archive_replay_preflight/price_oi_semantic_replay.py`. That adapter uses the current `_families_usable`, `_pct` and the thresholds in `config/beta_v0.yaml` (DOWN: price rank ≤ 0.05; UP: price rank ≥ 0.95; both: OI rank ≤ 0.10).
- **Price side** = the same `semantic_rule` evaluated on a copy of the bucket in which only the OI rank is replaced by a mature `0.0`. Every other input, including both families' usability and the price percentile's presence and maturity, is the real bucket. So the price metric, operator, threshold and gates are the production ones by construction.
- **Control B** = price side QUALIFIES **and** the real OI percentile is present, has a value, is `mature`, and has rank **≥ 0.50** (at or above the 30d median; the event tail is ≤ 0.10).

`≥ median` is appropriate here. The rules compare 30d percentile ranks, so "at or above the median" means OI change was not in the lower half of its own recent distribution. B does not simply drop the OI condition, which would mix contracting and non-contracting observations. Buckets with OI rank in (0.10, 0.50) belong to neither group.

- **Persistence:** both A and B go through the current `beta.detector.step_episode` with the family's current lifecycle (armed at streak 1, triggered at streak 2). A streak resets on a non-contiguous bucket, as in the replay.
- **Anchor:** `triggered_at`, the close of the triggering 5m bucket. One anchor per triggered episode.
- **Reference price:** `beta.state_tape.reference_price` over the reconstructed exchange features of the triggering bucket.

## 5. No future information in eligibility

Control eligibility uses only the B predicate at buckets ≤ the anchor, and the pre-anchor covariates. There is **no** exclusion around future or past episodes, and no temporal exclusion between an event and its controls. Outcome completeness (all reference-venue 1m bars present in the forward window) is required for A and B alike; it is data availability, not an outcome value.

## 6. Covariates (pre-anchor only)

All ranges use the unchanged `compute_outcome` realized-range formula with the anchor's reference price, and only 1m bars strictly before the anchor.

| Covariate | Use |
|---|---|
| `ln |price_move_pct_median|` of the triggering bucket | matched + balance |
| `ln` prior range over `[anchor−15m, anchor)` | matched + balance |
| `ln` prior range over `[anchor−1h, anchor)` | matched + balance |
| `ln` prior range over `[anchor−4h, anchor)` | matched + balance |
| UTC hour of the triggering bucket, as sin/cos | balance only |
| weekend (Sat/Sun UTC) indicator | balance only |
| `ln` prior range over `[anchor−24h, anchor)` | reported only |

An anchor with any matched covariate unavailable (incomplete bars, non-positive value) is excluded and counted.

## 7. Matching

- Scale `s_j` = population SD of covariate `j` over eligible A ∪ eligible B of the family.
- Distance `D = sqrt(mean_j ((x_e,j − x_c,j) / s_j)²)` over the four matched covariates.
- Up to **k = 3** nearest controls with `D ≤ 0.75`, **with replacement**. Ties: smaller `D`, then earlier control anchor.
- An event with no control inside the caliper is unmatched. Nothing is relaxed.

## 8. Gates (evaluated before the outcome comparison is interpreted)

**Support → `PILOT_INSUFFICIENT_CONTROL_SUPPORT`** if any of: eligible controls < 10; matched events < 10; distinct UTC dates of matched events < 5; distinct controls used < 5; placebo matched pseudo-events < 10.

**Balance → `PILOT_BALANCE_FAILED`.** `SMD = (mean_e x_e − mean_e mean_{c∈M(e)} x_c) / sqrt((var_A + var_B)/2)` over matched events, with population variances of the eligible pools. Each matched covariate needs `|SMD| ≤ 0.25`. Hour sin, hour cos and weekend need `|SMD| ≤ 0.50`. A zero scale passes only with a mean difference of exactly 0. A placebo failure (§10) is also reported as `PILOT_BALANCE_FAILED` (reason `PLACEBO_FAILED`): the pipeline would be manufacturing differences.

## 9. Endpoint

- Per matched event and horizon: `d_e = ln(R_e) − mean_{c∈M(e)} ln(R_c)`, with `R` = `realized_range_pct`.
- **Primary:** median `d_e` at **4h**. **Secondary:** median `d_e` at 1h (reported, never used in the verdict).
- Also reported descriptively: `exp(median d)`, and the count of events with `d_e > 0`.
- Not reported: direction, close return, MAE/MFE, hit rate, PnL, p-values, confidence intervals.

## 10. Placebo

B-vs-B, deterministic, no randomisation: each eligible B anchor is a pseudo-event matched to the other eligible B anchors (itself excluded) with the same distance, caliper and k. **Pass** if `|median pseudo d(4h)| < ln(1.25)`.

## 11. De-clustering

Matched events sorted by anchor. A new cluster starts when the gap to the previous matched event anchor exceeds 4h. Reported: events, distinct UTC dates, clusters, and the median `d(4h)` over the first event of each cluster. No significance claim.

## 12. Verdict

Materiality: a range ratio of **1.25** (`ln 1.25 = 0.2231`).

Per family, in order:
1. `PILOT_DATA_BLOCKED`
2. `PILOT_INSUFFICIENT_CONTROL_SUPPORT`
3. `PILOT_BALANCE_FAILED`
4. `OI_INCREMENTAL_SIGNAL_PILOT_SURVIVES` if median `d(4h) ≥ ln 1.25` **and** first-per-cluster median `d(4h) ≥ ln 1.25`
5. `OI_ABLATION_NULL_LIKE` otherwise

Final:
- any family data-blocked → `PILOT_DATA_BLOCKED`;
- else any family survives → `OI_INCREMENTAL_SIGNAL_PILOT_SURVIVES` (family-scoped);
- else all families null-like → `OI_ABLATION_NULL_LIKE`;
- else any family with insufficient support → `PILOT_INSUFFICIENT_CONTROL_SUPPORT`;
- else `PILOT_BALANCE_FAILED`.

**Consequences.**
- `OI_ABLATION_NULL_LIKE`: do not expose PRICE_OI as a meaningful special state to external users without a redesign.
- `OI_INCREMENTAL_SIGNAL_PILOT_SURVIVES`: this is **not** validation. It only justifies designing a separate long-history test.

Never output: `VALIDATED_EDGE`, `PREDICTIVE`, `PROFITABLE`, `SIGNIFICANT_ALPHA`.

## 13. Known limitations (stated before outcomes)

- About 2.5 months of live archive, and tens of events per family. This is a kill-test, not inference.
- The replay is a current-rule semantic reconstruction. It does not prove historical `evaluation_fresh`, raw-revision coherence or alert delivery.
- Matched controls can share part of an event's forward window. This is allowed rather than excluded, because any exclusion keyed on event timing would condition controls on events after them. Overlap tends to pull `d` toward 0, so the share of matched pairs whose 4h windows overlap is reported next to the result.
