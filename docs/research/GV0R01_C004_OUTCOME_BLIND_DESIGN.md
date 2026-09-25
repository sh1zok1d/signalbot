# GV0R01-C004 outcome-blind design and power

`C004_DEFINITION_STATUS = UNAMBIGUOUS`
`OUTCOME_BLIND_GATE_RESULT = EXECUTION_INFORMATIONALLY_WEAK`
`MARKET_DATA_OPENED_FOR_C004 = false`
`NEXT_UNIT = NO_C004_EXECUTION_AUTHORIZED`

GV0CAL-C004 is a different candidate (CME settlement). This unit uses the GV0R01-C004 card only.

## Claim

A scheduled FOMC statement is a common-factor shock. The idiosyncratic share of ETHUSDT variance relative to BTCUSDT, after a beta frozen before the statement, is lower in the 60 minutes after the statement than on matched non-release weeks.

The primary universe is the 39 scheduled FOMC statements. CPI is not pooled. The card's CPI arm is an N-extension, and the primary target, function and name are FOMC windows. One statement, `20200129`, has a beta window that starts before 2020-01-01, so 38 events are covered.

## Endpoint and inference

`DELTA_SHARE` is the mean residual share on event windows minus the mean on 1:1 matched controls. The test is one-sided toward a lower event share. Alpha is 0.05.

The 60-minute outcome windows do not overlap. The 90-day beta windows do: 260 dependence edges, one component of all 76 windows. The full within-stratum permutation is not globally invariant (261 swaps change external neighborhoods). The primary randomization is the smaller subgroup of swaps that preserve that graph. Its label orbit has size 16, so the smallest exact p-value is 1/16, which is above 0.05. The test cannot reject at the frozen alpha.

## Power

The execution bar is a 0.10 residual-share decline at 80% power under idiosyncratic SD `sqrt(2)`. It is not the C012 0.50 single-window-SD bar. No simulated scenario reaches 80% power on the grid through a 0.20 decline. No BTC or ETH price was opened.

Machine contract: `GV0R01_C004_OUTCOME_BLIND_DESIGN.json`. Builder: `scripts/research/gv0r01_c004_design.py`.
