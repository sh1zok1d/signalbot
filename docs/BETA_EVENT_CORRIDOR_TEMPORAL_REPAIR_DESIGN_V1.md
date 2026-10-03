# Event corridor — temporal repair design record V1

**Status:** `DESIGN_ONLY for the event model (K1 not implemented, no retrain) / §9 FALLBACK IMPLEMENTED in the V2 branch / NOT_DEPLOYED`
**Date:** 2026-10-03
**Scope:** the scheduled-release conditioning (CPI, FOMC) of the decision-support range corridor (`beta/rangecast.py`, `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §2). It does not change the generic range model, thresholds, the research registry, user copy or deployment. Those are separate tasks.
**Trigger:** red-team of branch `ccr-b5339153-71haxv` at `86dd802` (owner-relayed), plus the read-only checks in §4.

```
EVENT_CODE_CHANGED_FOR_K1       = NO
EVENT_MODEL_RETRAINED           = NO
EVENT_SEMANTICS_STATUS          = FAILS_IN_LIVE_USE / NOT_CALIBRATED
GENERIC_RANGECAST_SKILL_STATUS  = DIAGNOSTICALLY_SUPPORTED / NOT YET PROSPECTIVELY CONFIRMED
DATA_2024_EVENT_WINDOWS         = EXPOSED / DIAGNOSTIC / REPAIR DATA
CONFIRMATION                    = PROSPECTIVE ONLY; BitMEX 2017-2019 = NOT_PROVABLY_INDEPENDENT (§6)
FEASIBILITY                     = FALSIFICATION_FEASIBLE / CALIBRATION_CONFIRMATION_NOT_FEASIBLE_SHORT_TERM (§8, exact method)
FALLBACK                        = IMPLEMENTED (§9): no numerical corridor in an event zone; no multiplier
```

## 1. Current semantics

- **Feature.** `event_cpi` and `event_fomc`: per horizon H ∈ {1h, 4h, 24h}, the flag is 1 when a release r of that kind lies in `[anchor close t, t + H)` (`event_in_window`, `beta/rangecast.py`). It enters the log-range OLS as an additive term, so it multiplies the scale. In the 2022–2024 local fit, the 1h coefficients are FOMC +0.989 (×2.69) and CPI +1.034 (×2.81).
- **Training anchors.** Hourly: only anchors whose close falls on a UTC hour (`ANCHOR_STRIDE = 12` on the 5m grid, `_valid_anchors`). The held-out check uses the same hourly anchors.
- **Live anchors.** Every 5 minutes: `forecast()` anchors at the last closed 5m bar, and the flag uses the same `[t, t + H)` rule.
- **Where it is shown.**
  - The corridor lines of `/btc`, `/catchup` and the briefing («в окне — …»).
  - `/risk` and touch probabilities.
  - The event reminder push 30 minutes before a release («Коридор 1ч с учётом события», `corridor_1h`).
  - The sharp-move alert's 1h corridor.

## 2. Failure mode

The flag marks "a release lies ahead inside the window". It does not mark "a release has just happened".

- **Before a release** (live anchors in `(r − H, r]`), the flag is on and the corridor widens by about ×2.7. It covers almost everything: the red-team table for the 8 FOMC releases of 2024 shows 98–100% inside, at ±3.3–3.7% against an average move of 1.3–1.8%.
- **From the first 5-minute anchor after the release**, the flag is off for every horizon, although the reaction is still under way. The corridor falls back to an ordinary hour, ±1.2–1.3%. Inside: 42% at +5…+30 min and 25% at +30…+60 min against an average move of 1.6–1.8%. CPI 2024 at +30…+60 min: 37.5% inside.
- **Why the hourly calibration does not see it.**
  - FOMC releases at 18:00/19:00 UTC. The hourly training anchor that closes at the release has the flag on, and its window is exactly the first post-release hour. That anchor looks fine: 21 of 24 releases held in 2022–2024. This comes from a box about 2.7× wider, not from timing skill: 8/8 in 2024 with the coefficient, 1/8 without it.
  - CPI releases at 12:30/13:30 UTC. The anchor 30 minutes before carries the flag; the next hourly anchor, 30 minutes after, does not.
  - No hourly anchor represents the 5-minute live anchors just after a release. The calibration (79.4 / 79.6 / 79.8%) therefore never measures the moment the product is used for.
- **Stacking.** The coefficient multiplies a scale that may already be elevated. The red team's example: 2024-03-20, ±6.99% for one hour against a 2.18% move.

The red-team −60…+60 min table was computed by the red team. Its mechanism follows directly from the code above. This record has not re-run that table, and it is not used for any choice below.

## 3. Two separate questions

**A. Generic scale skill.** Does the rangecast carry useful conditional scale information beyond a constant band, away from scheduled releases?

**B. Event-specific conditioning.** Does the event term produce calibrated corridors in the minutes before and after a scheduled release, at the live 5-minute cadence?

A is about every ordinary hour. B is about about 20 releases a year. Evidence for one is not evidence for the other.

## 4. Evidence status

### 4.1 Question A — `DIAGNOSTICALLY_SUPPORTED / NOT YET PROSPECTIVELY CONFIRMED`

- **Setup.** Binance BTCUSDT 5m, repository archives, 2022–2024. Fitted on 2022–2023, evaluated on the 2024 hourly anchors. Every anchor with a CPI/FOMC release in `[t − 60 min, t + H)` is excluded, and the constant band is fitted on training anchors with the same exclusion.
- **Results.**

| Horizon | Anchors | Coverage, model / constant | Model coverage by past-24h-range quintile (low → high) | Constant coverage by quintile | Interval score, model − constant (α = 0.2, day bootstrap 95%) |
|---|---|---|---|---|---|
| 1h | 8 720 | 79.4% / 79.5% | 76, 77, 80, 82, 82% | 93, 87, 84, 77, 60% | −0.29 [−0.38; −0.22] |
| 4h | 8 660 | 79.6% / 80.6% | 75, 77, 80, 82, 81% | 94, 86, 83, 79, 64% | −0.45 [−0.63; −0.29] |
| 24h | 8 279 | 79.0% / 78.7% | 69, 76, 80, 82, 85% | 87, 81, 80, 77, 71% | −0.53 [−0.95; −0.15] |

- **Reading.**
  - Marginal coverage is the same for a model and a constant by construction, so the aggregate ~80% is not evidence of skill and is not used as such.
  - The only skill evidence is this exposed diagnostic: conditional adaptation across volatility regimes and the interval-score improvement. 2024 is not a new holdout.
  - The constant over-covers calm hours and misses volatile ones. The model stays near 80% across regimes and has a lower interval score on all three horizons.
  - Remaining weakness: the model under-covers the calmest fifth (69–76%).
- **Status limits.**
  - The 2024 holdout has now been examined several times (build check, red team, this record). This is diagnostic support, not a confirmation.
  - The shipped model is refit on all data, so the published holdout figure describes a model fitted without 2024. That is a disclosure issue, not look-ahead in the forecasts.
  - Prospective live tracking (`beta_forecasts`) is the confirmation path for A.

### 4.2 Question B — `FAILS_IN_LIVE_USE / NOT_CALIBRATED`

- **Status.** No event-specific skill claim is supported under the current semantics (§2).
- **What the coefficients show.** Event hours are larger than ordinary hours. The product's own event-day statistics agree: CPI hour ×3.2 and FOMC hour ×3.3 by median, 2022–2024.
- **What is missing.** The current feature does not place that information at the right moments.

## 5. Data classification

| Surface | Status for the event semantics | Allowed use |
|---|---|---|
| Binance BTCUSDT 2024 releases (12 CPI, 8 FOMC) | `EXPOSED / DIAGNOSTIC / REPAIR DATA` | Reproduce the bug; outcome-blind implementation checks (flags on the right anchors). Never a confirmatory holdout for any new event semantics, and never a basis for choosing between candidates by coverage |
| Binance 2024 hourly anchors (all hours) | Exposed holdout for question A | Diagnostic only |
| Binance 2020–2023 releases (48 CPI, 31 FOMC) | Training | Fitting. FOMC post-release volatility 2020–2024 is also exposed by D11 |
| Binance 2025-01-01 → 2026-10-03 (20 CPI, 14 FOMC) | Opened by the owner for product statistics; `RESEARCH_LEDGER`: consumed for research over event days. Its event hours have not been read in this branch | Not independent: it would also be part of the VPS fit |
| E1-RUN-001 holdout `[2026-08-16, 2026-08-25 17:20)` | Protected | Never read (`beta/history_data.py` rejects every overlapping object) |
| Other venues for the same dates (OKX spot 2022–2024 in the repository, Bybit live) | Same releases, same market reaction | Not independent units |

## 6. Independent confirmation surface (none opened)

1. **Prospective releases — the only eligible surface.**
   - **Scope.** Every scheduled CPI and FOMC release after the event semantics are frozen, scored from the project's own Stage-1 Binance 1m data with event-relative forecast tracking.
   - **Calendar now.** CPI 2026-10-14, 2026-11-10, 2026-12-10. FOMC 2026-10-28, 2026-12-09 and 8 meetings in 2027. 2027 CPI dates go in when BLS publishes them.
   - **Rate.** About 20 releases a year pooled (8 FOMC + 12 CPI).
2. **BitMEX XBTUSD 2017–2019 — `NOT_PROVABLY_INDEPENDENT`.** Provenance audit of 2026-10-03; no outcome was computed for it.
   - **Who read it.** The 5m data (`docs/research_data/D2_BITMEX_PRE2020_XBTUSD`, `docs/research_data/D7_BITMEX_ACTIVITY_V0`) was read in bulk by:
     - D2: calendar and schema feasibility (`d2_bitmex_pre2020.py`), the replication and its corrected one-shot (daily decisions 2017-01-24 … 2019-12-30), and the alternative-surface feasibility;
     - D7: activity check, support and power, dependence review, and the confirmatory primary run (hourly states for every hour 2016–2019).
   - **What was published.** Aggregates only: D2 means and per-year values, D7 theta, standard error and per-year theta, state counts by year and volatility bucket. The committed result files hold no per-hour or per-day outcomes.
   - **Event timestamps and calendars.** No BitMEX-reading script joins a CPI or FOMC calendar; their "calendar" fields are the 5m time grid. The ledger records no event-conditioned BitMEX outcome.
   - **Leak paths that cannot be excluded.**
     - Every hour, event hours included, entered D7's states and D2's daily volatility, so post-event volatility shaped published aggregates.
     - The C012 feasibility triage (`GV0R01_STREAM_B_FEASIBILITY_TRIAGE.json`) already named this surface as a confirmation candidate "around 2017-09..2019-12 scheduled events".
     - The raw pages are in the repository and were read whole.
   - **Missing before any use.** No point-in-time 2017–2019 release calendar is in the repository, and the instrument equivalence (inverse XBTUSD against linear BTCUSDT) is not adjudicated.
   - **Verdict.** Provenance is not provably clean, so the surface is `NOT_PROVABLY_INDEPENDENT`. It is not a confirmation surface for the event semantics.
3. **Not eligible.** Everything in §5 except item 1. Binance 2025–2026 is excluded although unread: by governance and because the nightly build fits on it.

## 7. Candidate temporal semantics (defined before any fit)

Notation: anchor close t, release r of one kind, horizon H.

| Id | Definition | Status |
|---|---|---|
| K0 | `IN_WINDOW_H = 1[r ∈ [t, t + H)]` (current) | Reference only |
| **K1** | `PRE_H = 1[r ∈ [t, t + H)]` and `POST = 1[r ∈ [t − 60 min, t)]`; separate coefficients, per kind, per horizon | **Preferred a priori** |
| K2 | `PRE_H` + elapsed buckets `POST_0–15`, `POST_15–60`, `POST_60–360` min | Documented, not selected: three post terms per kind and horizon against about 31–48 training releases per kind |
| K3 | `ACTIVE_H = 1[r ∈ [t − 60 min, t + H)]` (one state) | Rejected by principle: it merges "ahead" and "just happened" |

- **Why K1.**
  - It is the smallest change that separates the two user moments: «событие впереди» and «событие только что произошло».
  - The 60-minute post span is fixed by that product moment (the hour after a release, the reminder's horizon). It is not fitted from data.
  - It changes only the time definition: no kind pooling, no new thresholds.
- **Shared requirements for any candidate.**
  - Fit and evaluate at the live cadence: event-relative anchors every 5 minutes from `r − H` to `r + 60 min` for each training release, weighted so each release counts once per state. Hourly anchors stay as they are elsewhere.
  - Evaluation units are releases, not anchors. Per release: one PRE unit (the anchor 30 minutes before) and one POST unit (the first anchor after the release, r + 5 min).
- **Selection rule.**
  - K1 is fixed now, before any K1 fit.
  - 2024 may be used only to reproduce the failure and to check that the K1 flags land on the intended anchors (outcome-blind).
  - No candidate is compared with another by 2024 coverage.
  - If K1 fails the prospective check, the product stays on the fallback (§9). It does not switch to K2 on the same data.

## 8. Feasibility (outcome-blind)

**Method, fixed before computing (2026-10-03).** Sample sizes are small (8–300 releases), so the binomial rows use exact calculations, not normal approximations. Each method was chosen before its number was computed and was not tuned to earlier figures.

- **Unit.** One release. All 5-minute anchors around a release share one market reaction, so they are not independent. Per release there is one PRE unit and one POST unit (§7), each analysed separately. Releases are treated as independent Bernoulli trials.
- **Outcome.** 1 when the corridor issued at the unit's anchor contains the realised maximum excursion over its horizon.
- **Detection rows (falsification).**
  - Test: exact one-sided binomial test of H0: p = 0.80 (calibrated) against H1: p = p1 < 0.80 (under-coverage), α = 0.05.
  - Rejection region: X ≤ c(n), where c(n) is the largest c with P(X ≤ c | n, 0.80) ≤ 0.05; the attained size is reported.
  - Power(n) = P(X ≤ c(n) | n, p1); target power 0.80.
  - Rounding: n\* is the smallest n with power ≥ 0.80 for every m in [n, n + 100]. This handles the sawtooth of exact binomial power.
- **Precision rows (estimation).**
  - Interval: two-sided 95% Wilson score interval at the expected p̂ = 0.80.
  - Criterion for "±d": both sides within d, i.e. p̂ − L ≤ d and U − p̂ ≤ d.
  - Rounding: n\* is the smallest n meeting the criterion for every m in [n, n + 100].
- **Script.** The rows are reproducible with SciPy `binom` / `norm`. They read no market data.

| Question | H0 | H1 / effect | Sided | α | Power | Method | n\* (releases) | Notes |
|---|---|---|---|---|---|---|---|---|
| Detect a gross failure | p = 0.80 | p = 0.40 | one | 0.05 | 0.80 | exact binomial | **12** | reject if X ≤ 6; size 0.019; power 0.84; first n reaching 0.80 is 10 |
| Detect a clear failure | p = 0.80 | p = 0.60 | one | 0.05 | 0.80 | exact binomial | **38** | reject if X ≤ 25; size 0.029; power 0.81; first n reaching 0.80 is 35 |
| Detect a moderate failure | p = 0.80 | p = 0.70 | one | 0.05 | 0.80 | exact binomial | **127** | reject if X ≤ 93; size 0.040; power 0.81; first n reaching 0.80 is 116 |
| Estimate coverage to ±10 pp | — | — | two | 0.05 | — | Wilson | **81** | interval [0.700; 0.873] |
| Estimate coverage to ±5 pp | — | — | two | 0.05 | — | Wilson | **289** | interval [0.750; 0.842] |

- **Wilson 95% interval for an observed 80%.**

| n | 95% interval |
|---|---|
| 8 | [0.455; 0.950] |
| 12 | [0.517; 0.937] |
| 20 | [0.584; 0.919] |
| 40 | [0.652; 0.895] |
| 60 | [0.682; 0.882] |
| 100 | [0.711; 0.867] |

- **Superseded figures.** The first version of this record gave 8 / 29 / 109 / 62 / 246. They reproduce exactly from two different normal approximations:
  - n = ⌈((z₀.₉₅√(p₀q₀) + z₀.₈₀√(p₁q₁)) / (p₀ − p₁))²⌉;
  - n = ⌈(z₀.₉₇₅√(p₀q₀) / d)²⌉.

  No method was declared, and at these sizes both approximations are optimistic. They are superseded by the table above.
- **Scale calibration (continuous, per release; planning only).**
  - Method: normal theory, two-sided 95% half-width 1.96·σ/√n.
  - σ = 0.50 is the upper end of the 0.49–0.50 log-range residual on 2022–2023 training anchors without releases. It is a lower bound for event hours.

| n | 95% half-width, log units | As a factor |
|---|---|---|
| 20 | ±0.22 | ×1.24 |
| 40 | ±0.15 | ×1.17 |

- **Prospective timeline at about 20 releases a year pooled (8 FOMC + 12 CPI).**

| Question | Releases | Time |
|---|---|---|
| p = 0.40 against 0.80 | 12 | under 1 year |
| p = 0.60 against 0.80 | 38 | about 2 years |
| p = 0.70 against 0.80 | 127 | about 6 years |
| ±10 pp | 81 | about 4 years |
| ±5 pp | 289 | about 14 years |

  FOMC alone needs about 4.75 years for 38 releases.
- **Status.** `FALSIFICATION_FEASIBLE / CALIBRATION_CONFIRMATION_NOT_FEASIBLE_SHORT_TERM`. No per-bin target is fixed. A prospective falsification rule is to be frozen in a separate evaluation contract before the first prospective release is scored.

## 9. Fallback product behavior (pre-committed)

This applies until an event semantics passes the pre-registered prospective check. **Implemented** in the V2 branch (owner authorisation of 2026-10-03), not deployed.

- **Event span.** For each horizon H, the span around a scheduled CPI or FOMC release r is `[r − H, r + 60 min)`. About 6% of hours a year for 24h, less for 1h and 4h.
- **Inside the span, Signalbot:**
  - shows no numerical corridor for that horizon and no touch probability or `/risk` figure derived from it;
  - drops «Коридор 1ч с учётом события» from the event reminder push;
  - never writes «4 из 5» or any coverage claim.
- **What it shows instead (as implemented).** The release, its day and time, and a neutral statement that around a release the usual corridor calibration does not apply. No direction, no probability, no corridor.
  - **No multiplier.** The «×N шире обычного» line is not shown. Its window, comparator and timestamp semantics have not been separately verified for this purpose; the event reminder no longer carries it either.
- **Outside the spans,** the generic corridor stays as it is; its own wording issues are a separate task.

- **Implementation.**
  - **Source.** `beta/decision.py` `event_zones()` computes the zones, CPI and FOMC only, at the clock time `now`. `_build` drops every horizon whose zone holds `now` from `block["corridor"]["horizons"]` and from every zone's touch chances, and records `block["event_zone"]`.
  - **Downstream.** No text, `/risk` figure, `/alert` reply, alert line or tracked forecast can be built from a withheld horizon. The texts name the release and its time (`zone_note`). The corridor header drops «4 из 5» in an event context. The «Коридор 1ч с учётом события» string is removed.
  - **Outside every zone.** The generic corridor is unchanged, and its event flag can never be on there.
  - **Tests.** `tests/beta/test_beta_v2_event_zone.py`: the zone boundaries for 1h/4h/24h; every surface in RU/EN; alert payloads that still carry a corridor; an end-to-end PostgreSQL run around a CPI release.

## 10. What this record does not do

- It changes no code and retrains nothing.
- It does not fix thresholds to reach 80%.
- It does not touch the research registry, user copy or weekend calibration.
- It does not open any confirmation surface or the E1 holdout.
- It deploys nothing.
