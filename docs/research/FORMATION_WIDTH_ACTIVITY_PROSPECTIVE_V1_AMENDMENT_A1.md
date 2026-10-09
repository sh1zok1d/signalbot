# FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1 — Amendment A1

`outcome_read = false`
`future_association_read = false`
`accrued_analysis_n = 0`
`status = AWAITING_START`
`amendment = A1`
`parent_design_rewritten = false`

Pre-outcome repair of the sequential error budget. No forward association is computed. The parent design file is unchanged.

## Parent identity

| item | value |
| --- | --- |
| parent design | `docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_DESIGN.md` |
| parent design SHA256 | `d07b83ca9baea11d0af16424da6f7a7a29d43a2a61b6d850d974c8ed80da9612` |
| parent HEAD | `6b178352e464fac7cc3c847448cb3bc9018ae6a4` |
| parent spec | `docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SPEC.json` |
| parent spec role | superseded for the error budget and the checkpoint grid |

The active machine contract is `docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_AMENDMENT_A1.json`.

## Reason

The parent design gave each one-sided family a cumulative alpha of `0.05`. Those two families are alternative decisive magnitude verdicts of one unit. Their union bound is `0.10`. This amendment replaces that split before any forward score.

## Unchanged

Binance USD-M BTCUSDT perpetual, `BINANCE_UM_LIVE_FORWARD`, column `CANDLES`. Prospective start `2026-10-10T00:00:00Z`. UTC formation `[00:00, 01:00)`. Endpoint hour `[01:00, 02:00)`. `V = (high−low)/P0`. `ACTIVITY = RV_NEXT`. Covariate `RV_FORMATION`. Partial Spearman, one covariate. Practical reference `+0.10`. ISO-week block bootstrap, `B = 2000`, seed `20261109` restarted at each look. Lag placebo remains option A, once on the stopping sample, not a route input. Stability remains the calendar midpoint split, not a route input. Neither diagnostic receives an alpha budget. Product integration stays off. L3 stays unauthorized. Historical points stay context and are not a prior.

## Budget

`OVERALL_DECISIVE_MAGNITUDE_ERROR_BUDGET = 0.05`

Split evenly:

- lower-tail cumulative budget `0.025`
- upper-tail cumulative budget `0.025`

Under the frozen union bound on positively dependent looks, the probability of any false decisive magnitude statement is at most `0.05`.

## Spending

Kim–DeMets power family, exponent `1`, inside each tail:

`A(t) = 0.025 * t`

`t` is forecast effective N at the look divided by forecast effective N at the terminal. At look `k`,

`incremental_alpha_k = A(t_k) − A(t_{k−1})`

with `A(t_0) = 0`. The two tails share information times, so the increments match. The spec stores them separately as `lower_tail_spend` and `upper_tail_spend`.

The bootstrap lower quantile is the lower increment. The bootstrap upper quantile is one minus the upper increment. One lower bound `L_k` and one upper bound `U_k` are formed at each formal checkpoint.

## Positive relation, option A

`PROSPECTIVE_POSITIVE_RELATION_SUPPORTED` is not a third alpha family. The same lower bound answers both comparisons:

- `L_k >= +0.10` is the practical-magnitude claim
- at the terminal, `0 < L_k < +0.10` is the positive-relation claim

No extra alpha is spent. The error of calling the association positive when it is not is already inside the lower-tail budget `0.025`.

## Forecast, still outcome-blind

Same parent forecaster: phi `0.5483151377537036`, AR(1) inside an ISO week, Kish effective N, Fisher SE, accrual `1820/1827`, week ratio `1820/262`. This remains `FORECAST_ASSUMPTION`. It is not the test. No forward bar is read.

`MDE80` at a look is `(z_k + z_80) * SE`, where `z_k` is the normal quantile of that look's incremental alpha and `z_80 = 0.8416212335729143`. The parent MDE used the quantile of `0.05`. Maturity uses this spent-increment MDE, so the new alpha enters the boundary.

## Checkpoint rule

The search grid is frozen as analysis N `365, 730, …, 4380`: one candidate per year for 12 years. The selector does not add points after that grid.

A look is legal only when its incremental alpha is at least `20/2000 = 0.01`. That floor is the bootstrap resolution of `B = 2000`: twenty tail draws. It is not a success probability.

The first formal look is the earliest grid point, against a candidate terminal, whose cumulative spend `A(t)` is at least `0.01` and whose sequential power at planted `+0.10` is at least `0.50`. The value `0.50` is a minimum information threshold. It is not a route and it is not lowered after the table.

A later grid point before the terminal is admitted only when the residual increment is at least `0.01` and that increment's sequential power at planted `+0.10` is at least `0.50`. A skipped point does not consume alpha.

The terminal is the earliest grid point for which that schedule has every increment, including the terminal remainder, at least `0.01`, and at least one admitted look has spent-increment `MDE80 <= +0.10`. Nothing after that terminal is a look in V1.

Maturity is the earliest admitted look with spent-increment `MDE80 <= +0.10`.

## Schedule this rule returns

| N | role | ISO weeks | effective N | SE | information time | each tail cumulative | each tail increment | lower quantile | upper quantile | MDE80 | power at +0.10 | expected formation date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1460 | first look | 210 | 547.49 | 0.042855 | 0.500000 | 0.012500 | 0.012500 | 0.012500 | 0.987500 | 0.132124 | 0.536664 | 2030-10-14 |
| 2920 | maturity and terminal | 420 | 1094.99 | 0.030262 | 1 | 0.025000 | 0.012500 | 0.012500 | 0.987500 | 0.093297 | 0.856136 | 2034-10-19 |

The two tail increments each sum to `0.025`. Full values are in the amendment JSON.

Annual points before `1460` and the points `1825`, `2190`, and `2555` fail the `0.01` increment floor against this terminal. Points after `2920` are outside V1.

The parent checkpoints `1095`, `1825`, and `2190` are not the active schedule. Under the `0.025` boundary their spent-increment MDE does not reach `+0.10` while also keeping a bootstrap-resolvable remainder.

Maturity and the terminal are the same look. The next annual point, `3285`, would leave a remainder below `0.01`, so it is not a legal extra look. The test stops at `2920`.

## Routes

Before analysis N `1460`: `PROSPECTIVE_INFORMATION_IMMATURE`. No interval is computed.

On a formal checkpoint, first match:

1. Interpretable, point strictly positive, and `L >= +0.10`: `PROSPECTIVE_PRACTICAL_MAGNITUDE_SUPPORTED`. This may stop at either look.
2. The look is the maturity checkpoint and `U < +0.10`: `PROSPECTIVE_PRACTICAL_MAGNITUDE_NOT_SUPPORTED`.
3. The look is the terminal, the point is strictly positive, and `0 < L < +0.10`: `PROSPECTIVE_POSITIVE_RELATION_SUPPORTED`.
4. The terminal look is otherwise unresolved or not interpretable: `PROSPECTIVE_INCONCLUSIVE_AT_TERMINAL`.

Before maturity, `U < +0.10` does not stop. The first look is before maturity, so an upper bound below `+0.10` there is not a verdict. While accrual continues, `0 < L < +0.10` is interim evidence only.

## Evaluator

Until a separate owner go for the first formal checkpoint, and only once analysis N has reached `1460`, the evaluator returns `REFUSING_OUTCOME_BEFORE_OWNER_GO` and loads no panel. That go is not given here.

No further pre-outcome amendment is indicated by this repair. After A1 the unit accrues prospective rows until N `1460`.
