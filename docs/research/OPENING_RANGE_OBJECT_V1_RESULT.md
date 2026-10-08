# OPENING_RANGE_OBJECT_V1 — one historical outcome read

UTC_00, UTC_08, and UTC_16 cleared and the funding-hour contrasts did not separate them. This is a shared clock, not a funding-causality claim.

- Route: `FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`
- opening_wording_allowed: `false`
- hour_adopted: `None`
- Claim: `L2_HISTORICAL_DIFFERENCE_ON_DISCOVERY_SURFACE`
- Claim ceiling: `L2`
- Atlas state name for this read: `CLOSED_ON_SURFACE`
- outcome_read: `true`
- Read at: `2026-10-08T20:41:03Z`
- Surface: `CORE_BTC_BINANCE_V0` `2020-01-01` inclusive to `2025-01-01` exclusive
- Evaluator commit: `fb434d3c467ebde6d00b93c3551d3a965f789eb5`
- Code digest: `f4774f348672864b3e6c9ffca97acca42bdc4a1744104a76142186cf4ea7c5d1`
- Touch-time handling: `PUBLISH_AUDIT_NO_CORRECTION`

Touch time was not used to rematch, stratify, or add a sensitivity.

## Foundation

Family `FOUNDATION_CELL_EFFECTS`. Simultaneous intervals are single-step standardized max-stat intervals from the joint week bootstrap. Marginal intervals are percentile intervals.

- UTC_00: real 0.9179755671902269, pseudo 0.8231529959278651, delta 0.09482257126236183, N 1719, weeks 262, marginal [0.06554117178177524, 0.12573608971459116], simultaneous [0.057620747673490014, 0.13202439485123366], passes `true`
- UTC_08: real 0.9714452214452215, pseudo 0.9055944055944056, delta 0.06585081585081586, N 1716, weeks 262, marginal [0.04624887959468655, 0.0878438485255816], simultaneous [0.04046172984011863, 0.09123990186151308], passes `true`
- UTC_12: real 0.965962441314554, pseudo 0.9166666666666666, delta 0.04929577464788732, N 1704, weeks 262, marginal [0.03110009260688378, 0.070042993029698], simultaneous [0.025184163601035883, 0.07340738569473876], passes `true`
- UTC_16: real 0.9387514723203769, pseudo 0.8639575971731449, delta 0.07479387514723204, N 1698, weeks 262, marginal [0.052166526498908954, 0.09899941002161612], simultaneous [0.04547196530544434, 0.10411578498901974], passes `true`

## Clock contrasts

- delta UTC_00 minus UTC_08: 0.02897175541154598, marginal [0.003869017296288381, 0.0559079400827946], simultaneous [-0.002360610425532386, 0.060304121248624346], passes `false`
- delta UTC_00 minus UTC_12: 0.045526796614474514, marginal [0.018441341958192754, 0.07600795760012065], simultaneous [0.011798496247656567, 0.07925509698129246], passes `true`
- delta UTC_00 minus UTC_16: 0.020028696115129793, marginal [-0.007513200593846407, 0.04918754695369318], simultaneous [-0.013086748454723275, 0.05314414068498286], passes `false`

## Non-foundation map on UTC_00

- DIRECTION_EXTENSION_FIRST (BARRIER_FAMILY_DECOMPOSITION): real 0.506108202443281, pseudo 0.43571844095404305, delta 0.07038976148923792, N 1719, marginal [0.039396310780653185, 0.10239069732149628], bootstrap p 0.0004997501249375312, Holm p 0.0014992503748125937, scale 0.03, passes `true`
- OUTSIDE_OCCUPANCY (INDEPENDENT_OBSERVABLE): real 0.4717980414969944, pseudo 0.4804392088423502, delta -0.008641167345355827, N 1719, marginal [-0.029099395642027282, 0.013180367140179347], bootstrap p 0.42528735632183906, Holm p 0.42528735632183906, scale 0.03, passes `false`
- OUTWARD_EXCURSION (INDEPENDENT_OBSERVABLE): real 1.0665417868447058, pseudo 1.3309779506106267, delta -0.2644361637659211, N 1719, marginal [-0.4394672355581854, -0.11468206289664873], bootstrap p 0.0009995002498750624, Holm p 0.001999000499750125, scale 0.25, passes `true`
- candidates, declaration order: `[{"row": "DIRECTION_EXTENSION_FIRST", "role": "BARRIER_FAMILY_DECOMPOSITION"}, {"row": "OUTWARD_EXCURSION", "role": "INDEPENDENT_OBSERVABLE"}]`

## Stability

Calendar year needs 30 paired days. Real-interaction side needs 100. A slice is not a winner.

- UTC_00: `{"calendar_year": {"2020": {"eligible": true, "n_pairs": 352, "paired_effect": -0.019886363636363636, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2021": {"eligible": true, "n_pairs": 319, "paired_effect": -0.05642633228840126, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2022": {"eligible": true, "n_pairs": 355, "paired_effect": 0.030985915492957747, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2023": {"eligible": true, "n_pairs": 337, "paired_effect": 0.3353115727002967, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2024": {"eligible": true, "n_pairs": 356, "paired_effect": 0.1797752808988764, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}, "real_side": {"high": {"eligible": true, "n_pairs": 825, "paired_effect": 0.10545454545454545, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "low": {"eligible": true, "n_pairs": 894, "paired_effect": 0.08501118568232663, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}}`
- UTC_08: `{"calendar_year": {"2020": {"eligible": true, "n_pairs": 345, "paired_effect": 0.020289855072463767, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2021": {"eligible": true, "n_pairs": 317, "paired_effect": -0.012618296529968454, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2022": {"eligible": true, "n_pairs": 355, "paired_effect": 0.008450704225352112, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2023": {"eligible": true, "n_pairs": 340, "paired_effect": 0.22647058823529412, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2024": {"eligible": true, "n_pairs": 359, "paired_effect": 0.08356545961002786, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}, "real_side": {"high": {"eligible": true, "n_pairs": 840, "paired_effect": 0.07142857142857142, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "low": {"eligible": true, "n_pairs": 876, "paired_effect": 0.06050228310502283, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}}`
- UTC_12: `{"calendar_year": {"2020": {"eligible": true, "n_pairs": 348, "paired_effect": 0.0028735632183908046, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2021": {"eligible": true, "n_pairs": 322, "paired_effect": -0.015527950310559006, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2022": {"eligible": true, "n_pairs": 351, "paired_effect": 0.03418803418803419, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2023": {"eligible": true, "n_pairs": 327, "paired_effect": 0.1834862385321101, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2024": {"eligible": true, "n_pairs": 356, "paired_effect": 0.0449438202247191, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}, "real_side": {"high": {"eligible": true, "n_pairs": 832, "paired_effect": 0.05048076923076923, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "low": {"eligible": true, "n_pairs": 872, "paired_effect": 0.0481651376146789, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}}`
- UTC_16: `{"calendar_year": {"2020": {"eligible": true, "n_pairs": 345, "paired_effect": -0.014492753623188406, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2021": {"eligible": true, "n_pairs": 321, "paired_effect": -0.012461059190031152, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2022": {"eligible": true, "n_pairs": 348, "paired_effect": 0.04597701149425287, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2023": {"eligible": true, "n_pairs": 326, "paired_effect": 0.2147239263803681, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "2024": {"eligible": true, "n_pairs": 358, "paired_effect": 0.13966480446927373, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}, "real_side": {"high": {"eligible": true, "n_pairs": 854, "paired_effect": 0.05035128805620609, "role": "DESCRIPTIVE_NOT_A_SEARCH"}, "low": {"eligible": true, "n_pairs": 844, "paired_effect": 0.0995260663507109, "role": "DESCRIPTIVE_NOT_A_SEARCH"}}}`

No resolution clock, realized-volatility transition, traverse endpoint, extra hour, extra horizon, or extra barrier fraction was computed.
No 2025/2026 object, no E1 window, no product sample, no prospective sample.
