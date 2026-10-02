# Selling-exhaustion support feasibility V0

**Status:** `DESIGN FROZEN BEFORE STATE COUNTS`. Results follow in a separate commit.
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

## Results

Pending: they will be added by the result commit, from `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.json`.
