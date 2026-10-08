# Level race — calibration, gates, monitors and states (design V1, the [F3] part of F1's note)

**Status:** `PROPOSAL_FOR_MINI_HEAD / SYNTHETIC_ONLY / BEFORE_ANY_OUTCOME` (ОПГ-2 track F3, 2026-10-08). For freezing with `LEVEL_RACE_FORECAST_V1_DESIGN.md` before the held-out read.

**What this study used:**
- No market bar, no level event and no real outcome was read.
- Every number below is a design choice checked on synthetic worlds (§10).
- **Dev-informed inputs, disclosed:** the synthetic worlds and two choices (s_level, the slope prior) use F1's descriptive development numbers, relayed by the mini-head:
  - the level − generic intercepts, R +0.92 and B +0.33;
  - the M1 head-B slope, 0.78;
  - the M1 gains, +0.028 nats against B0 and +0.069 against G1@event.

**Authority:**
- `LEVEL_RACE_FORECAST_V1_DESIGN.md` §7, §8a, §11b (F1): the objects, the gate names G0–G3 and D0–D3, and the cases A / B;
- `FORECAST_LAYER_DECISION_V1.md` §5–§7, §6a, §6b;
- `EVIDENCE_AND_CLAIMS_DECISION_V1.md` §4–§5.

**Code:**
- `beta/level_race_calibration.py`: pure, no database; the constants in its header are the numbers below. It is the only calibrator: the held-out prequential pass and live both import it (mini-head, 2026-10-08).
- `scripts/research/level_race_calibration_sim.py`: the study.
- `scripts/research/level_race_weekly_report.py`: the weekly report.
- Results: `LEVEL_RACE_CALIBRATION_MONITORING_V1_SIM.json` (200 replications per scenario).

## 0. Claims this note guarantees (red-team list)

1. **No look-ahead in calibration.** The calibrator used at time t is fitted only on outcomes resolved strictly before its batch cutoff ≤ t (`fit_calibrator(…, cutoff_ms)`; test `test_calibrator_uses_only_outcomes_resolved_before_cutoff` flips every later outcome and gets the same version).
2. **Versioned and deterministic.** Each calibrator version is a digest of its class set, cutoff, prior and parameters; the same inputs give the same version.
3. **No real outcome was read** for any number here; all are synthetic (§10).
4. **Calm-world false exits.** With the proposed numbers, a class that starts in an L3 state leaves it falsely (to FALLBACK or HIST) in ≤ 6 % by 52 weeks and ≤ 10 % by 104 weeks at T0 (T15 6 % / 11 %), under weekly regime clustering τ = 0.25 (§10.1).
5. **D1 alone** (E > 30 per outcome, on published probabilities): ≤ 10 % lifetime false alarm per epoch under conditional calibration (Ville, three outcomes × 1/30); ≈ 4 % (T15 5 %) by 52 weeks in the τ = 0.25 world.
6. **Slope correction (R3).** With the hierarchical slope, a level head-B slope of 0.78 is learned from the held-out stage. The end-of-held-out level slope averages 0.80 (truth 0.78). With a tied slope and a generic slope of 1, the published level slope stays at about 0.70 (T0) / 0.76 (T15) (§3.3).
7. **Case B ⇒ HIST in practice.** On the dev numbers, the GENERIC-intercept fallback passes G2 on level events in 0 % of replications, so a class in case B never leaves HIST (§7.3).
8. **HIST_ONLY mode** gives only HIST or OFF, whatever the monitors say (`test_mode_hist_only_is_hist_or_off`).
9. **OFF at once** on any D0 fault, and back to the previous state when healthy.
10. **FALLBACK is never shown for a class whose fallback model fails G2:** on the held-out read, and on the last 150 live records once there are that many.
11. **Case B never enters an L3 state** (rule, not only a simulation result). Its only model state is FALLBACK, entered while the fallback passes G2, otherwise HIST. The L3 templates would otherwise print a number next to itself as «обычно» (§6b). Tested in `test_case_b_never_enters_l3`.
12. **One rule for "which calibrator applies at t":** `calibrator_at(t_ms, versions)` returns the version with the latest cutoff ≤ t. The held-out pass (F1) and the live loop (F2) both call it. A test checks that t at a cutoff and t one ms before select different versions.
13. **Generic-stream alarm:** it sends every L3_* and FALLBACK level class to HIST, never to FALLBACK, and counts as a drift exit. Return needs the generic alarm cleared first (≥ 50 windows, every e < 1), then the class's own return rule. Tests: `test_generic_alarm_sends_l3_and_fallback_to_hist_and_counts_as_a_drift_exit`, `test_generic_return_needs_the_alarm_cleared_and_the_class_recovered`.
14. **No model number without its accuracy line:** `display_contract` raises if L3_HISTORY_BACKED, L3_LIVE or FALLBACK lacks its held-out, live or generic line. Test: `test_no_model_number_without_its_accuracy_line`.

All numbers: 200 replications per scenario, §10.

## 1. Object and heads

As F1 §2.3: head R = P(a barrier within 4h) = 1 − P(NEITHER); head B = P(BREAK | resolved) (UP | resolved on the generic stream). P(BREAK) = R·B, P(REJECT) = R·(1 − B), P(NEITHER) = 1 − R. Gates and drift run per outcome (one against the rest) where F1 says so (G2, D1, D2) and per head where F1 says so (G3, the calibrator).

**What feeds the level rows of the calibrator** (mini-head, 2026-10-08):
- case A: the M1 raw output;
- case B: the fallback raw output (G1@event);
- the generic rows: the G1 raw output on the generic stream.

## 2. Held-out gates (`L3_HISTORY_BACKED`)

Scored on the **prequential published** probabilities of the held-out read: weekly then 4-weekly batches, each from the identity prior, each fitted only on held-out outcomes resolved before its cutoff (F1 §5).

| Gate | Rule | Value | Change from F1 planning |
|---|---|---|---|
| G0 | scored held-out events per class | ≥ 200 | — |
| G1 | upper end of the week-clustered 95 % interval of LL_published − LL_B0 | ≤ **+0.02 nats** | was +0.01 |
| G2 | per outcome: \|CITL\| ≤ 5 pp and its 95 % interval inside ±10 pp (iid floor on the SE) | 5 / 10 pp | iid floor added |
| G3 | per head: the slope's 95 % interval overlaps [0.8, 1.25] | — | — |

**G1 is a non-inferiority gate:** the published model may be up to 0.02 nats worse than raw B0 and still pass. Superiority over B0 (and over G1@event) comes only from F1 §11b's case-A rule, applied to raw outputs.

**Why G1 is +0.02.**
- The prequential calibrator costs about 0.007 nats on a calibrated champion (early batches learn from few events).
- At ≈ 630 / 420 events, the week-clustered interval of the log-loss gap is about ±0.015.
- At +0.01, a calibrated champion that truly beats B0 failed G1 in about 45 % of synthetic replications.
- At +0.02 the champion's own G0–G3 pass rate is 90 % at T0 and 67 % (s_level = 1.0; 96 % / 84 % at s_level = 0.5, §10.7) at T15 (§10.4).

**iid floor.** Every week-clustered interval in this note uses a standard error no smaller than the independent-events one. With 13–20 weekly clusters the cluster-robust estimate alone was sometimes far too small; in the first synthetic pass that alone produced 25 % false FALLBACKs.

## 3. Calibrator

### 3.1 Form

Per head, logit p′ = a_class + b_(GENERIC or LEVEL)·logit p. θ = (a_GENERIC, a_LEVEL_T0, a_LEVEL_T15, b_GENERIC, b_LEVEL). MAP with a Laplace covariance, Newton, deterministic. Published probabilities are rebuilt from the two calibrated heads. The fallback model and case B use the `GENERIC` intercept and the generic slope (F1 §7, §11b).

### 3.2 Prior (held-out prequential start)

- a_G ~ N(0, 0.5²);
- b_G ~ N(1, 0.25²);
- **a_level − a_G ~ N(0, s_level²)**, independently per level class.

**s_level by case** (`PRIOR_S_LEVEL_BY_CASE`, `prior_for_cases`): **0.5 in case A, 1.0 in case B.** The case is known before the prequential pass, because F1 §11b decides it on raw outputs.

**Why by case.**
- **Case A:** the level rows feed M1 raw, and M1 already carries the level terms. The level intercept is only a residual correction on top of them; M1's dev CITL is within ±2 pp, so a tight prior is appropriate.
- **Case B:** the level rows feed G1@event raw, which has no level term. The level intercept would have to absorb the whole level offset, about R +0.92 and B +0.33 on the dev numbers, so a tight prior would pull it toward generic. In case B these intercepts are shadow only: never published, estimated for a later version.

**Fixing rule.** The case is fixed by the §11b raw-output rule before the prequential pass. This is the last prior change: after the freeze nothing in the prior moves (architect, 2026-10-08).

**Search exposure (synthetic, disclosed).**
- Values tried: s_level ∈ {0.5, 1.0, 1.5} (§10.7).
- Champion's held-out G0–G3 pass rate, T0 / T15: 96 % / 84 % at 0.5, 90 % / 62 % at 1.0, 85 % / 56 % at 1.5.
- End-of-held-out level intercepts with G1@event raw against the true +1.07 / +0.74: +0.86 / +0.56 at 0.5, +1.01 / +0.67 at 1.0.
- An earlier proposal was a single value of 1.0; it was superseded by this by-case rule.

### 3.3 Slope: hierarchical, not fully shared

**b_L − b_G ~ N(0, 0.25²) (`PRIOR_S_SLOPE_LEVEL = 0.25`)**: one level slope shared by both level classes, tied loosely to the generic slope.

The reason is R3, from the first synthetic grid with a fully shared slope:
- when the level head-B slope is 0.78 and the generic slope is 1, the generic rows (≈ 40 independent windows a week, against 12.5 level events) hold the shared slope near 1;
- the published held-out level slope then stays at 0.70 (T0) and 0.75 (T15), so the level over-confidence is not corrected;
- with the hierarchical slope it is (§10.6).

When the slope really is shared, the hierarchical prior costs little: §10.6, r3_shared vs r3_shared_tied. `PRIOR_S_SLOPE_LEVEL = 0` restores the fully shared slope as one setting.

### 3.4 Live prior and batches

- **Live prior:** the held-out posterior mean. Its precision is reset to 150 events of each class's held-out design (150 × the mean per-event Fisher information of that class at the held-out mean), plus 0.1 % of the identity prior's precision. FORECAST_LAYER §5 sets the range at 100–200.
- **Batches:** every week for 12 weeks after a stage starts, then every 4 weeks.
- **No isotonic map** below 300 events; V1 has none.

### 3.5 Generic rows and dependence

The generic stream has 4 hourly anchors per independent 4h window and 4 price pairs per anchor. Each generic row therefore enters the likelihood with weight **1/16** (`GENERIC_ROW_WEIGHT`), so the generic class counts its information in independent windows, about 40 a week. F1 §8a states the same non-overlapping reading for its report. The synthetic study simulates independent generic windows at weight 1, which is equivalent.

## 4. Live floor (`L3_LIVE`)

At least **150** resolved live forecasts in the class, and G2 and G3 on the whole live record of the version (F1 §7). In the calm world, L3_LIVE is reached at about week 33 (T0) and 46 (T15) after the switch to MODEL.

**L3_LIVE is not reached inside the beta.** The 30-day test sees about 30 (T0) and 20 (T15) resolved live forecasts per class, far below the floor of 150. During the beta a passing class shows `L3_HISTORY_BACKED` with «live: копится (N = …)».

## 5. Drift monitors

All run at batch cutoffs on the resolved live records of the class (published or not), each from the start of the current epoch where stated. An epoch starts at the switch to MODEL and at every exit from or return to an L3 state.

| Monitor | Rule | Value | Change from F1 planning |
|---|---|---|---|
| D0 | data fault, stale bars (> 10 min at issue), parity break → `OFF` at once | — | — |
| D1 | per outcome, betting e-process Π(1 + λ(y − p)), λ ∈ {±0.25, ±0.5}, mean over λ, from the epoch start; trigger when any outcome's E > threshold | **E > 30** | was 10 |
| D2 | per outcome over the last **150** resolved: \|CITL\| > 10 pp and its **99.7 %** interval (iid floor) excludes 0 | 150 / 3.0 | was 100 / 95 % |
| D3 | case A: LL_published − LL_fallback over the last 150 with a 99.7 % interval above 0, ≥ 8 weeks | 150 / 3.0 | was 100 / 95 % |
| Input drift | median σ, mean B0 BREAK probability, events per week of the last 8 weeks against the held-out 8-week blocks' 2.5–97.5 % range | reported, no state change | — |

### 5.1 D1 threshold 30

The three outcome e-processes share the 0.1 Ville budget (3 × 1/30). The bound assumes each forecast is calibrated given the past known at its issue time. Two touches of one class less than 4h apart have overlapping windows, and the earlier outcome is not yet known at the later issue, so the bound is then approximate. The τ = 0.25 simulation does not model such overlaps; they are rare (about one a day across both classes). In the τ = 0.25 calm world, D1 at E > 30 fires on 4 % (T15 5 %) of L3 starts by 52 weeks at T0. At F1's E > 10 it fires on 14 %.

**D1 on a frozen reference map (p_ref) was tested twice and rejected** as a state rule:
- p_ref is the raw model under the end-of-held-out calibrator, held fixed.
- First design: false FALLBACK 34 % against 9 % over 104 calm weeks.
- In this design (§10.2): 31 % against 4 % (T15 5 %) for p_pub by 52 weeks.
- The cause: p_ref carries the held-out fit's own estimation error as a persistent bias, and an e-process eventually detects any persistent bias.

The variant whose null allows that error (`d1_paths(…, margin=…)`, margin = half the 95 % interval of the held-out CITL per outcome) brings p_ref down to 7 %, but it detects real drift more slowly (§10.2). It stays a reported diagnostic in the weekly report, not a state rule (mini-head, 2026-10-08).

### 5.2 D2 and D3 window and interval

- At F1's 100 events and 95 %, with 3 outcomes and about 35 looks, D2 alone sent 55 % of calm L3 starts to an exit by 52 weeks (τ = 0.25).
- At 150 events and 99.7 % (iid floor) it is 4 %.
- D3 uses the same window and interval. It never fired in the calm world, because the champion beats G1@event by a wide margin there.

### 5.3 Return

From FALLBACK, or from a HIST entered by drift, back to L3, all of:
- ≥ **50** resolved records since the exit;
- every outcome's epoch e-value **< 1** (F1 planning: ≤ 10, which almost any calm epoch satisfies, so it gave no hysteresis);
- every outcome's epoch |CITL| ≤ 10 pp;
- no drift reason at that batch;
- the version's held-out gate passed.

The target is L3_LIVE if §4 holds on the whole live record, else L3_HISTORY_BACKED.

### 5.4 Second exit is final

The second drift exit of a model version is final for it. "Final" means the class stays in HIST (or FALLBACK while that is available and passes G2) until a new model version enters. A new version enters as a challenger with its own record (FORECAST_LAYER §7). In the calm world, a second exit within 104 weeks happens in 0 % (T0) and 0 % (T15) of replications.

### 5.5 Limitation: drift power at 5–7.5 events a week

**In short:** a level-specific drift of about ±10 pp is detected in about a year, not weeks; inside the beta the accuracy line next to the number is the guard. A fall of the calibration slope to about 0.7 is practically not detected by the monitors; the weekly report's slope line is its only check.


No monitor catches a 7 pp drift within a year at these event rates. An 11–15 pp drift takes months (§10.3). The batched calibrator meanwhile partly absorbs a drift, so the published probabilities stay closer to the truth than the raw model. The mitigation is the generic stream, about 40 independent windows a week (FORECAST_LAYER §5 pooling):
- the generic intercept and slope track a market-wide drift within weeks;
- the level classes only have to show that their offset has not moved.

The weekly report puts the drift statistics in front of the mini-head long before a monitor fires.

**Detection delay** (required before the freeze; flagged to the architect on 2026-10-08):
- Median delay from onset to the first exit from L3, in weeks and in events since onset.
- Counted among runs in L3 at onset; runs with no exit are censored at the 78-week horizon.
- τ = 0.25, 200 replications.
- Chosen values: D1 E > 30, D2/D3 over 150 at 99.7 %. Planning values: D1 E > 10, D2/D3 over 100 at 95 %, return E ≤ 10.

| Drift (from live week 26) | chosen T0 | chosen T15 | planning T0 | planning T15 |
|---|---|---|---|---|
| head B +0.4 logit (≈ +10 pp) | > 78 w (47 % by 78 w; false exit before onset 3 %) | > 78 w (30 % by 78 w; false exit before onset 0 %) | 18 w / 125 ev (91 % by 78 w; false exit before onset 32 %) | 34 w / 180 ev (73 % by 78 w; false exit before onset 11 %) |
| head B −0.4 logit (≈ −10 pp) | 66 w / 479 ev (58 % by 78 w; false exit before onset 7 %) | > 78 w (43 % by 78 w; false exit before onset 3 %) | 14 w / 107 ev (96 % by 78 w; false exit before onset 29 %) | 22 w / 106 ev (92 % by 78 w; false exit before onset 16 %) |
| head B slope falls to 0.7 | > 78 w (9 % by 78 w; false exit before onset 1 %) | > 78 w (5 % by 78 w; false exit before onset 2 %) | 54 w / 404 ev (66 % by 78 w; false exit before onset 30 %) | 60 w / 295 ev (60 % by 78 w; false exit before onset 22 %) |

**What this says.**
- At the chosen values, a ±10 pp shift is detected within the 78 weeks in about half the runs at T0 and a third at T15; a slope falling to 0.7 almost never.
- The planning values detect ±10 pp in a median of 14–34 weeks. But they leave L3 falsely before any drift in 29–32 % of runs within 26 weeks, and in 42–56 % within 52 weeks (§10.1).
- Neither set reaches about 8 weeks, which is 40–60 level events, where a calibration intercept has a standard error of about 7 pp.
- Faster detection needs more events per class (pooling T0 and T15, or the generic stream), not another threshold.

### 5.6 Generic-stream drift monitor (architect, 2026-10-08)

**Rows.** One independent row per 4h window: the (1, 1) price pair at anchors on the 4h UTC grid, about 42 a week (`generic_monitor_rows`).

**Statistic.**
- Per outcome, a change-point mixture of the D1 betting e-process (`changepoint_paths`): starts every 40 windows, weight 1/((j+1)(j+2)), starts not yet reached counted as 1. It is a test martingale, and a late drift is not buried under a long calm period.
- It runs on **p_ref**, the raw generic model under the frozen end-of-held-out generic calibrator, with the **held-out margin**: half the 95 % interval of the held-out CITL per outcome, about 1.5–2 pp.
- p_ref is right here, unlike on the level classes (§5.1). The generic held-out has about 3 500 independent windows, so its own estimation error is small and is covered by the margin.
- On published probabilities, the batched calibrator would absorb a market-wide shift within weeks.

**Frozen numbers.**
- Threshold: **E > 30** per outcome (`GEN_THRESHOLD`).
- False alarm over 52 calm weeks: **7 %** at τ = 0.25, **0.5 %** at τ = 0.
- Median delay for a ±10 pp market-wide shift on head B: **38 / 37 weeks**, about 1557 windows. On head R (±0.4 logit): 23 / 29 weeks.

**Effect.**
- An alarm sends every level class in `L3_*` or `FALLBACK` to `HIST` (`GEN_ALARM_TARGET`), never FALLBACK, because FALLBACK is the generic model itself.
- It counts as a drift exit, and the second exit is final.
- Return, first on the generic stream: ≥ 50 windows since the alarm and every outcome's e-process from the alarm below 1. Then on the class, by its own §5.3 rule.
- A level-stream drift keeps its own target (`LEVEL_DRIFT_TARGET = FALLBACK` while the fallback passes G2, else HIST). The interim constant is kept for that path only.

**Why the generic stream is not fast either.**
- A ±10 pp shift in the head-B conditional is about ±7.5 pp per outcome, one against the rest.
- After the 2 pp margin, that is about 0.007 nats of evidence per window.
- Weekly regime noise (τ = 0.25 ≈ ±6 pp per week) has to be told apart from a sustained shift.

**Tested and rejected: a rolling rule.** Over the last 6 weeks: per outcome |CITL| > margin + 5 pp with a 99.7 % interval beyond the margin. It shortens the delay but more than doubles the calm-world alarms:

| | e-process only (frozen) | + rolling 6-week rule (tested, rejected) |
|---|---|---|
| calm, alarm within 52 w, τ = 0.25 | 7.0 % | 16.5 % |
| calm, alarm within 52 w, τ = 0 | 0.5 % | 6.0 % |
| market-wide head B +0.4 logit (≈ +10 pp): median delay | 38 w / 1557 windows (6 % within 8 w) | 21 w / 823 windows (22 % within 8 w) |
| head B −0.4: median delay | 37 w / 1474 windows (4 % within 8 w) | 18 w / 714 windows (22 % within 8 w) |
| head R −0.4 (more NEITHER): median delay | 23 w / 934 windows (7 % within 8 w) | 15 w / 590 windows (25 % within 8 w) |
| head R +0.4: median delay | 29 w / 1163 windows (3 % within 8 w) | 17 w / 675 windows (22 % within 8 w) |

## 6. Challengers

Promotion is looked at only when the challenger has 150, 300, 450 and 600 paired resolved live events. At a look it is promoted when the week-clustered 95 % interval of its log-loss gain over the published champion lies above 0 and it passes G2 and G3 on the paired record. It is retired at 600. At most two run at once.

**C1 has no historical held-out** (F1 §8):
- its record starts at Day 0 in shadow;
- its calibrator starts from the champion's live prior.

At about 5 T15 events a week, the 450 look comes at about week 90, and the 600 look is not reached within two years. The synthetic power is in §10.8.

## 7. States

### 7.1 Inputs

`Setup` is fixed per class and model version after the held-out read, plus the mode setting:
- `mode` (HIST_ONLY / MODEL);
- `case` (A / B, by F1 §11b's publication rule);
- `holdout_passed` (G0–G3 of the published model);
- `fallback_g2_holdout` (the fallback model passes G2 on this class's held-out events).

`next_state(prev, setup, health, mon, mon_fb, now)` is pure. `mon` monitors the published model of the case; `mon_fb` monitors the fallback model on the class (case A only).

### 7.2 Transitions

| From | To | Rule |
|---|---|---|
| any | `OFF` | a D0 fault, at once (any call) |
| `OFF` | previous | all health checks pass |
| any (HIST_ONLY) | `HIST` | the mode is HIST_ONLY (FORECAST_LAYER §6a), whatever the monitors say |
| switch to MODEL | `L3_HISTORY_BACKED` | case A and the held-out gate passed |
| switch to MODEL | `FALLBACK` | otherwise, if the fallback passes G2 on the held-out (case B: always this or HIST) |
| switch to MODEL | `HIST` | otherwise; terminal for the version |
| `L3_HISTORY_BACKED` | `L3_LIVE` | ≥ 150 resolved live and G2 + G3 on the live record |
| `L3_*` | `FALLBACK` | D1 / D2 / D3, case A, the fallback passes G2 (held-out, and the last 150 live once there are 150) |
| `L3_*` | `HIST` | D1 / D2 / D3 otherwise (always in case B) |
| `FALLBACK` | `HIST` | D1 / D2 on the fallback model, or it stops passing G2 |
| `L3_*` / `FALLBACK` | `HIST` | generic-stream alarm (§5.6), at once; a drift exit |
| generic-drift `HIST` | as below | only after the generic alarm has cleared (≥ 50 generic windows since the alarm, every e < 1), then the class's own return rule |
| `FALLBACK` / drift-`HIST` | `L3_*` | case A: the return rule of §5.3 (not after the second exit) |
| drift-`HIST` | `FALLBACK` | case B: the return rule of §5.3 on the fallback model, which must still pass G2 |

### 7.3 Case B ⇒ HIST in practice

The rule (mini-head review, 2026-10-08): case B never enters an L3 state; its only model state is FALLBACK. The consequence below was accepted by the architect on 2026-10-08 as following from §6b.
- In case B the published model is the fallback model: G1@event with the GENERIC intercept and slope. It carries no level offset.
- On the dev numbers it misses the level offset by R +0.92 and B +0.33, and on synthetic level events it passes G2 in 0 % of replications.
- So a class in case B fails the held-out gate and stays in HIST.
- Case A happens in 52 % (T0) and 46 % (T15) of synthetic replications in the base world, and in 70 % / 63 % at the dev-observed gains (§10.5).
- The model states will therefore show at a landmark only where the champion beats both B0 and G1@event on the held-out read.

## 8. Weekly report

`scripts/research/level_race_weekly_report.py` (journal export in JSON lines). Per class, raw and published separately, in the order of F1 §6:
- log-loss skill and week-clustered paired gain against B0, G1@event (`p_g1`), the fallback model (`p_fb`) and B1;
- intercept (pp) and slope per head;
- 5-bin reliability, Brier with its decomposition, sharpness, AUC and ECE (descriptive) per outcome;
- challengers paired against the champion, with their look verdicts.

`--cut <ISO time>` splits every class at dated layer events (FORECAST_LAYER §6a) and reports each segment separately. `split_by_events` gives the monitors the same cut.

## 9. Interface for F2

`display_contract(state_record, setup, calibrator_version)` → `{mode, case, state, since_ms, reason, template, push_template, probabilities, calibrator_version, accuracy_line}`.
- `template` / `push_template` are F1 §9 ids: `LR_L3H_V1` / `LR_PUSH_L3H_V1`, `LR_L3L_V1` / `LR_PUSH_L3L_V1`, `LR_FB_V1` / `LR_PUSH_FB_V1`, `LR_OFF_V1` / `LR_PUSH_OFF_V1`; `HIST` keeps F1 §0.
- `probabilities`:
  - `CHAMPION`: an L3 state (case A only), calibrated with its class intercept;
  - `FALLBACK`: the FALLBACK state (either case); G1@event with the GENERIC intercept;
  - `None` otherwise.
- `accuracy_line`: `holdout` / `live` / `generic` / none.

F2 owns texts and prices. The stored state is proposed as one runtime-health component per class, written by the batch job (as `touch_live_cal` in `beta/claims.py`). That wiring is ОПГ-1's file and is not touched here.

## 10. Synthetic study

**Worlds:**
- **Event rates:** generic 40 independent 4h windows a week; T0 7.5 and T15 5 level events a week.
- **Weeks:** 84 held-out weeks, then 104 live weeks.
- **Weekly regime:** a random effect τ ∈ {0, 0.25} logit on every class and head, unknown to every model.
- **Truth at a level:** G1@event plus the dev level offsets (R +1.07 / +0.74, B +0.33 / +0.32).
- **M1:** knows the offsets up to an estimation error (SD 0.1 logit).
- **Raw B0:** misses part of the offset. The base world gives smaller M1-vs-B0 gains than dev; `ho_dev_gains` matches dev (§10.5).
- **Drifts:** from live week 26, on the level truth only.
- **Priors in the grid:** the hierarchical slope (s = 0.25) and s_level = 1.0 for both level classes in every scenario except `ho_s_level*` and the `*_tied` ones. The by-case s_level of §3.2 came after this grid; its case-A effect is the `ho_s_level0.5` row of §10.7.

### 10.1 Calm world, false exits from L3 (share of replications that started in L3)

| Rule set | world | T0 52 w | T0 104 w | T15 52 w | T15 104 w | 2nd exit T0 / T15 | D1 / D2 by 52 w (T0) |
|---|---|---|---|---|---|---|---|
| proposed | τ = 0.25 | 6 % | 10 % | 6 % | 11 % | 0 % / 0 % | 4 % / 4 % |
| proposed | τ = 0 | 4 % | 5 % | 2 % | 10 % | 0 % / 0 % | 3 % / 2 % |
| F1 planning (D1 E>10, D2 100/95 %, G1 0.01, return E≤10) | τ = 0.25 | 56 % | 78 % | 42 % | 70 % | 14 % / 6 % | 14 % / 55 % |
| F1 planning (D1 E>10, D2 100/95 %, G1 0.01, return E≤10) | τ = 0 | 44 % | 75 % | 42 % | 55 % | 16 % / 4 % | 9 % / 43 % |
| proposed, tied slope (first grid) | τ = 0.25 | 7 % | 10 % | 6 % | 12 % | 0 % / 0 % | 5 % / 4 % |
| proposed, tied slope (first grid) | τ = 0 | 4 % | 5 % | 2 % | 10 % | 0 % / 0 % | 4 % / 2 % |

### 10.2 D1 on the frozen reference map (calm world τ = 0.25, share of L3 replications with a trigger by 52 w)

| Rule | T0 | T15 |
|---|---|---|
| D1 on p_pub (E > 30) | 4 % | 5 % |
| D1 on p_ref (E > 30) | 31 % | 19 % |
| D1 on p_ref with the held-out margin (E > 30) | 7 % | 0 % |
| D1 on p_pub (E > 10, planning) | 14 % | 10 % |
| D1 on p_ref (E > 10, planning) | 45 % | 40 % |
| D1 on p_ref with the held-out margin (E > 10, planning) | 9 % | 2 % |

Detection after onset within 26 w (D1 variants, τ = 0.25):

| Drift | D1 p_pub T0 | D1 p_ref T0 | D1 p_ref+margin T0 | D1 p_pub T15 | D1 p_ref+margin T15 |
|---|---|---|---|---|---|
| drift_b+0.45 | 3 % | 13 % | 3 % | 0 % | 0 % |
| drift_b-0.45 | 8 % | 28 % | 7 % | 8 % | 3 % |
| drift_b+0.6 | 12 % | 28 % | 7 % | 4 % | 3 % |
| drift_b-0.6 | 24 % | 42 % | 21 % | 17 % | 4 % |
| drift_r-0.6 | 11 % | 30 % | 9 % | 21 % | 10 % |

### 10.3 Drift detection (exit from L3 within 26 / 52 weeks of onset at live week 26; τ = 0.25)

| True shift | T0 | T15 |
|---|---|---|
| head B +0.3 logit (≈ +7 pp) | 14 % / 22 % | 1 % / 8 % |
| head B −0.3 | 14 % / 27 % | 16 % / 25 % |
| head B +0.45 (≈ +11 pp) | 18 % / 34 % | 5 % / 19 % |
| head B −0.45 | 29 % / 57 % | 16 % / 31 % |
| head B +0.6 (≈ +15 pp) | 37 % / 70 % | 21 % / 44 % |
| head B −0.6 | 51 % / 74 % | 29 % / 57 % |
| head R −0.6 (more NEITHER) | 20 % / 46 % | 24 % / 57 % |
| head R +0.6 | 6 % / 10 % | 4 % / 12 % |

### 10.4 Held-out stage

| World | case A T0 / T15 | gate of the published model T0 / T15 | champion's own G0–G3 T0 / T15 | fallback G2 T0 / T15 |
|---|---|---|---|---|
| calibrated M1, τ = 0.25 | 52 % / 46 % | 50 % / 42 % | 90 % / 67 % | 0 % / 0 % |
| calibrated M1, τ = 0 | 58 % / 46 % | 57 % / 43 % | 96 % / 70 % | 0 % / 0 % |
| no level effect in truth | 0 % / 0 % | 96 % / 88 % | 94 % / 48 % | 97 % / 90 % |
| M1 head B +0.2 logit | 22 % / 22 % | 22 % / 19 % | 87 % / 56 % | 0 % / 0 % |
| M1 head B +0.4 | 10 % / 7 % | 10 % / 7 % | 92 % / 63 % | 0 % / 0 % |
| M1 head B +0.6 | 0 % / 3 % | 0 % / 3 % | 91 % / 81 % | 0 % / 0 % |
| level head B slope 0.78, generic 1 | 50 % / 46 % | 47 % / 38 % | 90 % / 72 % | 0 % / 0 % |
| head B slope 0.78 everywhere | 52 % / 45 % | 50 % / 42 % | 90 % / 77 % | 0 % / 0 % |

### 10.5 Power of the §11b publication rule at the dev-observed gains (raw, held-out, per landmark)

| World | gain vs B0 T0 / T15 (nats) | beats B0 | gain vs G1@event | beats G1@event | case A |
|---|---|---|---|---|---|
| ho_dev_gains | 0.027 / 0.030 | 70 % / 64 % | 0.080 / 0.045 | 98 % / 82 % | 70 % / 63 % |
| ho_dev_gains_tau0 | 0.026 / 0.031 | 74 % / 70 % | 0.081 / 0.047 | 100 % / 84 % | 74 % / 70 % |
| null | 0.014 / 0.016 | 52 % / 46 % | 0.078 / 0.045 | 100 % / 84 % | 52 % / 46 % |

### 10.6 Slope (R3): held-out fit of head B and the published held-out slope

| World | slope prior | fitted b_G / b_L (end of held-out) | published held-out slope T0 / T15 | champion G3 T0 / T15 |
|---|---|---|---|---|
| level 0.78, generic 1 | hierarchical s = 0.25 | 0.98 / 0.80 | 0.76 / 0.83 | 96 % / 99 % |
| level 0.78, generic 1 | tied | 0.95 / 0.95 | 0.70 / 0.76 | 88 % / 94 % |
| 0.78 everywhere | hierarchical s = 0.25 | 0.77 / 0.77 | 0.81 / 0.88 | 98 % / 98 % |
| 0.78 everywhere | tied | 0.77 / 0.77 | 0.82 / 0.89 | 98 % / 98 % |
| 1 everywhere | hierarchical s = 0.25 | 0.98 / 0.99 | 0.85 / 0.94 | 99 % / 99 % |

### 10.7 s_level (end-of-held-out level intercepts on head R; truth +1.07 / +0.74 when level rows feed G1@event raw)

| s_level | level rows = M1 raw: a_T0 − a_G / a_T15 − a_G | champion gate T0 / T15 | level rows = G1@event raw: a_T0 − a_G / a_T15 − a_G |
|---|---|---|---|
| 0.5 | +0.01 / +0.03 | 96 % / 84 % | +0.86 / +0.56 |
| 1.0 | +0.00 / +0.02 | 90 % / 62 % | +1.01 / +0.67 |
| 1.5 | -0.03 / -0.01 | 85 % / 56 % | +1.04 / +0.72 |

### 10.8 Challenger promotion (C1-like covariate on head B at T15; looks at 150 / 300 / 450 paired; 600 not reached in 104 w)

| True effect β | promoted at any look | by look 150 / 300 / 450 |
|---|---|---|
| 0.0 | 2 % | 0 % / 0 % / 1 % |
| 0.2 | 20 % | 2 % / 16 % / 18 % |
| 0.35 | 32 % | 6 % / 22 % / 29 % |

### 10.9 Live floor

| World | reached L3_LIVE (of all reps) T0 / T15 | mean week T0 / T15 |
|---|---|---|
| null | 50 % / 40 % | 33 / 46 |
| null_tau0 | 57 % / 43 % | 31 / 45 |


## 11. Limitations

- Synthetic worlds only. Real regime clustering may be stronger than τ = 0.25.
- T0 and T15 events are simulated independently; in reality T15 is a subset of T0, which correlates their monitors.
- Overlapping 4h windows within a class are rare (about one a day); the e-process assumes each forecast is calibrated given the outcomes resolved before it.
- Detection of 7–11 pp drifts is slow (§5.5).
- The slope and s_level choices are dev-informed (disclosed above). The shared-slope assumption of F1 §8a is replaced by a hierarchical slope; `PRIOR_S_SLOPE_LEVEL = 0` restores it.
