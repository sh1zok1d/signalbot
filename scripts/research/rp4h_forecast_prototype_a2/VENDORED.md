# rp4h_forecast_prototype_a2: vendored sources

The package holds Cursor's frozen `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1` with amendment A2. A2 changes only the 2025–2026 data source; see `docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_AMENDMENT_A2.md`.

- **Source tip:** `origin/cursor/range-position-4h-forecast-prototype-v1-08d8` at `a7b0805e58831e317c1218c18da0ac4aa519bf90`.
- **Blob ids:** git blob ids (`git rev-parse <tip>:<path>`, or `git hash-object <file>` locally).
- **"identical":** the local file has the same blob id as the source.

## Prototype package

The source directory is `scripts/research/range_position_4h_forecast_prototype_v1/`.

| local file | source blob | local blob | state |
|---|---|---|---|
| `__init__.py` | `f4e87e8a82d6e97ba0f9528d84403550b6b0d974` | same | identical |
| `eligibility.py` | `e245654f4d181968b53bd9662e677dd20dbacfa6` | same | identical |
| `folds.py` | `ae2dd3ca9ee3fb56467d5971c0b3d24ecd4b4659` | same | identical |
| `model.py` | `3d0cfe9624ba148bc09d9d0e79c115e90f248b5d` | same | identical |
| `evaluate.py` | `184ad44e8d2caf0007c85092025ebb871b8d38e2` | same | identical |
| `constants.py` | `40b2580b006630cfbc97b003429699dd03005f07` | changed | A2: the unit label, the parent label, the A2 paths, the 2025–2026 manifest pins, the excluded window and the A2 census counts. The scientific constants are unchanged. |
| `market.py` | `7a2044ed539d640a36106a8839b2c41fa4a69842` | changed | `features` is imported from `vendored_grid`. The 2025–2026 file digest is replaced by the Unit B manifest digest. Adds the A2 freeze gate, the fold-clock guard, A2 coverage totals, an A2 journal path and A2 report hashes. |
| `support.py` | `92af7e7e76ee8a3139fc43d92a883683e664d642` | changed | Imports now point to the vendored modules and Unit B. `_modern_grid` reads Unit B's `load_series`, `census`, `assert_census` and `place`, then checks the result against the `build_sample` mask. Adds the comparison with the parent A1 census, the A2 payload fields and the A2 markdown title. |

## Dependency modules

The same blob ids appear on the dependency branches below and on the forecast tip.

| local file | source branch (tip) | source path | source blob | edit |
|---|---|---|---|---|
| `vendored_grid_constants.py` | `origin/cursor/range-position-4h-incremental-replication-v1-08d8` (`d04b6559a1fb9da57552ebc7fd930944e6976ffe`) | `scripts/research/range_position_4h_incremental_replication_v1/constants.py` | `0f7de86699442a35f960f87ced319c3254a92c13` | none (identical) |
| `vendored_grid.py` | same | `scripts/research/range_position_4h_incremental_replication_v1/grid.py` | `18112255083d4c04f2f316156782d0993266758f` | one import line: `from . import vendored_grid_constants as K` (local blob `36f2a525dea5fbe385f456ff3070b2c3f8ced72f`) |
| `vendored_bitmex_constants.py` | `origin/cursor/range-position-4h-bitmex-temporal-replication-v1-08d8` (`027948e2b91a31259ebb6e8ef2aec10ab514561e`) | `scripts/research/range_position_4h_bitmex_temporal_replication_v1/constants.py` | `927e115b6b5df65abe2c3c7ef69dc8bb2c7c7c28` | none (identical) |
| `vendored_bitmex_sample.py` | same | `scripts/research/range_position_4h_bitmex_temporal_replication_v1/sample.py` | `8387874f508d3b17df31c7bb4500d6b5ea0e2ba3` | two import lines: `from .vendored_grid import place`, `from . import vendored_bitmex_constants as K` (local blob `db5391abfb4207cd817083ae559a5cdb01f88909`) |

Cursor's 2025–2026 sample module (`range_position_4h_binance_2025_2026_temporal_replication_v1/sample.py`) is **not** vendored. A2 replaces it with `scripts.research.rp4h_binance_2025_2026_temporal_v1`, which is already in this repository.

## New A2 file

- `runtime_guard.py`. `folds.iso_parts` is vendored unchanged, and it assumes nanosecond pandas timestamps. That holds under pandas 2.2.3, the version pinned in `requirements.txt`. Under pandas 3, `unit="ms"` gives millisecond timestamps, and every block start becomes 1970. The guard refuses such a runtime with `FOLD_CLOCK_RUNTIME_MISMATCH`.

## Parent documents

These files are vendored byte-identical under their original paths in `docs/research/`.

| file | blob | SHA256 |
|---|---|---|
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_DESIGN.md` | `795b06b5ab99fe590c789a5dba7be17b0137e157` | `7a04ddb59bf752299d3566065f57d29ec7f81a685aa1a10ca62b40535ca143d7` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_DESIGN.json` | `98b2c22667f6e038a63daf779e2dbc52af41e689` | `2801aac6aee333b3f4ca226d89cf6f61d8c16a53c971702482e55a6874ff49b4` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_AMENDMENT_A1.md` | `8942c0837755b1c6d9f6fdc260abab66227ba8f6` | `6d0d93d34d031351fc363623247bab30ab02232b6f08fb46343a3ece46019ddf` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_ADAPTER.json` | `66f051ddce6554139e7b1a24b799db35fec3a451` | `3e5306104d183dbb474d7d7ab46e0b1e2a2370adc291aa3be7e35febba6a4f52` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_SUPPORT.json` | `b5cab9dfd83cb6932121dfe208cec057c67f7a5e` | `f63f7f970e8689a1b0f6290984278eab4a907f75efdea5d72f91c3d5ac7a2ebd` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_FOLDS.json` | `66c89f72c6e521dd0431bfb458628117d32562c0` | `798ee69e4bd6b7effd1c586c810214b76624a5aedf1bef986b884499dfca2ee2` |
| `RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_SUPPORT.md` | `afdbb1e3cde941408923a086d9afb4e06605bf45` | `07cc476dae4e9435da3aafc890f72039681710a67a863b0fcec87a26f9792b74` |

## Tests

`tests/research/test_rp4h_forecast_prototype_a2.py` is vendored from `tests/research/test_range_position_4h_forecast_prototype_v1.py`, blob `a41e1c73110cde1f48fe716bf2ec0f94c3d58dab`.

- **Adapted:** the package path, the A2 census numbers and the A2 manifest fields. The writes to `/opt/cursor/artifacts` are removed.
- **Added:** synthetic A2 tests.
