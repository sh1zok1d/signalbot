# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 — pre-outcome amendment A1

**Status.** Label-availability repair. Written while the forecast model is unfitted. No market probability, coefficient, Brier score, log loss, AUROC, or bootstrap draw on market rows was computed. This file does not replace the original design and does not retune the model.

## Provenance

| | |
| --- | --- |
| Original design | `docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_DESIGN.md` |
| Original design JSON | `docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_DESIGN.json` |
| Original design commit | `483dc4028f3baa0ed5c4ef4d382639926f249937` |
| Original design SHA256 | `7a04ddb59bf752299d3566065f57d29ec7f81a685aa1a10ca62b40535ca143d7` |
| Original design JSON SHA256 | `2801aac6aee333b3f4ca226d89cf6f61d8c16a53c971702482e55a6874ff49b4` |
| Support census before A1 | SHA256 `8400e2f20abb79ea074ce2ea93614c1675987c7ef55282060b43c9c0e576abc4` |
| Fold schedule before A1 | SHA256 `ec7a94e1f5c24928c756eda5ead050beb4c67da5f233784bb3fe1b98550e1bb5` |
| Support census after A1 | SHA256 `f63f7f970e8689a1b0f6290984278eab4a907f75efdea5d72f91c3d5ac7a2ebd` |
| Fold schedule after A1 | SHA256 `798ee69e4bd6b7effd1c586c810214b76624a5aedf1bef986b884499dfca2ee2` |
| `model_fit` | false |
| `OWNER_GO` | false |
| What changed | the training-admission clock |

The original design admitted every labeled anchor with `T` strictly before Monday 00:00:00Z. `R_1H(T)` is the log return from `T` to `T + 1h`, so that label is known only at `T + 1h`. A Sunday 23:15, 23:30, or 23:45 anchor has `T` before Monday and a label that arrives after Monday 00:00. A1 closes that gap.

Unchanged: the target, the zero-return rule, the three segments, eligibility, the baseline features, the candidate feature, the unpenalized Newton logistic, the iteration cap, the gradient tolerance, the sigmoid clip, standardization, climatology, the loss definitions, the bootstrap seed `20261120`, `B = 2000`, the percentile pair, the minimum valid draws, the floors 1000 and 20, the route table, and the original design bytes.

## Formula

A training row is admitted only when

`T + HORIZON * BAR_MS <= block_start`

with `HORIZON = 12` and `BAR_MS = 300000`. The label is available at `T + 3600000`. Sunday 23:00 is admitted, because its label is available at Monday 00:00. Sunday 23:15, 23:30, and 23:45 are excluded.

The same predicate is applied inside `build_training_matrix`, which is the matrix the walker fits. The fold census uses the same function. A mask that keeps a late label, a non-finite value, or a disallowed source raises `FORECAST_IMPLEMENTATION_INVALID`. There is no fallback fit and no penalty term.

## Files

Changed for the admission rule, the scorer, or the rewritten census:

- `scripts/research/range_position_4h_forecast_prototype_v1/folds.py`
- `scripts/research/range_position_4h_forecast_prototype_v1/evaluate.py`
- `scripts/research/range_position_4h_forecast_prototype_v1/support.py`
- `scripts/research/range_position_4h_forecast_prototype_v1/constants.py`
- `docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_SUPPORT.json`
- `docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_SUPPORT.md`
- `docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_FOLDS.json`
- `tests/research/test_range_position_4h_forecast_prototype_v1.py`
- `docs/CURRENT_RESEARCH_STATE.md`
- `docs/RESEARCH_LEDGER.md`
- `docs/DOCUMENTATION_INDEX.md`

The original design markdown and design JSON are byte-identical to commit `483dc4028f3baa0ed5c4ef4d382639926f249937`.

## Census after the repair

Labeled counts are unchanged: BitMEX `125983`, Binance 2020–2024 `175309`, Binance 2025–2026 `60999`. Primary test rows stay `113210 + 162084 + 60999`. Primary test weeks stay 171, 242, and 92. Training-week counts on every matched test block stay the same. Hourly training counts stay the same, because the only exact hour in the last hour before Monday is Sunday 23:00 and that label is available at Monday 00:00.

On the 15-minute cadence, each test block's training count falls by the labeled anchors in `(block_start − 1h, block_start)`.

| segment | cadence | first n_train before | first n_train after | first train weeks | max drop | min drop |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| BitMEX 2016–2019 | 15m | 12773 | 12770 | 20 | 3 | 2 |
| BitMEX 2016–2019 | hourly | 3187 | 3187 | 20 | 0 | 0 |
| Binance 2020–2024 | 15m | 13225 | 13222 | 20 | 3 | 2 |
| Binance 2020–2024 | hourly | 3307 | 3307 | 20 | 0 | 0 |
| Binance 2025–2026 | 15m | 175120 | 175117 | 261 | 3 | 0 |
| Binance 2025–2026 | hourly | 43782 | 43782 | 261 | 0 | 0 |

The 15-minute drop is 3 on 169 BitMEX blocks, 240 Binance 2020–2024 blocks, and 91 Binance 2025–2026 blocks. It is 2 on BitMEX Mondays `2016-11-07` and `2019-05-13`, and on Binance Mondays `2022-12-19` and `2023-10-02`: one of the three quarter-hour anchors in that open hour is absent from the labeled set. It is 0 on the Monday `2026-08-24`, whose preceding hour sits in the stored August hole. The latest training label available for that block is `2026-08-16T00:00:00Z`.

The shared Monday `2024-12-30` still separates the 2024 anchors from the 2025 anchors. The 2025 block's first training count is `175117`. Its latest training label is available at `2024-12-30T00:00:00Z`. The three anchors `2024-12-29T23:15`, `23:30`, and `23:45` are the three exclusions. Binance training for that block does not include BitMEX rows.

Every block with at least one training row, primary and hourly, warmup and test, satisfies `max(train_label_available_at) <= block_start`. The census checked 1086 such blocks and recorded 0 violations.

## Evaluator

`evaluate_frame` walks an in-memory frame: training-matrix admission, training-only mean and population standard deviation, climatology equal to the training mean of `Y`, unpenalized baseline and candidate logistics, stored test probabilities, Brier score, log loss, block bootstrap of those stored probabilities, calibration slope, and the frozen route. The bootstrap does not refit. A convergence failure, a late label, a non-finite value, or a broken invariant returns `FORECAST_IMPLEMENTATION_INVALID`.

`main` and `run_market` exit `AWAITING_OWNER_GO` before any price load. The market frame is not assembled in this revision. Synthetic checks cover the Sunday boundary, both cadences, the 2024/2025 Monday, and Binance-only training. They do not score BitMEX or Binance prices.

The amendment SHA256 is pinned beside the design hashes. It is not written in this file.
