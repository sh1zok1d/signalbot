# LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1

Routing: `NO_INCREMENTAL_ZONE_TRADED_ACTIVITY`
Claim ceiling: `L2` / `DISCOVERY_ONLY`
Design SHA: `ee2abb0dd3c4c6b0b9d2e2e1a0b48ba1ebfa6e19`
Outcomes read: True
Overall class: `NONE`
Product integration: False
Successor: `NONE`

The question is whether unsigned executed notional inside the frozen structural zone
during the first 15 minutes adds information about later BREAK versus REJECT after
END_POSITION_X, OTHER_VENUE_MEDIAN_MOVE, and TOUCH_OFFSET_SECONDS.

Unresolved feature-complete N=1215
Resolved primary N=1044
Late counts: {'BREAK': 432, 'REJECT': 612, 'NEITHER': 170, 'AMBIGUOUS': 1}
RAW_TOUCH_MATCH_RATE=0.9870689655172413

Baseline, no ZA feature
- END_POSITION_X +13.13 pp CI [+8.70, +17.39] pp
- OTHER_VENUE_MEDIAN_MOVE +9.33 pp CI [+5.35, +13.35] pp
- TOUCH_OFFSET_SECONDS -0.09 pp CI [-3.34, +2.97] pp
- N=1044 clusters=238

### ZONE_NOTIONAL_INTENSITY_15M

effect -0.95 pp per +1 SD, CI [-4.25, +2.27] pp
p=0.557414 q=0.557414 N=1044 clusters=238 bootstrap=2000/2000
class `NONE` specificity `NOT_APPLIED` statistical=False conjunction=False failed=['statistical']

Tertiles of late BREAK rate
- T1: 31.67% N=360
- T2: 42.24% N=348
- T3: 50.89% N=336

Years
- 2020: -2.65 pp N=147
- 2021: -2.87 pp N=230
- 2022: -2.11 pp N=239
- 2023: +3.19 pp N=194
- 2024: -1.39 pp N=234
LOYO
- omit_2020: -0.60 pp N=897
- omit_2021: -0.63 pp N=814
- omit_2022: -0.56 pp N=805
- omit_2023: -2.32 pp N=850
- omit_2024: -0.82 pp N=810
Family
- DAY: -0.62 pp N=918
- WEEK: -3.03 pp N=114
- MONTH: NA N=12
Side
- resistance: -1.26 pp N=584
- support: -0.66 pp N=460

matched status `NOT_APPLIED` N=0
matched real NA CI NA
matched pseudo NA CI NA
delta NA CI NA

### ZONE_NOTIONAL_SHARE_15M

effect -1.76 pp per +1 SD, CI [-5.19, +1.48] pp
p=0.308931 q=0.557414 N=1044 clusters=238 bootstrap=2000/2000
class `NONE` specificity `NOT_APPLIED` statistical=False conjunction=False failed=['statistical']

Tertiles of late BREAK rate
- T1: 37.05% N=359
- T2: 41.34% N=358
- T3: 46.18% N=327

Years
- 2020: -6.33 pp N=147
- 2021: -3.56 pp N=230
- 2022: -5.86 pp N=239
- 2023: +4.84 pp N=194
- 2024: -2.70 pp N=234
LOYO
- omit_2020: -1.26 pp N=897
- omit_2021: -1.39 pp N=814
- omit_2022: -0.82 pp N=805
- omit_2023: -4.28 pp N=850
- omit_2024: -1.44 pp N=810
Family
- DAY: -0.92 pp N=918
- WEEK: -9.86 pp N=114
- MONTH: NA N=12
Side
- resistance: -2.48 pp N=584
- support: -0.35 pp N=460

matched status `NOT_APPLIED` N=0
matched real NA CI NA
matched pseudo NA CI NA
delta NA CI NA

No product surface was changed. No successor was started.
A historical association is not a current probability and not a trading instruction.
