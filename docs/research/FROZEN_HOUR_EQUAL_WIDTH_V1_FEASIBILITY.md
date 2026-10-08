# FROZEN_HOUR_EQUAL_WIDTH_V1 — support census

Outcome labels were not computed. Counts are the size of a later estimand, not the estimand.
The information gate does not authorize that estimand.

- Unit: `FROZEN_HOUR_EQUAL_WIDTH_V1`
- Mode: `CONFIRMATION`
- Branch: `cursor/frozen-hour-equal-width-design-v1-08d8`
- HEAD at the run: `3b02de8380064aa2ce3fe384e86899e08d2b3778`
- Design commit: `5c3f6e6bdc4df8ef3ce7266b318253c42dada4a3`
- Design SHA256: `abb3283046277201278f2e952196e870e324009d86e39324d4fdca530b4cfef7`
- Code digest: `803dd81cb9fe981ff1f1e5825702641105f5ca8a6b60a42497ab2c7aefa93bcb`
- Surface: `DH1_BINANCE_SPOT_BTCUSDT_5M_V0` `2017-09-01` inclusive to `2020-01-01` exclusive
- Months requested: `2017-09` through `2019-12`
- Evidence class: `TIME_DISJOINT_OUTCOME_UNREAD`
- First access for this estimand: `true`
- outcome_read: `false`
- barrier_path_read: `false`
- 2025/2026 opened: `false`
- E1 opened: `false`
- Prospective opened: `false`
- Product opened: `false`
- Information floor: 614 paired outcome-eligible days and 100 ISO weeks
- UTC_00 information: `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`
- UTC_12 information: `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`
- Joint gate: `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`

ISO week labels of the last days of 2019 can fall in ISO year 2020. No 2020 bar was requested.
A noon life that reaches 2020-01-01 is truncated. The missing bars are not filled.

Panel: 243894 present bars, 1482 missing, grid 245376.
Off-grid opens left unplaced: 241. An open time that is not divisible by 300000 ms is not moved onto a bucket.

## UTC_00 (primary)

- calendar_days: 852
- formation_incomplete: 4
- formation_complete: 848
- nonpositive_width: 0
- close_not_strictly_inside: 20
- usable_real_geometry: 828
- lifespan_truncated: 0
- valid_equal_width_pseudo_geometry: 828
- solver_attempts: 828
- solver_success: 828
- scale_unbounded: 0
- scale_tolerance_failed: 0
- invalid_partner_geometry: 0
- collisions: 0
- partner_not_found: 0
- weekday_group_too_small: 0
- partner_failures: 0
- no_real_interaction: 1
- first_real_interaction: 827
- ambiguous_real: 0
- high_side_real: 409
- low_side_real: 418
- immediate_real: 221
- outcome_window_incomplete_real: 6
- one_sided_outcome_eligible_real: 821
- no_pseudo_interaction: 1
- first_pseudo_interaction: 827
- ambiguous_pseudo: 1
- high_side_pseudo: 413
- low_side_pseudo: 413
- immediate_pseudo: 200
- outcome_window_incomplete_pseudo: 9
- one_sided_outcome_eligible_pseudo: 817
- paired_outcome_eligible: 817
- paired_neither_immediate: 488
- paired_iso_weeks: 123
- solver_rel_width_error_max: 1.0142121012243703e-13
- asymmetry_abs_diff_max: 1.3034018309099338e-13
- information_status: `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`
- usable_by_year: {"2017": 111, "2018": 356, "2019": 361}
- valid_pseudo_by_year: {"2017": 111, "2018": 356, "2019": 361}
- paired_by_year: {"2017": 111, "2018": 353, "2019": 353}
- usable_by_weekday: {"Fri": 116, "Mon": 120, "Sat": 120, "Sun": 118, "Thu": 119, "Tue": 117, "Wed": 118}
- paired_by_weekday: {"Fri": 116, "Mon": 117, "Sat": 120, "Sun": 117, "Thu": 117, "Tue": 115, "Wed": 115}

## UTC_12 (diagnostic, not adoptable)

- calendar_days: 852
- formation_incomplete: 4
- formation_complete: 848
- nonpositive_width: 0
- close_not_strictly_inside: 10
- usable_real_geometry: 838
- lifespan_truncated: 1
- valid_equal_width_pseudo_geometry: 838
- solver_attempts: 838
- solver_success: 838
- scale_unbounded: 0
- scale_tolerance_failed: 0
- invalid_partner_geometry: 0
- collisions: 0
- partner_not_found: 0
- weekday_group_too_small: 0
- partner_failures: 0
- no_real_interaction: 3
- first_real_interaction: 835
- ambiguous_real: 1
- high_side_real: 445
- low_side_real: 389
- immediate_real: 222
- outcome_window_incomplete_real: 1
- one_sided_outcome_eligible_real: 833
- no_pseudo_interaction: 0
- first_pseudo_interaction: 838
- ambiguous_pseudo: 0
- high_side_pseudo: 450
- low_side_pseudo: 388
- immediate_pseudo: 229
- outcome_window_incomplete_pseudo: 1
- one_sided_outcome_eligible_pseudo: 837
- paired_outcome_eligible: 833
- paired_neither_immediate: 483
- paired_iso_weeks: 123
- solver_rel_width_error_max: 1.2667057127756146e-13
- asymmetry_abs_diff_max: 1.5815126985785355e-13
- information_status: `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`
- usable_by_year: {"2017": 114, "2018": 362, "2019": 362}
- valid_pseudo_by_year: {"2017": 114, "2018": 362, "2019": 362}
- paired_by_year: {"2017": 113, "2018": 361, "2019": 359}
- usable_by_weekday: {"Fri": 119, "Mon": 120, "Sat": 121, "Sun": 119, "Thu": 119, "Tue": 121, "Wed": 119}
- paired_by_weekday: {"Fri": 119, "Mon": 119, "Sat": 120, "Sun": 118, "Thu": 119, "Tue": 121, "Wed": 117}

No resolution, extension, reentry, excursion, occupancy, or paired effect is in this file.
