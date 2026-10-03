# Selling-exhaustion support feasibility V0

**Status:** `COMPLETE`. The design was frozen before state counts in `a4b76fd`; the result was added in a separate commit.
**Verdict (binary primary):** `INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON`
**Date:** 2026-10-02
**Owner decision:** `DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3.md`
**Machine twin:** `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0_DESIGN.json`. It is authoritative and binds code and frozen-artifact hashes. The result is in `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.json`.

**Kind:** feasibility only. This is a new research object. It is not a continuation or rescue of SEED-0001, it creates no SEED, and it computes no E-versus-S outcome contrast anywhere.

## Question

Within an already-present support state, does a pre-specified state of weakening selling pressure and non-expanding open interest carry useful information about the subsequent reversal or trading outcome, independently of classical oscillator divergence?

**Motivation, not evidence.** The exploratory pooled observation of about +4 pp was found on already-opened data. It is not used.

## Surface and E1

**Panel:** BTC, ETH, SOL, BNB, DOGE and XRP USD-M perpetuals. It is fixed, with no expansion.

**Decisions:** 2023-01-01 .. 2026-08-11. Reads end before the exclusive horizon 2026-08-15.

**Status of the surface.** It is previously exposed, so here it is discovery: detector construction, counts, dependence, feasibility and descriptive mechanism. It is never presented as validation. The only clean confirmation surface is prospective data after a new, separately authorized freeze.

**E1-RUN-001** `[2026-08-16, 2026-08-25 17:20)` cannot be reached by any route:
- **Lookbacks.** Detector windows, feature lookbacks, the 720h book and flow baselines and the OI windows all end at or before T (≤ 2026-08-11).
- **Forward reads.** The only one is the 48h state-blind outcome used for dependence calibration (≤ 2026-08-13).
- **Loaders.** They assert the read horizon.
- **No new download.** The verified local archive of the full-history program is reused.

## Population

**Episodes:** support episodes (arms A and B) of the unchanged SEED-0001 detector, over the whole exposed decision range.

**Integrity checks:**
- the discovery-window episodes must reproduce the V0 digests;
- the validation-window episode ids must reproduce the full-history validation CSV.

## Candidate states (no oscillator input)

**What the detector already guarantees.** The new local low (low_i < low_j, after a decline of at least 3 ATR) and the support state.

The two variants share one shape: E is "flow above the reference AND OI not above the reference".

| Variant | Reference | Flow input (E needs > 0) | OI input (E needs ≤ 0) |
|---|---|---|---|
| `SE_LEG` | prior downswing | net taker-flow share over the second leg (j, i], minus that over the equal-length window ending at j | OI(close of i) / OI(close of j) − 1 |
| `SE_BASELINE` | local baseline | net taker-flow share over the 24 bars ending at i, minus the median of the same 24-bar statistic over windows ending i−696..i−24 (bars i−719..i) | OI(close of i) / OI(24h earlier) − 1 |

**Net taker-flow share** = Σ(2·taker_buy − volume) / Σ volume over 1h bars.

**OI** comes from 5m metrics, available at create_time + 5 min and stale after 30 min.

**Justification.**
- **No tuned numbers.** Thresholds are the no-change point (or the median). Window lengths reuse frozen SEED-0001 constants (24, 720).
- **`SE_LEG` pre-dates the 2025+ opening.** It is the state pre-specified as `DEEPER_STATE_FLOW_OI` in the full-history design, frozen before any 2025+ byte. Its exploratory association is not used.

**Undefined.** A missing OI value or zero volume excludes the episode from that variant's E/S; the exclusions are counted.

**Divergence flags.** They are descriptive cross-tabulations only.

**PIT.** Every input ends at or before the close of pivot bar i. A truncation audit at T covers 30 episodes per symbol.

**Selection.** Both variants are reported in full. No variant is selected by outcome.

## Estimand and effects

**Primary:** `E − S` inside support.

**Planning outcome:** `Y1_48H`, +1R before −1R within 48h under the SEED-0001 bracket.

**Planning model.** LPM on the E indicator with symbol fixed effects; CR1 by panel-wide UTC week; t(G − 1); two-sided 0.05 with a positive estimate required. The comparator rate is 0.5, and the outcomes are synthetic.

**Effect sizes.**
- **Reported:** power at 3, 5, 7.5 and 10 pp, with MDE80 on a 0.5 pp grid and analytically.
- **Decision line:** 5 pp, with 4 pp reported beside it.

## Continuous score (feasibility only)

**Definition.** `SCORE_<variant>` is the mean of the variant's flow component and its sign-flipped OI component. Each component is robust-z scaled per symbol (median, 1.4826·MAD) and clipped to ±3.

**Constants.** They come from feature values only, and are frozen in the result.

**Degrees of freedom.** There is one fixed transformation per variant, with nothing left open.

**Comparison.** Under each profile, the binary E test and the continuous slope test are compared on two planning worlds:
- **STEP:** the effect is a step at the state;
- **LINEAR:** the effect is linear in the score, scaled to the same mean E − S gap.

This comparison is reported, but not used for the primary verdict.

## Dependence

**Structural measures:**
- nominal E and S, unique decision times, dates and week clusters;
- within-symbol 48h overlap chains and panel 24h market chains;
- maximum episodes per date;
- symbol and half-year concentration;
- cross-symbol same-state co-occurrence.

**Profiles:**

| Profile | Shocks |
|---|---|
| INDEPENDENT | none (diagnostic) |
| BASE | one probit shock per UTC date, latent ICC 0.25 |
| **STRESS (gate)** | one shock per (UTC date, state), latent ICC 0.50 |
| COLLAPSED | one unit per (date, state) with the BASE shock |
| EMPIRICAL | week, date and symbol-chain probit components calibrated to state-blind outcome pair correlations |
| EMPIRICAL_UPPER | the same calibration at the 95th bootstrap percentile |

**State-blind calibration.**
- **Outcomes used.** It uses `Y1_48H` of support episodes inside the frozen full-history slices. These were already opened; no gap-day outcome is opened.
- **Inputs.** The routine receives only outcome, symbol, time and week. No candidate state reaches it, so no E − S contrast can be formed.
- **Pair classes:**
  - same week, other date, other symbol;
  - same date, other symbol;
  - same symbol chain, other date.
- **Link.** rho = sin(π·φ/2).
- **Bootstrap.** 999 week resamples.

## Projection and verdict

**Prospective weeks for 80% power** = W_ref · (2.8016 · SD / mean)², from the simulation on the exposed layout.
- **Confirmation.** Each projection up to 520 weeks is checked by direct simulation on a prospective stand-in that cycles the exposed weeks.
- **Start date.** Dates assume a prospective start on 2026-10-12.
- **Exposed data does not count.** Confirmation needs prospective data alone.

**Verdict on the binary primary:**

| Status | Condition |
|---|---|
| `FEASIBLE_FOR_PREREGISTRATION` | some variant reaches 80% at 5 pp under STRESS within 104 prospective weeks |
| `INFORMATIONALLY_WEAK / FEASIBLE_ONLY_UNDER_WEAKER_DEPENDENCE` | only under BASE or EMPIRICAL within 104 weeks |
| `INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON` | otherwise |
| `INFERENCE_SUPPORT_INSUFFICIENT` | no variant has ≥ 30 E episodes in ≥ 30 weeks |
| `PIT_BLOCKED` | an audit mismatch |

The horizon of 104 weeks is the length of the frozen SEED-0001 prospective leg.

## Not in this unit

- `RSI_GRADIENT_SUPPORT_CANDIDATE`: recorded separately, not evaluated and not combined.
- Any E − S outcome contrast.
- Any SEED.
- Any prospective activation.
- E1.
- A PR #303 merge.

## Results (from `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.json`)

```
VERDICT_BINARY_PRIMARY        = INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON
4-5 PP TESTABLE IN 104 WEEKS  = NO (no variant, no dependence profile)
E_MINUS_S_OUTCOME_CONTRAST    = not computed
PIT_TRUNCATION_AUDIT          = 30/30 identical on every symbol
DISCOVERY / VALIDATION IDS    = reproduced (V0 digests; full-history validation CSV)
E1_INTERVAL_TOUCHED           = false
SEED_CREATED                  = false
```

### Population and frequency

**Support episodes:** 3,005 over 186 calendar weeks (2023-01-01 .. 2026-08-11). That is 1,590 discovery-window, 1,411 validation-window and 4 between the slices.

**Undefined states:** 3 for `SE_LEG` and 7 for `SE_BASELINE`, because the OI value was missing.

| | `SE_LEG` | `SE_BASELINE` |
|---|---:|---:|
| E (exhaustion state) | 667 (22.2% of support) | 349 (11.6%) |
| S (support only) | 2,335 | 2,649 |
| E per week / per year | 3.6 / 187 | 1.9 / 98 |
| S per year | 655 | 743 |
| E decision dates / distinct times | 433 / 573 | 274 / 328 |
| E week clusters (of 186) | 172 | 150 |
| E within-symbol 48h overlap chains | 506 | 281 |
| E panel 24h market chains | 315 | 233 |
| E with another symbol in E within 0 / 6 / 24h | 26% / 43% / 68% | 12% / 23% / 40% |
| E max symbol share / HHI | 0.18 / 0.167 | 0.19 / 0.169 |
| E max half-year share | 0.16 | 0.17 |

**Overlap of the two variants.** They mark largely different episodes: the Jaccard similarity of the two E sets is 0.13.

**Relation to divergence (descriptive only).**
- **`SE_LEG`.** The E episodes carry the divergence flag more often than the S episodes: 19% against 8%. The pattern holds for the RSI family (29% against 13%) and the CVD family (19% against 7%).
- **`SE_BASELINE`.** Here E has divergence 15% against 10%.
- **Why.** The states are not oscillator-free in effect, because flow and divergence share information. Any future test would need divergence as a covariate.

### State-blind outcome dependence (support population, already-opened outcomes, no state)

| Pair class | φ | week-bootstrap 5–95% range |
|---|---:|---|
| same date, other symbol | **0.227** | 0.189 .. 0.262 |
| same week, other date, other symbol | 0.026 | 0.004 .. 0.048 |
| same symbol chain, other date | 0.003 | −0.027 .. 0.036 |

**What this means.**
- **Common-market shocks dominate.** Same-day episodes across symbols are strongly dependent, with a latent correlation of about 0.31.
- **The contrast is largely shielded.** Within a date, both states share the shock, so in the calibrated profile it cancels in E − S. The design effect is 1.04–1.05.
- **STRESS is not identifiable state-blind.** It assumes the shocks are state-specific, which this calibration cannot test. Under STRESS the design effect is 1.29–1.45, and under COLLAPSED it is 1.33–1.74.

### Power of E − S on a sample the size of the exposed surface (186 weeks)

This sample is exposed, so it can never confirm anything. It only shows the information content.

| Profile | `SE_LEG`: power at 3 / 5 / 7.5 / 10 pp | MDE80 | `SE_BASELINE`: power at 3 / 5 / 7.5 / 10 pp | MDE80 |
|---|---|---:|---|---:|
| INDEPENDENT | 0.26 / 0.62 / 0.92 / 0.99 | 6.5 pp | 0.18 / 0.42 / 0.76 / 0.94 | 8.0 pp |
| BASE | 0.28 / 0.59 / 0.92 / 0.99 | 6.5 pp | 0.18 / 0.43 / 0.70 / 0.92 | 8.5 pp |
| EMPIRICAL | 0.26 / 0.60 / 0.91 / 0.99 | 6.5 pp | 0.19 / 0.40 / 0.71 / 0.93 | 8.5 pp |
| **STRESS** | 0.19 / 0.45 / 0.80 / 0.97 | 8.0 pp | 0.15 / 0.34 / 0.63 / 0.87 | 9.5 pp |
| COLLAPSED | 0.18 / 0.42 / 0.77 / 0.95 | 8.0 pp | 0.14 / 0.30 / 0.61 / 0.85 | 9.5 pp |

**With 104 prospective weeks** the analytic MDE80 is 8.3–9.9 pp for `SE_LEG` and 10.8–12.2 pp for `SE_BASELINE`.

### Prospective data needed for 80% power (prospective only)

The figures are analytic weeks. Each projection up to 520 weeks was confirmed by direct simulation, with power 0.78–0.82.

| Profile | `SE_LEG` at 5 pp | `SE_LEG` at 4 pp | `SE_BASELINE` at 5 pp | `SE_BASELINE` at 4 pp |
|---|---:|---:|---:|---:|
| INDEPENDENT | 270 w (5.2 y) | 453 w (8.7 y) | 472 w (9.1 y) | 706 w (13.5 y) |
| BASE | 310 w (5.9 y) | 475 w (9.1 y) | 479 w (9.2 y) | 818 w (15.7 y) |
| EMPIRICAL | 303 w (5.8 y) | 469 w (9.0 y) | 516 w (9.9 y) | 780 w (14.9 y) |
| **STRESS** | 430 w (8.2 y) | 665 w (12.8 y) | 604 w (11.6 y) | 983 w (18.8 y) |

**Against the 104-week horizon.** Even the most favourable case needs about 2.6 times the realistic horizon.

**Calendar.** Starting on 2026-10-12, the earliest 80%-powered 5 pp test (`SE_LEG`, INDEPENDENT) would end around 2031-12. Under STRESS it would end around 2035-01.

**Effective information per prospective year:** about 580–840 effective support units for `SE_LEG` (484 under COLLAPSED), and 630–840 for `SE_BASELINE`.

### Binary versus continuous score

| | `SE_LEG` | `SE_BASELINE` |
|---|---:|---:|
| Point-biserial correlation of state and score | 0.58 | 0.48 |
| Score gap, E − S | 1.39 SD | 1.49 SD |
| Weeks for 80% at 5 pp, LINEAR world: binary / continuous | 268–436 / **87–122** | 471–595 / **114–149** |
| Weeks for 80% at 4 pp, LINEAR world: continuous | 139–182 | 188–230 |
| Weeks for 80% at 5 pp, STEP world: binary / continuous | 283–422 / 860–1048 | 461–636 / 2065–2793 |

**When the score helps.** It improves efficiency 3–4× only when the effect is truly graded. In that LINEAR world, the 5 pp E − S gap implies a gradient of about +3.6 pp per SD of the score (+3.4 pp for `SE_BASELINE`).

**When it hurts.** When the effect is a step at the state, the score costs about 3×.

**Which world holds is unknown without outcomes.** It cannot be learned from the exposed surface without consuming it further.

**Researcher degrees of freedom.** These are bounded: there is one frozen transformation per variant, and its constants are in the result.

**Does the score rescue the realistic horizon?** Only partly:
- **Yes, narrowly.** At a 5 pp-equivalent gradient, `SE_LEG` reaches it only under INDEPENDENT (87 weeks) and BASE (104 weeks, at the boundary). It misses under EMPIRICAL (106) and STRESS (122).
- **No, at 4 pp-equivalent.** It needs 139–182 weeks there.
- **It is a different estimand.** A slope per SD, not E − S.

## Answers to the owner's feasibility questions

1. **Frequency of the exhaustion state.** `SE_LEG` is 22% of support, about 187 per year across the panel. `SE_BASELINE` is 12%, about 98 per year.
2. **Frequency of support-only.** About 655 per year (`SE_LEG` split) or about 743 per year (`SE_BASELINE` split).
3. **Expected primary sample under honest clustering.** Per prospective year, about 187 E and 655 S in about 48 E weeks. That is about 580–840 effective units (484 under COLLAPSED).
4. **MDE80.** On the exposed-surface-sized sample: 6.5–8.0 pp (`SE_LEG`) and 8.0–9.5 pp (`SE_BASELINE`). With 104 prospective weeks: 8.3–9.9 pp and 10.8–12.2 pp.
5. **Can 4–5 pp be tested in a realistic horizon? No.**
6. **Prospective data required.** For `SE_LEG` at 5 pp: 5.2–8.2 years. At 4 pp: 8.7–12.8 years. `SE_BASELINE` needs 9–19 years.
7. **Does a binary state throw away too much?** Only if the true effect is graded. Then the binary test needs 3–4× the data. If the effect is a step, the binary test is the efficient one.
8. **Does a continuous score help?**
   - **Efficiency.** It improves materially under a graded effect, and the degrees of freedom are bounded (one frozen transformation).
   - **Cost.** It changes the estimand, and it bets on gradedness.
   - **Still not realistic at 4 pp-equivalent:** 139–182 weeks.

## Verdict

`INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON`.

**What it means.**
- **No realistic test.** An E − S effect of about 4–5 pp cannot be tested with realistic prospective data, under any variant or dependence profile.
- **No rescue from history.** The exposed history cannot serve as confirmation, and even at its own size it would reach only 0.45–0.62 power at 5 pp (`SE_LEG`).
- **Next step is the owner's.** No SEED is created and nothing is activated.
