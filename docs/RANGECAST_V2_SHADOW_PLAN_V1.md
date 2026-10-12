# Rangecast V2 paired shadow — plan and promotion rule V1

**Status:** `SUPERSEDED BEFORE ANY SHADOW OUTCOME` (2026-10-12) by `RANGECAST_V2_SHADOW_PLAN_V2.md` (`RANGECAST_V2_PROMOTION_RULE_V2`): owner instruction to block a recommendation on an observed 4h result against W_L1, to report non-inferiority apart from superiority, to output a recommendation instead of a switch, and to evaluate W_L1 refitted nightly. Rule V1 was never applied: no shadow row exists. Kept as the record.
**Original status:** `RULE_FROZEN_BEFORE_ANY_SHADOW_OUTCOME` (2026-10-12).

## 1. Three kinds of evidence, kept apart

| Kind | State | Where |
|---|---|---|
| Technical readiness | Done on this branch: the frozen artifact, the adapter with statuses, parity at hourly and 5-minute anchors, the event-zone rule, tests | `research/RANGECAST_V2_SHADOW_AUDIT.md`, `RANGECAST_V2_SHADOW_PARITY.json` |
| Historical diagnostic | Done, exposed surfaces: 4h log loss −0.97 % on the folds 2021–2024 and −1.5 % on the one 2025–2026 read | `research/RANGECAST_V2_RESULT.md` |
| Prospective confirmation | Not started: this plan | the live journal |

A historical gain is not a live calibration. This plan does not make a user-facing claim; promotion is an owner decision informed by the rule.

## 2. What is compared

- **Pairs.** Each hour, V1 and V2 on the same snapshot, anchor, price and levels: the six journal distances on both sides and the 16 «ни один» pairs, at 1h, 4h and 24h. Rows exist only outside CPI / FOMC event zones, as the product's own claims.
- **Outcomes.** `TOUCH_V1` and `NEITHER_V1`, shared by both models. A row whose window has under 90 % of its minutes is left out for both models, hit or miss.
- **Per anchor.** V2 − V1 in log loss and in Brier, averaged over the anchor's distances.
- **Per week.** The mean over the week's anchors, an ISO week, every week weighted equally.

Reported every week, decided only at the look:

| Measure | Books |
|---|---|
| Paired log-loss difference with its interval | touch and «ни один», 1h, 4h, 24h |
| Paired Brier difference | same |
| Each model's calibration intercept and slope, reliability by bin | same |
| Near (≤ 0.5 %) and far (≥ 2 %) touch groups | 4h |
| Combined endpoint (Δ1h + Δ4h) / 2 | touch |
| Pairing completeness, statuses, parity faults | all |
| The six V2 books of calibration monitor V2 | as the monitor states them |

## 3. Promotion rule `RANGECAST_V2_PROMOTION_RULE_V1`

All constants are fixed now, before any shadow outcome.

- **Clock.** Week 1 is the first complete ISO week after the writer is switched on. A week counts when at least 140 of its 168 hourly anchors are usable at both 1h and 4h. Weeks that do not count are skipped, not pooled.
- **One look,** on the first 12 counted weeks. Weeks after them are reported and never change the look.
- **Primary.** For the combined weekly endpoint C, `mean(C) < 0` and `mean(C) + 1.5 · t(0.975, 11) · sd(C) / √12 < 0.001` nats. V2 must lead on the live record and must not be worse by more than 0.001 nats, about a third of the historical gain.
- **Gates, all required:**
  - No book is significantly worse: for touch and «ни один» at 1h, 4h and 24h, the lower bound with the same inflation is at most 0.
  - 4h near and far groups are not significantly worse.
  - V2 calibration at 1h and 4h: slope in [0.85, 1.15] and |intercept| ≤ 0.15.
  - No V2 book of calibration monitor V2 is suspected, confirmed, faulted or incomplete at the look, and all four 1h / 4h books are present.
  - The artifact is unchanged and there is no parity fault.
- **Harm stop,** checked weekly from week 6: the combined lower bound is above 0. The shadow stops with no promotion.
- **Outcomes:**
  - `PROMOTE`: the primary and every gate hold.
  - `NO_PROMOTION`: anything else at the look.
  - `STOP_HARM`.
  - `NOT_EVALUABLE`: faults.
  - The label `LIVE_SUPERIORITY_CONFIRMED` (inflation 2.0, upper bound below 0) is reported beside the decision. It is never a condition.
- **No extension.** A failed look is not extended. Continuing needs a new registered rule.
- **No tuning.** The artifact is frozen for the whole shadow. A refit, a feature change or a new threshold is a new version with a new registration. It never feeds the running books.

## 4. Why this form

These numbers come from the development folds 2021–2024 (`research/RANGECAST_V2_SHADOW_AUDIT.json`, `planning`).

| Quantity | 1h | 4h | 24h |
|---|---|---|---|
| Mean paired difference, journal grid (nats) | −0.0027 | −0.0035 | −0.0047 |
| Weekly SD of the difference | 0.0022 | 0.0045 | 0.0109 |
| Weeks for 80 % power at that mean | 5 | 13 | 42 |

- **Why the combined endpoint.** The combined endpoint has a mean of −0.0031 and a weekly SD of 0.0031.
- **Why a non-inferiority rule.** Weekly differences are autocorrelated (lags 1, 2, 4 and 8: 0.38, 0.23, 0.22 and 0.25), because the size of the gain moves with the market regime.
  - A plain t-interval on 12 weekly means is then too narrow. With the gain removed, a single superiority look on 12 weeks still promoted in 19.8 % of windows.
  - The rule therefore uses the historical superiority record (every year 2021–2026 negative) and asks the live record to show that V2 is not worse and leads.
  - It inflates the standard error by 1.5. Applied to 100 historical 12-week windows, the primary passed in 84 %. With the series shifted so that V2 is worse by exactly the margin, it passed in 5 %.
- **One look only.** A second look at 20 weeks raised that 5 % to 13.5 %, so there is one look.
- **24h** cannot decide anything in 12 weeks, so it enters only as a harm gate.
- **The superiority label** appeared in 42 % of historical windows and in 2 % with the gain removed.

## 5. What the owner sees

- **Every week:** the report of §2 and the rule's state, `CONTINUE` before week 12. No decision is announced before the look except `STOP_HARM`.
- **At the look:** the decision, every check, the live estimate beside the historical one, and the label.
- **After a `PROMOTE`:** switching the product to V2 is a separate owner go. At that point:
  - the held-out bins are computed for V2;
  - the claim classes get a new rule version;
  - the calibration monitor starts new books;
  - the sharp-move push stays on V1's event-neutral 1h scale.
