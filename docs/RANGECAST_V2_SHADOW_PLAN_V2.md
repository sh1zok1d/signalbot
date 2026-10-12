# Rangecast V2 paired shadow — plan and promotion rule V2

**Status:** `RULE_FIXED_BEFORE_ANY_SHADOW_OUTCOME` (2026-10-12). It replaces `RANGECAST_V2_SHADOW_PLAN_V1.md`, which was never applied: no shadow row exists.
- **Code:** `beta/rangecast_paired.py` (`RANGECAST_V2_PROMOTION_RULE_V2`); tests in `tests/beta/test_rangecast_paired.py` and `tests/beta/test_rangecast_shadow_contract.py`.
- **Storage and outcomes:** the paired shadow store (`BETA_PAIRED_SHADOW_CONTRACT_V1.md`). The forecast side is `RANGECAST_V2_SHADOW_CONTRACT_V2.md`.

**Changes from V1** (owner instruction of 2026-10-12):
- the observed 4h result must not be against W_L1;
- the output is a recommendation to the owner, never a switch;
- non-inferiority and superiority are reported as different evidence;
- the evaluated procedure is W_L1 refitted nightly, not one frozen artifact.

## 1. Three kinds of evidence, kept apart

| Kind | State | Where |
|---|---|---|
| Technical readiness | Done on this branch: identity, binders, nightly snapshots, integration with the store, parity at hourly and 5-minute anchors, the event-zone rule, tests | `RANGECAST_V2_SHADOW_CONTRACT_V2.md`, `research/RANGECAST_V2_SHADOW_AUDIT.md` |
| Historical diagnostic | Done, exposed surfaces: 4h log loss −0.97 % on the folds 2021–2024 and −1.5 % on the one 2025–2026 read | `research/RANGECAST_V2_RESULT.md` |
| Prospective confirmation | Not started: this plan | the paired shadow store |

A historical gain is not a live calibration. This plan makes no user-facing claim.

## 2. What is compared

- **Anchors.** Each hour, V1 and W_L1 on the same anchors of the store, on the same snapshot and bar. `rangecast_shadow.paired_forecast` provides the record; the store's `execute_hour` stores it:
  - the six journal distances on both sides and the 16 «ни один» pairs;
  - at 1h, 4h and 24h;
  - outside CPI / FOMC event zones;
  - a horizon either model cannot answer is withheld for both.
- **Outcomes.** One outcome per anchor from `beta.claims.evaluate` (`TOUCH_V1` / `NEITHER_V1`), shared by both models. An anchor whose window has under 90 % of its minutes is left out for both.
- **Pairing.** `rangecast_paired.rows_from_ledger` pairs the store's joined rows by anchor. It reports unpaired anchors, the spec digests seen and the W_L1 snapshot ids.
- **Per anchor group** (one issue slot and horizon): V2 − V1 in log loss and in Brier, averaged over its distances or pairs.
- **Per week:** the mean over the week's groups, in an ISO week, every week weighted equally.

Reported every week, decided only at the look:

| Measure | Books |
|---|---|
| Paired log-loss and Brier differences with their intervals | touch and «ни один», 1h, 4h, 24h |
| Each model's calibration intercept and slope, reliability by bin | same |
| Near (≤ 0.5 %) and far (≥ 2 %) touch groups | 4h |
| Combined endpoint (Δ1h + Δ4h) / 2 | touch |
| Completeness: withheld horizons by status, unpaired anchors, spec digests, snapshot ids | all |
| The six W_L1 books of calibration monitor V2 | as the monitor states them |
| The store's own `paired_report` (pooled means) | same; it agrees with this evaluator (test) |

## 3. Rule `RANGECAST_V2_PROMOTION_RULE_V2`

All constants are fixed now, before any shadow outcome.

- **Clock.**
  - Week 1 is the first complete ISO week after recording is switched on.
  - A week counts when at least 140 of its 168 hourly groups are usable at both 1h and 4h. Weeks that do not count are skipped, not pooled.
- **One look,** on the first 12 counted weeks. Later weeks are reported and never change the look.
- **Primary, non-inferiority.** For the combined weekly endpoint C:
  - `mean(C) < 0`, and
  - `mean(C) + 1.5 · t(0.975, 11) · sd(C) / √12 < 0.001` nats.
- **4h gate.** For touch and «ни один» at 4h, the mean weekly difference V2 − V1 is below 0 in log loss and in Brier. An observed 4h result against W_L1 blocks the recommendation, whatever the other horizons show.
- **Gates, all required:**
  - no book is significantly worse: for touch and «ни один» at 1h, 4h and 24h, the lower bound with the same inflation is at most 0;
  - the 4h near and far groups are not significantly worse;
  - W_L1 calibration at 1h and 4h: slope in [0.85, 1.15] and |intercept| ≤ 0.15;
  - no W_L1 book of calibration monitor V2 is suspected, confirmed, faulted or incomplete at the look, and all four 1h / 4h books are present;
  - one spec digest per procedure over the look, and every W_L1 snapshot id is verifiable in the snapshot store.
- **Harm stop,** checked weekly from week 6: the combined lower bound is above 0. The shadow stops with no recommendation.
- **Outcomes:**
  - `RECOMMEND_SWITCH`: the primary, the 4h gate and every other gate hold.
  - `NO_RECOMMENDATION`: anything else at the look.
  - `STOP_HARM`.
  - `CONTINUE`: before the look.
  - `NOT_EVALUABLE`: faults, identity drift or an unverifiable snapshot.
- **Evidence label**, only with `RECOMMEND_SWITCH:`
  - `SUPERIORITY_SHOWN`: the stricter interval (inflation 2.0) lies below 0. The statement says W_L1 scored better.
  - `NON_INFERIORITY_ONLY`: otherwise. The statement says W_L1 is not worse within 0.001 nats and was observed better at 4h, and that superiority is not shown.
- **Never a switch.** The result carries `automatic_switch: false`. Switching the product to W_L1 is a separate owner decision.
- **No extension.** A failed look is not extended. Continuing needs a new registered rule.
- **No tuning on shadow results.** The specification is fixed for the whole shadow; nightly refits change only the snapshot. A change of any constant in the procedure digest is a new `spec_id`, a new stream and a new registered rule. It never feeds the running books.

## 4. How the rule behaves on history

The development folds 2021–2024 are consumed. These figures come from `research/RANGECAST_V2_PROMOTION_RULE_V2_HISTORY.json`: the journal grid, 210 weeks, 100 windows of 12 weeks, every second start.

| Part of the rule | As observed | V2 equal to V1 (every series centred at 0) | V2 worse by the margin |
|---|---|---|---|
| Primary (non-inferiority) | 84 % | 25 % | 5 % |
| 4h gate alone | 91 % | 42 % | 12 % |
| Primary and 4h gate: `RECOMMEND_SWITCH` before the other gates | 84 % | 25 % | 5 % |
| … with `SUPERIORITY_SHOWN` | 42 % | 2 % | 0 % |

**What this means for the owner:**
- **The 4h gate.** It costs nothing when the gain is as observed: every window that passed the primary also passed the gate. It stops the case the owner named, a 4h result against W_L1.
- **A `NON_INFERIORITY_ONLY` recommendation is weak evidence on its own.** With no real gain it would still appear in about a quarter of 12-week windows.
  - It says the live record is consistent with the historical gain and shows no harm.
  - It does not say W_L1 is better live.
  - It leans on the historical record: W_L1 was ahead in every year 2021–2026.
- **A `SUPERIORITY_SHOWN` recommendation** appeared in 42 % of windows with the observed gain and in 2 % with none.

Inputs, from the planning section of `research/RANGECAST_V2_SHADOW_AUDIT.json`:

| Quantity | 1h | 4h | 24h |
|---|---|---|---|
| Mean paired log-loss difference, journal grid (nats) | −0.0027 | −0.0035 | −0.0047 |
| Weekly SD | 0.0022 | 0.0045 | 0.0109 |
| «Ни один» mean / weekly SD | −0.0057 / 0.0055 | −0.0100 / 0.0121 | −0.0154 / 0.0295 |

Why the rule has this form:
- **The standard error.** Weekly differences are autocorrelated: 0.38, 0.23, 0.22 and 0.25 at lags 1, 2, 4 and 8. A plain t-interval is too narrow, so the standard error is inflated by 1.5.
- **One look.** A second look at 20 weeks raised the 5 % to 13.5 %.
- **24h.** It cannot decide anything in 12 weeks, so it enters only as a harm gate.

## 5. What the owner sees

- **Every week:** the report of §2 and the rule's state. `CONTINUE` before week 12; nothing is announced before the look except `STOP_HARM`.
- **At the look:**
  - the decision and its evidence label;
  - every check;
  - the live estimate beside the historical one;
  - one plain statement saying which evidence it is.
- **If the owner decides to switch:**
  - the held-out bins are computed for W_L1;
  - user wording, `touch_live_cal` and the claim classes get new rule versions;
  - calibration monitor V2 starts new production books;
  - the sharp-move push stays on V1's event-neutral 1h scale.
