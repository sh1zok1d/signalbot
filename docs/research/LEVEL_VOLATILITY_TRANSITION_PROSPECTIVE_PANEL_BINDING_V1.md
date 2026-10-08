# LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_PANEL_BINDING_V1

Status: `FORWARD_PANEL_BOUND_OUTCOME_BLIND`. Owner go 2026-10-08 («Привяжи и проверь что все пишется»). Not a result. No transition, RV, barrier label, pseudo touch or pair was computed.

The frozen design (`LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1_DESIGN.md`, `d30622de`) names the forward source in its Data section: the existing Signalbot collection, aggregated to complete 5m bins by `scripts.research.dh1.data.aggregate_1m_to_5m`. Until now `status` always reported `panel_bound = false`. This note binds that source. The estimand, the stop, the epochs, the inference, the routes, the manifest and its digest are unchanged. The manifest stays immutable; its `forward_panel_path` stays `null`, because the panel is the live table, not a file. This note is the binding record.

## Source

- Table `klines_1m` of the Stage-1 collector (`storage/schema.sql`), `exchange = 'binance'`, `symbol = 'BTCUSDT'` (Binance USD-M perpetual). `ts` is the open time of the minute. Rows of both `source = 'live'` and `source = 'backfill'` (the collector's own startup gap fill) are the collection; the status prints the split.
- Read-only transaction. No write, no new table (the design forbids one).
- Warm-up from `2026-09-01T00:00:00Z`: October's month levels need September. Warm-up bars build levels and the 24h sigma only. They never open an eligible episode. The warm-up lies after the E1-RUN-001 holdout; the code refuses a row inside it.
- A minute counts only when closed (`ts + 1m <= now`). A 5m bin counts only when all five minutes are present. Nothing is filled.

## What the bound status reports

`python -m scripts.research.level_volatility_transition_prospective_confirmation_v1.status --live-db`

- the frozen clock fields (start, completed weeks, next checkpoint, stop flags) as before;
- `structural_episodes` and `real_first_touches` after the start, with `family_counts` and `side_counts` (resistance / support), from the frozen #352 constructor through `events.prospective_episodes` and `events.first_touches`;
- `bar_gaps_logged`: incomplete post-start 5m bins;
- `forward_panel`: rows read, rows by source, first and last closed minute, the age of the last closed minute, and the post-start coverage (expected, present and missing minutes, incomplete 5m bins, up to 50 missing runs).

`matched_path_complete_provisional` stays `null`: the pseudo map exists only at cohort close (`PERMANENT_PSEUDO_DURING_ACCRUAL = False`). `exact_outcome_read` stays `false`. The module imports neither the claim, the pairing nor the evaluator (test `tests/research/test_level_volatility_transition_prospective_panel_binding_v1.py`).

## Checks on the VPS (owner, read-only)

Pulling main into `/opt/signalbot` would be a deploy: the timer units run the new code on their next start. Run the check from a separate extract instead; `git fetch` only moves remote refs:

```bash
cd /opt/signalbot && git fetch origin main
rm -rf /tmp/sb368 && mkdir -p /tmp/sb368 && git archive origin/main | tar -x -C /tmp/sb368
cd /tmp/sb368 && set -a && . /opt/signalbot/.env && set +a && \
  /opt/signalbot/.venv/bin/python -m scripts.research.level_volatility_transition_prospective_confirmation_v1.status --live-db
```

If `/opt/signalbot/.env` is readable only by the service user, run the last two lines as that user (`sudo -u signalbot bash -c '…'`).

Expected before the start: `status = AWAITING_START`, `panel_bound = true`, `forward_panel.last_minute_age_s` under about 120, `rows_read` near 1 440 per day since 2026-09-01. After the start: `post_start_coverage.missing_minutes` near 0 and `incomplete_5m_bins` near 0.

Run it once now, once after 2026-10-09T00:10Z, then weekly. A gap after the start is recovered only from the official Binance USD-M archive, only for open times at or after the start, and only through `surface.append_recovery` into `LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_RECOVERY_V1.jsonl`. The status never chooses a gap by outcome; it lists all of them.

## Operational note

Any collector restart (`sudo systemctl restart signalbot.service`) makes a short hole in `klines_1m`. Before `2026-10-09T00:00:00Z` such a hole falls in warm-up and costs at most a few 5m bins of sigma history. After the start it is a post-start gap and needs a logged recovery. The data-reliability fix D1 is deployed only together with D2 (an OKX percentile history of zeros would otherwise make every OKX liquidation vote), so its restart will most likely fall after the start and be recovered this way.
