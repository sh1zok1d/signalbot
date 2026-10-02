"""Recorded-tape dry run of the 1h / 4h interpretation (owner review before the
UX thresholds are frozen; PRODUCT_FIRST_DECISION_V1 §3 build order).

Read-only. Recomputes the BETA_CONTEXT_1H_V2 readings at sampled buckets from the
recorded LIVE tape (and Stage-1 OI as-of), runs the pure interpretation, and
reports label frequencies, the behaviour of «биржи расходятся» (and how often the
ungated check would have fired in a calm market), and rendered examples.

`ignore_maturity=True` ranks against at least 3 days of history instead of the
production maturity tiers. Its numbers are PROVISIONAL: they show how the rules behave, not
what users would see before the ranks mature. Nothing here writes to the database,
changes a detector decision or feeds a research claim.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Sequence

from .config import BetaConfig
from .state_tape import BUCKET, iso

DRY_RUN_VERSION = "BETA_INTERPRETATION_DRY_RUN_V1"
# The percentile core needs strictly increasing tiers >= 1 day: provisional ranks count
# as mature after 3 days of history instead of the production span.
_NO_TIERS = {"none_below_days": 1, "low_below_days": 2, "building_below_days": 3}


# One rendered /catchup per category (the first sample that fits), for owner review.
RENDER_CATEGORIES = ("calm", "unusual_move", "inferred", "compression", "degraded", "venue_disagreement")


def _render_category(r1: Optional[Mapping[str, Any]], r4: Optional[Mapping[str, Any]],
                     done: Mapping[str, Any]) -> Optional[str]:
    from .interpretation import COMPRESSION, DATA_MISSING, INSUFFICIENT_HISTORY, INTERPRETED, NORMAL, VENUES_DIVERGE
    results = [r for r in (r1, r4) if r]
    checks = (
        ("venue_disagreement", lambda r: r["kind"] == VENUES_DIVERGE),
        ("inferred", lambda r: r["kind"] == INTERPRETED),
        ("unusual_move", lambda r: r["inputs"].get("price") in ("up", "down")),
        ("compression", lambda r: r["kind"] == COMPRESSION),
        ("degraded", lambda r: r["kind"] in (DATA_MISSING, INSUFFICIENT_HISTORY) or r["key"].endswith("_oi_na")),
        ("calm", lambda r: r["kind"] == NORMAL),
    )
    for name, fits in checks:
        if name not in done and any(fits(r) for r in results):
            return name
    return None


def _venue_signs_disagree(ctx: Mapping[str, Any]) -> bool:
    by = (ctx or {}).get("price_move_pct_by_venue") or {}
    signs = {(v > 0) - (v < 0) for v in by.values()}
    return len(signs) > 1


def run_dry_run(cfg: BetaConfig, *, sample_buckets: Sequence[datetime],
                metrics_by_bucket: Mapping[datetime, Mapping[str, Any]], oi_rows: Sequence[Mapping],
                liquidation_episodes: Sequence[Mapping], identity: Mapping[str, Any], code_version: str,
                tiers: Mapping[str, Any], ignore_maturity: bool = False, n_examples: int = 3,
                reference_prices: Optional[Mapping[datetime, float]] = None,
                triggered_episodes: Sequence[Mapping] = ()) -> dict:
    """Pure. `metrics_by_bucket` is the recorded tape (history before every sample
    included); every reading uses only buckets <= its sample bucket.

    `gate_coverage` is the decision's §3 row 7 diagnostic: of the sampled 1h windows
    that pass the unusual-hour gate, how many contain a TRIGGERED detector episode
    (`triggered_episodes`). A coverage check for the gate, never a research unit."""
    from .context import context_1h, history_span
    from .formatter import format_catchup
    from .horizons import build_horizons
    from .hour_gate import evaluate_hour
    from .interpretation import interpret, interpretation_text
    from .market_view import market_block
    from .oi_asof import OiAsofIndex
    oi_index = OiAsofIndex(oi_rows) if oi_rows else None
    use_tiers = _NO_TIERS if ignore_maturity else tiers
    ordered = sorted(metrics_by_bucket)
    counts = {"1h": Counter(), "4h": Counter()}
    examples: dict = {"1h": {}, "4h": {}}
    divergence = {"1h": [], "4h": []}
    calm_mixed_signs = Counter()
    gate_passed = Counter()
    kinds = {"1h": Counter(), "4h": Counter()}
    oi_degraded = {"1h": Counter(), "4h": Counter()}
    rendered: dict = {}
    coverage = {"unusual_hours": 0, "covered_by_triggered_episode": 0, "statuses": Counter()}
    span = history_span(cfg)
    for b in sample_buckets:
        if b not in metrics_by_bucket:
            continue
        lo = b - span
        hist = [(x, metrics_by_bucket[x]) for x in ordered if lo <= x < b]
        state = {"open": {}, "last_ended": {}}
        liq = [e for e in liquidation_episodes if e.get("opened_bucket") and datetime.fromisoformat(e["opened_bucket"]) <= b]
        for h in ("1h", "4h"):
            ctx = context_1h(cfg, bucket_ts=b, current_metrics=metrics_by_bucket[b], history=hist,
                             identity=identity, code_version=code_version, tiers=use_tiers,
                             oi_index=oi_index, horizon=h)
            state[f"context_{h}"] = ctx
            res = interpret(cfg, ctx, horizon=h, liquidation_episodes=liq)
            state[f"result_{h}"] = res
            if h == "1h":
                gate = evaluate_hour(cfg, ctx, liquidation_episodes=liq)
                coverage["statuses"][gate["status"]] += 1
                if gate["qualified"]:
                    coverage["unusual_hours"] += 1
                    if _hour_has_triggered(triggered_episodes, b):
                        coverage["covered_by_triggered_episode"] += 1
            counts[h][res["key"]] += 1
            kinds[h][res["kind"]] += 1
            if res["inputs"].get("oi") in ("MISSING", "IMMATURE"):
                oi_degraded[h][res["inputs"]["oi"]] += 1
            bucket_examples = examples[h].setdefault(res["key"], [])
            if len(bucket_examples) < n_examples:
                bucket_examples.append({"bucket": iso(b), "inputs": res["inputs"],
                                        "ru": interpretation_text(res, "ru"), "en": interpretation_text(res, "en"),
                                        "liquidation_episode": res["liquidation_episode"]})
            if res["key"] == "venues_diverge":
                pct = (ctx or {}).get("percentiles") or {}
                divergence[h].append({
                    "bucket": iso(b), "price_band": res["inputs"].get("price"),
                    "price_rank": (pct.get("price_move_pct_median") or {}).get("rank"),
                    "price_move_pct_median": (ctx or {}).get("price_move_pct_median"),
                    "by_venue": (ctx or {}).get("price_move_pct_by_venue"),
                    "oi": res["inputs"].get("oi"), "oi_change_pct_median": (ctx or {}).get("oi_change_pct_median"),
                    "taker": res["inputs"].get("taker"),
                    "taker_delta_notional_usd_sum": (ctx or {}).get("taker_delta_notional_usd_sum"),
                    "rendered_ru": interpretation_text(res, "ru")})
            if _venue_signs_disagree(ctx):
                if res["inputs"].get("price") == "flat":
                    calm_mixed_signs[h] += 1    # suppressed by the gate: aggregate move not unusual
                elif res["inputs"].get("price") in ("up", "down"):
                    gate_passed[h] += 1         # reached the agreement check
        category = _render_category(state.get("result_1h"), state.get("result_4h"), rendered)
        if category is not None:
            from .horizons import data_through, oi_boundaries
            metrics = {x: m for x, m in hist}
            metrics[b] = metrics_by_bucket[b]
            bounds = list(oi_boundaries(b)) + [data_through(b) - timedelta(hours=8)]
            oi = {bd: {ex: (oi_index.at(ex, bd) if oi_index else None) for ex in cfg.exchanges} for bd in bounds}
            tape = {"as_of": b, "metrics": metrics, "oi": oi}
            view = {"product_status": "NO ACTIVE EVENTS", "kind": "catchup",
                    "now": {"reference_price": (reference_prices or {}).get(b)},
                    "data_through": iso(b + BUCKET),
                    "horizons": build_horizons(cfg, as_of_bucket=b, metrics_by_bucket=metrics, oi_by_boundary=oi)}
            state["open"] = {e["event_type"]: e for e in liq}
            view["market"] = market_block(cfg, view, state, tape, window_hours=8)
            rendered[category] = {"bucket": iso(b), "ru": format_catchup(cfg, view, "ru")}
    total = {h: sum(c.values()) for h, c in counts.items()}
    coverage["statuses"] = dict(coverage["statuses"])
    coverage["share"] = (round(coverage["covered_by_triggered_episode"] / coverage["unusual_hours"], 4)
                         if coverage["unusual_hours"] else None)
    return {
        "version": DRY_RUN_VERSION,
        "gate_coverage": coverage,
        "status": "PROVISIONAL_RANKS_IGNORE_MATURITY" if ignore_maturity else "PRODUCTION_MATURITY_RULES",
        "samples": len([b for b in sample_buckets if b in metrics_by_bucket]),
        "first_sample": iso(min(sample_buckets)) if sample_buckets else None,
        "last_sample": iso(max(sample_buckets)) if sample_buckets else None,
        "frequencies": {h: {k: {"n": n, "share": round(n / total[h], 4) if total[h] else None}
                            for k, n in sorted(c.items(), key=lambda kv: -kv[1])} for h, c in counts.items()},
        "kinds": {h: dict(c) for h, c in kinds.items()},
        "oi_degraded": {h: dict(c) for h, c in oi_degraded.items()},
        "venues_diverge": {h: {"n": len(v), "cases": v} for h, v in divergence.items()},
        "calm_mixed_venue_signs_not_labelled": dict(calm_mixed_signs),
        "mixed_venue_signs_passed_gate": dict(gate_passed),
        "examples": examples,
        "rendered_catchup_ru": [{"category": c, **rendered[c]} for c in RENDER_CATEGORIES if c in rendered],
        "oi_rows": len(oi_rows), "liquidation_episodes": len(liquidation_episodes),
    }


def _hour_has_triggered(episodes: Sequence[Mapping], bucket: datetime) -> bool:
    """A TRIGGERED episode whose qualifying buckets reach into the rolling hour ending
    at `bucket` (12 closed 5m buckets)."""
    start, end = bucket - 11 * BUCKET, bucket + BUCKET
    for ep in episodes:
        if not ep.get("triggered_at") or not ep.get("opened_bucket"):
            continue
        first = datetime.fromisoformat(ep["opened_bucket"])
        last = datetime.fromisoformat(ep.get("last_bucket") or ep["opened_bucket"])
        if first < end and last + BUCKET > start:
            return True
    return False


def _close_median(cfg: BetaConfig, metrics: Mapping[str, Any]) -> Optional[float]:
    from .state_tape import metric_key
    closes = sorted(float(v) for v in (metrics.get(metric_key(ex, "kline_close")) for ex in cfg.exchanges)
                    if v is not None)
    if not closes:
        return None
    m = len(closes) // 2
    return closes[m] if len(closes) % 2 else (closes[m - 1] + closes[m]) / 2.0


def sample_grid(start: datetime, end: datetime, stride_buckets: int) -> list:
    out, b = [], start
    while b <= end:
        out.append(b)
        b += stride_buckets * BUCKET
    return out


async def run_dry_run_from_db(conn, cfg: BetaConfig, stage2_config, *, end: datetime, days: int,
                              stride_buckets: int, ignore_maturity: bool) -> dict:
    """Read-only reads, then the pure dry run."""
    from .context import history_span
    from .oi_asof import OI_ASOF_TOLERANCE
    latest = await conn.fetch_latest_live_tape(symbol=cfg.symbol)
    if latest is None:
        return {"version": DRY_RUN_VERSION, "status": "NO_LIVE_TAPE"}
    snap = latest["snapshot"]
    ident = snap.get("identity") or {}
    end = min(end, latest["bucket_ts"])
    start = end - timedelta(days=days)
    span = history_span(cfg)
    hist = await conn.fetch_tape_history(
        symbol=cfg.symbol, market_type=cfg.market_type, timeframe=cfg.timeframe,
        calculation_version=ident["calculation_version"], state_schema_versions=(cfg.state_schema_version,),
        start=start - span, end=end + BUCKET)
    oi_rows = await conn.fetch_open_interest_range(symbol=cfg.symbol, exchanges=list(cfg.exchanges),
                                                   start=start - span - OI_ASOF_TOLERANCE, end=end + BUCKET)
    liq = await conn.fetch_liquidation_episodes(symbol=cfg.symbol, start=start - timedelta(hours=4), end=end + BUCKET)
    triggered = await conn.fetch_triggered_episodes(symbol=cfg.symbol, start=start - timedelta(hours=4), end=end + BUCKET)
    tiers = stage2_config.resolve(cfg.symbol)["percentiles"]["confidence_tiers"]
    metrics = {b: m for b, m in hist}
    prices = {b: _close_median(cfg, m) for b, m in hist}
    report = run_dry_run(cfg, sample_buckets=sample_grid(start, end, stride_buckets), metrics_by_bucket=metrics,
                         oi_rows=oi_rows, liquidation_episodes=liq, identity=ident,
                         code_version=snap.get("feature_code_version") or "dry-run", tiers=tiers,
                         ignore_maturity=ignore_maturity, reference_prices=prices, triggered_episodes=triggered)
    report["tape_rows"] = len(hist)
    return report
