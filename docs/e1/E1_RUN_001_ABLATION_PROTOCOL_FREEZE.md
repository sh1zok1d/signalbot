# E1-RUN-001 — Exact ablation/simple-baseline protocol freeze

Status: **FROZEN BEFORE ABLATION/BASELINE OUTCOME INSPECTION**  
Date: 2026-08-25  
Frozen production basis: `main@8081eb31657f127141efb3a455f86690258164bc`

Candidate development outcomes and the first direction-inversion/matched-random controls have already been viewed. The variant names below were pre-registered before those outcomes; this note freezes their exact mechanical implementation before any variant population/outcome is inspected. No threshold is selected from development performance.

Holdout remains sealed at `2026-08-16T00:00:00Z`.

## General rules

- Replay only the development candidate window `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)`.
- Variant candidate generation reads no future outcomes.
- All variants reuse the frozen production Stage-3/4/5 loaders/detectors wherever possible.
- Synthetic context/trigger values below exist only to neutralize one named gate in a research ablation. They are not new model values, thresholds, or candidate strength claims.
- Full-horizon outcome reporting later uses the same `+4h` purge and the same Binance 1m outcome semantics as the already-consumed development candidate run.
- No Stage-6 lifecycle code.

## TREND_PULLBACK variants

### `TP_FULL`

Frozen production detector unchanged. Existing candidate population is the reference.

### `TP_NO_4H`

Purpose: remove only the 4h regime requirement.

Mechanical definition:

1. Keep the real 1h bias at T.
2. If the real bias is `BULLISH`, replace only `context.regime_4h` with a structurally valid synthetic `BULLISH_TRENDING` result on the same 4h bucket.
3. If the real bias is `BEARISH`, replace only `context.regime_4h` with synthetic `BEARISH_TRENDING` on the same 4h bucket.
4. If the real bias is neutral/unavailable, no direction is established and this variant does not qualify.
5. Run the unmodified production `detect_trend_pullback()` with all price-structure, range-proxy, quality and instrument inputs unchanged.

Thus the 1h layer still determines direction and all non-4h gates are preserved.

### `TP_NO_1H`

Symmetric counterpart:

1. Keep the real 4h regime at T.
2. If it is `BULLISH_TRENDING`, replace only `context.bias_1h` with a structurally valid synthetic `BULLISH` result on the same 1h bucket.
3. If it is `BEARISH_TRENDING`, replace only `context.bias_1h` with synthetic `BEARISH`.
4. Non-directional/insufficient 4h context establishes no direction and does not qualify.
5. Run production `detect_trend_pullback()` unchanged otherwise.

### `TP_NO_CONTEXT`

Purpose: preserve the frozen pullback price-structure definition while removing both context layers.

Mechanical definition:

- For every legal 15m formation boundary, evaluate the unmodified production detector twice against the same real setup inputs:
  - once with synthetic bullish 4h + bullish 1h context;
  - once with synthetic bearish 4h + bearish 1h context.
- Emit each direction that independently satisfies the unchanged retracement/range-proxy/quality/instrument structure.
- If neither qualifies, emit none; if both qualify, both are retained as distinct directional structural hypotheses at the same T rather than inventing a post-hoc tie-break.

## COMPRESSION_BREAKOUT variants

### `CB_FULL`

Frozen production detector unchanged.

### `CB_NO_TAKER`

Purpose: remove only the current-5m taker-flow requirement.

Mechanical definition:

- Real compression history, fresh-cross price direction, price-structure quality, `price_direction_agreement`, real 4h/1h context, reference prices, range proxy and instrument metadata are unchanged.
- Only the current B5 `taker_flow` gate is neutralized for research:
  - taker-flow family coverage is replaced by `1.0`;
  - taker-flow family confidence by `100.0`;
  - `taker_delta_notional_usd_sum` is supplied with a non-zero sign matching the direction being tested.
- Production `detect_compression_breakout()` is still called unchanged; both taker signs may be tried, but the real fresh-cross condition can select at most the structurally compatible direction.

This removes taker availability/quality/sign as a qualification condition and nothing else.

### `CB_SIMPLE_COMPRESSION_BREAKOUT`

Purpose: price compression + fresh price breakout only, while retaining required data-integrity/structure construction.

Mechanical definition:

- Keep the real compression run, reference range, current/previous 5m reference closes, price-structure family quality, range proxy and instrument metadata.
- Neutralize the three non-price directional gates:
  - taker-flow as in `CB_NO_TAKER`;
  - set current `price_direction_agreement=1.0` solely to neutralize its threshold;
  - replace 4h regime with valid `NON_DIRECTIONAL` and 1h bias with valid `NEUTRAL_NOT_ESTABLISHED`, which the frozen `directional_context_gate()` explicitly accepts for either breakout direction.
- Call production `detect_compression_breakout()` unchanged.

No compression threshold/duration/lookback or fresh-cross formula changes.

### `CB_ORDINARY_RANGE_BREAKOUT`

Purpose: simple price-only breakout baseline without the compression precondition.

Mechanical definition:

1. At each legal 5m boundary T, use the same exact 16 closed 15m reference-bucket grid ending at production `B15` as `COMPRESSION_BREAKOUT` uses for its compression lookback.
2. Require all 16 Binance 15m reference vectors to pass the canonical usability gate and all constituent 1m bars to be complete.
3. Define `range_high = max(HTF_high)` and `range_low = min(HTF_low)` across **all 16** buckets, with no percentile/compression selection.
4. Use the same previous/current closed Binance 5m reference closes as production.
5. LONG iff `previous_close <= range_high and current_close > range_high`; SHORT iff `previous_close >= range_low and current_close < range_low`.
6. No 4h/1h context, agreement, taker-flow, compression percentile/duration, or Stage-6 logic participates.

The 16-bucket window is fixed because it is the direct no-compression counterpart of the frozen CB lookback; no alternative lookback will be scanned on development.

## CONFIRMED_BREAKOUT variants

### `FB_FULL`

Frozen production detector unchanged.

### `FB_NO_CONTEXT`

- Keep the exact frozen 48x1h structural high/low and fresh 5m crossing logic.
- Replace 4h regime with valid `NON_DIRECTIONAL` and 1h bias with valid `NEUTRAL_NOT_ESTABLISHED` on the same decision-boundary buckets.
- Run production `detect_confirmed_breakout()` unchanged.

### `FB_DUMB_48H_LEVEL_BREAKOUT`

Under the frozen Stage-5 contract, `CONFIRMED_BREAKOUT` has no taker-flow or price-agreement trigger gate; its qualification is exactly 48h structural level + fresh 5m cross + directional context. Therefore removing context leaves precisely the dumb 48h level-breakout rule.

**Consequently `FB_DUMB_48H_LEVEL_BREAKOUT` is an alias of the exact same candidate population as `FB_NO_CONTEXT`, not a second independent variant.** Reporting must state this equivalence rather than double-counting evidence.

## Interpretation discipline

- A fuller variant does not earn complexity merely by having fewer/more candidates.
- Compare outcome distributions, concentration and uncertainty, not only hit rate.
- If a no-context/no-feature variant is indistinguishable from or better than FULL, the removed component has not demonstrated incremental value.
- These development comparisons are diagnostic. Holdout remains unopened until variant generation/outcome/reporting/delay rules are frozen and reviewed.
