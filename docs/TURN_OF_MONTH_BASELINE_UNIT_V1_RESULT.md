# Turn-of-month baseline evaluation — product-evidence unit V1: result

**Status:** `EXECUTED ONCE (2026-10-06) / PART B: NO_CHANGE / PART A: L1 PERMITTED BY THE NOTE'S RULE, NOT SHOWN (needs its own product go) / NO PRODUCT CHANGE`
**Design note (before outcome):** `TURN_OF_MONTH_BASELINE_UNIT_V1.md`, committed in `54421a0`. Deployment facts were corrected in `7607225`, also before the outcome.
**Owner go:** 2026-10-06. It covers one official run strictly per the design note, on `CORE_BTC_BINANCE_V0` 2020–2024, without the 2025/2026 slice and with no plan change after the outcomes were read.
**Evaluator:** `scripts/product/turn_of_month_baseline_v1/evaluate.py`.
- It was committed and pushed before the run (`1067bcb`).
- Its SHA-256 is `7fbb55ca…8c8f91d`. The SHA-256 of each imported module is in the JSON.
- 19 tests: `tests/product/test_turn_of_month_baseline_v1.py`.

**Raw output:** `TURN_OF_MONTH_BASELINE_UNIT_V1_RESULT.json` (`c6d60d8`). It holds the per-month sufficient statistics (n, sum) per label, construction and set, and the per-month Part A differences.
**Authority:** `research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` §3–§4. No verdict words: the statuses below are the note's own decision-rule outputs.

## 0. In short

- **Part B (decides): `NO_CHANGE`.**
  - Under C1 (deployed) no label is `BEYOND_TOLERANCE`.
  - One label is `WITHIN_TOLERANCE`: the 1h band move ≤ 0.20.
  - The other 12 are `NOT_RESOLVED`: their intervals are neither inside ±τ nor wholly past it.
  - C0 gives the same statuses (reported only).
- **Part A (L1 at most).** On 2020–2024 turn-of-month UTC days were **quieter** than days 8–21 of the same month on all three outcomes:
  - quote volume −0.24 SD (95 % −0.44 … −0.03);
  - trade count −0.32 SD (−0.52 … −0.12);
  - range −0.24 SD (−0.46 … −0.01).

  Each covers 58 months, and at least 4 of 5 years share the sign. The note's rule permits an L1 context line. No line is added: a `config/beta_research_findings.yaml` entry needs its own product go (note §6).
- **Direction.** The sign is opposite to G01-A1/A2's declared expectation (positive). G01 stays closed as recorded: this unit is not a G01 test and no G01 verdict changes. The note fixed no direction for Part A.

## 1. What was run

- **Data.**
  - `CORE_BTC_BINANCE_V0` BTCUSDT perpetual 1m, 2020-01-01 … 2024-12-31: 2 630 880 rows, gapless.
  - The pinned R03 loader SHA-verified all 60 monthly zips (dataset digest `93659495…2aa90b`).
  - Trade count is column 8 of the same zips, asserted equal to the loader's `open_ms`.
  - This is a single-venue proxy (`PROXY_SINGLE_VENUE`).
  - **Not read:** 2025/2026 objects, BitMEX, the live tape.
- **Calendar.** G01 `tom_state_days` / `comparator_days`, unchanged, on [2020-01-31, 2025-01-01):
  - 202 TOM days and 826 MID days;
  - 58 month units with both sets, plus 2022-10, which has MID days only (Sep 30 2022 is the last Friday; Oct 1–3 fall in the holiday window).

  These are exactly the counts in note §5.
- **Windows.**

  | Family | TOM | MID |
  |---|---|---|
  | 1h | 4 848 | 19 824 |
  | 4h | 1 212 | 4 956 |
  | 24h | 202 | 826 |
  | TOD (on the 1h windows) | 4 848 | 19 824 |

  Availability was 100 % for every family, set and construction from 2020-01-31.
- **Implementation readings.** Fixed in the evaluator's docstring and in commit `1067bcb`, before the run:
  - Part B pools every usable window of a set, so 2022-10 adds MID windows. The month-clustered SE therefore has G = 59 and the interval uses t(58) = 2.0017. The date-clustered SE is computed beside it and the larger is used; for every label the month SE was the larger.
  - Part A z uses ddof = 1 (R03 `standardize`).
  - The moving-block SE uses R03's 2000 draws and the note's seed.
  - The Student-t quantile is computed in the module (scipy is not a dependency) and tested against tabulated values.
- **Runs.** One. Nothing was added, dropped or re-run after the outcome.

## 2. Part B — label calibration (primary: C1)

`D = r_TOM − r_MID`, in percentage points. The interval is `D ± t(0.975, 58) · max(SE_month, SE_date)`.

### 2.1 C1 (deployed; decides)

| Label | Nominal | τ | r_TOM | r_MID | D (pp) | 95 % interval (pp) | SE month / date (pp) | D by year 2020…2024 (pp) | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1h flag range ≥ 0.95 | 5 % | 2 | 4.7 % | 6.4 % | −1.76 | −3.49 … −0.04 | 0.86 / 0.62 | +1.5 / −2.7 / −5.0 / −1.7 / −0.8 | NOT_RESOLVED |
| 1h flag volume ≥ 0.95 | 5 % | 2 | 4.6 % | 6.1 % | −1.51 | −3.01 … −0.00 | 0.75 / 0.53 | +1.3 / −2.4 / −2.4 / −1.9 / −2.0 | NOT_RESOLVED |
| 1h flag price ≥ 0.95 or ≤ 0.05 | 10 % | 2 | 9.7 % | 11.5 % | −1.80 | −3.99 … +0.39 | 1.09 / 0.76 | +1.7 / −1.5 / −5.2 / −4.6 / +0.6 | NOT_RESOLVED |
| 1h band range ≤ 0.20 | 20 % | 4 | 23.0 % | 19.9 % | +3.10 | −0.93 … +7.14 | 2.02 / 1.44 | −1.8 / +5.8 / +5.0 / +2.8 / +3.4 | NOT_RESOLVED |
| 1h band move ≥ 0.80 | 20 % | 4 | 18.5 % | 21.1 % | −2.68 | −4.79 … −0.57 | 1.05 / 0.77 | +1.8 / −3.2 / −3.8 / −4.2 / −3.8 | NOT_RESOLVED |
| 1h band move ≤ 0.20 | 20 % | 4 | 19.5 % | 21.2 % | −1.66 | −3.71 … +0.38 | 1.02 / 0.83 | +2.0 / −2.6 / −4.8 / −2.4 / −0.4 | WITHIN_TOLERANCE |
| 4h band range ≤ 0.20 | 20 % | 4 | 22.4 % | 20.0 % | +2.45 | −1.91 … +6.80 | 2.18 / 1.75 | −3.2 / +5.3 / +5.9 / +0.3 / +3.5 | NOT_RESOLVED |
| 4h band move ≥ 0.80 | 20 % | 4 | 17.5 % | 20.9 % | −3.43 | −6.30 … −0.57 | 1.43 / 1.30 | −2.6 / −0.4 / −6.1 / −3.6 / −4.3 | NOT_RESOLVED |
| 4h band move ≤ 0.20 | 20 % | 4 | 20.4 % | 22.2 % | −1.84 | −5.04 … +1.36 | 1.60 / 1.37 | +0.8 / −5.1 / −9.9 / −0.5 / +5.7 | NOT_RESOLVED |
| TOD range above median | 50 % | 4 | 45.0 % | 50.3 % | −5.31 | −10.89 … +0.27 | 2.79 / 1.87 | +5.9 / −7.5 / −9.8 / −9.0 / −5.5 | NOT_RESOLVED |
| TOD volume above median | 50 % | 4 | 47.3 % | 52.4 % | −5.11 | −10.73 … +0.51 | 2.81 / 1.85 | +4.6 / −5.8 / −10.4 / −7.4 / −6.2 | NOT_RESOLVED |
| 24h range above median | 50 % | 4 | 42.6 % | 51.9 % | −9.36 | −18.41 … −0.31 | 4.52 / 3.89 | +10.3 / −6.8 / −20.1 / −15.7 / −13.3 | NOT_RESOLVED |
| 24h volume above median | 50 % | 4 | 47.5 % | 54.7 % | −7.20 | −17.59 … +3.20 | 5.19 / 3.92 | +3.8 / −12.7 / −6.2 / −12.1 / −8.3 | NOT_RESOLVED |
| gate qualification (≥ 2 of 3 flags), reported only | — | — | 5.0 % | 6.6 % | −1.65 | −3.21 … −0.09 | 0.78 / 0.58 | +1.4 / −2.3 / −4.3 / −1.7 / −1.2 | reported only |

### 2.2 C0 (previous pooled reference; same rule, reported only)

| Label | Nominal | τ | r_TOM | r_MID | D (pp) | 95 % interval (pp) | SE month / date (pp) | D by year 2020…2024 (pp) | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1h flag range ≥ 0.95 | 5 % | 2 | 4.2 % | 6.3 % | −2.15 | −3.71 … −0.59 | 0.78 / 0.59 | +0.1 / −2.5 / −4.7 / −2.1 / −1.5 | NOT_RESOLVED |
| 1h flag volume ≥ 0.95 | 5 % | 2 | 4.2 % | 6.0 % | −1.84 | −3.22 … −0.45 | 0.69 / 0.53 | +0.7 / −2.9 / −2.2 / −2.5 / −2.2 | NOT_RESOLVED |
| 1h flag price ≥ 0.95 or ≤ 0.05 | 10 % | 2 | 9.4 % | 11.6 % | −2.18 | −4.33 … −0.02 | 1.08 / 0.76 | +1.4 / −1.9 / −4.6 / −4.1 / −1.4 | NOT_RESOLVED |
| 1h band range ≤ 0.20 | 20 % | 4 | 22.3 % | 19.7 % | +2.60 | −1.40 … +6.61 | 2.00 / 1.62 | −2.9 / +5.1 / +4.2 / +1.5 / +4.7 | NOT_RESOLVED |
| 1h band move ≥ 0.80 | 20 % | 4 | 18.6 % | 21.1 % | −2.51 | −4.49 … −0.53 | 0.99 / 0.80 | +1.7 / −2.9 / −3.8 / −4.6 / −2.6 | NOT_RESOLVED |
| 1h band move ≤ 0.20 | 20 % | 4 | 19.8 % | 21.0 % | −1.21 | −3.33 … +0.90 | 1.06 / 0.86 | +1.7 / −2.3 / −4.9 / −2.2 / +1.8 | WITHIN_TOLERANCE |
| 4h band range ≤ 0.20 | 20 % | 4 | 22.7 % | 20.3 % | +2.39 | −2.20 … +6.99 | 2.30 / 1.96 | −4.3 / +2.9 / +4.4 / +2.6 / +6.0 | NOT_RESOLVED |
| 4h band move ≥ 0.80 | 20 % | 4 | 18.1 % | 21.3 % | −3.22 | −6.20 … −0.24 | 1.49 / 1.37 | −1.7 / +0.5 / −5.3 / −2.5 / −7.0 | NOT_RESOLVED |
| 4h band move ≤ 0.20 | 20 % | 4 | 20.2 % | 22.1 % | −1.84 | −4.70 … +1.02 | 1.43 / 1.38 | −0.2 / −6.1 / −7.5 / −0.5 / +5.1 | NOT_RESOLVED |
| TOD range above median | 50 % | 4 | 44.8 % | 50.5 % | −5.72 | −11.65 … +0.21 | 2.96 / 2.04 | +4.6 / −5.7 / −9.8 / −9.7 / −7.5 | NOT_RESOLVED |
| TOD volume above median | 50 % | 4 | 47.5 % | 52.5 % | −4.95 | −10.68 … +0.79 | 2.87 / 2.02 | +5.3 / −7.3 / −7.7 / −7.9 / −6.6 | NOT_RESOLVED |
| 24h range above median | 50 % | 4 | 42.6 % | 51.9 % | −9.36 | −18.41 … −0.31 | 4.52 / 3.89 | +10.3 / −6.8 / −20.1 / −15.7 / −13.3 | NOT_RESOLVED |
| 24h volume above median | 50 % | 4 | 47.5 % | 54.7 % | −7.20 | −17.59 … +3.20 | 5.19 / 3.92 | +3.8 / −12.7 / −6.2 / −12.1 / −8.3 | NOT_RESOLVED |
| gate qualification (≥ 2 of 3 flags), reported only | — | — | 4.6 % | 6.5 % | −1.83 | −3.33 … −0.33 | 0.75 / 0.57 | +0.5 / −2.3 / −3.7 / −1.6 / −1.9 | reported only |

### 2.3 Gaps to nominal under C1 (secondary)

| Label | TOM gap (pp) | TOM 95 % | MID gap (pp) | MID 95 % |
|---|---|---|---|---|
| 1h flag range ≥ 0.95 | −0.34 | −1.57 … +0.89 | +1.43 | +0.16 … +2.69 |
| 1h flag volume ≥ 0.95 | −0.40 | −1.55 … +0.75 | +1.11 | +0.24 … +1.98 |
| 1h flag price ≥ 0.95 or ≤ 0.05 | −0.26 | −1.95 … +1.43 | +1.54 | −0.10 … +3.17 |
| 1h band range ≤ 0.20 | +3.04 | −1.00 … +7.08 | −0.06 | −3.24 … +3.11 |
| 1h band move ≥ 0.80 | −1.54 | −3.35 … +0.27 | +1.14 | −0.39 … +2.67 |
| 1h band move ≤ 0.20 | −0.51 | −2.36 … +1.35 | +1.16 | −0.33 … +2.64 |
| 4h band range ≤ 0.20 | +2.44 | −2.19 … +7.07 | −0.00 | −3.45 … +3.44 |
| 4h band move ≥ 0.80 | −2.51 | −4.83 … −0.19 | +0.92 | −0.79 … +2.64 |
| 4h band move ≤ 0.20 | +0.38 | −2.50 … +3.26 | +2.22 | +0.41 … +4.02 |
| TOD range above median | −5.01 | −10.00 … −0.02 | +0.30 | −4.29 … +4.88 |
| TOD volume above median | −2.70 | −7.76 … +2.35 | +2.41 | −1.70 … +6.52 |
| 24h range above median | −7.43 | −14.72 … −0.13 | +1.94 | −3.16 … +7.04 |
| 24h volume above median | −2.48 | −11.36 … +6.41 | +4.72 | −0.84 … +10.28 |

### 2.4 Construction comparison and reference size

- **Label-switch rate C1 vs C0 on TOM windows.** This is the share of windows where any label of the family differs:
  - 1h: 19.3 % of 4 848;
  - 4h bands: 14.3 % of 1 212;
  - TOD: 18.4 % of 4 848;
  - 24h: 0 % (identical construction, §3).
- **Median reference size, the same on TOM and MID windows.**

  | Family | C0 | C1 |
  |---|---|---|
  | 1h | 8 640 samples, 31 dates | ≈ 6 200 samples, 22 dates |
  | 4h | 8 640 samples, 31 dates | ≈ 6 200 samples, 22 dates |
  | TOD | 30 days | 21 days |
  | 24h | 30 prior days | 30 prior days |

### 2.5 Decision (note §6)

- **`BEYOND_TOLERANCE` under C1:** none. **Recommendation: `NO_CHANGE`.**
- **`WITHIN_TOLERANCE` (calibration shown to hold on TOM days relative to MID):** 1h band move ≤ 0.20 (D −1.66 pp, 95 % −3.71 … +0.38, τ 4).
- **`NOT_RESOLVED` (not enough information for either status):** every other label.
  - **1h flags:** range, volume, price.
  - **Bands:** 1h range ≤ 0.20 and move ≥ 0.80; 4h range ≤ 0.20, move ≥ 0.80 and move ≤ 0.20.
  - **TOD:** range, volume.
  - **24h:** range, volume.
- **Prospective option for the `NOT_RESOLVED` labels (note §6; nothing is built).** Monthly TOM-day vs MID-day label rates from the live tape, read-only, or the claim journal once it exists.

**What the numbers show, beside the rule.** The rule decides, and this does not change the status.
- **The common direction.** Every activity label fires less often on TOM days than on MID days. That covers the flags, the high-move bands, TOD "above usual" and 24h "above usual"; the low-range band fires more often.
- **Several intervals exclude zero but stay inside or straddle −τ.**
  - 1h flag range: −3.49 … −0.04.
  - 1h flag volume: −3.01 … −0.00.
  - 1h band move ≥ 0.80: −4.79 … −0.57.
  - 4h band move ≥ 0.80: −6.30 … −0.57.
  - 24h range: −18.4 … −0.3.
- **Against the nominal rate, MID days carry most of the 1h flag gap.**
  - On TOM days the 1h flags are within ±0.4 pp of nominal.
  - On MID days they are +1.1 to +1.5 pp above nominal.
  - TOD range and 24h range are the exceptions: there the TOM rate is below nominal (−5.0 and −7.4 pp).
- **2020 (February–December) is the one year with the opposite sign** on most labels.

## 3. Part A — day-level shift (secondary, descriptive)

z is standardized per calendar year and weekday class over all UTC days. `d_m` is the mean z of TOM days minus the mean z of MID days; the estimate is the equal-weight mean over the 58 months that have both sets.

| Outcome | Estimate (SD) | 95 % t-interval | SE t / sign-flip / moving-block 3m | sign-flip p | Mean by year 2020…2024 | Months | Claim decision |
|---|---|---|---|---|---|---|---|
| log quote volume | −0.239 | −0.444 … −0.035 | 0.102 / 0.106 / 0.102 | 0.0221 | +0.002 / −0.197 / −0.345 / −0.452 / −0.193 | 58 | L1_CONTEXT_LINE_PERMITTED |
| log trade count | −0.322 | −0.520 … −0.124 | 0.099 / 0.107 / 0.101 | 0.0011 | −0.087 / −0.274 / −0.481 / −0.466 / −0.297 | 58 | L1_CONTEXT_LINE_PERMITTED |
| log range | −0.236 | −0.463 … −0.009 | 0.113 / 0.116 / 0.114 | 0.0398 | −0.028 / −0.249 / −0.466 / −0.426 / −0.014 | 58 | L1_CONTEXT_LINE_PERMITTED |

**Claim decision (note §6, Part A).**
- **The rule.** For all three outcomes the 95 % interval excludes 0, and at least 4 of 5 yearly means share its sign. The years agreeing are volume 4/5 (2020 +0.002), trade count 5/5 and range 5/5. The rule's outcome is "an L1 context line is permitted".
- **Wording.** A template in the note's form would read: «в 2020–2024 в дни смены месяца объём был на 0,24 SD ниже середины месяца (95 % интервал −0,44…−0,03; 58 месяцев)».
- **Not added.** No such line is added. A findings entry and its wording need their own product go, and the registry records the unit under `no_bot_context`.
- **Materiality.** None of the three intervals lies inside ±0.15 SD. The point estimates (−0.24 to −0.32 SD) are about half the old G01 0.5 SD bar, which is not used here.

## 4. Result record (`EVIDENCE_AND_CLAIMS_DECISION_V1` §3)

| Field | Content |
|---|---|
| estimate | Part B: `D_L` per label, from −9.4 pp (24h range) to +3.1 pp (1h band range ≤ 0.20) under C1. Part A: −0.24 / −0.32 / −0.24 SD (volume / trades / range) |
| uncertainty | 95 % intervals as tabled. Part B: month-clustered vs date-clustered SE, max, t(58). Part A: t over months, with the sign-flip and moving-block SEs beside it (close to the t SE) |
| information | 58 month units (59 for MID in Part B); 202 TOM / 826 MID days; 4 848 / 19 824 1h windows. Realized half-widths: 1h flags 1.5–2.2 pp (planned 1.4–1.9); 1h bands 2.0–4.0 pp (planned 2.6); TOD 5.6 pp (planned 3.2); 4h bands 2.9–4.4 pp (planned 5); 24h 9.1–10.4 pp (planned 8–15); Part A 0.20–0.23 SD (planned 0.14–0.19) |
| stability | Per-year D shown. 2021–2024 mostly share the sign; 2020 (February–December) is often the opposite sign |
| falsification | None declared in the design note; none added after the outcome. The TOM-vs-nominal and MID-vs-nominal gaps (§2.3) are reported beside the difference as its comparator |
| limitations | Single venue (Binance perpetual). 2020–2024 only; exposed surface. Floating holidays (CN New Year, US Labor Day) remain as noise. The production 3-venue median, venue agreement, OI and taker ranks are not evaluated. Retrospective, not a confirmation |
| search exposure | Part B: 2 constructions × 13 labels + the gate (reported). Part A: 3 outcomes. G01's TOM definition only; no other window tried. No multiplicity correction beyond the τ + year-consistency rule (note §6) |
| method before outcome | `54421a0` (design note); `1067bcb` (evaluator and tests) |
| evidence summary | On Binance BTCUSDT 2020–2024 the turn-of-month days of 58 months had lower volume, trade count and range than days 8–21 of the same months (about −0.24 to −0.32 SD), and the bot's activity labels fired somewhat less often on them under C1 (1h flags about −1.5 to −1.8 pp), with intervals that do not establish a gap beyond the 2 / 4 pp tolerances |
| claim decision | Part B: a baseline-construction question, not a claim; `NO_CHANGE`. Part A: L1 permitted by the note's rule for volume, trade count and range; not shown (needs a product go) |

## 5. What this changes and what it does not

- **Product:** nothing. No change to `beta/`, config, schema, wording or deploy. No correction unit is proposed (Part B is `NO_CHANGE`).
- **Research records:**
  - G01-A1/A2 records and verdicts are unchanged.
  - The unit is added to the atlas (`TOM-BASELINE-V1`) with its exposure ledger row and hash-chained event.
  - `RESEARCH_LEDGER.md` and `CURRENT_RESEARCH_STATE.md` are updated, and the findings registry gets a `no_bot_context` entry.
- **History-audit tooling.**
  - Adding the atlas unit made `scripts.research.history_audit --check` and its test report `UNASSESSED atlas unit TOM-BASELINE-V1`, because the builder binds the merged V1 audit to the live atlas.
  - The builder now scopes the V1 census to the atlas as of its last event before the audit (seq 6). Units added by later atlas events are placed but not assessed.
  - The audit record files (`RESEARCH_HISTORY_AUDIT_V1.md`, `.json`, `_TABLE.md`, the assessments YAML) are unchanged; the census stays at 188.
  - The alternative, assessing the unit inside the V1 audit and rebuilding it, would edit the merged record (erratum 1 §4). It is left to the owner.
- **Not opened:** BitMEX 2017–2019 (still available as a later labelled check), 2025/2026, the live tape, E1, V3.
