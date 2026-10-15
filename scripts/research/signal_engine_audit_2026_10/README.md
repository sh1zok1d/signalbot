# Signal engine audit (2026-10-15) — scripts

Report: `docs/PULSY_SIGNAL_ENGINE_AUDIT_2026-10-15.md`. Diagnostic audit, not a research unit; nothing here changes the product.

Order: `product_events.py` → `pseudo_pairs.py` → `analyze_real.py` → `analyze_pairs.py` → `exposed_2025.py`.

- `product_events.py` — structural first touches from the PRODUCT constructor (`beta.levels.structural_first_touches`), outcomes over j+1..j+48 with the product barriers, T15 features (END_POSITION_X, own 15m move, OKX/Bybit OVMM from the pinned repo files), RV windows, B0 at T15 (Monte-Carlo), tradeable expressions.
- `pseudo_pairs.py` — half-rotation pseudo levels per the frozen `level_touch_degradation_v1/control.py` definition, on the product episodes; asserts the touch re-implementation matches the product constructor; matched pairs.
- `analyze_real.py` — T0/T15 economics and #363 incrementality (walk-forward 2021-2024) on all real touches.
- `analyze_pairs.py` — paired and unpaired real-vs-pseudo contrasts (#357, #365, #368, #361/#363 specificity), pair-selection diagnostics, economics on both arms.
- `exposed_2025.py` — T15 models trained 2020-2024 scored once on the exposed 2025-01..2026-07 touches; B0 calibration by period.
- `levels.py`, `race_analysis.py` — earlier provisional constructor (kept for history; `load_btc`, `load_venue`, `b0_probs` are reused).

Data: Binance USD-M BTCUSDT 5m cache from `scripts/research/independent_diagnostics_2026_10/build.py` (`btc5m.pkl`); cross-venue closes from `docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0` (end 2024-12). Results in `results/` (JSON, logs; pickles are rebuilt by the scripts).
