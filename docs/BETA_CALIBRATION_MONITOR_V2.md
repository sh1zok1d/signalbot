# Calibration monitor V2

**Status:** `SHADOW / NOT_THE_LIVE_WORDING_RULE` (2026-10-12).

`docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md` remains the rule for what users read. V1 (`beta.claims.touch_wording`, health component `touch_live_cal`) is unchanged. This monitor is a pure function of an immutable claim journal. Nothing here writes production, clears a sticky flag, or refits a model.

Code: `beta/calibration_monitor.py`. Tests: `tests/beta/test_calibration_monitor.py`. Comparison: `scripts/beta/compare_calibration_monitor_v1.py`, result `docs/BETA_CALIBRATION_MONITOR_V2_COMPARISON.json`.

## What it scores

One book is a forecast **procedure**, a **family** (`touch` or `neither`), and a **horizon** (`1h`, `4h`, `24h`).

- Procedure `TOUCH_CHANCE_PROCEDURE_V1` is the claim classes scored by `TOUCH_V1` / `NEITHER_V1`. It is not a coefficient vector.
- `snapshot_id` (the statistics row that issued the probability) is stored on the book and **does not reset** the evidence. A nightly refit can change coefficients and still leave the same procedure. The old claims stay in the journal and in the replay.
- A new procedure id, or two evaluation rules inside one book, does not get pooled. Mixed rules are `TECHNICAL_FAULT`.
- Monitor version is `CALIBRATION_MONITOR_V2`. Recomputing it does not rewrite claims or outcomes.

The monitor imports no rangecast module. A later rangecast only has to emit the same observation: probability, outcome, `as_of`, horizon, family, evaluation rule, snapshot id, procedure id.

## Dependence

The time index is the UTC day of `as_of`. Inside a day, claims that share a horizon-length slot are averaged first. Slots then get equal weight. A 16-pair «ни один» grid cannot outvote a single level by raw count, and it cannot multiply an e-value.

## Channels

Each book runs four channels. A near-zero average residual is not treated as a pass.

| Channel | Statistic | What a zero LEVEL residual can still hide |
|---|---|---|
| `LEVEL` | mean of y − p | a uniform shift of the horizon |
| `TAIL_HIGH` | y − p on p ≥ 0.70 | the upper tail |
| `TAIL_LOW` | y − p on p < 0.30 | the lower tail |
| `SHAPE` | (y − p on p ≥ 0.5) minus (y − p on p < 0.5) | a slope error |

`NEITHER` is its own family. It is not inferred from the touch residuals.

## States

Thresholds were written down before the synthetic replay. None were moved after it. `variants_tried_for_thresholds = 0`. They were not fit to 6–12 October 2026. The 5 pp gate is the tolerance already in the V1 design note. The day floors are longer than V1's 5-day bootstrap.

| State | Rule |
|---|---|
| `INSUFFICIENT_DATA` | Fewer than 10 UTC days on every present channel, or no complete claims. A large gap does not override this. |
| `WITHIN_NOISE` | Enough days, and neither the sequential bar nor the day-28 look has fired. |
| `SUSPECTED_DEGRADATION` | At least 10 days, \|estimate\| > 5 pp, and the mixture e-value ≥ 2, with the e-value's direction matching the estimate. No user-text change. |
| `CONFIRMED_DIVERGENCE` | Either the day-28 checkpoint (97.5% day bootstrap interval excludes 0 and \|estimate\| > 5 pp; one look) or, from day 20, e-value ≥ 20 and \|estimate\| > 5 pp. |
| `RECOVERED` | After a confirmation, a later stretch of 20 days has \|estimate\| ≤ 5 pp and a fresh e-value on that stretch below 2. The confirmation episode stays in the result, including its archived e-value. |
| `TECHNICAL_FAULT` | Illegal probability, naive timestamp, missing rule, or two evaluation rules in one book. |
| `INCOMPLETE_DATA` | At least 10 rows and more than 20% not `COMPLETE`. No calibration verdict is issued on top of a hole. |

The mixture e-process bets λ ∈ {−0.5, −0.25, +0.25, +0.5} on the daily statistic, which is kept inside [−1, 1]. One e-value per channel. Averaging wealth across λ is the mixture. It is anytime-valid for a single channel when each day's statistic has conditional mean zero. The day-28 look is an extra 2.5% test, used once per operating window. Across families and horizons the union bound is wider; the comparison below is the operating check, not a claim that every book shares one 5% guarantee.

`SUSPECTED` is not a stage the book must pass before `CONFIRMED`. A steady 10 pp shift reaches the day-28 look while its e-value is still below 2, so the owner digest is the confirmation itself.

Recovery uses the latest 20 days after confirmation, not the e-value that confirmation already inflated. An inflated e-value does not drift back to 1, so it cannot be a recovery test. Historical claims are not deleted; they remain in the archived episode.

## User action

The function returns an action. It does not render Telegram text and it is not called from the notifier.

| State | Action |
|---|---|
| Insufficient, noise, suspected, recovered | `NO_V2_OVERRIDE`. V1 wording stays. |
| Confirmed | `WITHHOLD_MODEL_PROBABILITY`. The model number is not shown. A softer sentence around the same number is not a substitute. A historical baseline may be shown only as a separate figure the caller already has. The monitor does not blend the model toward the live rate. |
| Fault, incomplete | `WITHHOLD_FIGURE`. No model number and no baseline. The figure is unavailable. |

Owner digests are at most once per UTC day, and only for suspected, confirmed, fault, incomplete, or the transition into recovered. V1's 30-minute repeat is a different component and is left in place.

## Comparison with V1

Surface: synthetic comonotonic slots. One uniform draw per slot, outcome 1 when the draw is below the true probability. Claims in a slot are one path. This is not the Binance 2024 archive and not the October journal. Replaying 2024 would refit rangecast; that fit belongs to the forecast engine, and the live journal is not in this repository.

Null, 20 seeds, 56 days, 280 windows of 7 days (the length on which V1's slot count already passes 30):

- V1 raised a divergence on 133/280 windows (0.475).
- V2 called every 7-day window `INSUFFICIENT_DATA` (0 exceptions).
- V2 on the full 56-day null: 0/20 seeds suspected, 0/20 confirmed.

Power, 3 seeds, predeclared shifts, not the October residuals. Confirmation in these runs is the day-28 checkpoint:

- Touch stated 10 pp below the true probability: `LEVEL` confirmed, mean residual about +0.08 to +0.10. `NEITHER` stayed `WITHIN_NOISE`.
- Tails shifted by 12 pp in opposite directions: mean touch residual about −0.007 to +0.017 (`LEVEL` stayed noise) while `TAIL_HIGH`, `TAIL_LOW` and `SHAPE` confirmed.
- Shape compressed away from 0.5: mean touch residual about −0.006 to +0.018 (`LEVEL` noise), `SHAPE` estimate about −0.14 to −0.15 and confirmed.
- Neither shifted by 10 pp, touch left calibrated: neither confirmed, every touch channel stayed noise. V1's touch bins did not diverge.
- 36 days of a 10 pp touch shift, then a null generator: V2 touch ended `RECOVERED`. V1, scored on the whole span, was still divergent at day 80.

## Safe switch

1. This tree does not call the monitor from `beta/health.py` or the notifier. Deploying the module alone does not change alerts or wording.
2. A later shadow recorder may write health component `touch_cal_monitor_v2` from the same journal. It must not update `touch_live_cal` and must not clear V1 flags.
3. User text changes only after a separate owner permission, and only through `user_action`. Confirmed books withhold the model probability. They do not keep it under the historical-wording fallback.
4. V1 stays armed until that permission. The two monitors can disagree; V1 remains the one users feel.

## Residual risks

- The synthetic null is one dependence structure. A real week can be more serially correlated than these slots. The day index still has conditional mean zero when the issued probability is the conditional probability, but the day-28 interval is a bootstrap, not an exact test under skew.
- Six books (two families, three horizons) do not share a single family-wise 5% bound. The null replay is the evidence that the joint false-confirm rate was 0/20 at 56 days on this generator.
- `SUSPECTED` rarely precedes the day-28 confirmation for a 10 pp shift. There is no owner page during days 10–27 unless the e-value has already reached 2.
- Recovery can close on a quiet 20-day slice while an older bias is only archived. The episode list is the record; the state is allowed to say recovered.
- October's 7 days and 34–35 slots stay `INSUFFICIENT_DATA` here however large the gap. That is the information floor, not a verdict that those probabilities were right.
- The live journal has not been replayed. Shadow mode is what checks these states on production claims.
