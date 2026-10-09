# FUNDING_TAIL_RISK_CROSS_VENUE_V1 — feasibility, stopped before any outcome

`outcome_read = false`. `status = BLOCKED_BY_CROSS_VENUE_FUNDING_PROVENANCE`.

This file records an outcome-blind source audit. It does not contain a Bybit path-risk score. It does not change `FUNDING_STATE_HISTORICAL_STRUCTURE_V1`.

## Question that was not scored

Does funding extremity carry historical information about subsequent BTC path risk on Bybit, and does that association remain after current volatility?

The parent Binance characterization stays `INCREMENTAL_ASSOCIATION_UNCERTAIN`. Its tail shape is a hypothesis-generating observation. It is not re-read here and it is not treated as a confirmed tail effect.

## What was required

Same-venue pair:

1. Bybit historical settled funding for linear BTCUSDT.
2. Bybit BTCUSDT perpetual price path.

Bybit funding is not joined to Binance price. Another venue is not substituted. Premium is not substituted for funding. Open interest is not opened. `2025/2026` is not opened.

## Price path, timestamps only

`LEVEL_CROSS_VENUE_PERP_5M_V0` / `bybit_btcusdt_linear_5m.csv.gz`.

- SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`. Matches the pin already used by the formation-width Bybit units.
- Header `open_ms,open,high,low,close`.
- Open-time census only. High, low, and close were not used as an outcome.
- Bars `476254`. First open `2020-03-31T21:00:00Z`. Last open `2024-12-31T20:55:00Z`.
- Strictly increasing. Duplicates `0`. Off the 5-minute grid `0`. Opens at or after `2025-01-01` `0`.
- Slots from the first open to the last open `499968`. Missing slots `23714`. Those holes stay missing. They are not filled.
- Prior exposure of this file is the level-reaction reads and the formation-width reads. None of those reads asked the funding-tail question. This census does not consume a new outcome.

## Funding source audit

No Bybit funding file is in the repository.

Official history endpoint, the same one the backfill client names:

`GET https://api.bybit.com/v5/market/funding/history`

Parameters that would have been used: `category=linear`, `symbol=BTCUSDT`, `endTime` strictly before `2025-01-01T00:00:00Z`, `limit=200`.

Checked `2026-10-09T11:47:34Z`.

- `https://api.bybit.com` returned HTTP `403`. Body: the Amazon CloudFront distribution is configured to block access from your country.
- `https://api.bytick.com`, the documented backup host, returned the same HTTP `403`.

The static public archive `https://public.bybit.com/` is reachable. Its root lists only:

- `kline_for_metatrader4/`
- `premium_index/`
- `spot_index/`
- `trading/`
- `spot/`

There is no funding directory. `kline_for_metatrader4/BTCUSDT/` lists year folders of OHLC files, not funding rates. `premium_index/` lists inverse `*USD` names, including `BTCUSD`, not linear `BTCUSDT` settled funding. Those files were not downloaded. Premium is a different object and is not a substitute.

`trading/BTCUSDT/` is the trade-print archive. It was not downloaded and it is not a funding series.

## Why this stops

A same-venue settled funding series cannot be acquired or reproduced from this environment. There is no pinned local copy, the official REST history is refused before any row, and the public file archive does not contain the series.

`BLOCKED_BY_CROSS_VENUE_FUNDING_PROVENANCE`.

No funding timestamp, cadence, duplicate count, gap count, or rate was observed, because no row was returned. No warmup was applied. No rank, extremity, excursion, or volatility control was computed. No bootstrap seed was spent.

## Object that stays unapplied

The child question had a specified form. It was not fitted and not scored:

- past-only rank `(1 + #{past < x} + 0.5 * #{past == x}) / (n_past + 1)` on Bybit history only, warm-up `90` prior events if a series existed;
- extremity `abs(rank - 0.5)`;
- primary outcome the parent's 8-hour absolute log excursion;
- control the same-venue 8-hour realized volatility ending at the decision;
- five descriptive bins copied from the parent;
- no magnitude floor and no threshold `55`.

None of these was applied to a Bybit outcome.

## What a later attempt needs

A new unit, after a pinned official settled-funding snapshot for Bybit linear BTCUSDT exists, with a checksum, a timestamp audit, and an end at or before `2024-12-31`. Same-venue price only. Not this file's score. Not a rerun of the Binance parent. Not premium. Not open interest. Not `2025/2026`.

## Product

`PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc` change. No trading rule.
