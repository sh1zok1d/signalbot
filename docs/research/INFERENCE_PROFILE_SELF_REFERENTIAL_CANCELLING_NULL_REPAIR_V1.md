# Self-referential cancelling-null repair V1

Implementation repair of `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`. This record does not change the frozen contract, the validation protocol, or the primary method. No official screen was executed before or by this repair.

Base: `9d96fad559ef9b9214f95867409f71fd9d0071e9`.

## Audited defect

`CANCELLING_CELLS` with `gap=none` was a gating law with population `theta != 0`.

At even `T`, cell `c0` contained `T/2 - 1` pairs with coefficient `+c` and the one inter-cell boundary pair, drawn from the marginal. Cell `c1` contained `T/2` pairs with coefficient `-c`, including the terminal lead. The signed autoregressive count was `-1`. With marginal probability `0.30`,

`theta = -c (1 - 0.30) / T`.

For `T = 2048` and `c = 0.10/0.7` the pair census was `1023` positive, one boundary, `1024` negative, and `theta = -1/20480`. One hundred region-5 worlds used `gap=none`.

`gap=interior` on even `T` was already balanced, because the gap removes the cross-cell pair and the two segments have equal length.

## Root cause

The boundary pair was charged to the first cell, and the terminal lead remained an autoregressive pair of the second cell. Equal cell lengths and opposite coefficients therefore did not produce equal autoregressive counts.

## Algebraic repair

`_cancelling_pair_sign` assigns each eligible pair a sign in `{+1, -1, 0}`.

- A sign of `+1` uses coefficient `+c`. A sign of `-1` uses coefficient `-c`. A sign of `0` draws the lead from the marginal `0.30`.
- The marginal probability of every state remains `0.30`, so a pair with sign `s` contributes excess `s * c * 0.30 * 0.70`.
- The population contrast is `(n_plus - n_minus) * c * 0.70 / T`.

The sign rule makes `n_plus = n_minus` for every `T >= 2`, both gap modes, and every coefficient:

- `gap=none`: the inter-cell boundary pair is marginal. Both cells then receive `floor(T/2) - 1` autoregressive pairs. Leftover pairs in the longer cell are marginal.
- `gap=interior`: there is no cross-cell pair. Both cells receive `floor(T/2)` autoregressive pairs. The one leftover pair when `T` is odd is marginal.

Cell labels, declared cells, deterministic blocks, and the coefficient list are unchanged. Blocks do not enter the transition law. For `T = 2048` and `gap=none` the census is `1023` positive, `1023` negative, and two marginal pairs (the boundary and the terminal lead). For `gap=interior` it is `1024` and `1024`, with no marginal pair.

The same identity gives `theta = 0` for the other gating families: IID Bernoulli draws are independent; interlaced lag-2 puts adjacent times on independent chains; even moving-average shocks of adjacent times are disjoint and the conditional probability stays inside `(0, 1)`; variance-regime draws are independent Bernoulli with a constant mean inside each cell; label-Markov outcomes are conditionally independent given the label.

## What this repair does not change

Primary method, moments, `g`, gradient, influence, block centering, Bartlett kernel, gap representation, bandwidth, multipliers, `R_VALIDATION`, `R_CONFIRMATORY`, the finite-R p-value, the 1600/95 gate, the 8×200/21 guard, the D7 1600 gate, RNG derivation, and process-pool execution are unchanged. Lexicographic configuration order, historical `9559` text, and the dense Bartlett reference used only by tests are unchanged.

`D7_BITMEX_PRIMARY_TARGET_OPENED`, `D7_PRIMARY_EFFECT_COMPUTED`, `PROFILE_VALIDATION_EXECUTED`, `D7_GEOMETRY_ADMISSION_EXECUTED`, and confirmatory RNG generation remain false. No official validation existed before this repair.

## Tests

`tests/research/self_referential_population_oracle.py` is the population oracle. It does not call `primitive_moments`. The implementation tests compare production signs with that oracle, including `T in {31, 32, 33, 2047, 2048, 2049}` and `c = 0.10/0.7` with `gap=none`, and they reject the census `(1023, 1, 1024)`.

Additional conformance tests require per-block means of the centered series to be zero when the block means differ, require each bootstrap draw's variance to equal `V(eta_r * c)`, require batch sizes `1`, `7`, and `R + 5` to share `T_obs`, the exceedance count, `p`, and status, abort the run on an injected zero or materially negative bootstrap variance, and reject an undeclared cell inside `primitive_moments`.
