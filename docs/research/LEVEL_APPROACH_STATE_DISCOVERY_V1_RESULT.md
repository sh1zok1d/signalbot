# LEVEL_APPROACH_STATE_DISCOVERY_V1 — result

MODE = `DISCOVERY`. Tracks: STRUCTURE, PRODUCT_EVIDENCE.
Dependencies: `dfc9e0f04358de15606382472badeb5aee787039` (PR #352), `c3d39bffda861b535605a98205d7578c0c84c782` (PR #353), `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26` (PR #354 methodology).
Design note commit `778e23dd4ea257bc7f42698b95843fecd554fb29`.

## routing

`STRUCTURE_PRESENT_BUT_UNSTABLE`. Atlas state `CLOSED_ON_SURFACE`. Claim ceiling for a selected cell is DISCOVERY_ONLY; the family statement is `L2`.
SUCCESSOR_CANDIDATE = NONE.
PRODUCT_INTEGRATION_CANDIDATE = NO.

## primary matrix

Adjusted Δ frequency per +1 SD. 95% cluster-bootstrap interval. q is Benjamini-Hochberg within the 21 primary slopes, q cut 0.1.

| feature | outcome | coef | 95% | q | N |
|---|---|---:|---|---:|---:|
| velocity | BREAK | -3.9 pp | -7.3 pp..-0.5 pp | 0.122 | 1973 |
| velocity | REJECT | +1.2 pp | -2.3 pp..+4.6 pp | 0.668 | 1973 |
| velocity | NEITHER | +2.7 pp | +0.1 pp..+5.3 pp | 0.166 | 1973 |
| efficiency | BREAK | -2.7 pp | -6.1 pp..+0.5 pp | 0.225 | 1973 |
| efficiency | REJECT | -1.7 pp | -5.0 pp..+1.7 pp | 0.527 | 1973 |
| efficiency | NEITHER | +4.4 pp | +2.2 pp..+6.8 pp | 0.002 | 1973 |
| persistence | BREAK | -2.2 pp | -4.7 pp..+0.5 pp | 0.225 | 1973 |
| persistence | REJECT | +0.7 pp | -2.1 pp..+3.4 pp | 0.668 | 1973 |
| persistence | NEITHER | +1.5 pp | -0.4 pp..+3.4 pp | 0.225 | 1973 |
| acceleration | BREAK | -0.4 pp | -2.6 pp..+1.8 pp | 0.764 | 1973 |
| acceleration | REJECT | +0.6 pp | -1.7 pp..+2.9 pp | 0.668 | 1973 |
| acceleration | NEITHER | -0.3 pp | -2.1 pp..+1.5 pp | 0.764 | 1973 |
| range_state | BREAK | +0.8 pp | -1.7 pp..+3.3 pp | 0.668 | 1973 |
| range_state | REJECT | +1.2 pp | -1.4 pp..+3.7 pp | 0.569 | 1973 |
| range_state | NEITHER | -1.9 pp | -4.1 pp..+0.2 pp | 0.225 | 1973 |
| rel_volume | BREAK | +1.7 pp | -0.9 pp..+4.4 pp | 0.360 | 1973 |
| rel_volume | REJECT | +1.0 pp | -1.8 pp..+3.7 pp | 0.658 | 1973 |
| rel_volume | NEITHER | -2.7 pp | -4.9 pp..-0.7 pp | 0.059 | 1973 |
| dwell | BREAK | -1.7 pp | -3.7 pp..+0.5 pp | 0.225 | 1973 |
| dwell | REJECT | -3.0 pp | -5.3 pp..-0.7 pp | 0.059 | 1973 |
| dwell | NEITHER | +4.7 pp | +2.6 pp..+6.7 pp | 0.000 | 1973 |

## shapes

| feature | outcome | shape | low | mid | high | high−low |
|---|---|---|---:|---:|---:|---|
| velocity | BREAK | monotonic | 33.1% (N=658) | 38.1% (N=657) | 39.4% (N=658) | +6.2 pp (+1.1 pp..+11.2 pp), N=1316 |
| velocity | REJECT | near_zero | 44.5% (N=658) | 47.8% (N=657) | 46.5% (N=658) | +2.0 pp (-3.3 pp..+7.5 pp), N=1316 |
| velocity | NEITHER | monotonic | 22.3% (N=658) | 14.2% (N=657) | 14.1% (N=658) | -8.2 pp (-12.3 pp..-4.2 pp), N=1316 |
| efficiency | BREAK | near_zero | 36.0% (N=658) | 35.9% (N=657) | 38.6% (N=658) | +2.6 pp (-2.4 pp..+7.9 pp), N=1316 |
| efficiency | REJECT | near_zero | 44.1% (N=658) | 49.3% (N=657) | 45.4% (N=658) | +1.4 pp (-3.8 pp..+6.6 pp), N=1316 |
| efficiency | NEITHER | u_shape | 19.9% (N=658) | 14.8% (N=657) | 16.0% (N=658) | -4.0 pp (-8.1 pp..+0.1 pp), N=1316 |
| persistence | BREAK | near_zero | 36.1% (N=670) | 36.8% (N=789) | 37.9% (N=514) | +1.8 pp (-3.5 pp..+7.5 pp), N=1184 |
| persistence | REJECT | near_zero | 45.2% (N=670) | 46.5% (N=789) | 47.3% (N=514) | +2.1 pp (-3.8 pp..+7.7 pp), N=1184 |
| persistence | NEITHER | monotonic | 18.7% (N=670) | 16.7% (N=789) | 14.8% (N=514) | -3.9 pp (-8.1 pp..+0.2 pp), N=1184 |
| acceleration | BREAK | u_shape | 39.6% (N=657) | 35.3% (N=657) | 35.7% (N=659) | -3.9 pp (-9.0 pp..+1.1 pp), N=1316 |
| acceleration | REJECT | near_zero | 46.1% (N=657) | 43.8% (N=657) | 48.9% (N=659) | +2.7 pp (-2.3 pp..+8.1 pp), N=1316 |
| acceleration | NEITHER | near_zero | 14.3% (N=657) | 20.9% (N=657) | 15.5% (N=659) | +1.2 pp (-2.5 pp..+5.1 pp), N=1316 |
| range_state | BREAK | monotonic | 32.7% (N=657) | 37.7% (N=658) | 40.1% (N=658) | +7.4 pp (+2.4 pp..+12.3 pp), N=1315 |
| range_state | REJECT | near_zero | 44.1% (N=657) | 48.0% (N=658) | 46.7% (N=658) | +2.5 pp (-2.6 pp..+7.9 pp), N=1315 |
| range_state | NEITHER | monotonic | 23.1% (N=657) | 14.3% (N=658) | 13.2% (N=658) | -9.9 pp (-14.0 pp..-5.8 pp), N=1315 |
| rel_volume | BREAK | monotonic | 32.5% (N=658) | 36.1% (N=657) | 41.9% (N=658) | +9.4 pp (+4.4 pp..+14.4 pp), N=1316 |
| rel_volume | REJECT | u_shape | 43.0% (N=658) | 49.3% (N=657) | 46.5% (N=658) | +3.5 pp (-1.7 pp..+8.7 pp), N=1316 |
| rel_volume | NEITHER | monotonic | 24.5% (N=658) | 14.6% (N=657) | 11.6% (N=658) | -12.9 pp (-16.7 pp..-8.8 pp), N=1316 |
| dwell | BREAK | monotonic | 39.6% (N=949) | 34.7% (N=378) | 34.1% (N=646) | -5.6 pp (-10.3 pp..-1.0 pp), N=1595 |
| dwell | REJECT | monotonic | 48.6% (N=949) | 45.2% (N=378) | 43.5% (N=646) | -5.1 pp (-9.8 pp..-0.1 pp), N=1595 |
| dwell | NEITHER | monotonic | 11.8% (N=949) | 20.1% (N=378) | 22.4% (N=646) | +10.6 pp (+7.1 pp..+14.6 pp), N=1595 |

## companions

### without touch ordinal

| feature | outcome | coef | 95% | N |
|---|---|---:|---|---:|
| velocity | BREAK | -4.0 pp | -7.4 pp..-0.6 pp | 1973 |
| velocity | REJECT | +1.2 pp | -2.3 pp..+4.6 pp | 1973 |
| velocity | NEITHER | +2.8 pp | +0.2 pp..+5.4 pp | 1973 |
| efficiency | BREAK | -3.1 pp | -6.4 pp..+0.2 pp | 1973 |
| efficiency | REJECT | -1.6 pp | -5.0 pp..+1.7 pp | 1973 |
| efficiency | NEITHER | +4.7 pp | +2.5 pp..+7.1 pp | 1973 |
| persistence | BREAK | -2.3 pp | -4.8 pp..+0.3 pp | 1973 |
| persistence | REJECT | +0.7 pp | -2.0 pp..+3.4 pp | 1973 |
| persistence | NEITHER | +1.6 pp | -0.3 pp..+3.5 pp | 1973 |
| acceleration | BREAK | -0.4 pp | -2.7 pp..+1.7 pp | 1973 |
| acceleration | REJECT | +0.6 pp | -1.7 pp..+2.9 pp | 1973 |
| acceleration | NEITHER | -0.2 pp | -1.9 pp..+1.6 pp | 1973 |
| range_state | BREAK | +0.9 pp | -1.6 pp..+3.4 pp | 1973 |
| range_state | REJECT | +1.2 pp | -1.4 pp..+3.7 pp | 1973 |
| range_state | NEITHER | -2.1 pp | -4.3 pp..-0.0 pp | 1973 |
| rel_volume | BREAK | +2.2 pp | -0.5 pp..+4.8 pp | 1973 |
| rel_volume | REJECT | +1.0 pp | -1.8 pp..+3.6 pp | 1973 |
| rel_volume | NEITHER | -3.2 pp | -5.3 pp..-1.1 pp | 1973 |
| dwell | BREAK | -1.9 pp | -3.9 pp..+0.2 pp | 1973 |
| dwell | REJECT | -2.9 pp | -5.2 pp..-0.7 pp | 1973 |
| dwell | NEITHER | +4.8 pp | +2.6 pp..+6.9 pp | 1973 |

### without log duration

| feature | outcome | coef | 95% | N |
|---|---|---:|---|---:|
| velocity | BREAK | +1.2 pp | -0.9 pp..+3.2 pp | 1973 |
| velocity | REJECT | +1.5 pp | -0.6 pp..+3.6 pp | 1973 |
| velocity | NEITHER | -2.7 pp | -4.3 pp..-1.0 pp | 1973 |
| efficiency | BREAK | +1.4 pp | -0.6 pp..+3.5 pp | 1973 |
| efficiency | REJECT | +0.4 pp | -1.8 pp..+2.4 pp | 1973 |
| efficiency | NEITHER | -1.8 pp | -3.4 pp..-0.2 pp | 1973 |
| persistence | BREAK | +0.3 pp | -1.8 pp..+2.5 pp | 1973 |
| persistence | REJECT | +1.2 pp | -1.0 pp..+3.4 pp | 1973 |
| persistence | NEITHER | -1.6 pp | -3.2 pp..+0.1 pp | 1973 |
| acceleration | BREAK | -1.2 pp | -3.5 pp..+0.9 pp | 1973 |
| acceleration | REJECT | +0.2 pp | -2.0 pp..+2.4 pp | 1973 |
| acceleration | NEITHER | +0.9 pp | -0.8 pp..+2.5 pp | 1973 |
| range_state | BREAK | +2.4 pp | +0.4 pp..+4.5 pp | 1973 |
| range_state | REJECT | +1.6 pp | -0.5 pp..+3.6 pp | 1973 |
| range_state | NEITHER | -3.9 pp | -5.8 pp..-2.2 pp | 1973 |
| rel_volume | BREAK | +3.1 pp | +1.1 pp..+5.3 pp | 1973 |
| rel_volume | REJECT | +1.5 pp | -0.7 pp..+3.5 pp | 1973 |
| rel_volume | NEITHER | -4.6 pp | -6.3 pp..-2.9 pp | 1973 |
| dwell | BREAK | -2.8 pp | -4.6 pp..-0.8 pp | 1973 |
| dwell | REJECT | -3.1 pp | -5.0 pp..-1.0 pp | 1973 |
| dwell | NEITHER | +5.8 pp | +3.9 pp..+7.8 pp | 1973 |

### band mult 2

| feature | outcome | coef | 95% | N |
|---|---|---:|---|---:|
| velocity | BREAK | -0.6 pp | -4.4 pp..+3.1 pp | 2102 |
| velocity | REJECT | +0.3 pp | -3.4 pp..+4.1 pp | 2102 |
| velocity | NEITHER | +0.3 pp | -1.7 pp..+2.4 pp | 2102 |
| efficiency | BREAK | -2.1 pp | -6.7 pp..+2.6 pp | 2102 |
| efficiency | REJECT | -1.2 pp | -6.1 pp..+3.4 pp | 2102 |
| efficiency | NEITHER | +3.4 pp | +0.6 pp..+6.2 pp | 2102 |
| persistence | BREAK | -1.0 pp | -3.8 pp..+2.0 pp | 2102 |
| persistence | REJECT | +0.5 pp | -2.4 pp..+3.6 pp | 2102 |
| persistence | NEITHER | +0.4 pp | -1.2 pp..+2.0 pp | 2102 |
| acceleration | BREAK | +0.5 pp | -1.6 pp..+2.6 pp | 2102 |
| acceleration | REJECT | +0.2 pp | -2.0 pp..+2.3 pp | 2102 |
| acceleration | NEITHER | -0.6 pp | -2.0 pp..+0.6 pp | 2102 |
| range_state | BREAK | +2.9 pp | +0.2 pp..+5.5 pp | 2102 |
| range_state | REJECT | -1.3 pp | -3.9 pp..+1.5 pp | 2102 |
| range_state | NEITHER | -1.7 pp | -3.6 pp..+0.1 pp | 2102 |
| rel_volume | BREAK | +3.1 pp | +0.6 pp..+5.5 pp | 2102 |
| rel_volume | REJECT | -0.7 pp | -3.3 pp..+2.1 pp | 2102 |
| rel_volume | NEITHER | -2.4 pp | -4.2 pp..-0.7 pp | 2102 |
| dwell | BREAK | -2.0 pp | -4.3 pp..+0.1 pp | 2102 |
| dwell | REJECT | -1.4 pp | -3.5 pp..+0.8 pp | 2102 |
| dwell | NEITHER | +3.4 pp | +1.6 pp..+5.3 pp | 2102 |

### pseudo-level

| feature | outcome | coef | 95% | N |
|---|---|---:|---|---:|
| velocity | BREAK | +4.0 pp | +0.4 pp..+7.8 pp | 1828 |
| velocity | REJECT | -3.6 pp | -7.6 pp..+0.1 pp | 1828 |
| velocity | NEITHER | -0.4 pp | -3.0 pp..+2.3 pp | 1828 |
| efficiency | BREAK | -0.1 pp | -3.5 pp..+3.3 pp | 1828 |
| efficiency | REJECT | -3.8 pp | -7.5 pp..-0.4 pp | 1828 |
| efficiency | NEITHER | +3.9 pp | +1.0 pp..+6.8 pp | 1828 |
| persistence | BREAK | +0.2 pp | -2.4 pp..+2.7 pp | 1828 |
| persistence | REJECT | -1.4 pp | -4.0 pp..+1.3 pp | 1828 |
| persistence | NEITHER | +1.2 pp | -1.0 pp..+3.6 pp | 1828 |
| acceleration | BREAK | -0.8 pp | -3.1 pp..+1.4 pp | 1828 |
| acceleration | REJECT | -0.0 pp | -2.6 pp..+2.5 pp | 1828 |
| acceleration | NEITHER | +0.8 pp | -1.1 pp..+2.7 pp | 1828 |
| range_state | BREAK | +4.4 pp | +1.8 pp..+7.3 pp | 1828 |
| range_state | REJECT | +0.6 pp | -2.4 pp..+3.5 pp | 1828 |
| range_state | NEITHER | -5.0 pp | -7.5 pp..-2.4 pp | 1828 |
| rel_volume | BREAK | +5.7 pp | +3.0 pp..+8.5 pp | 1828 |
| rel_volume | REJECT | -1.2 pp | -4.3 pp..+1.9 pp | 1828 |
| rel_volume | NEITHER | -4.5 pp | -6.8 pp..-2.1 pp | 1828 |
| dwell | BREAK | +0.2 pp | -1.7 pp..+2.2 pp | 1828 |
| dwell | REJECT | -4.2 pp | -6.6 pp..-2.3 pp | 1828 |
| dwell | NEITHER | +4.1 pp | +2.3 pp..+5.9 pp | 1828 |

## year

### BREAK

| feature | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|
| velocity | -4.9 pp (N=338) | -1.9 pp (N=450) | -3.3 pp (N=392) | -6.8 pp (N=343) | -4.7 pp (N=450) |
| efficiency | -5.1 pp (N=338) | -4.4 pp (N=450) | +0.0 pp (N=392) | -5.6 pp (N=343) | -1.2 pp (N=450) |
| persistence | -3.4 pp (N=338) | -3.3 pp (N=450) | -0.5 pp (N=392) | -3.4 pp (N=343) | -0.7 pp (N=450) |
| acceleration | +0.7 pp (N=338) | -1.7 pp (N=450) | +2.2 pp (N=392) | -0.7 pp (N=343) | -1.6 pp (N=450) |
| range_state | +2.0 pp (N=338) | +0.9 pp (N=450) | -1.2 pp (N=392) | +2.3 pp (N=343) | +0.7 pp (N=450) |
| rel_volume | +1.6 pp (N=338) | +2.4 pp (N=450) | -0.5 pp (N=392) | +3.4 pp (N=343) | +2.2 pp (N=450) |
| dwell | -1.6 pp (N=338) | +0.1 pp (N=450) | -1.3 pp (N=392) | -3.0 pp (N=343) | -3.0 pp (N=450) |

### REJECT

| feature | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|
| velocity | +1.9 pp (N=338) | -0.8 pp (N=450) | +0.0 pp (N=392) | +7.0 pp (N=343) | -0.5 pp (N=450) |
| efficiency | +2.8 pp (N=338) | +1.8 pp (N=450) | -6.6 pp (N=392) | +1.0 pp (N=343) | -3.9 pp (N=450) |
| persistence | +6.0 pp (N=338) | +2.2 pp (N=450) | -1.7 pp (N=392) | +1.0 pp (N=343) | -2.5 pp (N=450) |
| acceleration | +2.2 pp (N=338) | +1.4 pp (N=450) | -4.1 pp (N=392) | +4.4 pp (N=343) | +0.5 pp (N=450) |
| range_state | -3.0 pp (N=338) | -0.9 pp (N=450) | +4.1 pp (N=392) | -1.0 pp (N=343) | +3.6 pp (N=450) |
| rel_volume | -0.5 pp (N=338) | -2.8 pp (N=450) | +3.6 pp (N=392) | +0.3 pp (N=343) | +2.2 pp (N=450) |
| dwell | -0.9 pp (N=338) | -3.5 pp (N=450) | -5.2 pp (N=392) | -3.2 pp (N=343) | -1.5 pp (N=450) |

### NEITHER

| feature | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|
| velocity | +3.0 pp (N=338) | +2.7 pp (N=450) | +3.3 pp (N=392) | -0.2 pp (N=343) | +5.2 pp (N=450) |
| efficiency | +2.3 pp (N=338) | +2.5 pp (N=450) | +6.6 pp (N=392) | +4.6 pp (N=343) | +5.1 pp (N=450) |
| persistence | -2.5 pp (N=338) | +1.1 pp (N=450) | +2.2 pp (N=392) | +2.4 pp (N=343) | +3.2 pp (N=450) |
| acceleration | -2.8 pp (N=338) | +0.3 pp (N=450) | +1.9 pp (N=392) | -3.7 pp (N=343) | +1.1 pp (N=450) |
| range_state | +1.1 pp (N=338) | -0.1 pp (N=450) | -2.8 pp (N=392) | -1.4 pp (N=343) | -4.4 pp (N=450) |
| rel_volume | -1.2 pp (N=338) | +0.4 pp (N=450) | -3.1 pp (N=392) | -3.7 pp (N=343) | -4.3 pp (N=450) |
| dwell | +2.5 pp (N=338) | +3.4 pp (N=450) | +6.5 pp (N=392) | +6.2 pp (N=343) | +4.4 pp (N=450) |

## family

### BREAK

| feature | DAY | WEEK | MONTH |
|---|---:|---:|---:|
| velocity | -4.0 pp (N=1439) | -4.5 pp (N=420) | -3.7 pp (N=114) |
| efficiency | -2.0 pp (N=1439) | -4.8 pp (N=420) | -6.5 pp (N=114) |
| persistence | -1.9 pp (N=1439) | -1.2 pp (N=420) | -13.4 pp (N=114) |
| acceleration | -0.7 pp (N=1439) | -0.2 pp (N=420) | +2.8 pp (N=114) |
| range_state | +1.0 pp (N=1439) | -0.2 pp (N=420) | -0.2 pp (N=114) |
| rel_volume | +2.4 pp (N=1439) | -1.2 pp (N=420) | +1.6 pp (N=114) |
| dwell | -1.1 pp (N=1439) | -3.4 pp (N=420) | +0.4 pp (N=114) |

### REJECT

| feature | DAY | WEEK | MONTH |
|---|---:|---:|---:|
| velocity | +0.6 pp (N=1439) | +5.0 pp (N=420) | -7.6 pp (N=114) |
| efficiency | -2.2 pp (N=1439) | +0.5 pp (N=420) | +0.4 pp (N=114) |
| persistence | +0.8 pp (N=1439) | -1.2 pp (N=420) | +7.9 pp (N=114) |
| acceleration | +1.1 pp (N=1439) | +0.4 pp (N=420) | -1.0 pp (N=114) |
| range_state | +0.3 pp (N=1439) | +3.0 pp (N=420) | +5.9 pp (N=114) |
| rel_volume | -0.4 pp (N=1439) | +5.5 pp (N=420) | +1.4 pp (N=114) |
| dwell | -2.0 pp (N=1439) | -3.5 pp (N=420) | -9.5 pp (N=114) |

### NEITHER

| feature | DAY | WEEK | MONTH |
|---|---:|---:|---:|
| velocity | +3.4 pp (N=1439) | -0.5 pp (N=420) | +11.3 pp (N=114) |
| efficiency | +4.2 pp (N=1439) | +4.3 pp (N=420) | +6.1 pp (N=114) |
| persistence | +1.0 pp (N=1439) | +2.4 pp (N=420) | +5.5 pp (N=114) |
| acceleration | -0.4 pp (N=1439) | -0.2 pp (N=420) | -1.8 pp (N=114) |
| range_state | -1.3 pp (N=1439) | -2.9 pp (N=420) | -5.7 pp (N=114) |
| rel_volume | -2.0 pp (N=1439) | -4.3 pp (N=420) | -3.0 pp (N=114) |
| dwell | +3.0 pp (N=1439) | +6.9 pp (N=420) | +9.0 pp (N=114) |

## side

### BREAK

| feature | resistance | support |
|---|---:|---:|
| velocity | -3.0 pp (N=1071) | -5.2 pp (N=902) |
| efficiency | -2.3 pp (N=1071) | -3.5 pp (N=902) |
| persistence | -2.1 pp (N=1071) | -2.5 pp (N=902) |
| acceleration | +1.2 pp (N=1071) | -2.9 pp (N=902) |
| range_state | +2.1 pp (N=1071) | -0.8 pp (N=902) |
| rel_volume | +3.4 pp (N=1071) | -0.8 pp (N=902) |
| dwell | -0.6 pp (N=1071) | -2.6 pp (N=902) |

### REJECT

| feature | resistance | support |
|---|---:|---:|
| velocity | +0.7 pp (N=1071) | +2.3 pp (N=902) |
| efficiency | -3.1 pp (N=1071) | +0.2 pp (N=902) |
| persistence | +0.6 pp (N=1071) | +0.8 pp (N=902) |
| acceleration | -1.5 pp (N=1071) | +3.7 pp (N=902) |
| range_state | -0.1 pp (N=1071) | +2.5 pp (N=902) |
| rel_volume | +0.0 pp (N=1071) | +2.6 pp (N=902) |
| dwell | -5.3 pp (N=1071) | +0.8 pp (N=902) |

### NEITHER

| feature | resistance | support |
|---|---:|---:|
| velocity | +2.3 pp (N=1071) | +2.9 pp (N=902) |
| efficiency | +5.3 pp (N=1071) | +3.3 pp (N=902) |
| persistence | +1.5 pp (N=1071) | +1.6 pp (N=902) |
| acceleration | +0.2 pp (N=1071) | -0.8 pp (N=902) |
| range_state | -2.0 pp (N=1071) | -1.7 pp (N=902) |
| rel_volume | -3.5 pp (N=1071) | -1.8 pp (N=902) |
| dwell | +5.9 pp (N=1071) | +1.8 pp (N=902) |

## leave-one-year-out

### BREAK

| feature | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|
| velocity | -3.8 pp (N=1635) | -4.5 pp (N=1523) | -4.1 pp (N=1581) | -3.3 pp (N=1630) | -3.8 pp (N=1523) |
| efficiency | -2.3 pp (N=1635) | -2.5 pp (N=1523) | -3.7 pp (N=1581) | -2.1 pp (N=1630) | -3.2 pp (N=1523) |
| persistence | -1.9 pp (N=1635) | -2.0 pp (N=1523) | -2.6 pp (N=1581) | -1.9 pp (N=1630) | -2.6 pp (N=1523) |
| acceleration | -0.5 pp (N=1635) | +0.1 pp (N=1523) | -1.0 pp (N=1581) | -0.4 pp (N=1630) | -0.0 pp (N=1523) |
| range_state | +0.8 pp (N=1635) | +0.8 pp (N=1523) | +1.3 pp (N=1581) | +0.3 pp (N=1630) | +0.8 pp (N=1523) |
| rel_volume | +1.8 pp (N=1635) | +1.6 pp (N=1523) | +2.4 pp (N=1581) | +1.3 pp (N=1630) | +1.5 pp (N=1523) |
| dwell | -1.7 pp (N=1635) | -2.4 pp (N=1523) | -1.6 pp (N=1581) | -1.4 pp (N=1630) | -1.3 pp (N=1523) |

### REJECT

| feature | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|
| velocity | +1.1 pp (N=1635) | +1.8 pp (N=1523) | +1.4 pp (N=1581) | -0.0 pp (N=1630) | +1.7 pp (N=1523) |
| efficiency | -2.4 pp (N=1635) | -2.3 pp (N=1523) | -0.2 pp (N=1581) | -2.2 pp (N=1630) | -0.8 pp (N=1523) |
| persistence | -0.3 pp (N=1635) | +0.4 pp (N=1523) | +1.2 pp (N=1581) | +0.6 pp (N=1630) | +1.7 pp (N=1523) |
| acceleration | +0.3 pp (N=1635) | +0.4 pp (N=1523) | +1.8 pp (N=1581) | -0.0 pp (N=1630) | +0.8 pp (N=1523) |
| range_state | +1.7 pp (N=1635) | +1.6 pp (N=1523) | +0.2 pp (N=1581) | +1.8 pp (N=1630) | +0.3 pp (N=1523) |
| rel_volume | +1.2 pp (N=1635) | +1.9 pp (N=1523) | +0.1 pp (N=1581) | +1.2 pp (N=1630) | +0.6 pp (N=1523) |
| dwell | -3.3 pp (N=1635) | -2.7 pp (N=1523) | -2.7 pp (N=1581) | -2.9 pp (N=1630) | -3.4 pp (N=1523) |

### NEITHER

| feature | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|
| velocity | +2.7 pp (N=1635) | +2.7 pp (N=1523) | +2.7 pp (N=1581) | +3.4 pp (N=1630) | +2.1 pp (N=1523) |
| efficiency | +4.7 pp (N=1635) | +4.8 pp (N=1523) | +3.9 pp (N=1581) | +4.4 pp (N=1630) | +4.1 pp (N=1523) |
| persistence | +2.2 pp (N=1635) | +1.6 pp (N=1523) | +1.5 pp (N=1581) | +1.3 pp (N=1630) | +1.0 pp (N=1523) |
| acceleration | +0.2 pp (N=1635) | -0.5 pp (N=1523) | -0.8 pp (N=1581) | +0.4 pp (N=1630) | -0.8 pp (N=1523) |
| range_state | -2.4 pp (N=1635) | -2.4 pp (N=1523) | -1.5 pp (N=1581) | -2.1 pp (N=1630) | -1.1 pp (N=1523) |
| rel_volume | -3.0 pp (N=1635) | -3.5 pp (N=1523) | -2.5 pp (N=1581) | -2.5 pp (N=1630) | -2.1 pp (N=1523) |
| dwell | +5.0 pp (N=1635) | +5.1 pp (N=1523) | +4.3 pp (N=1581) | +4.3 pp (N=1630) | +4.7 pp (N=1523) |

## information

Analysis touches N=1973. Episode clusters=1210. Ambiguous next bars dropped: 3. Control N=1828. Sensitivity N=2102. Busiest family share 72.9%.

## search exposure

441 material cells. FDR family size 21. No cell was added after the outcomes were read. Interactions estimated: 0.

## limitations

The sample is touches of ex-ante structural zones that had an observed entry into the predeclared outer band and a later 4h window. Features use only bars before the touch. Separate linear probability models are not constrained to sum to one across BREAK, REJECT and NEITHER. Episode clustering does not model every shared path across zones. A 5m bar that hits both barriers is dropped. One venue, 2020–2024, on a surface already used for level research. A historical frequency here is not a current probability. A cell that passes the successor rule is DISCOVERY_ONLY on this selection surface.

## product

Not integrated. No `/levels` change, no findings-registry edit, no deploy. Confirmation was not started.
