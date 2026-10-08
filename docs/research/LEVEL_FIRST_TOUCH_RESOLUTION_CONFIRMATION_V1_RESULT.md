# LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1 — result

MODE = CONFIRMATION.
Design note commit `a4f3a0d6e5aeb8e07c5998babb0fe26c77621dd5`.
Tracks: STRUCTURE, PRODUCT_EVIDENCE. One official run. The primary contrast was frozen before this file existed.

## evidence

The first touch of a pre-known structural level resolved into BREAK or REJECT within 4 hours more often than the matched first touch of the deterministic half-rotation pseudo-price. Δ_resolution = +8.0 pp (95% +4.4 pp .. +11.8 pp), N = 548 pairs. Real resolution rate 91.1%, pseudo resolution rate 83.0%. This is a historical resolution contrast. It is not a direction and not a current probability.

Evidence label: `REPLICATED_POSITIVE_RESOLUTION_DIFFERENCE`.
Supporting clauses: `{'positive': True, 'interval_excludes_zero': True, 'at_least_3pp': True, 'epoch_sign': True, 'loeo_sign': True, 'eligible_epochs': 3, 'positive_epochs': 3}`.

## primary

Δ_resolution = +8.0 pp.
95% week-block interval: +4.4 pp .. +11.8 pp.
Real resolution rate: 91.1%.
Pseudo resolution rate: 83.0%.
Analysis pairs: 548. Availability-matched pairs before the ambiguous drop: 558.
Weeks in the analysis sample: 119.
Ambiguous real labels among availability-matched touches: 4.
Ambiguous pseudo labels among availability-matched touches: 7.
Pairs excluded because either label was ambiguous: 10.
Pairs excluded because a label was unclassified: 0.

## discordant pairs

Both resolved: 419. Both neither: 13.
Real resolved and pseudo neither: 80. Pseudo resolved and real neither: 36.

## adjusted sensitivity

Long-form coefficient on the real-touch indicator: +7.9 pp (95% +4.0 pp .. +11.7 pp).
Status: ok. Columns: family_week, support, vol_mid, vol_high, epoch_2018, epoch_2019.
This coefficient does not replace the paired mean.

## decomposition

BREAK: Δ=+10.0 pp (95% +4.6 pp .. +15.4 pp); real 55.3%, pseudo 45.3%.
REJECT: Δ=-2.0 pp (95% -7.1 pp .. +3.0 pp); real 35.8%, pseudo 37.8%.
NEITHER: Δ=-8.0 pp (95% -12.0 pp .. -4.1 pp); real 8.9%, pseudo 17.0%.

## epochs

2017H2 N=100 Δ=+5.0 pp (95% -4.0 pp .. +15.7 pp); real 86.0%, pseudo 81.0%
2018 N=250 Δ=+5.2 pp (95% -0.4 pp .. +10.7 pp); real 90.8%, pseudo 85.6%
2019 N=198 Δ=+13.1 pp (95% +7.1 pp .. +18.8 pp); real 93.9%, pseudo 80.8%

## families

DAY N=480 Δ=+8.5 pp (95% +4.3 pp .. +12.9 pp); real 90.6%, pseudo 82.1%
WEEK N=59 Δ=+5.1 pp (95% -5.1 pp .. +16.9 pp); real 93.2%, pseudo 88.1%
MONTH N=9 Δ=+0.0 pp (95% +0.0 pp .. +0.0 pp); real 100.0%, pseudo 100.0%

## approach side of the real touch

resistance N=264 Δ=+7.2 pp (95% +0.4 pp .. +13.7 pp); real 85.2%, pseudo 78.0%
support N=284 Δ=+8.8 pp (95% +5.1 pp .. +12.5 pp); real 96.5%, pseudo 87.7%

## leave-one-epoch-out

omit_2017H2 N=448 Δ=+8.7 pp (95% +4.6 pp .. +12.8 pp); real 92.2%, pseudo 83.5%
omit_2018 N=298 Δ=+10.4 pp (95% +5.1 pp .. +15.8 pp); real 91.3%, pseudo 80.9%
omit_2019 N=350 Δ=+5.1 pp (95% +0.0 pp .. +10.2 pp); real 89.4%, pseudo 84.3%

## claim

Claim level: L2. Status: issued.
Ceiling L2. A historical frequency is not a current probability. L3 needs prospective calibration of this claim class. L4 is not available.
Replicated historical mechanism: True.

## product

PRODUCT_INTEGRATION_CANDIDATE = YES.
No /btc, /levels, /check, /risk, scoring, findings-registry, Telegram or deploy change. Integration needs a separate owner go.

## bootstrap

Draws 2000, seed 20261012, cluster = product week of the real first touch.
Each cell uses an independent stream at seed + cell index, in the order primary, BREAK, REJECT, NEITHER, three epochs, three families, two sides, three leave-one-epoch-out cuts, adjusted coefficient.
Search cells predeclared: 16. No FDR screen. One primary contrast.

## dataset

Surface DH1_BITMEX_XBTUSD_TRADES_5M_V0, days 2017-08-01..2019-12-31, canonical SHA256 df3c32922e95bdca80fcf0fa695ec2c8f29455cf8c1ab930277e92c994b4995f.
Event window 2017-09-01 inclusive to 2020-01-01 exclusive.
Exposure: TIME_DISJOINT / OUTCOME_UNREAD_FOR_THIS_CLAIM / FEASIBILITY_EXPOSED.

## limitations

One venue and one symbol. The surface had been used for outcome-blind DH1 feasibility counts. Same-bar barrier ties are excluded. The pseudo price is one deterministic half-rotation, not every non-structural price. The cohort is the first touch only. The endpoint is resolution into either barrier, not the direction of the move. The week block does not model every form of dependence. The discovery gap on Binance is not a required magnitude.

FOLLOW_UP_IDEA: none.
