"""C1 product validation: replay recorded beta history under C0 (BETA_CONTEXT_1H_V2, pooled
reference) and C1 (BETA_CONTEXT_1H_V3, same UTC day type) side by side.

Read-only. Same inputs, two context identities: reports how many /btc states, unusual-hour gate
qualifications, compression / interpretation labels and time-of-day "обычно" ratios change, and
which recorded push decisions would have had a different gate outcome. This is product
validation of the change, not a new evaluation of C1. Nothing is written; no decision changes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Sequence

from .config import BetaConfig
from .state_tape import BUCKET, iso

REPLAY_VERSION = "BETA_C1_REPLAY_V1"
C0_VERSION = "BETA_CONTEXT_1H_V2"


def c0_config(cfg: BetaConfig) -> BetaConfig:
    return cfg.with_overrides(context={**cfg.section("context"), "version": C0_VERSION})


def _readings(cfg, b, metrics_by_bucket, ordered, span, identity, code_version, tiers, oi_index):
    from .context import context_1h
    lo = b - span
    hist = [(x, metrics_by_bucket[x]) for x in ordered if lo <= x < b]
    return {h: context_1h(cfg, bucket_ts=b, current_metrics=metrics_by_bucket[b], history=hist,
                          identity=identity, code_version=code_version, tiers=tiers,
                          oi_index=oi_index, horizon=h) for h in ("1h", "4h")}


def _state(cfg, ctx: Mapping[str, Any], liq) -> dict:
    """The /btc-relevant state of one reading: interpretation keys, gate, level labels."""
    from .context import level_label
    from .hour_gate import evaluate_hour
    from .interpretation import interpret
    out = {}
    for h in ("1h", "4h"):
        c = ctx.get(h)
        res = interpret(cfg, c, horizon=h, liquidation_episodes=liq) if c else None
        out[f"interp_{h}"] = None if res is None else res["key"]
        pct = (c or {}).get("percentiles") or {}
        for m in ("range_width_pct_median", "volume_notional_usd_sum"):
            p = pct.get(m) or {}
            out[f"level_{h}_{m}"] = level_label(cfg, p.get("rank"), p.get("tier"))
    gate = evaluate_hour(cfg, ctx.get("1h"), liquidation_episodes=liq) if ctx.get("1h") else None
    out["gate_status"] = None if gate is None else gate["status"]
    out["gate_qualified"] = bool(gate and gate["qualified"])
    passed = (gate or {}).get("passed") or {}
    out["flag_range"], out["flag_volume"] = bool(passed.get("range")), bool(passed.get("volume"))
    out["flag_price"] = passed.get("price") is not None
    return out


def _tod(cfg, metrics_by_bucket, b, day_type: bool) -> dict:
    from .horizons import _baseline_tod
    base = _baseline_tod(cfg, metrics_by_bucket, b, 12, day_type=day_type)
    return {m: base["median"][m] for m in ("range_width_pct_median", "volume_notional_usd_sum")}


def run_c1_replay(cfg: BetaConfig, *, sample_buckets: Sequence[datetime],
                  metrics_by_bucket: Mapping[datetime, Mapping[str, Any]], oi_rows: Sequence[Mapping],
                  liquidation_episodes: Sequence[Mapping], identity: Mapping[str, Any], code_version: str,
                  tiers: Mapping[str, Any], push_decisions: Sequence[Mapping] = ()) -> dict:
    """Pure. `cfg` is the C1 (V3) config; C0 is the same config under the V2 label."""
    from .context import history_span, rolling_window_values
    from .day_type import window_day_type
    from .oi_asof import OiAsofIndex
    c0, c1 = c0_config(cfg), cfg
    oi_index = OiAsofIndex(oi_rows) if oi_rows else None
    ordered = sorted(metrics_by_bucket)
    span = history_span(cfg)
    by_type = {"WEEKDAY": Counter(), "WEEKEND": Counter()}
    qualified_days: dict = {"C0": Counter(), "C1": Counter()}
    examples: list = []
    for b in sample_buckets:
        if b not in metrics_by_bucket:
            continue
        liq = [e for e in liquidation_episodes if e.get("opened_bucket")
               and datetime.fromisoformat(e["opened_bucket"]) <= b]
        r0 = _readings(c0, b, metrics_by_bucket, ordered, span, identity, code_version, tiers, oi_index)
        r1 = _readings(c1, b, metrics_by_bucket, ordered, span, identity, code_version, tiers, oi_index)
        s0, s1 = _state(c0, r0, liq), _state(c1, r1, liq)
        kind = window_day_type(b, 12)
        cnt = by_type[kind]
        cnt["samples"] += 1
        changed = [k for k in s0 if s0[k] != s1[k]]
        cnt["btc_state_changed"] += bool(changed)
        for k in changed:
            cnt[f"changed:{k}"] += 1
        for name, s in (("C0", s0), ("C1", s1)):
            cnt[f"{name}:gate_qualified"] += s["gate_qualified"]
            cnt[f"{name}:compression_1h"] += s["interp_1h"] in ("compression", "compression_oi_na")
            cnt[f"{name}:compression_4h"] += s["interp_4h"] in ("compression", "compression_oi_na")
            cnt[f"{name}:immature_1h"] += s["gate_status"] == "IMMATURE"
            mature = s["gate_status"] not in (None, "IMMATURE", "CONTEXT_UNAVAILABLE")
            cnt[f"{name}:mature_1h"] += mature
            for f in ("flag_range", "flag_volume", "flag_price"):   # live calibration vs 5 / 5 / 10 %
                cnt[f"{name}:{f}"] += mature and s[f]
            if s["gate_qualified"]:
                qualified_days[name][b.date().isoformat()] += 1
        cur = rolling_window_values(cfg, metrics_by_bucket, b, 12)
        if cur is not None:
            t0, t1 = _tod(cfg, metrics_by_bucket, b, False), _tod(cfg, metrics_by_bucket, b, True)
            for m in t0:
                v = cur.get(m)
                a0 = None if v is None or t0[m] is None else v > t0[m]
                a1 = None if v is None or t1[m] is None else v > t1[m]
                cnt[f"tod_{m}:above_C0"] += bool(a0)
                cnt[f"tod_{m}:above_C1"] += bool(a1)
                cnt[f"tod_{m}:status_changed"] += a0 != a1
        if changed and len(examples) < 12:
            examples.append({"bucket": iso(b), "day_type": kind,
                             "changed": {k: [s0[k], s1[k]] for k in changed}})
    # recorded push decisions: the gate outcome at the decision bucket under C0 vs C1
    push = {"WEEKDAY": Counter(), "WEEKEND": Counter()}
    for d in push_decisions:
        b = d["decision_ts"] - BUCKET
        if b not in metrics_by_bucket:
            continue
        kind = window_day_type(b, 12)
        r0 = _readings(c0, b, metrics_by_bucket, ordered, span, identity, code_version, tiers, oi_index)
        r1 = _readings(c1, b, metrics_by_bucket, ordered, span, identity, code_version, tiers, oi_index)
        g0, g1 = _state(c0, r0, [])["gate_qualified"], _state(c1, r1, [])["gate_qualified"]
        p = push[kind]
        p["decisions"] += 1
        p[f"recorded:{d['decision']}:{d.get('suppression_reason') or '-'}"] += 1
        if g0 and not g1:
            p["gate_lost_under_C1"] += 1                    # a push here would become HOUR_NOT_UNUSUAL
            p["recorded_push_that_C1_would_suppress"] += d["decision"] == "PUSH"
        if g1 and not g0:
            p["gate_gained_under_C1"] += 1                  # now passes the gate; later rules still apply
            p["recorded_hour_not_unusual_that_C1_would_pass"] += d.get("suppression_reason") == "HOUR_NOT_UNUSUAL"
    days0, days1 = qualified_days["C0"], qualified_days["C1"]
    return {
        "version": REPLAY_VERSION, "c0": C0_VERSION, "c1": cfg.section("context")["version"],
        "samples": sum(c["samples"] for c in by_type.values()),
        "first_sample": iso(min(sample_buckets)) if sample_buckets else None,
        "last_sample": iso(max(sample_buckets)) if sample_buckets else None,
        "by_day_type": {k: dict(v) for k, v in by_type.items()},
        "push_decisions": {k: dict(v) for k, v in push.items()},
        "gate_qualified_samples_per_day": {"C0": dict(days0), "C1": dict(days1),
                                           "max_C0": max(days0.values(), default=0),
                                           "max_C1": max(days1.values(), default=0)},
        "examples": examples,
        "nominal_flag_rates": {"flag_range": 0.05, "flag_volume": 0.05, "flag_price": 0.10},
        "historical_expectation_unit_v2": {
            "C0": {"WEEKDAY": {"flag_range": 0.0677, "flag_volume": 0.0675, "flag_price": 0.1272, "gate": 0.0713},
                   "WEEKEND": {"flag_range": 0.0251, "flag_volume": 0.0198, "flag_price": 0.0566, "gate": 0.0239}},
            "C1": {"WEEKDAY": {"flag_range": 0.0569, "flag_volume": 0.0549, "flag_price": 0.1080, "gate": 0.0591},
                   "WEEKEND": {"flag_range": 0.0560, "flag_volume": 0.0563, "flag_price": 0.1072, "gate": 0.0585}}},
        "note": "Samples are on the replay grid (stride); a gate-qualified sample is an hour that "
                "would be listed as unusual. Pushes additionally need a TRIGGERED detector episode "
                "and the unchanged push policy (cooldowns, quiet hours, daily cap).",
    }


async def run_c1_replay_from_db(conn, cfg: BetaConfig, stage2_config, *, end: datetime, days: int,
                                stride_buckets: int) -> dict:
    """Read-only reads (the same as --beta-context-dry-run, plus the recorded push decisions)."""
    from .context import history_span
    from .dry_run import sample_grid
    from .oi_asof import OI_ASOF_TOLERANCE
    latest = await conn.fetch_latest_live_tape(symbol=cfg.symbol)
    if latest is None:
        return {"version": REPLAY_VERSION, "status": "NO_LIVE_TAPE"}
    ident = latest["snapshot"].get("identity") or {}
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
    decisions = await conn.fetch_push_decisions_range(start=start, end=end + BUCKET)
    tiers = stage2_config.resolve(cfg.symbol)["percentiles"]["confidence_tiers"]
    report = run_c1_replay(cfg, sample_buckets=sample_grid(start, end, stride_buckets),
                           metrics_by_bucket={b: m for b, m in hist}, oi_rows=oi_rows,
                           liquidation_episodes=liq, identity=ident,
                           code_version=latest["snapshot"].get("feature_code_version") or "replay",
                           tiers=tiers, push_decisions=decisions)
    report["tape_rows"] = len(hist)
    report["status"] = "OK"
    return report
