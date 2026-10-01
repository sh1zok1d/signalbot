# Beta — D7 regime-context promotion gate V1

**Status:** `IMPLEMENTED / HARD ALLOW ON / OWNER STATE DEFAULT OFF`
**Date:** 2026-10-01

The code for §§4–5 is in place. `regime_d7.enabled` is the committed hard allow (`true`). The line stays off until the owner sends `/admin_d7_on` after deploy, after warm-up of at least 1440 valid hours, and after the sanity SQL in `docs/PRIVATE_BETA_V0_DEPLOY.md`. `docs/DOCUMENTATION_INDEX.md` stays unmarked while the owner state is off.

**Owner decision (2026-10-01):** D7 is used in `/btc` as market-regime context. It is not a trade signal and not a price forecast. The owner delegated the detailed choices; they are recorded in §9.

**Role:** this is the separate promotion gate required by decision 7 of `docs/PRIVATE_BETA_V0_RESTART_DECISION.md` ("No research result is promoted into the beta without a separate, future promotion gate").
- It authorizes exactly one claim (§2) and nothing else.
- It does not lift `PREDICTIVE_PRODUCT_FROZEN` for any other content.
- It does not change any research record.

Screen placement is specified in `BETA_BTC_MULTI_HORIZON_UX_V1.md` §§4, 5.2.

## 1. Evidence and its limits

**Discovery.** `docs/research/DISCOVERY_SPRINT_02_D7_RESULT.json`:
- data: Binance USD-M BTCUSDT, 2020–2024;
- `MU_D7_RULE = 0.1894` (following hour also in state);
- `MU_D7_CONTROL = 0.0986` (rate-matched base);
- `DELTA_D7 = 0.0909`;
- every year 2020–2024 positive;
- label `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`.

**Confirmation.** `docs/research/D7_CONFIRMATORY_PRIMARY_RESULT_V1.json`, SHA-256 `b4efa972cec9acfacb2987be7aef3ad1ed239c8279977374a18265dfe60df503`:
- data: BitMEX XBTUSD 2016–2019;
- `theta_hat = 0.1293`, DWB `p = 0.0001` (R = 9999);
- 2017, 2018 and 2019 all positive; lower bound `L = 0.1139`;
- `EVIDENCE_LABEL = CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`;
- the seed source was amended to a deterministic seed before opening, so the external-beacon unpredictability guarantee does not apply.

**Not established:**
- 2025/2026 behaviour (protected, sealed);
- Bybit and OKX;
- price direction, size of the move, profitability;
- cellwise or assumption-free confirmation.

## 2. The one allowed claim

**Meaning:** after a clock hour in which BTC moved a lot relative to its traded volume, the following clock hour was historically about twice as often the same kind of hour: about 1 in 5, against about 1 in 10 usually. Nothing about direction, size or profitability.

**Label: "high impact", not "thin market".** The observable is the price move per unit of relative volume. "Thin market" would assert an order-book mechanism (missing depth) that D7 never measured.

**Exact strings.** `HH` is a clock hour rendered in Kyiv time, per `BETA_BTC_MULTI_HORIZON_UX_V1.md` §3.2.

Main screen:
- `ru`: `High impact в прошлый час`
- `en`: `High impact last hour`

1h tab, line 1:
- `ru`: `High impact HH:00–HH:00 (Киев): цена прошла много относительно объёма торгов.`
- `en`: `High impact HH:00–HH:00 Kyiv: price moved a lot relative to traded volume.`

1h tab, line 2:
- `ru`: `Исторически следующий час был таким же примерно в 1 из 5 случаев (обычно в 1 из 10).`
- `en`: `Historically, the following hour was also like this about 1 in 5 times (usually 1 in 10).`

1h tab, line 3:
- `ru`: `Направление цены это не показывает.`
- `en`: `This says nothing about price direction.`

**The numbers are fixed** from the Binance discovery means, rounded (0.189 → 1 in 5, 0.099 → 1 in 10). Binance is used because it is the live instrument. The numbers are never recomputed live and never shown as percentages.

**Vocabulary:** the strings pass the English and Russian `assert_descriptive` lists unchanged, and the lists are not relaxed.

## 3. Forbidden

- Direction or path words in either language: up/down, continue/continuation, reversal, breakout, trend, рост/падение продолжится, разворот, пробой, тренд.
- Forecast words: likely, expect, will, probability, a percent figure, вероятно, ожидается, прогноз.
- "Persists" / "stays" / "сохранится". About 80% of the time the following hour is *not* in the state.
- Any size-of-move statement or trade instruction.
- "Thin market" / "тонкий рынок" (§2).
- A push notification triggered by D7.
- D7 opening a detector episode, or entering a score combined with detector events.
- D7 shown for any other instrument, or computed from Bybit or OKX data.

## 4. Live computation (must equal the researched state)

**Definition.** The state is exactly `aggregate_completed_hours` plus `build_d7_states` in `scripts/research/discovery_sprint_02_impl.py`:

- **Instrument:** Binance USD-M BTCUSDT perpetual.
- **Hour:** UTC clock hour [HH:00, HH+1:00).
  - It counts only when all 60 one-minute bars exist.
  - `ret = ln(close of the last 1m bar / open of the first 1m bar)`.
  - `quote_volume_1h` = sum of the 1m quote-asset volumes.
- **Lists of valid hours:** incomplete hours are skipped, never zero-filled.
- **Impact:** `qrel = quote_volume_1h / median(previous 720 valid hourly quote volumes)` and `impact = |ret| / qrel`.
- **State:** `impact > p90` of the previous 720 valid impacts, with linear interpolation (`PERCENTILE_METHOD = "linear"`).
- **Warm-up:** 720 valid hours before impacts exist, then 720 impacts, so at least 1440 valid hours.

**Data source (decided).** Stage-1 `klines_1m` has no quote-volume column (`storage/schema.sql`), so D7 has its own beta-owned feed:
- **Tables:** `beta_d7_klines_1m` (Binance USD-M BTCUSDT 1m bars with `quoteAssetVolume`, `fetched_at`) and `beta_d7_hour_states` (one row per completed hour: inputs, impact, p90, state, `available_at`, version digest). Both are additive tables in `storage/beta_v0_schema.sql`.
- **Hourly job** (`runtime/beta_cli.py --beta-d7-once`, systemd timer in `deploy/signalbot-beta-*`):
  - runs at HH:01 UTC;
  - fetches the last 120 one-minute bars from `/fapi/v1/klines` (the overlap repairs a missed run);
  - stores only closed bars (`closeTime < now`);
  - computes the state of the hour that just closed.
- **Backfill:** at install, 90 days of 1m bars, about 87 requests of 1500 bars. That is 2160 hours, which covers the 1440-hour warm-up with margin for gaps.
- **1h klines are not used.** They would hide missing minutes, and the research rule needs them.
- **Timing:** the state for hour H is usable from its `available_at` (at least H+1h), the same as the research `available_at_ms`.

**Parity tests (required):**
1. **In CI:** the research functions and the beta implementation run on the same synthetic 1m series with gaps and incomplete hours. The state booleans must be identical for every hour.
2. **Owner-run once before activation:** the same comparison on the real `CORE_BTC_BINANCE_V0` 1m data for 2020–2024.
- Neither test reads any 2025 or 2026 data.
- The research function stops at its protected-start constant; the live implementation must not inherit that cutoff.

## 5. Display rules

**Shown only when all of these hold:**
- `regime_d7.enabled` is true and the durable owner state is on (`/admin_d7_on`; a missing row is off);
- the most recent completed clock hour H is complete;
- `state(H) = True`;
- warm-up is complete;
- H's row was computed before H+1h+10min. A late or missing computation hides the line; it is never shown as "inactive";
- the `/btc` view is not `DATA STALE` / `DATA DEGRADED`.

**Shown regardless of the detector event state.** A calm screen can show it, and an unusual screen may not.

**Lifetime:** shown during hour H+1, the hour the claim is about. At H+2 the state of H+1 decides.

**Persistence:** stored in the `/btc` view payload under `regime` (hour bounds, state, `available_at`, version digest).

**Readiness:** if warm-up is incomplete, the Readiness view says `Контекст импакта: бот собирает историю` / `Impact context: history building`.

## 6. No live evaluation on protected data

The bot computes D7 states on live 2026 data for display only. Counting whether the following hour was also high-impact on 2025/2026 data is an evaluation of protected data, and this gate does not authorize it. Any such monitoring needs its own decision and is recorded in `docs/RESEARCH_LEDGER.md`.

## 7. Push

None. D7 never triggers or changes a notification.

## 8. Preconditions before activation (all required)

1. The D7 confirmation records are on `main`. Satisfied 2026-10-01: the stack was merged (`466346d`, PR #262 and its predecessors).
2. The owner approved D7 in `/btc` (2026-10-01). The §2 strings are recorded here.
3. Both parity tests (§4) pass.
4. Warm-up is complete on the deployed database: at least 1440 valid hours in `beta_d7_hour_states`.
5. `docs/PRIVATE_BETA_V0_RESTART_DECISION.md` gets a pointer that decision 7 is satisfied for this claim only. `docs/DOCUMENTATION_INDEX.md` marks this gate active.

## 9. Decision record (2026-10-01)

| Topic | Decision | By |
|---|---|---|
| Use D7 in `/btc` | yes, as regime context only | owner |
| Label | "High impact" in both languages (owner string amendment: the Russian UI keeps the English term), not "thin market" | owner |
| Numbers | fixed 1 in 5 vs 1 in 10, from Binance discovery | delegated |
| Data source | beta-owned Binance 1m feed with quote volume, hourly job, 90-day backfill | delegated |
| Main-screen line | yes, one line, only while active | delegated |
| Push | never | delegated |
| Parity | CI synthetic plus owner-run real 2020–2024; no 2025/2026 | delegated |
| Live hit-rate monitoring | not authorized | delegated (protected-data rule) |
