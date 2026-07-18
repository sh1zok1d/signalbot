"""
Stage-1 validation / smoke check.

Answers the spec's stage-1 acceptance question directly - "получить, сохранить и
ПРОВАЛИДИРОВАТЬ реальные 1m бары по всем 4 биржам ... показать рабочий прототип":
after a backfill and/or a live run, this queries TimescaleDB and prints a
human-readable report so you can eyeball that data is actually landing and looks
sane, without hand-writing SQL each time.

Run:
    python main.py --validate          # report only, no backfill, no live WS

It is read-only. It classifies every (exchange, metric) against the structural
capability registry (exchange_capabilities, seeded from common/capabilities.py)
so it can distinguish, per the spec:
  * not_available   - the exchange structurally has no such feed (supported=false)
                      -> shown as not_available, NOT as zero and NOT as an error
  * no_data         - supported=true but nothing stored -> ERROR
  * stale           - newest row older than the metric's freshness budget -> ERROR
  * short_history   - historical coverage shorter than the 30d window -> WARNING
  * ok              - fresh, present
Freshness is reported separately for ohlcv, taker_flow, open_interest, funding,
mark_price and liquidations, and coverage is summarised per metric (how many
exchanges are currently valid) so the spec's "min 3 exchanges" / "coverage shown
separately" rules can be read off directly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from common.config import Config
from storage.db import Database

logger = logging.getLogger(__name__)

SHORT_HISTORY_TOLERANCE_H = 6   # allow the window start to slip a few hours before warning

# Continuous / polled metrics that ARE freshness-gated. Liquidations are
# handled separately (event-driven — see the dedicated section) and must NOT be
# marked stale just because no liquidation happened recently. taker_flow lives
# in the klines_1m taker columns; we only count bars where the split is known.
METRIC_SOURCES = {
    "ohlcv":         ("klines_1m", None),
    "taker_flow":    ("klines_1m", "taker_buy_volume IS NOT NULL AND taker_sell_volume IS NOT NULL"),
    "open_interest": ("open_interest", None),
    "funding":       ("funding_rate", None),
    "mark_price":    ("mark_price", None),
}

# How far back "events in window" counts for the liquidation activity indicator.
LIQ_WINDOW_MIN = 60

# Which metrics feed the spec's 3-exchange consensus (price/OI/order flow).
CONSENSUS_METRICS = ("ohlcv", "open_interest", "taker_flow")


def _confidence_tier(span_days, cfg) -> tuple[str, bool]:
    """Map a historical-sample span (days) to a data-confidence tier using the
    percentiles config. Returns (tier, gate_ok) where gate_ok=False means the
    future percentile_engine MUST disable the corresponding hard gate / treat
    this source's coverage as low (spec: percentile thresholds need enough
    history before they mean anything)."""
    if span_days is None:
        return "none", False
    p = cfg["percentiles"]
    if span_days < p["min_days_for_confidence"]:
        return "none", False
    if span_days < p["window_days"]:
        return "low", True
    if span_days < p["window_days_mature"]:
        return "building", True
    return "mature", True


def _fmt_ts(ts) -> str:
    if ts is None:
        return "—"
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%SZ")
    return str(ts)


def _fmt_age(seconds) -> str:
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 90:
        return f"{s}s"
    if s < 5400:
        return f"{s // 60}m"
    return f"{s // 3600}h"


async def validate_ingestion(db: Database, cfg: Config, redis=None) -> dict:
    symbol = cfg.symbol
    exchanges = cfg.enabled_exchanges          # ACTIVE set (coverage is over these)
    disabled = cfg.disabled_exchanges          # known-but-inactive (e.g. bitget)
    min_sources = cfg["consensus"]["price_oi_orderflow_min"]  # normal consensus min
    window_days = cfg["backfill"]["window_days"]
    now = datetime.now(tz=timezone.utc)
    expected_start = now - timedelta(days=window_days)

    report: dict = {"symbol": symbol, "checked_at": now, "enabled_exchanges": exchanges,
                    "disabled_exchanges": disabled, "exchanges": {},
                    "metrics": {}, "problems": [], "warnings": []}

    # Structural capability registry from the DB (NOT the client classes).
    caps_rows = await db.get_capabilities()
    caps = {(r["exchange"], r["metric"]): r for r in caps_rows}

    lines: list[str] = []
    lines.append("=" * 78)
    lines.append(f"STAGE-1 VALIDATION  |  {symbol}  |  {_fmt_ts(now)}")
    lines.append(f"Active exchanges: {', '.join(exchanges)} "
                 f"(consensus min {min_sources}/{len(exchanges)})")
    if disabled:
        lines.append(f"Disabled (data retained, not ingested): {', '.join(disabled)}")
    lines.append(f"Expected {window_days}d backfill window start ~ {_fmt_ts(expected_start)}")
    if not caps:
        lines.append("!! exchange_capabilities is empty — run the bot once to seed it "
                     "(python main.py --backfill-only).")
        report["problems"].append("capability registry not seeded")
    lines.append("=" * 78)

    # ---------------- per-metric freshness / availability ----------------
    # coverage_counts[metric] = number of exchanges currently OK (present+fresh)
    coverage_counts: dict[str, int] = {m: 0 for m in METRIC_SOURCES}

    for metric, (table, filt) in METRIC_SOURCES.items():
        lines.append("")
        lines.append(f"{metric.upper()}  ({table})")
        lines.append(f"  {'exchange':<9} {'rows':>8} {'last':>21} {'age':>6} "
                     f"{'cover':>10} {'status':>13}")
        for ex in exchanges:
            cap = caps.get((ex, metric))
            where = f"exchange=$1 AND symbol=$2" + (f" AND {filt}" if filt else "")
            r = (await db.fetch(
                f"SELECT count(*) n, min(ts) f, max(ts) l FROM {table} WHERE {where}",
                ex, symbol))[0]
            n, first_ts, last_ts = r["n"], r["f"], r["l"]
            age_s = (now - last_ts).total_seconds() if last_ts else None
            cover = cap["coverage_type"] if cap else "?"
            fresh_budget = cap["expected_freshness_s"] if cap else None

            status, is_ok = _classify(metric, cap, n, age_s, fresh_budget)
            if is_ok:
                coverage_counts[metric] += 1

            lines.append(f"  {ex:<9} {n:>8} {_fmt_ts(last_ts):>21} {_fmt_age(age_s):>6} "
                         f"{cover:>10} {status:>13}")

            report["exchanges"].setdefault(ex, {})[metric] = {
                "rows": n, "first_ts": first_ts, "last_ts": last_ts,
                "age_s": age_s, "coverage_type": cover, "status": status}

            # Record problems/warnings by severity.
            if status == "STALE":
                report["problems"].append(
                    f"{ex}/{metric}: STALE — newest row {_fmt_age(age_s)} old "
                    f"(budget {fresh_budget}s)")
            elif status == "NO_DATA":
                report["problems"].append(
                    f"{ex}/{metric}: supported but NO DATA stored")

            # Short historical coverage (only where history is expected).
            if cap and cap["historical_supported"] and first_ts and n:
                if first_ts > expected_start + timedelta(hours=SHORT_HISTORY_TOLERANCE_H):
                    short_h = (first_ts - expected_start).total_seconds() / 3600.0
                    report["warnings"].append(
                        f"{ex}/{metric}: short history — starts {_fmt_ts(first_ts)} "
                        f"(~{short_h:.0f}h into the {window_days}d window)")

        report["metrics"][metric] = coverage_counts[metric]

    # ---------------- liquidations (event-driven, NOT freshness-gated) ----------------
    # A liquidation feed being quiet does NOT mean it's unavailable or stale —
    # liquidations are sporadic. So we report the orthogonal facts separately:
    # structural capability, coverage_type, live connection/subscription health
    # (from Redis, if a session is/was running), events in the window, and the
    # last event time. We NEVER emit a 'stale'/error just for a quiet feed.
    liq_status = {}
    if redis is not None:
        try:
            liq_status = await redis.get_all_exchange_status()
        except Exception:  # noqa: BLE001
            liq_status = {}
    lines.append("")
    lines.append("LIQUIDATIONS (event-driven — quiet feed is NOT stale/unavailable)")
    lines.append(f"  {'exchange':<9} {'capability':>11} {'coverage':>10} {'conn health':>16} "
                 f"{f'evt<{LIQ_WINDOW_MIN}m':>9} {'total':>7} {'last event':>21}")
    report["liquidations"] = {}
    for ex in exchanges:
        cap = caps.get((ex, "liquidations"))
        supported = bool(cap and cap["live_supported"])
        capability = "supported" if supported else "unavailable"
        cov = cap["coverage_type"] if cap else "?"
        r = (await db.fetch(
            f"SELECT count(*) n, max(ts) l, "
            f"count(*) FILTER (WHERE ts > now() - interval '{LIQ_WINDOW_MIN} minutes') recent "
            f"FROM liquidations WHERE exchange=$1 AND symbol=$2", ex, symbol))[0]
        total, last_ts, recent = r["n"], r["l"], r["recent"]

        # Connection/subscription health from the live session's Redis snapshot.
        st = liq_status.get(ex)
        if not supported:
            health = "n/a"
        elif st is None:
            health = "no live session"
        else:
            age = (now.timestamp() - st.get("updated_at", 0))
            hs = "conn+healthy" if st.get("healthy") else (
                "connected" if st.get("connected") else "down")
            health = f"{hs} ({_fmt_age(age)} ago)"

        lines.append(f"  {ex:<9} {capability:>11} {cov:>10} {health:>16} "
                     f"{recent:>9} {total:>7} {_fmt_ts(last_ts):>21}")
        report["liquidations"][ex] = {"capability": capability, "coverage_type": cov,
                                      "events_window": recent, "total": total,
                                      "last_event_ts": last_ts, "conn_health": health}
        # Only flag a genuine capability/health problem — never a quiet feed.
        if supported and st is not None and not st.get("connected"):
            report["warnings"].append(
                f"{ex}/liquidations: feed supported but connection is down")

    # ---------------- coverage per metric ----------------
    lines.append("")
    lines.append("COVERAGE PER METRIC (exchanges currently valid = present + fresh)")
    for metric in METRIC_SOURCES:
        c = coverage_counts[metric]
        flag = ""
        if metric in CONSENSUS_METRICS:
            if c < min_sources:
                flag = f"  << below consensus min {min_sources} (blocks TRIGGERED)"
                report["warnings"].append(
                    f"{metric}: coverage {c}/{len(exchanges)} < required "
                    f"{min_sources} for consensus")
        lines.append(f"  {metric:<15} {c}/{len(exchanges)}{flag}")
    # Liquidation coverage = how many exchanges STRUCTURALLY provide it (with
    # coverage_type), not how many fired recently. Event-driven, so no min-fresh.
    liq_supported = sum(1 for ex in exchanges
                        if caps.get((ex, "liquidations")) and caps[(ex, "liquidations")]["live_supported"])
    liq_types = ", ".join(f"{ex}:{caps[(ex,'liquidations')]['coverage_type']}"
                          for ex in exchanges if caps.get((ex, "liquidations")))
    lines.append(f"  {'liquidations':<15} {liq_supported}/{len(exchanges)} supported "
                 f"(event-driven; [{liq_types}])")

    # ---------------- taker-flow historical sample & data confidence ----------------
    # Only Binance has a historical taker split; Bybit/OKX/Bitget accumulate it
    # live from process start (never faked/zero-filled). The percentile_engine
    # (stage 2) must know how much real taker history exists per exchange so it
    # can disable the taker hard gate / lower coverage where it's too thin.
    lines.append("")
    lines.append("TAKER FLOW — historical sample & data confidence")
    lines.append(f"  {'exchange':<9} {'taker bars':>11} {'sample span':>13} "
                 f"{'days':>6} {'confidence':>11} {'gate':>6}")
    report["taker_confidence"] = {}
    for ex in exchanges:
        r = (await db.fetch(
            "SELECT count(*) n, min(ts) f, max(ts) l FROM klines_1m "
            "WHERE exchange=$1 AND symbol=$2 "
            "AND taker_buy_volume IS NOT NULL AND taker_sell_volume IS NOT NULL",
            ex, symbol))[0]
        n, f_ts, l_ts = r["n"], r["f"], r["l"]
        span_days = (l_ts - f_ts).total_seconds() / 86400.0 if (f_ts and l_ts) else None
        tier, gate_ok = _confidence_tier(span_days, cfg)
        span_txt = f"{_fmt_ts(f_ts)[:10]}→{_fmt_ts(l_ts)[:10]}" if f_ts else "—"
        lines.append(f"  {ex:<9} {n:>11} {span_txt:>13} "
                     f"{(f'{span_days:.1f}' if span_days is not None else '—'):>6} "
                     f"{tier:>11} {('ok' if gate_ok else 'OFF'):>6}")
        report["taker_confidence"][ex] = {"bars": n, "span_days": span_days,
                                          "tier": tier, "gate_ok": gate_ok}
        if not gate_ok:
            report["warnings"].append(
                f"{ex}/taker_flow: confidence '{tier}' "
                f"({span_days:.1f}d < {cfg['percentiles']['min_days_for_confidence']}d) "
                f"— percentile_engine must disable the taker gate for this exchange"
                if span_days is not None else
                f"{ex}/taker_flow: no taker history yet — percentile_engine must "
                f"disable the taker gate for this exchange")

    # ---------------- backfill_runs bookkeeping ----------------
    lines.append("")
    lines.append("BACKFILL RUNS (most recent per exchange/source)")
    lines.append(f"  {'exchange':<9} {'source':<15} {'status':<9} {'rows':>9}  note")
    runs = await db.fetch(
        """
        SELECT DISTINCT ON (exchange, source)
               exchange, source, status, rows_written, note
        FROM backfill_runs WHERE symbol = $1
        ORDER BY exchange, source, id DESC
        """,
        symbol,
    )
    for r in runs:
        note = (r["note"] or "")[:42]
        lines.append(f"  {r['exchange']:<9} {r['source']:<15} {r['status']:<9} "
                     f"{r['rows_written']:>9}  {note}")
        if r["status"] == "failed":
            report["problems"].append(
                f"{r['exchange']}/{r['source']}: backfill FAILED - {r['note']}")
    if not runs:
        lines.append("  (no backfill runs recorded yet)")

    # ---------------- disabled exchanges (data retained, not ingested) ----------------
    if disabled:
        lines.append("")
        lines.append("DISABLED EXCHANGES (config.enabled_exchanges excludes these — "
                     "data retained, NOT ingested, NOT in coverage)")
        lines.append(f"  {'exchange':<9} {'klines rows':>12} {'last bar':>21} {'note':>22}")
        for ex in disabled:
            r = (await db.fetch(
                "SELECT count(*) n, max(ts) l FROM klines_1m WHERE exchange=$1 AND symbol=$2",
                ex, symbol))[0]
            lines.append(f"  {ex:<9} {r['n']:>12} {_fmt_ts(r['l']):>21} {'disabled':>22}")
            report["exchanges"].setdefault(ex, {})["disabled"] = True
        # Disabled exchanges are intentionally excluded — never an error/stale.

    # ---------------- continuous aggregates sanity ----------------
    lines.append("")
    lines.append("CONTINUOUS AGGREGATES (row counts; empty is OK before first refresh)")
    for cagg in ("klines_5m", "klines_15m", "klines_1h", "klines_4h"):
        try:
            cnt = await db.fetchval(f"SELECT count(*) FROM {cagg}")
        except Exception as exc:  # noqa: BLE001
            cnt = f"error: {exc}"
            report["problems"].append(f"{cagg}: not queryable - {exc}")
        lines.append(f"  {cagg:<12} {cnt}")

    # ---------------- verdict ----------------
    lines.append("")
    lines.append("-" * 78)
    if report["warnings"]:
        lines.append(f"⚠  {len(report['warnings'])} warning(s):")
        for w in report["warnings"]:
            lines.append(f"   - {w}")
    if report["problems"]:
        lines.append(f"✗  {len(report['problems'])} error(s):")
        for p in report["problems"]:
            lines.append(f"   - {p}")
    if not report["problems"] and not report["warnings"]:
        lines.append("✓  No problems detected. Data is landing and looks sane.")
    lines.append("-" * 78)

    report["ok"] = not report["problems"]
    print("\n".join(lines))
    return report


def _classify(metric: str, cap, n: int, age_s, fresh_budget):
    """Return (status_label, counts_toward_coverage).

    Distinguishes, per spec:
      not_available (structural, supported=false) vs no_data (supported=true,
      empty) vs stale (too old) vs ok. Liquidations are event-driven, so an
      empty/aged liquidations feed is 'no_events', never an error.
    """
    if cap is None:
        return "no_registry", False
    if not cap["live_supported"] and cap["coverage_type"] == "unavailable":
        return "not_available", False

    if metric == "liquidations":
        # Event-driven: absence is not an error, and "age" is meaningless
        # (liquidations are sporadic). Report presence only.
        if n == 0:
            return "no_events", False
        return "ok", True

    if n == 0:
        return "NO_DATA", False

    if fresh_budget is not None and age_s is not None and age_s > fresh_budget:
        return "STALE", False
    return "ok", True
