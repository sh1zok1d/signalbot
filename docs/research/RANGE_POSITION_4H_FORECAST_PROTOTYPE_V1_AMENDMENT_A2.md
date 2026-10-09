# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 — pre-outcome amendment A2 (frozen before any fit)

**Status:** `FROZEN` before any fit. This file's SHA256 is pinned in `scripts/research/rp4h_forecast_prototype_a2/constants.py` (`AMENDMENT_A2_SHA256`). The market path refuses on a mismatch (`AMENDMENT_A2_HASH_MISMATCH`), and refuses with `AWAITING_OWNER_GO` while `OWNER_GO` is false.

**Owner decision.** 2026-10-09, option (b): run Cursor's frozen prototype first, but only on the canonical Opus 2025–2026 surface, and decide on ADAPTIVE_B1_FORECAST_V1 afterwards.

**Execution, after a separate owner GO:**
- A go commit sets `OWNER_GO = True` in `constants.py`. Nothing else changes.
- The one-shot fit runs through the parent's market entry point on the pinned runtime below.
- It writes its journal under `docs/research/range_position_4h_forecast_prototype_v1_a2_execution/`. A second attempt exits `REFUSING_RERUN` (`ATTEMPT.json`).

**Runtime pin (fail-closed):**
- Python 3.11 with numpy 2.1.3 and pandas 2.2.3 (the `requirements.txt` pins; the CI runtime).
- The vendored fold clock is correct only there. `runtime_guard.assert_fold_clock` refuses any other result with `FOLD_CLOCK_RUNTIME_MISMATCH`.
- On the container's default Python 3.13 / pandas 3, 15 vendored tests fail for that reason, and the guard blocks the run.

**Unit label:** `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_A2`. Parent: `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1`.

**Pre-outcome:** this amendment was written while the forecast model is unfitted.
- No market probability, coefficient, Brier score, log loss, AUROC, P(UP) or bootstrap draw was computed.
- No return statistic was computed on market rows.
- The only market read was the outcome-blind support census, which counts rows and weeks.

The original design and A1 are not edited.

| flag | value |
|---|---|
| `model_fit` | false |
| `OWNER_GO` | false |
| `model_metrics_computed` | false |
| `market_fit_executed` | false |
| `claim_ceiling` | `RETROSPECTIVE_FORECAST_PROTOTYPE` (unchanged) |

## What changed: only the 2025–2026 data source

| | parent (Cursor, A1) | A2 |
|---|---|---|
| 2025–2026 price path | `docs/research_data/RANGE_POSITION_4H_BINANCE_2025_2026_V1/canonical_5m.jsonl.gz`, SHA256 `64c1646acf7b371904ee6fcb25373383589e16c368d23267f136f4481f9894b9` | the canonical RP4H Unit B surface: `scripts.research.rp4h_binance_2025_2026_temporal_v1.data` `load_series()` → `census()` → `evaluate.assert_census()` (refuses with `CENSUS_MISMATCH`) → `place()` |
| manifest | none | `docs/research_data/RP4H_BINANCE_UM_BTCUSDT_5M_2025_2026_V0/MANIFEST.json`, object-list SHA256 `5369e8dc265ada989fa048fd49e8d694a2478e69916338223fe118f0dd0db621` (64 objects) |
| missing on the grid | `[2026-08-16T00:00Z, 2026-08-26T00:00Z)` | `[2026-08-02T00:00Z, 2026-08-26T00:00Z)`, NaN holes, never requested |
| eligibility check | `== range_position_4h_binance_2025_2026_temporal_replication_v1.sample.classify` | `== Unit B evaluate.build_sample` rows on the same grid, else `BINANCE_ELIGIBILITY_DIVERGED` |

The Unit B census pinned for this surface:
- 179,136 rows and 6,912 holes, holes SHA256 `7217c65f26284833eb0b95ab9d766bc16e27a70ec785df7ce44f152fcf474090`.
- The holes are the E1 window (2,800), the E1-development slice (4,032) and the rest of the refused 25th (80). There are no other holes.

**Why.** Cursor's 2025–2026 file contains bars from 2026-08-02 to 2026-08-15. On this surface, that is the E1-RUN-001 development slice.
- `docs/research/RANGE_POSITION_4H_BINANCE_2025_2026_EXPOSURE_AUDIT_V1.md` classes the slice as an **exact-class** exposure of `RANGE_POSITION_4H → R_1H`. E1 development `CB_ORDINARY_RANGE_BREAKOUT` read direction-aligned returns at 15m–4h after a close beyond the trailing 4h range.
- Unit B cut that slice at the object level before its freeze.
- **Owner decision 2026-10-09, option (b):** run Cursor's prototype only on that canonical Opus 2025–2026 surface.

**Fail-closed guards added in `support._modern_grid`:**
- `UNIT_B_SURFACE_MISMATCH`: the Unit B manifest, the object list, the clock or the excluded period differ from the A2 constants.
- `E1_EXCLUDED_BAR_PRESENT`: a loaded bar or a finite grid slot falls inside `[2026-08-02, 2026-08-26)`. This check runs before the census.
- `CENSUS_MISMATCH`: Unit B's own `assert_census` fails.
- `BINANCE_GRID_CLOCK_MISMATCH`: the grid does not span `[2025-01-01, 2026-10-09)` exactly.
- `BINANCE_ELIGIBILITY_DIVERGED`: the mask differs from Unit B's sample.

In `market.py`, the 2025–2026 file digest check becomes `require_manifest(MANIFEST, OBJECT_LIST_SHA256)`.

## What is unchanged

- The target `Y = 1[R_1H > 0]`, the horizon of 12 bars of 5 minutes, and `ZERO_RETURN_EXCLUDED`.
- The three segments and their clocks: `BITMEX_2016_2019` before 2020-01-01; `BINANCE_2020_2024` over `[2020-01-01, 2025-01-01)`; `BINANCE_2025_2026` over `[2025-01-01, 2026-10-09)`.
- No stitching and no venue dummy. Bybit is not included.
- **BitMEX source:** `D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz`, SHA256 `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`, read through Cursor's sample module. That module is now vendored.
- **CORE source:** `scripts.research.dh1.data.load_binance_perp_5m`, snapshot label `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.
- **Training sources:** BitMEX trains on BitMEX. 2020–2024 trains on 2020–2024. 2025–2026 trains on 2020–2024 plus 2025–2026.
- **Eligibility:** residue 2 from 2020-01-01, a complete 4h lookback including `T`, a complete 1h future, and a positive span.
- **Features:** `RET_4H`, `RV_4H`, `RET_1H`, `RET_15M`, `RANGE_POSITION_4H`, each from the same functions.
- **Model and fit:**
  - an unpenalized Newton logistic with at most 30 iterations, gradient tolerance `1e-8` and sigmoid clip 30;
  - training-only mean and population standard deviation;
  - climatology equal to the training mean of `Y`;
  - log-loss clip `1e-12` and calibration logit clip `1e-6`.
- **A1 admission:** a row trains only when `T + 12 × 300000 <= block_start`.
- **Folds:** ISO weeks with floors of 1000 rows and 20 weeks. The primary cadence is 15m; the hourly cadence is a diagnostic.
- **Bootstrap:** B = 2000, seed `20261120`, percentiles 0.025 and 0.975, at least 1900 valid draws, no refit.
- **Bins, routes and evaluator:** the probability bins `(0.44, 0.47, 0.50, 0.53, 0.56)`, the route table, the one-shot journal and `REFUSING_RERUN`.
- **Unchanged files:** `eligibility.py`, `folds.py`, `model.py`, `evaluate.py` and `__init__.py` are byte-identical to Cursor's.

## Provenance

| | |
|---|---|
| Cursor tip | `origin/cursor/range-position-4h-forecast-prototype-v1-08d8` @ `a7b0805e58831e317c1218c18da0ac4aa519bf90` |
| Original design | `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_DESIGN.md`, commit `483dc4028f3baa0ed5c4ef4d382639926f249937`, SHA256 `7a04ddb59bf752299d3566065f57d29ec7f81a685aa1a10ca62b40535ca143d7` |
| Original design JSON | SHA256 `2801aac6aee333b3f4ca226d89cf6f61d8c16a53c971702482e55a6874ff49b4` |
| Amendment A1 | SHA256 `6d0d93d34d031351fc363623247bab30ab02232b6f08fb46343a3ece46019ddf` |
| Parent census (A1) | SUPPORT `f63f7f970e8689a1b0f6290984278eab4a907f75efdea5d72f91c3d5ac7a2ebd`, FOLDS `798ee69e4bd6b7effd1c586c810214b76624a5aedf1bef986b884499dfca2ee2`, ADAPTER `3e5306104d183dbb474d7d7ab46e0b1e2a2370adc291aa3be7e35febba6a4f52` |
| Parent documents | vendored byte-identical under their original names in `docs/research/` |

The vendored code is in `scripts/research/rp4h_forecast_prototype_a2/`. `VENDORED.md` lists every source path, branch and blob.

| local | source blob | local blob |
|---|---|---|
| `__init__.py`, `eligibility.py`, `folds.py`, `model.py`, `evaluate.py` | `f4e87e8a…`, `e245654f…`, `ae2dd3ca…`, `3d0cfe96…`, `184ad44e…` | identical |
| `constants.py` / `market.py` / `support.py` | `40b2580b…` / `7a2044ed…` / `92af7e7e…` | adapted for A2 |
| `vendored_grid_constants.py` (incremental-replication `constants.py`) | `0f7de86699442a35f960f87ced319c3254a92c13` | identical |
| `vendored_grid.py` (incremental-replication `grid.py`) | `18112255083d4c04f2f316156782d0993266758f` | import line only |
| `vendored_bitmex_constants.py` (BitMEX temporal `constants.py`) | `927e115b6b5df65abe2c3c7ef69dc8bb2c7c7c28` | identical |
| `vendored_bitmex_sample.py` (BitMEX temporal `sample.py`) | `8387874f508d3b17df31c7bb4500d6b5ea0e2ba3` | import lines only |
| tests (`test_range_position_4h_forecast_prototype_v1.py`) | `a41e1c73110cde1f48fe716bf2ec0f94c3d58dab` | adapted, plus A2 tests |

`runtime_guard.py` is the one new code file.
- The vendored `folds.iso_parts` assumes nanosecond pandas timestamps. That holds under pandas 2.2.3, the version pinned in `requirements.txt`.
- Under pandas 3, every block start collapses to 1970. The guard refuses that runtime with `FOLD_CLOCK_RUNTIME_MISMATCH`.
- Neither `folds.py` nor the census logic changed.

## A2 support census (outcome-blind; counts only)

The census ran with Python 3.11.17, numpy 2.1.3 and pandas 2.2.3. A rebuild in memory reproduced both JSON files byte for byte.

| segment | feature rows | exact zeros dropped | labeled | 15m test rows | 15m test weeks | hourly test rows | hourly test weeks |
|---|---:|---:|---:|---:|---:|---:|---:|
| BITMEX_2016_2019 | 127,303 | 1,320 | 125,983 | 113,210 | 171 | 28,323 | 171 |
| BINANCE_2020_2024 | 175,372 | 63 | 175,309 | 162,084 | 242 | 40,523 | 242 |
| BINANCE_2025_2026 | **59,672** (A1 61,016) | **15** (A1 17) | **59,657** (A1 60,999) | **59,657** (A1 60,999) | **90** (A1 92) | **14,916** (A1 15,252) | **90** (A1 92) |
| total | | | | **334,951** (A1 336,293) | **503** (A1 505) | | |

**BitMEX and 2020–2024.** Every count, and both fold schedules (15m and hourly, every warm-up and test block), equal Cursor's A1 census exactly.

**2025–2026.**
- Feature rows equal Unit B's sample, 59,672. The masks are equal.
- ISO weeks 2026-W32 and 2026-W33 leave the test set.
- 2026-W31 loses Sunday 2026-08-02 and the three quarter-hour anchors of 2026-08-01 23:xx whose 1h future reaches it. Its 15m test rows go from 672 to 573, and its hourly test rows from 168 to 144.
- Test blocks W35–W41 keep their test rows. They train on 1,342 fewer 15m rows (336 hourly) and 2 fewer weeks.
- The first 2025 block is unchanged: 175,117 training rows, 261 weeks.
- The label proof checked 1,082 blocks and found 0 violations.

| A2 census file | SHA256 |
|---|---|
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_A2_SUPPORT.json` | `54b82c61636ab2121d437608a9432fa32847c5ee0beaa338b2247bd7be455839` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_A2_FOLDS.json` | `d03f1b907c23b039b7157502ed87f6d99101dbd7796586665f0b634958545153` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_A2_SUPPORT.md` | `6348c62dd376c59c7056a9df10a95666255de7782c58b125576e4db3b5110d4b` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_A2_ADAPTER.json` | `efd7b8a8c0646900c1f811c2b7d38dbe2206a69abc998920e58c31e0d7dcadd7` |

Pinned expected coverage for the market path: 113,210 / 162,084 / 59,657 rows and 171 / 242 / 90 weeks. The market path refuses any other count with `COVERAGE_MISMATCH`.

## Evidence class

Unchanged: `RETROSPECTIVE_FORECAST_PROTOTYPE / ALREADY_CONSUMED_SURFACES`. Unit B has already read `RP4H → R_1H` on the A2 2025–2026 surface, so this is not a pristine check. A2 removes only the exact-class E1-development exposure from that surface.

No product use, live probability, bot finding or trade rule follows from this unit.
