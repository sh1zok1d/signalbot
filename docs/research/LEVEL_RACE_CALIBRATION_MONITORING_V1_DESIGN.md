# Level race — calibration, gates and monitoring (design V1, part of the F1 design note)

**Status:** `PROPOSAL_FOR_MINI_HEAD / SYNTHETIC_ONLY / BEFORE_ANY_OUTCOME` (ОПГ-2 track F3, 2026-10-08).
No market bar, no level event and no real outcome was read for this note. Every number below is a design choice checked on synthetic worlds (§10). The mini-head reconciles it with F1's design note and freezes both before the held-out read.

**Authority:**
- `docs/FORECAST_LAYER_DECISION_V1.md` §4–§7 (object, held-out stage, live record, calibration, states, drift, challengers);
- `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` §4–§5 (L3 needs a live count fixed in the design note; claim journal);
- `docs/PRE_BETA_SCOPE_DECISION_V1.md` §4 (history first, live joins by a rule frozen before Day 0) and §11.

**Code:** `beta/level_race_calibration.py` (pure, no database; constants in its header are the numbers below), `scripts/research/level_race_calibration_sim.py` (the synthetic study), `scripts/research/level_race_weekly_report.py` (§8). Results: `LEVEL_RACE_CALIBRATION_MONITORING_V1_SIM.json`.

## 0. Proposed numbers at a glance

| Item | Proposal | Planning value in FORECAST_LAYER |
|---|---|---|
| Outcome representation | two heads: RESOLVE (a barrier within 4h) and BREAK \| resolve | "two heads or multinomial" |
| Held-out gate (per class, each head) | walk-forward published \|intercept\| ≤ 5 pp; fitted recalibration curve within 7.5 pp of the diagonal (10–90 % range); raw \|intercept\| ≤ 10 pp; ≥ 20 weeks | "frozen tolerance" |
| M1 or B0 published | M1 only if its held-out log-loss gain over B0 has a week-clustered one-sided 95 % lower bound > 0 | "if M1 does not beat B0" |
| Calibrator | 2-parameter Bayesian logistic per head, Laplace; prior = held-out fit worth **150** events | 100–200 |
| Batches | weekly for 12 weeks, then every 4 weeks; versioned; outcomes resolved before the cutoff only | weekly, then monthly |
| L3_LIVE floor | **150** resolved live events of the class | 150 |
| L3_LIVE tolerance | live \|intercept\| ≤ 7.5 pp and fitted curve within 10 pp, each head; no drift alarm | — |
| e-process | change-point mixture of intercept-shift likelihood ratios on the published probabilities; FALLBACK at **E ≥ 10** | e > 10 |
| Rolling intercept | last 100 resolved: 99 % week-clustered interval wholly outside **±5 pp** | "interval outside ±10 pp" |
| Rolling paired log loss vs B0 | last 100 resolved, ≥ 8 weeks: 99 % interval of (B0 − published) wholly below 0 | ~100 events |
| Large correction | calibrator's mean \|p′ − p\| > 10 pp on the held-out design → drift | "a drift signal, not a fix" |
| Return from FALLBACK | ≥ **50** new resolved, epoch e-value < 1, epoch \|intercept\| ≤ 10 pp, not worse than B0; the 2nd FALLBACK of a version is final | ≥ 50 |
| Challenger promotion | looks at 150 / 300 / 450 / 600 paired; 95 % week-clustered gain interval > 0 and live-tolerance calibration; retired after 600; ≤ 2 at once | ≥ 150, interval excludes 0 |
| Input drift, data health | input drift is reported, never a state change; any health fault → OFF at once | — |

## 1. Object and heads

The three outcomes BREAK first / REJECT first / NEITHER within the original 4h window are carried as two binary heads:

- **RESOLVE**: P(a barrier is reached) = 1 − P(NEITHER), on every event;
- **BREAK_GIVEN_RESOLVE**: P(BREAK | resolved), on resolved events only.

P(BREAK) = P(resolve)·P(BREAK | resolve), P(REJECT) = P(resolve)·(1 − P(BREAK | resolve)), P(NEITHER) = 1 − P(resolve). The decomposition is exact, so it works whichever form F1 fits (multinomial M1 or two heads): the calibrator and the monitors read the heads derived from the three published probabilities.

**Why heads and not three one-against-rest maps:** three independent maps do not sum to 1, and the 14 % NEITHER share (FORECAST_LAYER §2) makes one-against-rest NEITHER the least informed map of all. The heads also separate the two questions the product asks: «дойдёт ли за 4ч» and «какая первой».

**For F1 to confirm:** the two classes are the landmarks `L3_LEVEL_RACE_T0_4H` and `L3_LEVEL_RACE_T15_4H`; each has its own calibrator, monitors and state. The same machinery runs on the generic race stream (FORECAST_LAYER §5 pooling) as a separate class; this note does not fix its numbers.

## 2. Held-out gate (`L3_HISTORY_BACKED`)

**What is checked.** The held-out check scores what users would see, not the raw model alone:
- the held-out events are walked forward in time with the calibrator of §3, starting from the identity map worth 150 events; each event's published probabilities come from the calibrator fitted on held-out outcomes resolved before its batch cutoff;
- the «на истории: говорили X → было X′, N = …» line is computed from these walk-forward published probabilities, so it is out of sample at every event;
- the final held-out fit becomes the live prior (§3).

**Pass rule, per class, for each head:**
1. walk-forward published calibration intercept (mean y − p) |·| ≤ **5 pp**;
2. the logistic recalibration curve fitted to the walk-forward published probabilities stays within **7.5 pp** of the diagonal at the 10/25/50/75/90 % quantiles of the published probabilities;
3. the **raw** model's |intercept| ≤ **10 pp** (a larger correction is a drift signal, not a calibration: FORECAST_LAYER §5);
4. at least **20 weeks** with events.

The slope itself is reported, not gated: the RESOLVE head has little spread (the barriers are a fixed number of σ away), so its slope is poorly identified (synthetic SD ≈ 0.3 at 650 events) while its probabilities hardly move. The curve criterion gates what a user would see.

**M1 or B0.** M1 is published only if its held-out log-loss gain over B0 has a one-sided 95 % week-clustered lower bound above 0 (`BEATS_B0_Z = 1.645`). Otherwise the calibrated B0 is published, and the wording carries no level effect (FORECAST_LAYER §6). The gate of 1–4 then applies to the published model.

**Synthetic operating characteristics** (300 replications each; T0 ≈ 650, T15 ≈ 420 held-out events; τ = week effect, §10):

| World (miscalibration of the raw model on BREAK \| resolve) | T0 pass | T15 pass |
|---|---|---|
| calibrated | 100 % | 96–99 % |
| intercept +0.2 logit (≈ +5 pp) | 93–94 % | 89–93 % |
| intercept +0.4 logit (≈ +10 pp) | 58 % | 57–63 % |
| intercept +0.6 logit (≈ +15 pp) | 9 % | 14 % |
| slope 0.7 (over-confident) | 97–99 % | 82–84 % |
| slope 1.4 (under-confident) | 88 % | 68–71 % |

The walk-forward calibrator absorbs a 5 pp error, as intended; a 10 pp error fails about half the time; 15 pp almost always.

**Power of «M1 beats B0»** (share of replications publishing M1):

| True structural offset over B0 (logit; FORECAST_LAYER §2 records ≈ 0.35) | z = 1.96 | **z = 1.645** | z = 1.28 |
|---|---|---|---|
| 0 (no level effect) | 0 % | ≤ 0.3 % | ≤ 0.7 % |
| 0.2 | 1–2 % | 2–6 % | 3–10 % |
| 0.35 | T0 18–25 %, T15 10 % | **T0 32–39 %, T15 18–19 %** | T0 49–53 %, T15 29 % |
| 0.5 | T0 64–71 %, T15 33–38 % | T0 76–80 %, T15 48–49 % | T0 87–89 %, T15 62–64 % |

**Read this before Day 0.** At the recorded offset, the most likely Day-0 outcome is the calibrated B0 published with no level effect claimed, because about 650 / 420 held-out events cannot separate a +9 pp offset from zero with confidence. This is the honest consequence of the event rate, not a defect of the rule. A lower z buys power at a small false-claim cost (table); the choice is the mini-head's and F1's.

## 3. Bayesian calibrator

- **Map, per head:** p′ = expit(c + a + b·(logit p − c)), with c the mean raw logit of the held-out design (fixed per head and version). (a, b) = (0, 1) is the identity; a is the shift at the design centre. Centring makes a and b nearly independent.
- **Prior:** Gaussian at the held-out fit; its precision is reset to **150 events** of the held-out design (150 × the mean per-event Fisher information at the prior mean). The information uses raw probabilities only, never an outcome.
- **Fit:** MAP by Newton with a Laplace covariance, refit from the prior on every live outcome resolved strictly before the cutoff. Deterministic.
- **Batches:** cutoffs every week for the first 12 weeks after the freeze, then every 4 weeks. A forecast issued at t uses the calibrator of the last cutoff ≤ t. Each calibrator has a version `LEVEL_RACE_CAL_V1:<digest>` over its class, cutoff, prior and parameters; the journal stores it with the forecast.
- **No isotonic or other non-parametric map** below 300 events (`ISOTONIC_MIN_EVENTS`); V1 has none at all.
- **Large correction:** when the calibrator's mean |p′ − p| over the held-out design exceeds 10 pp on either head, that is a drift signal (§5), not a fix. The map is still recorded.

## 4. Live floor (`L3_LIVE`)

- **Floor:** 150 resolved live events of the class (RESOLVE head count; the BREAK \| resolve head then has about 130).
- **Tolerance:** on all live events of the version, each head: |intercept| ≤ 7.5 pp and the fitted curve within 10 pp of the diagonal; and no drift reason (§5) at that batch.
- **Why 7.5 pp and not 5:** at 150 events the intercept's standard error is about 4 pp; 5 pp would refuse a calibrated model about one time in five. The live line printed beside the number shows the actual «говорили → было» and N, so the user sees the residual.
- **Synthetic:** a calibrated model reaches L3_LIVE in 100 % of replications, median live week 24 (T0) and 32 (T15). Day 0 to the live line is therefore about 6–8 months.

## 5. Drift monitors

All are evaluated at each batch cutoff on the resolved live records of the class, in issue order, published or not.

### 5.1 Anytime-valid e-process on the calibration intercept

- **Increment:** for each event, the likelihood ratio of an alternative that shifts the published logit by δ_A on RESOLVE and by δ_B on BREAK \| resolve (head B only when resolved), against the published probabilities. Grid δ ∈ {−0.6, −0.3, 0, 0.3, 0.6} per head, (0, 0) excluded, equal weights.
- **Change points:** a new start every 25 events, start j weighted 1/((j + 1)(j + 2)); starts not yet reached count as 1. E is a test martingale under conditional calibration, so P(sup E ≥ 10) ≤ 0.1 over the whole life of an epoch (Ville), while a drift that begins late is not buried under the evidence of the early calm period.
- **FALLBACK at E ≥ 10.** E restarts at each FALLBACK entry and each return (a new epoch, a new ≤ 0.1 budget).
- **Tested and rejected:** running E on the raw model under the frozen held-out map (`E_KEY = "p_ref"`). It detects drifts faster (≈ 76 % vs 64 % within 52 weeks for a 15 pp shift), but it also detects the held-out fit's own estimation error: 34 % false FALLBACK over two calm years against 9 % on the published probabilities (T0, τ = 0.25, 200 replications). Rejected.

### 5.2 Rolling intercept

Over the last 100 resolved events, each head: FALLBACK when the 99 % week-clustered interval of the intercept lies wholly outside ±5 pp. The standard error never goes below the independent-events one (with 13–20 weekly clusters the cluster-robust estimate alone was too small and gave 25 % false FALLBACK in the first synthetic pass).

### 5.3 Rolling paired log loss against B0

Over the last 100 resolved events with at least 8 weeks: FALLBACK when the 99 % week-clustered interval of (log loss B0 − log loss published) lies wholly below 0, i.e. the published forecast is worse than «обычно».

### 5.4 Input drift (reported, never a state change)

Per batch, over the last 8 weeks against the held-out period: the median PIT σ, the distribution of the B0 BREAK probability (the position), and the event rate per week. A value outside the 2.5–97.5 % range of the held-out 8-week blocks is flagged in the weekly report and to the mini-head. It does not change the state: a regime the model has not seen is a reason to look, and the calibration monitors decide whether the forecast became wrong.

### 5.5 Data health (OFF at once)

`OFF` on any of: stale price data, a parity break between the live detector and the #352 constructor, a journal write failure, or σ-window coverage below the frozen minimum. The state returns to where it was when every check is healthy again. The checks themselves belong to the live pipeline (F2 / ОПГ-1); this module takes their booleans.

## 6. Challengers

- Logged in shadow from registration, paired on the same events, each with its own walk-forward calibrator from the same prior.
- **Looks only at 150, 300, 450 and 600 paired resolved events** (not at every batch: repeated looks inflate false promotions). At a look: promoted when the 95 % week-clustered interval of the log-loss gain over the published champion lies above 0 and the challenger's live calibration meets §4. Retired unpromoted after the 600 look.
- At most two at once, each in the exposure ledger. A promoted challenger's shadow record is its live record. A retrain is a new version and enters as a challenger.
- **Synthetic (C1-like covariate, coefficient estimated with SD 0.1):** see §10 table.

## 7. State machine

`next_state(prev, health, monitors, now)` is a pure function; the record carries the state, its start, the epoch start index, the FALLBACK count and the model version (`LEVEL_RACE_STATE_V1`).

| From | To | Rule |
|---|---|---|
| — | `L3_HISTORY_BACKED` / `HIST` | held-out gate passed / not passed (§2) |
| any | `OFF` | any health fault, at once (any call) |
| `OFF` | previous | all health checks pass |
| `HIST` | — | terminal for the version: a failed held-out check is not rescued by live data; a new version enters as a challenger |
| `L3_HISTORY_BACKED` | `L3_LIVE` | live N ≥ 150 and §4 tolerance |
| `L3_*` | `FALLBACK` | any drift reason of §5.1–§5.3 or a large correction (§3); a new epoch starts |
| `FALLBACK` | `L3_LIVE` or `L3_HISTORY_BACKED` | ≥ 50 resolved since entry, epoch E < 1, each head's epoch \|intercept\| ≤ 10 pp, not worse than B0, no drift reason; `L3_LIVE` if §4 holds on the whole live record, else `L3_HISTORY_BACKED`; a new epoch starts |
| `FALLBACK` (2nd of the version) | — | final for the version |

Model rules are evaluated at batch cutoffs only; health at every call. Hysteresis comes from the entry/exit asymmetry (E ≥ 10 to leave, E < 1 to return), the 50-event dwell and the two-FALLBACK cap.

## 8. Weekly report

`scripts/research/level_race_weekly_report.py` reads the journal export (JSON lines) and reports per class, raw and published separately, in the order of FORECAST_LAYER §5: log-loss skill against B0 and B1 with the week-clustered paired interval; intercept (pp) and slope with intervals per head, plus the curve gap; the 5-bin reliability table per outcome; three-category Brier and, per outcome, reliability / resolution / uncertainty; sharpness (share outside 40–60 %); AUC per outcome; ECE (descriptive); each challenger paired against the published champion with its look verdict.

## 9. Interface for F2 (display)

`display_contract(state_record, published_model, calibrator_version, holdout_line, live_line)` returns, per class:

```
state, since_ms, reason, template            # lr_hist_l2 / lr_b_holdout / lr_b_live / lr_fallback_b0 / lr_off
probabilities                                # "M1" | "B0" | "B0_GENERIC" (FALLBACK) | None (HIST, OFF)
level_effect_claimed                         # True only when M1 is printed
calibrator_version                           # stored with the journal row
accuracy_line                                # "holdout" | "live" | None
holdout_line, live_line                      # {predicted, realized, n} blocks, only in the L3 states
```

F2 owns the template texts and prices; this module never emits a word. To agree through the mini-head: the template ids, and where F2 reads the stored state (proposal: one runtime-health component per class, as `touch_live_cal` in `beta/claims.py`, written by the batch job).

## 10. The synthetic study

**Worlds** (from the planning numbers of FORECAST_LAYER §2 and §4 only):
- T0: 7.5 events / week, P(resolve) ≈ 0.90 (per-event logit SD 0.4), B0 BREAK \| resolve ≈ 0.43 (logit SD 0.5);
- T15: 5 events / week, P(resolve) ≈ 0.86, B0 BREAK \| resolve ≈ 0.37 (logit SD 1.0: the position spread of #361);
- truth = B0 + structural offset 0.35 logit on BREAK \| resolve; M1 knows the offset up to an estimation error (SD 0.1);
- a weekly random effect τ ∈ {0, 0.25} logit on both heads, unknown to every model (regime clustering);
- 84 held-out weeks, then 104 live weeks; drifts start at live week 26.

**Calm world: false transitions per class.**

| | T0 τ=0 | T0 τ=0.25 | T15 τ=0 | T15 τ=0.25 |
|---|---|---|---|---|
| any FALLBACK within 52 live weeks | 3 % | 5 % | 4 % | 3 % |
| any FALLBACK within 104 live weeks | 5 % | 6 % | 4 % | 4 % |
| two or more FALLBACKs | 0 % | 0 % | 0 % | 1 % |
| e-process ever ≥ 10 / ≥ 20 / ≥ 50 (104 w, no restarts) | 4 / 1 / 0 % | 8 / 5 / 1 % | 4 / 1 / 0 % | 3 / 2 / 1 % |

**Drift detection** (share in FALLBACK within 26 / 52 weeks of onset, τ = 0.25):

| True shift from live week 26 | T0 | T15 |
|---|---|---|
| BREAK \| resolve +0.3 logit (≈ +7 pp) | 8 / 16 % | 3 / 11 % |
| BREAK \| resolve −0.3 | 8 / 18 % | 6 / 12 % |
| BREAK \| resolve +0.45 (≈ +11 pp) | 16 / 40 % | 7 / 21 % |
| BREAK \| resolve −0.45 | 29 / 51 % | 15 / 34 % |
| BREAK \| resolve +0.6 (≈ +15 pp) | 31 / 64 % | 15 / 41 % |
| BREAK \| resolve −0.6 | 45 / 77 % | 26 / 60 % |
| RESOLVE −0.6 (more NEITHER) | 14 / 32 % | 14 / 36 % |

**What this says.** At 5–7.5 events a week, no monitor can catch a 7 pp drift within a year, and a 15 pp drift takes a median of 5–8 months. Meanwhile the batched calibrator partly absorbs the drift (published probabilities stay closer to the truth than the raw model). Faster detection would need either more events (pooling with the generic race stream, FORECAST_LAYER §5) or a lower bar that would put a calm model into FALLBACK several times a year. This note keeps false FALLBACK near 5 % per class over two years and accepts slow detection; the weekly report shows the drift numbers to the mini-head long before a monitor fires.

**Challenger promotion** (share promoted at any look; covariate z ~ N(0, 1) with true effect β on BREAK \| resolve): filled from the final run, see the JSON (`chal_beta*`).

## 11. What would change our mind (before the freeze)

- F1 fits a model whose RESOLVE head has more spread than assumed: the slope then becomes identified and could be gated directly.
- F1's held-out event counts are much lower than 650 / 420: the gate and power tables are recomputed on the new counts before the freeze.
- The mini-head prefers more power for «M1 beats B0» (z = 1.28) or for drift (E ≥ 10 without the 99 % rolling rules): the tables show the price of each.

## 12. Limitations

- Synthetic worlds only; real regime clustering may be stronger than τ = 0.25.
- Overlapping 4h windows: the e-process assumes each forecast is calibrated given earlier resolved outcomes. Events of one class rarely overlap (≈ 1 a day); where they do, validity is approximate.
- The structural offset of 0.35 logit is the planning value from recorded results; the real held-out offset is unknown here by design.
