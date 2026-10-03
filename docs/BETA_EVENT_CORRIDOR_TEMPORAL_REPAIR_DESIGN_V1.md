# Event corridor — temporal repair design record V1

**Status:** `DESIGN_ONLY / NO_CODE_CHANGE / NO_RETRAIN / NOT_DEPLOYED`
**Date:** 2026-10-03
**Scope:** the scheduled-release conditioning (CPI, FOMC) of the decision-support range corridor (`beta/rangecast.py`, `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §2). It does not change the generic range model, thresholds, the research registry, user copy or deployment. Those are separate tasks.
**Trigger:** red-team of branch `ccr-b5339153-71haxv` at `86dd802` (owner-relayed), plus the read-only checks in §4.

```
EVENT_CODE_CHANGED              = NO
EVENT_MODEL_RETRAINED           = NO
EVENT_SEMANTICS_STATUS          = FAILS_IN_LIVE_USE / NOT_CALIBRATED
GENERIC_RANGECAST_SKILL_STATUS  = SUPPORTED_ON_EXPOSED_2024 (diagnostic, not confirmatory)
DATA_2024_EVENT_WINDOWS         = EXPOSED / DIAGNOSTIC / REPAIR DATA
CONFIRMATION                    = PROSPECTIVE ONLY (primary); BitMEX 2017-2019 = unaudited secondary
FEASIBILITY                     = FALSIFICATION_FEASIBLE / CALIBRATION_CONFIRMATION_NOT_FEASIBLE_SHORT_TERM
FALLBACK                        = PRE-COMMITTED (§9): no numerical corridor around releases
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

### 4.1 Question A — `SUPPORTED_ON_EXPOSED_2024` (diagnostic)

- **Setup.** Binance BTCUSDT 5m, repository archives, 2022–2024. Fitted on 2022–2023, evaluated on the 2024 hourly anchors. Every anchor with a CPI/FOMC release in `[t − 60 min, t + H)` is excluded, and the constant band is fitted on training anchors with the same exclusion.
- **Results.**

| Horizon | Anchors | Coverage, model / constant | Model coverage by past-24h-range quintile (low → high) | Constant coverage by quintile | Interval score, model − constant (α = 0.2, day bootstrap 95%) |
|---|---|---|---|---|---|
| 1h | 8 720 | 79.4% / 79.5% | 76, 77, 80, 82, 82% | 93, 87, 84, 77, 60% | −0.29 [−0.38; −0.22] |
| 4h | 8 660 | 79.6% / 80.6% | 75, 77, 80, 82, 81% | 94, 86, 83, 79, 64% | −0.45 [−0.63; −0.29] |
| 24h | 8 279 | 79.0% / 78.7% | 69, 76, 80, 82, 85% | 87, 81, 80, 77, 71% | −0.53 [−0.95; −0.15] |

- **Reading.**
  - Marginal coverage is the same for a model and a constant by construction, so it says nothing about skill.
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

1. **Prospective releases — primary.**
   - **Scope.** Every scheduled CPI and FOMC release after the event semantics are frozen, scored from the project's own Stage-1 Binance 1m data with event-relative forecast tracking.
   - **Calendar now.** CPI 2026-10-14, 2026-11-10, 2026-12-10. FOMC 2026-10-28, 2026-12-09 and 8 meetings in 2027. 2027 CPI dates go in when BLS publishes them.
   - **Rate.** About 20 releases a year pooled (8 FOMC + 12 CPI).
2. **BitMEX XBTUSD 2017–2019 — secondary, not audited, not opened.**
   - **What exists.** 5m data is in the repository (`docs/research_data/D2_BITMEX_PRE2020_XBTUSD`). D2 (daily) and D7 (hourly) read it in bulk for generic volatility persistence. The ledger records no event-conditioned outcome on it.
   - **Size.** About 24 FOMC and 36 CPI releases.
   - **Before use.** It needs a point-in-time 2017–2019 release calendar (not in the repository) and an exposure audit.
   - **What it can show.** Being another venue and an inverse contract, it could confirm the temporal mechanism, not the Binance calibration.
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

- **Independent units.** Releases: all 5-minute anchors around one release share one market reaction. About 20 a year pooled; FOMC alone 8 a year.
- **Coverage around releases (binomial).**
  - 95% Wilson interval for an observed 80%, by number of releases n:

| n | 95% interval |
|---|---|
| 8 | [45%; 95%] |
| 12 | [52%; 94%] |
| 20 | [58%; 92%] |
| 40 | [65%; 90%] |
| 60 | [68%; 88%] |
| 100 | [71%; 87%] |

  - Releases needed (one-sided 5%, power 80%):

| Question | Releases needed |
|---|---|
| Detect a true coverage of 40% against 80% | 8 |
| Detect 60% against 80% | 29 |
| Detect 70% against 80% | 109 |
| Estimate coverage to ±10 pp | 62 |
| Estimate coverage to ±5 pp | 246 |

- **Scale calibration (continuous, per release).**
  - The log-range residual on training anchors without releases has σ ≈ 0.49–0.50 at all horizons. Event hours are likely noisier, so this is a lower bound.
  - The 95% interval of the mean log ratio (realized / predicted) is ±0.98/√n:

| n | 95% interval, log units | As a factor |
|---|---|---|
| 20 | ±0.22 | ×1.24 |
| 40 | ±0.15 | ×1.17 |

  - An error of ×2.7, like the current pre-release box, shows within a handful of releases.
- **Prospective timeline at about 20 releases a year.**
  - A gross failure (true coverage at or below 60%) can be falsified within about 1.5 years.
  - Coverage to ±10 pp needs about 3 years; to ±5 pp, over 10 years.
  - FOMC alone needs about 3.6 years for the 60%-against-80% question.
- **Status.** `FALSIFICATION_FEASIBLE / CALIBRATION_CONFIRMATION_NOT_FEASIBLE_SHORT_TERM`.
  - An "80% around events" or «4 из 5» claim cannot be independently confirmed for years.
  - No per-bin target (5- or 30-minute) is fixed. With these sample sizes a bin-level target would be unsupported.
  - A prospective falsification rule, PRE and POST units separately with a minimum number of releases, is to be pre-registered before the first prospective release is scored.

## 9. Fallback product behavior (pre-committed)

This applies until an event semantics passes the pre-registered prospective check. It is the planned behavior; its implementation needs separate approval.

- **Event span.** For each horizon H, the span around a scheduled CPI or FOMC release r is `[r − H, r + 60 min)`. About 6% of hours a year for 24h, less for 1h and 4h.
- **Inside the span, Signalbot:**
  - shows no numerical corridor for that horizon and no touch probability or `/risk` figure derived from it;
  - drops «Коридор 1ч с учётом события» from the event reminder push;
  - never writes «4 из 5» or any coverage claim.
- **What it shows instead.**
  - The release and its time.
  - A descriptive event-risk line from the event-day statistics: the median size of such hours and days against a usual hour and day, with N and the period (Binance, since 2020).
  - No direction, no probability, no corridor.
- **Outside the spans,** the generic corridor stays as it is; its own wording issues are a separate task.

## 10. What this record does not do

- It changes no code and retrains nothing.
- It does not fix thresholds to reach 80%.
- It does not touch the research registry, user copy or weekend calibration.
- It does not open any confirmation surface or the E1 holdout.
- It deploys nothing.
