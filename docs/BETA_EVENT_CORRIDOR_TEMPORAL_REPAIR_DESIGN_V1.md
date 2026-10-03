# Event corridor — temporal repair design record V1

**Status:** `DESIGN_ONLY for the event model (K1 not implemented, no retrain) / §9 corridor FALLBACK and §10 sharp-move FALLBACK IMPLEMENTED in the V2 branch / NOT_DEPLOYED`
**Date:** 2026-10-03
**Scope:** the scheduled-release conditioning (CPI, FOMC) of the decision-support range corridor (`beta/rangecast.py`, `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §2). It does not change the generic range model, thresholds, the research registry, user copy or deployment. Those are separate tasks.
**Trigger:** red-team of branch `ccr-b5339153-71haxv` at `86dd802` (owner-relayed), plus the read-only checks in §4.

```
EVENT_CODE_CHANGED_FOR_K1       = NO
EVENT_MODEL_RETRAINED           = NO
EVENT_SEMANTICS_STATUS          = FAILS_IN_LIVE_USE / NOT_CALIBRATED
GENERIC_RANGECAST_SKILL_STATUS  = DIAGNOSTICALLY_SUPPORTED / NOT YET PROSPECTIVELY CONFIRMED
DATA_2024_EVENT_WINDOWS         = EXPOSED / DIAGNOSTIC / REPAIR DATA
PRIMARY_CONFIRMATION_SURFACE    = PROSPECTIVE RELEASES AFTER K1 FREEZE (§6)
BITMEX_CONFIRMATION_STATUS      = NOT_PROVABLY_INDEPENDENT (§6)
SURFACE_2024                    = EXPOSED / DIAGNOSTIC / REPAIR
SURFACE_2025_2026               = EXPOSED_FOR_OTHER_PURPOSES / NOT CONFIRMATORY
HISTORICAL_SURFACE_OPENED       = NONE
FEASIBILITY                     = FALSIFICATION_FEASIBLE / CALIBRATION_CONFIRMATION_NOT_FEASIBLE_SHORT_TERM (§8)
EVENT_FEASIBILITY_METHOD        = EXACT ONE-SIDED BINOMIAL (detection) + WILSON 95% (precision) (§8)
EVENT_FEASIBILITY_TABLE         = LOCKED 2026-10-03: 12 / 38 / 127 / 81 / 289 releases; earlier figures in §12 only
FALLBACK                        = IMPLEMENTED (§9): no numerical corridor in an event zone
EVENT_MULTIPLIER_USER_FACING    = NO (§9; /events, briefing «Сегодня», reminder, glossary)
RAPID_MOVE_EVENT_RISK_CLASS     = C / EVENT_FLAG_DECISION_RELEVANT_UNCALIBRATED (§10, audit)
SHARP_MOVE_EVENT_CONDITIONING   = DISABLED_PENDING_VALIDATION (§10, Option 1 implemented)
```

**Current product safety state (V2 branch, not deployed).** These are fallbacks. None of them confirms any event semantics.
1. The numerical corridor is suppressed around CPI/FOMC releases (§9).
2. Event-specific touch probabilities and `/risk` figures are suppressed there (§9).
3. Event multipliers are removed from every user-facing event surface (§9).
4. The sharp-move detector no longer uses the unvalidated event coefficients (§10).
5. K1 remains `DESIGN_ONLY`.
6. Prospective releases after the K1 freeze remain the only primary confirmation surface (§6).

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
| Binance 2025-01-01 → 2026-10-03 (20 CPI, 14 FOMC) | `EXPOSED_FOR_OTHER_PURPOSES / NOT CONFIRMATORY`: opened by the owner for product statistics; `RESEARCH_LEDGER`: consumed for research over event days. Its event hours have not been read in this branch | Not a confirmation surface. Not independent either: it would also be part of the VPS fit |
| E1-RUN-001 holdout `[2026-08-16, 2026-08-25 17:20)` | Protected | Never read (`beta/history_data.py` rejects every overlapping object) |
| Other venues for the same dates (OKX spot 2022–2024 in the repository, Bybit live) | Same releases, same market reaction | Not independent units |

## 6. Independent confirmation surface (none opened)

```
PRIMARY_CONFIRMATION_SURFACE = PROSPECTIVE RELEASES AFTER K1 FREEZE
BITMEX_CONFIRMATION_STATUS   = NOT_PROVABLY_INDEPENDENT
2024                         = EXPOSED / DIAGNOSTIC / REPAIR
2025-2026                    = EXPOSED_FOR_OTHER_PURPOSES / NOT CONFIRMATORY
HISTORICAL SURFACES OPENED   = NONE (this record opens no historical surface)
```

1. **Prospective releases after the K1 freeze — primary, and the only eligible surface.**
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
3. **Not eligible.** Everything in §5 except item 1.
   - 2024 is `EXPOSED / DIAGNOSTIC / REPAIR`.
   - 2025–2026 is `EXPOSED_FOR_OTHER_PURPOSES / NOT CONFIRMATORY`. It is excluded although its event hours are unread here: it was opened for product statistics and research, and the nightly build fits on it.

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

**Locked (2026-10-03).** The table below is the only current feasibility table. Its parameters:

```
H0                  = p = 0.80 (the corridor's nominal coverage)
SIDEDNESS / ALPHA   = one-sided (under-coverage), alpha = 0.05, attained size <= alpha
POWER               = 0.80
REJECTION RULE      = reject H0 iff X <= c(n), c(n) = max{ c : P(X <= c | n, p = 0.80) <= 0.05 }
STABILITY           = n* = smallest n with power >= 0.80 for every m in [n, n + 100]
PRECISION           = two-sided Wilson 95% interval at p-hat = 0.80; both sides within d,
                      for every m in [n, n + 100]
```

After any prospective outcome is seen, none of these numbers, parameters or rules changes except by a written, dated amendment to this record that states the change, its reason, and which prospective outcomes had been seen when it was made. The earlier figures are kept in §12 (changelog) only.

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
  - **No multiplier anywhere.** No «×N» is shown for a scheduled event. Its window, comparator and timestamp semantics have not been verified for this purpose. The 2026-10-03 cleanup removed it from every event-facing surface:
    - the event reminder;
    - `/events`, which is now a plain calendar: each line has the name and the exact Kyiv time;
    - the briefing's and `/catchup`'s «Сегодня» lines.
  - **The neutral warning.** When a CPI or FOMC release is listed, one line follows the list: «<release>: вокруг публикации обычная калибровка коридора не применяется.» / "<release>: around the release, the usual corridor calibration does not apply." Expiries make no zone and get no warning.
  - **Research lines.** A CPI/FOMC event context no longer adds a «Проверено» line on these surfaces (D11's «в 1,76 раза» would otherwise ride on them). The registry is unchanged and `/research` still lists every unit.
  - **Glossary.** The corridor entry no longer says the corridor accounts for events. It says that around CPI and Fed decisions the numerical corridor and the chance to reach are not shown.
- **Outside the spans,** the generic corridor stays as it is; its own wording issues are a separate task.

- **Implementation.**
  - **Source.** `beta/decision.py` `event_zones()` computes the zones, CPI and FOMC only, at the clock time `now`. `_build` drops every horizon whose zone holds `now` from `block["corridor"]["horizons"]` and from every zone's touch chances, and records `block["event_zone"]`.
  - **Downstream.** No text, `/risk` figure, `/alert` reply, alert line or tracked forecast can be built from a withheld horizon. The texts name the release and its time (`zone_note`). The corridor header drops «4 из 5» in an event context. The «Коридор 1ч с учётом события» string is removed.
  - **Outside every zone.** The generic corridor is unchanged, and its event flag can never be on there.
  - **Tests.** `tests/beta/test_beta_v2_event_zone.py`: the zone boundaries for 1h/4h/24h; every surface in RU/EN; alert payloads that still carry a corridor; an end-to-end PostgreSQL run around a CPI release.

## 10. Rapid-move detector: event-feature audit (read-only, detector unchanged)

- **Where the detector reads the event feature.**
  - `beta/market_alerts.py` `detect_move()` computes `S = scale_at(model, b, j, "1h", events=events)`, where j is the last 5m bar closed before the 15-minute move began.
  - `scale_at` → `design()` → `event_in_window(close_ms, events[k], HORIZON_MS["1h"])` (`beta/rangecast.py`).
  - The threshold is calibrated nightly by `sharp_move_threshold()` on `move_ratio()`. That builds S with the same `design()` and the same event columns, at the same anchor (the bar three bars back).
  - Only the 1h flags enter. The 4h and 24h flags are not used by the detector.
- **What changes when the flag is 1.**
  - S is multiplied by exp(β): ×2.81 for CPI and ×2.69 for FOMC in the 2022–2024 local fit.
  - The rule is `|move| / S ≥ threshold`, so a move must be about 2.7–2.8 times larger in % to alert.
- **What it affects.**
  - **Affected:** the push decision, i.e. whether a candidate exists at all (eligibility, via the effective threshold).
  - **Not affected directly:** the 120-minute cooldown, the UTC-day cap for level + move, quiet hours, the dedup key, and the text. The «примерно раз в N дней» line uses the calibration's pooled episode rate; the payload's `ratio` is stored and not rendered. There is no severity field.
  - **Indirect effect:** the cooldown and the cap start only from a pushed move, so a suppressed move also changes what can fire after it.
- **Semantics.** The move window is `[E − 15 min, E)`, where E is the close of the last closed 5m bar, and the anchor is a = E − 15 min. The flag is 1 ⇔ r ∈ [a, a + 60 min) ⇔ E ∈ (r − 45 min, r + 15 min].

| now (detector on time) | Move window checked | 1h flag | Effective threshold |
|---|---|---|---|
| r − H for 24h / 4h | [r − H − 15m, r − H) | 0 | normal |
| r − 60m (r − H for 1h) | [r − 75m, r − 60m) | 0 | normal |
| r − 5m | [r − 20m, r − 5m) | 1 | ×2.7–2.8 |
| r (release) | [r − 15m, r) | 1 | ×2.7–2.8 |
| r + 5m | [r − 10m, r + 5m) | 1 | ×2.7–2.8 |
| r + 30m | [r + 15m, r + 30m) | 0 | normal |
| r + 60m | [r + 45m, r + 60m) | 0 | normal |
| r + 61m | [r + 45m, r + 60m) (E = r + 60m) | 0 | normal |

- **Grid boundaries.**
  - E = r − 45m: last normal window before the release.
  - E = r − 40m: first inflated window.
  - E = r + 15m, i.e. the window [r, r + 15m): last inflated window.
  - E = r + 20m: first normal window after the release.
- **Check.** Synthetic bars and a synthetic model carrying only the CPI coefficient; no market data was read. The same 1.0% 15-minute move at threshold 0.5:
  - alerts at E = r − 60m, r − 45m, r + 20m, r + 30m and r + 60m;
  - is suppressed at every E from r − 40m to r + 15m.
- **Pre/post asymmetry: possible.**
  - The flag covers windows that start in (r − 60m, r]: windows before the release, the ones that cross it, and only one window entirely after it, [r, r + 15m).
  - A move made in the first minutes after the release is checked only in windows ending at r + 5m, r + 10m and r + 15m, all inflated. The same move in [r + 5m, r + 20m) is checked against the normal threshold.
  - Before the release, the same move alerts in [r − 60m, r − 45m) and needs about ×2.8 in [r − 55m, r − 40m).
- **Calibration.**
  - β was fitted for the 1h forward range at hourly anchors, not for 15-minute close-to-close moves.
  - The threshold targets about 0.35 episodes a day pooled over all bars. Nothing calibrates the alert rate around releases.
  - The past-range features also rise after any large move. That part is generic, not event-specific.
- **Class: C — `EVENT_FLAG_DECISION_RELEVANT_UNCALIBRATED`.**
- **Minimal fallback, as proposed in the audit.** Option 1 below was authorised by the owner on 2026-10-03 and is implemented; see "Implemented".
  - **Option 1 (preferred).** Drop the event term from the move scale only: compute S from the same model with the event columns at 0, in both `detect_move` and `move_ratio` / `sharp_move_threshold`. The next nightly build then recalibrates the threshold on the same statistic.
    - An identical move gets an identical decision on both sides of a release.
    - The corridor model and its coefficients are untouched.
    - About two call sites plus tests.
  - **Option 2.** No sharp-move push while E is in the 1h event zone [r − 60m, r + 60m). This is simpler, but the release move itself is then never alerted; the reminder 30 minutes before stays.
  - **Either way.** Inside a zone the move alert already shows no corridor (§9). The «примерно раз в N дней» line is an unconditional, all-hours frequency; whether it stays inside an event zone is a copy question for the same authorisation.

### Implemented (Option 1, owner authorisation of 2026-10-03)

`SHARP_MOVE_EVENT_CONDITIONING = DISABLED_PENDING_VALIDATION`. This is a product safety fallback for the move detector. It neither repairs nor confirms the event model.

- **One statistic, one function.**
  - `rangecast.sharp_move_scale()` is the 1h rangecast scale with every CPI/FOMC column at 0. It keeps the same fitted coefficients and the same volatility (1h, 4h, 24h, 7d past ranges), time-of-day and weekend terms. It is not a constant scale.
  - `move_ratio()` divides the 15-minute move by it and no longer takes events.
  - The nightly calibration (`fit_range_model` → `sharp_move_threshold` → `move_ratio`) and the live detector (`detect_move` → `move_ratio_at` → `move_ratio` on the bars ≤ i slice) call the same function. `detect_move` no longer takes events.
  - There are no other call sites, and no replay or backfill path for the detector exists.
- **The threshold is tied to its statistic.**
  - `model["move"]["statistic"] = "MOVE15_OVER_1H_SCALE_EVENT_NEUTRAL_V1"`.
  - The detector refuses a threshold without that tag. A stats row built before this change sends no sharp-move push until the next nightly build.
- **Unchanged.**
  - The calibration procedure: quantiles 0.99 / 0.995 / 0.998 / 0.999 / 0.9995, target 0.35 episodes a day, 2h declustering, 15-minute window, and the closest-to-target selection.
  - The corridor model: `design`, `event_in_window` (K0), the event coefficients, the fit and `forecast`. A pre-change snapshot of the 2022-01..04 fit and forecast is reproduced exactly.
  - The §9 corridor fallback.
- **Threshold, as a diagnostic consequence only.** Same procedure, same fitted model, Binance BTCUSDT 5m repository archives 2022-01..2024-12, pooled over all bars:
  - **OLD:** 2.0618 (event-conditioned statistic; quantile 0.998; 0.323 episodes a day).
  - **NEW:** 2.0963 (event-neutral statistic; quantile 0.998; 0.319 episodes a day).

  The production value comes from the nightly build on the server's history. The difference changes nothing in the algorithm.
- **Copy inside the release's 1h zone.** The move alert keeps:
  - the fact of the move;
  - its size, time span and prices;
  - the nearest levels;
  - the neutral warning.

  It drops «Такой ход бывает примерно раз в N дней», which is a pooled all-hours frequency. It also drops the «Проверено» line, because no research unit tested release moves. Outside the 1h zone the generic copy is unchanged.
- **Tests.** `tests/beta/test_beta_v2_sharp_move.py`:
  - the discontinuity at r − 61m … r + 61m with an identical market state;
  - live = calibration `move_ratio`;
  - one shared function;
  - CPI and FOMC flags with no effect on the move scale;
  - the non-event conditioning kept;
  - the threshold procedure and the statistic tag;
  - the corridor's K0 term and the pre-change corridor snapshot;
  - the copy in RU/EN;
  - an end-to-end PostgreSQL run with a move in [r, r + 15m).

## 11. What this record does not do

- It changes no code and retrains nothing.
- It does not fix thresholds to reach 80%.
- It does not touch the research registry, user copy or weekend calibration.
- It does not open any confirmation surface or the E1 holdout.
- Its §10 fallback changes only the scale of the sharp-move statistic and the copy inside the 1h zone. It is not a confirmation of any event semantics.
- It deploys nothing.

## 12. Changelog

- **2026-10-03, first version.** Feasibility figures 8 / 29 / 109 / 62 / 246 releases. No method was declared. They reproduce exactly from two different normal approximations:
  - n = ⌈((z₀.₉₅√(p₀q₀) + z₀.₈₀√(p₁q₁)) / (p₀ − p₁))²⌉;
  - n = ⌈(z₀.₉₇₅√(p₀q₀) / d)²⌉.

  At these sizes both approximations are optimistic. **Superseded** by the exact table in §8, which was computed with methods fixed beforehand.
- **2026-10-03, fallback.** §9 was implemented in the V2 branch, and BitMEX 2017–2019 was audited as `NOT_PROVABLY_INDEPENDENT` (§6).
- **2026-10-03, event safety cleanup.**
  - The event multiplier was removed from `/events` and from «Сегодня».
  - The neutral warning was added, and CPI/FOMC research lines were taken off event surfaces.
  - The glossary was corrected.
  - The feasibility table was locked (§8) and the confirmation surfaces recorded (§6).
  - The detector audit was added (§10, class C, no code change).
- **2026-10-03, sharp-move fallback (Option 1).**
  - The sharp-move statistic became event-neutral, shared by the live detector and the calibration, and tagged.
  - In the release's 1h zone, the move alert's pooled frequency line and research line were removed.
  - OLD/NEW thresholds were recorded as a diagnostic.
  - `SHARP_MOVE_EVENT_CONDITIONING = DISABLED_PENDING_VALIDATION`.
