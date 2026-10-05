# Touch-chance calibration and the «B» wording — design note V1

**Status:** `DESIGN_NOTE / COMMITTED_BEFORE_OUTCOME` (2026-10-05). This note was written and committed before any of the binned held-out results below was computed. The range model's existing three-point `touch_reliability` output (predicted 50 / 20 / 10 %) exists in the statistics rows; it was not read for this note.

**Authority:**
- `PRE_BETA_SCOPE_DECISION_V1.md` §5 (wording «B»; a design note before implementation) and §4 (history first, live joins);
- `research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` §3 (design note) and §4 (L3).

It covers backlog items B3 and X8 (`PRE_BETA_BACKLOG_V1.md`). It changes no model, corridor or threshold.

## 1. Estimand

The chance that BTC (Binance USD-M BTCUSDT) reaches a price `d` % away on one side within horizon H ∈ {1h, 4h, 24h}, measured from the close the estimate is made at.

This is the quantity behind every «шанс дойти» on a user surface:
- `/levels`;
- the `/btc` and briefing level lines;
- the next level in a level alert;
- `/alert`, the `/risk` table and `/check`.

It is computed today as `rangecast.touch_probability = 1 − F(d / S)`, where F is the empirical distribution of the standardized one-sided excursion (`q_one`) and S is the model's scale.

## 2. Method, fixed by design

**Held-out check (history first).**
- **Model and period.** The range model is fitted on data before the held-out last 365 days: the `train` split of `fit_range_model`, unchanged. Its estimates are scored on the hourly anchors of the held-out year.
- **Distances.** The claim journal's grid `beta/claims.py::TOUCH_GRID_PCT` = 0.25 / 0.5 / 1 / 2 / 3 / 5 %, on both sides. An arbitrary level is a point on the same curve; the bins below are in probability, not distance.
- **Predicted:** `1 − F_train(d / S_train)`.
- **Realized:** the up excursion (side +1) or the down excursion (side −1) over the next H bars is at least `d`. These are the model's own targets, from Binance 5m bars.
- **Event zones are excluded**, as live: an anchor is excluded for horizon H when a CPI or FOMC release r satisfies r − H ≤ anchor < r + 60 min. Nothing is shown or journaled there either.

**Bins** (predicted probability, %), the claim journal's `PROB_BINS`: [0, 5), [5, 15), [15, 30), [30, 50), [50, 70), [70, 85), [85, 100].

**Effective N** of a bin: the number of distinct UTC-aligned horizon-length slots holding at least one of its estimates. Hourly anchors overlap, so their raw count overstates the information.

**Per bin, the record shows:**
- the mean predicted;
- the realized share;
- the difference in percentage points;
- raw N and effective N;
- a 95 % UTC-day-clustered bootstrap interval of the difference (1000 replicates, seed 20261005).

## 3. Decision rule

| Case | Rule | Wording on every surface |
|---|---|---|
| **Held-out pass** (horizon × bin) | effective N ≥ 30 (`MIN_N_SHOWN`) **and** \|realized − mean predicted\| ≤ 5 pp | «B»: «шанс ≈ X %» with «на истории: говорили P % → было R % (N = n)» |
| **Held-out not passed** | effective N < 30, or \|difference\| > 5 pp | fallback: «исторически в X % случаев», no calibration line |
| **Live line** | the journal's class `L3_*_TOUCH_{H}` reaches effective N ≥ 30 in the bin (complete outcomes, same bins, same effective-N rule) | the calibration line becomes «вживую: говорили P % → было R % (N = n)»; `/accuracy` shows both |
| **Divergence** | a live bin with effective N ≥ 30 whose \|realized − mean predicted\| > 5 pp **and** whose day-clustered 95 % interval of the difference excludes 0 | that bin falls back to «исторически в X % случаев» on every surface until the next model version, and the owner is flagged |

- **The held-out pass is computed nightly** by the history build. Its verdict is applied automatically.
- **On divergence**, the live line stays visible in `/accuracy`. The number itself is never adjusted toward the live rate during the test.
- **This rule is frozen before Day 0.** During the test no bin, tolerance or threshold changes.

X is the model's estimate, printed as today (`decision_format.fmt_prob`). P and R are rounded to whole percent.

## 4. What would change our mind

- If no bin of a horizon passes the held-out rule, that horizon never uses «B»; the fallback holds everywhere.
- If fewer than half of the populated bins pass across the three horizons, the owner is told before Day 0 and «B» is not shown at all.
- No other bins, tolerance or distance grid are tried after the result.

## 5. Search exposure and limitations

**Search exposure:**
- 3 horizons × 7 bins = 21 cells judged once;
- variants tried before this note: none.

**Limitations:**
- **One venue and one model.** Binance only; the model is linear in log past ranges.
- **The check is of the procedure, not of the exact numbers shown.** Live chances come from the final fit, which includes the held-out year.
- **The held-out year is no longer untouched for this quantity.** It is part of the product statistics (`PRODUCT_DECISION_V2` §4).
- **The live line needs months for 24h** (the claim journal design, §5). The history-first rule exists for that reason.

## 6. Implementation and first result (added after the note was committed in `47ed3d8`)

**Code.**
- `beta/rangecast.py::touch_calibration`: the held-out bins in `range_model.calibration.<h>.touch_bins`, nightly.
- `beta/claims.py`:
  - `live_touch_bins`, `diverged_bins` and `refresh_touch_calibration`: the hourly live bins and the sticky divergence;
  - `touch_wording`: the §3 rule as one function, for every surface.
- `beta/health.py`: `TOUCH_CALIBRATION_DIVERGED`.
- `/accuracy`: the held-out bins, «говорили P → было R (N)», with bins outside the rule marked.

**First result (local, not production).**
- Data: the Binance 2022–2024 archives kept in the repository (`tests/beta/v2_fakes.VISION_DIR`); held-out year 2024.
- Every one of the 21 cells passed.
  - The largest difference: 1h, bin 85–100 %, −4.1 pp at effective N 48.
  - Every other bin: within ±1.8 pp.
- `tests/beta/test_beta_claims.py::test_touch_chances_are_calibrated_on_the_real_held_out_year` pins this.

**Not yet decided by this result.**
- Production builds the bins nightly on 2020 → yesterday, and that verdict is the one the surfaces use.
- The rule above did not change after the result.
