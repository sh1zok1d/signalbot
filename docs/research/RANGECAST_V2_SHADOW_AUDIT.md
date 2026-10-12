# RANGECAST_V2 — shadow-readiness audit of W_L1

**Status:** `ENGINEERING_AUDIT` (2026-10-12). Owner go of 2026-10-12: prepare a paired shadow of W_L1 beside V1 without changing a user-facing probability.
**Surfaces:** the development folds 2021–2024 (consumed by the unit); synthetic bars in tests. The one read of 2025–2026 was not repeated. E1-RUN-001 objects were never requested.
**Records:** `RANGECAST_V2_SHADOW_AUDIT.json` (`scripts/research/rangecast_v2/audit.py`), `RANGECAST_V2_SHADOW_PARITY.json` (`parity.py`), frozen artifact `RANGECAST_V2_W_L1_MODEL_V1.json` (`freeze.py`).
**Not changed:** `beta/rangecast.py` (V1), the sharp-move detector, the claim journal, any table, any user text.

## 1. Findings

| Area | Check | Result | Action |
|---|---|---|---|
| Point in time | Features read bars at or before the anchor; a perturbation of later bars leaves them identical (test). Calendar inputs are scheduled: weekend share from the clock, CPI / FOMC from the calendar file | pass | none |
| 5-minute anchors, numbers | The live slice (`state_at`, 30 days of bars) against the vectorized research path at all 12 five-minute offsets, fold 2024 | max \|Δp\| 4.6·10⁻¹⁴ | none |
| 5-minute anchors, calibration | Both models are fitted on hourly anchors. Off the hour, 1h chances read about 1 pp high (W_L1 −1.1 / −0.9 / −0.7 pp at :15 / :30 / :45 against +0.1 at :00; V1 −1.2 / −1.2 / −1.0 against −0.5). 4h: W_L1 −0.2 to −0.3 pp, V1 −0.7. 24h: none | W_L1 beats V1 at every offset (4h −0.0040 / −0.0040 / −0.0038 / −0.0036 nats) | not changed: a fix is a new model version (§3). The shadow is issued at the hour, the trained regime |
| Incomplete data | Fitting and evaluation took a window at 90 % of its bars. Live, a hole in the 1m tail could still yield a number | gap | **fixed**: a live gate (complete 1h and 4h windows; 99 / 98 / 95 % of 24h / 7d / 30d) returns `INCOMPLETE_WINDOW`. After the E1 gap the 30-day window fails until 2026-09-23, as expected |
| Extreme chances | `as_v1_model` drops the 0.001 / 0.005 quantile levels. On the evaluation grids plus 0.05 %, a research-path chance above 0.99 occurs 0 times at 1h and 4h and in 0.045 % of 24h chances; the largest difference is 0.0018 | equal wherever p ≤ 0.99 | the adapter publishes the research path, so the shadow scores the numbers that were evaluated |
| CPI / FOMC | The event flag is 1 only for anchors in (r − H, r], which lies inside the product's event zone [r − H, r + 60 min). The adapter withholds those horizons with the same rule (`decision.event_zones`, test) | outside the zone the event term is 0: no shadow number depends on it (test) | none. Event-time chances stay withheld; V1's temporal-semantics failure is not carried into any shadow number |
| «Ни один» | 400 states × 625 level pairs per horizon, fold 2024 | 0 monotonicity and 0 Fréchet-bound violations | none |
| Nightly fit | A fit uses only anchors whose window has closed (test); the shadow uses one frozen artifact, so no refit happens during it | pass | none |
| Identity | Nothing tied a forecast to the procedure that issued it | gap | **fixed**: `spec_id`, `spec_digest` (every procedure constant), `params_digest` (fitted numbers), `artifact_id`; an artifact whose spec digest differs from the code's is refused, and golden outputs pin the math |

## 2. What changed in code

- `beta/rangecast_v2.py`: identity (`SPEC_ID`, `spec`, `spec_digest`, `params_digest`) and the live data-quality gate (`MIN_PRESENT`, `data_quality_failures`). The fitted formulas are unchanged: the artifact reproduces the evaluated path to 4.6·10⁻¹⁴.
- `docs/research/RANGECAST_V2_W_L1_MODEL_V1.json`: one W_L1 fit on the product surface 2020-01-01 … 2026-10-11 (the surface V1 is fitted on nightly; E1 objects never requested). No outcome was scored. File sha256 `2c7e3eca…0533`, parameter digest `095f409f…e261`, spec digest `00539f2d…7246`.
- `beta/rangecast_shadow.py`: the paired adapter (contract `docs/RANGECAST_V2_SHADOW_CONTRACT_V1.md`).
- `beta/rangecast_paired.py`: the paired evaluator and the frozen promotion rule (plan `docs/RANGECAST_V2_SHADOW_PLAN_V1.md`).

## 3. Not changed, because it would change the model

- **Off-hour calibration.** Training on every 5-minute anchor (or on a 15-minute grid) is the direct remedy. It is a new version (`W_L1_A5`). It would need its own frozen design and could only be evaluated on the development folds plus a later shadow. It is not started. The product's V1 has the same property today.
- **Event semantics.** The K1 candidate of `BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1.md` §7 stays a separate unit. Shadow numbers inside event zones do not exist.

## 4. Remaining risks

- The 1h shadow book is scored at hourly anchors. A user's `/check` at :25 meets the off-hour bias of both models.
- The frozen artifact ages. The recency weights were fitted to 2026-10-11, and a 12-week shadow adds about 3 % to the age of the newest data, which is small against a 365-day half-life. A refit is a new artifact and a new registered shadow.
- The gate turns some live anchors into `INCOMPLETE_WINDOW` that V1 would still answer. These anchors are counted, and the pairing completeness gate of the plan uses them.
