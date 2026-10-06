"""Prospective claim journal (docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md; PRE_BETA_SCOPE_DECISION_V1 §6.2).

Every L2 / L3 number the bot is entitled to state is written with the numbers exactly as its
template prints them and an evaluation rule frozen at write, on a grid that does not depend on
users:

- **hourly** (inside `run_market_alerts`, beside the corridor forecasts):
  - `L3_LEVEL_TOUCH_{4H,24H}`: the chance to reach each level zone of the decision block;
  - `L3_DISTANCE_TOUCH_{1H,4H,24H}`: the chance to reach a fixed grid of distances on each side
    (the `/risk` table and every arbitrary level of `/check` are read off this curve);
  - `L2_STATE_ANALOG_{W}_{H}`: «после похожих» for the live 1h / 4h label at the full hour;
  - `L2_DH3_P1_RANGE_4H`: the DH3-P1 cohort (quiet hours, OI built up over 4h or not);
- **at every level-touch evaluation** (`PUSH` or `SUPPRESSED`): `L2_LEVEL_FIRST_TOUCH_HOLD_{1H,4H}`.

Whether a surface showed a claim is a separate link (`record_displays`). The scorer reads the rule
from the claim row; the database refuses an outcome under another rule. Nothing here reads an
outcome at write time, steers a push, or changes a corridor, a touch chance or a text.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

import numpy as np

from .hist_series import BAR_MS, BARS_PER_DAY, Bars, to_ms
from .state_tape import sha256_json

logger = logging.getLogger("beta.claims")

JOURNAL_VERSION = "BETA_CLAIMS_V1"
HORIZON_MS = {"1h": 3_600_000, "4h": 14_400_000, "24h": 86_400_000}
TOUCH_GRID_PCT = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)        # contains the /risk table (0.25 / 0.5 / 1 / 2)
NEITHER_GRID_PCT = (0.5, 1.0, 2.0, 3.0)                 # «ни один» pairs (calibration note §7)
WRITE_WINDOW = timedelta(minutes=10)                    # as the corridor forecasts (market_alerts)
SETTLE = timedelta(minutes=3)
NO_DATA_AFTER = timedelta(hours=6)
COVERAGE_MIN = 0.9
SCORE_LIMIT = 1000
TOUCH_ANCHOR_MS = BAR_MS                                # a live touch bar is closed at most 5 min after its open
SHOWN = "SHOWN_N_AT_LEAST_MIN"
BASELINE_ONLY = "BASELINE_COHORT_ONLY_N_BELOW_MIN"

# DH3-P1, frozen from the research record (docs/research/DH3_RESULT.md;
# DH3_RESULT_DISCOVERY.json CELLS.DH3-P1). A test keeps it equal to the record.
DH3_P1_RECORD = {
    "finding": "DH3-P1", "status": "WEAK", "endpoint": "RANGE_4H",
    "adjusted_shift_log": 0.12549730992705843,
    "ci95_log": [0.09455846973148252, 0.15764184562718356],
    "raw_mean_state": -4.5103062282920785, "raw_mean_comparator": -4.744302154078247,
    "n": 12397, "n_state": 3581, "n_comparator": 8816, "bar_log": 0.13976194237515863,
    "data": "Binance BTCUSDT 2020-2024", "record": "docs/research/DH3_RESULT.md",
}

_PRICE = "Binance USD-M BTCUSDT: beta_hist_bars_5m, then the Stage-1 klines_1m tail (decision.load_live_bars)"
_NO_DATA = "not decided 6h after horizon_end"
EVAL_RULES = {
    "TOUCH_V1": {
        "outcome": "touched: a closed bar wholly inside (as_of, horizon_end] with high >= level (side +1) "
                   "or low <= level (side -1)",
        "complete": "touched, or not touched with >= 90% of the window's minutes present",
        "cohort_metric": "reliability by probability bin, Brier score and Brier skill against the cohort's "
                         "own base rate; N_eff = distinct horizon-length UTC slots",
    },
    "NEITHER_V1": {
        "outcome": "neither: no closed bar wholly inside (as_of, horizon_end] with high >= level_up or "
                   "low <= level_down",
        "complete": "either level touched (neither = false), or >= 90% of the window's minutes present",
        "cohort_metric": "as TOUCH_V1, on the «ни один» chance (calibration note §7)",
    },
    "ANALOG_V1": {
        "outcome": "return = close at horizon_end / close of the 5m bar closing at as_of - 1 (%); "
                   "went_up = return > 0; up / down = highest high and lowest low of the window vs that close",
        "complete": ">= 90% of the window's minutes present and a bar ending within 5 min of horizon_end",
        "cohort_metric": "share up of the SHOWN rows of a label minus the share up of all rows of the class "
                         "weighted to that label's volatility-tercile mix, against the claimed diff_pp; "
                         "UTC-day-clustered bootstrap interval; N_eff = distinct UTC days",
    },
    "LEVEL_HOLD_V1": {
        "outcome": "hold: side x (close at horizon_end - level) > 0; as_of = touch bar open + 5 min "
                   "(history: the touching 5m bar's close)",
        "complete": ">= 90% of the window's minutes present and a bar ending within 5 min of horizon_end",
        "cohort_metric": "live hold rate against the claimed observed and random-level rates; "
                         "UTC-day-clustered interval",
    },
    "DH3_P1_RANGE_4H_V1": {
        "outcome": "RANGE_4H = log((max high - min low over the 48 5m bars after T) / close at T) "
                   "(docs/research/DH3_DESIGN.md)",
        "cohort": "quiet hours (prior 4h log range <= P1_QUIET_RANGE_MAX); arm STATE when the 4h OI "
                  "change >= P1_DOI4_MIN, else COMPARATOR (config/beta_research_cuts.json)",
        "complete": ">= 90% of the window's minutes present",
        "cohort_metric": "mean RANGE_4H of STATE minus COMPARATOR (raw), against the record's raw shift; "
                         "UTC-week-clustered interval",
    },
}

# class -> (level, template keys or registry id, evaluation rule id)
CLASSES = {
    "L3_LEVEL_TOUCH_4H": ("L3", ("lv_touch", "lv_touch_4h", "dc_btc_level_b", "dc_btc_level_fb"), "TOUCH_V1"),
    "L3_LEVEL_TOUCH_24H": ("L3", ("lv_touch", "lv_touch_24h", "dc_level_line", "pa_next", "dc_btc_level_b",
                                  "dc_btc_level_fb"), "TOUCH_V1"),
    "L3_DISTANCE_TOUCH_1H": ("L3", ("rk_line", "rk_table_line"), "TOUCH_V1"),
    "L3_DISTANCE_TOUCH_4H": ("L3", ("rk_line", "rk_table_line"), "TOUCH_V1"),
    "L3_DISTANCE_TOUCH_24H": ("L3", ("rk_line", "rk_table_line", "al_set"), "TOUCH_V1"),
    "L3_NEITHER_1H": ("L3", ("ck_neither",), "NEITHER_V1"),
    "L3_NEITHER_4H": ("L3", ("ck_neither",), "NEITHER_V1"),
    "L3_NEITHER_24H": ("L3", ("ck_neither",), "NEITHER_V1"),
    "L2_STATE_ANALOG_1H_1H": ("L2", ("dc_analog_line",), "ANALOG_V1"),
    "L2_STATE_ANALOG_1H_4H": ("L2", ("dc_analog_line",), "ANALOG_V1"),
    "L2_STATE_ANALOG_4H_4H": ("L2", ("dc_analog_line",), "ANALOG_V1"),
    "L2_STATE_ANALOG_4H_24H": ("L2", ("dc_analog_line",), "ANALOG_V1"),
    "L2_LEVEL_FIRST_TOUCH_HOLD_1H": ("L2", ("lv_hist", "pa_level_hist"), "LEVEL_HOLD_V1"),
    "L2_LEVEL_FIRST_TOUCH_HOLD_4H": ("L2", ("lv_hist", "pa_level_hist"), "LEVEL_HOLD_V1"),
    "L2_DH3_P1_RANGE_4H": ("L2", "registry:DH3-P1", "DH3_P1_RANGE_4H_V1"),
}
HOURLY_GROUPS = {
    "touch": tuple(c for c in CLASSES if c.startswith("L3_")),
    "analog": tuple(c for c in CLASSES if c.startswith("L2_STATE_ANALOG_")),
    "dh3_p1": ("L2_DH3_P1_RANGE_4H",),
}


# ---- identities ---------------------------------------------------------------------------------
def eval_rule(rule_id: str) -> dict:
    return {"id": rule_id, "journal": JOURNAL_VERSION, "price_source": _PRICE, "settle_s": int(SETTLE.total_seconds()),
            "no_data": _NO_DATA, **EVAL_RULES[rule_id]}


def template_digest(claim_class: str) -> str:
    """sha256 over the RU / EN text the class's numbers are printed with (or its registry entry)."""
    keys = CLASSES[claim_class][1]
    if isinstance(keys, str):
        from .research_link import load_findings
        fid = keys.split(":", 1)[1]
        entry = next((dict(f) for f in load_findings() if f["id"] == fid), None)
        return sha256_json({"registry": fid, "entry": entry})
    from .i18n import _CATALOG
    return sha256_json({k: _CATALOG[k] for k in keys})


def printed_prob(p: Optional[float]) -> Optional[str]:
    """A touch chance as every surface prints it (decision_format.fmt_prob, without HTML escaping)."""
    if p is None:
        return None
    if p < 0.01:
        return "<1%"
    if p > 0.99:
        return ">99%"
    return f"{round(p * 100):d}%"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def claim_row(claim_class: str, *, issued_at: datetime, issue_slot: datetime, as_of: datetime, subject: dict,
              subject_key: str, numbers: dict, rule_version: str, eligible_reason: str, horizon_ms: int,
              context_pk: Optional[int] = None, stats_pk: Optional[int] = None,
              stats_digest: Optional[str] = None) -> dict:
    level, _keys, rule_id = CLASSES[claim_class]
    rule = eval_rule(rule_id)
    row = {"claim_class": claim_class, "level": level, "issued_at": issued_at, "issue_slot": issue_slot,
           "as_of": as_of, "context_pk": context_pk, "stats_pk": stats_pk, "stats_digest": stats_digest,
           "subject": subject, "subject_key": subject_key, "numbers": numbers, "rule_version": rule_version,
           "template_id": "+".join(_keys) if not isinstance(_keys, str) else _keys,
           "template_digest": template_digest(claim_class), "eval_rule_id": rule_id, "eval_rule": rule,
           "eval_rule_digest": sha256_json(rule), "horizon_end": as_of + timedelta(milliseconds=horizon_ms),
           "eligible_reason": eligible_reason}
    row["claim_digest"] = sha256_json({k: (_iso(v) if isinstance(v, datetime) else v) for k, v in row.items()})
    return row


# ---- hourly claims from the decision block --------------------------------------------------------
def _stats_ids(stats: Optional[Mapping[str, Any]]) -> dict:
    return {"stats_pk": (stats or {}).get("_stats_pk"), "stats_digest": (stats or {}).get("_payload_digest")}


def touch_claims(block: Mapping[str, Any], model: Optional[Mapping[str, Any]], *, now: datetime,
                 slot: datetime, stats: Optional[Mapping[str, Any]] = None) -> list:
    """L3: every level zone of the block and the distance grid, for every horizon outside its event
    zone (the block drops those horizons at the source, so no claim exists where nothing is shown)."""
    from .rangecast import touch_probability
    if model is None or not block.get("available") or not block.get("price_ts"):
        return []
    hz = (block.get("corridor") or {}).get("horizons") or {}
    price = float(block["price"])
    as_of = datetime.fromisoformat(block["price_ts"]) + timedelta(minutes=1)     # close of the last 1m bar
    version = str(model.get("version") or "")
    ids = _stats_ids(stats)
    out = []
    lv = block.get("levels") or {}
    for side_name, side in (("above", +1), ("below", -1)):
        for z in lv.get(side_name) or ():
            for h in ("4h", "24h"):
                p = (z.get("touch") or {}).get(h)
                x = hz.get(h)
                if p is None or x is None:
                    continue
                subject = {"side": side, "level": z["edge"], "kinds": list(z.get("kinds") or ()),
                           "distance_pct": round(abs(z["distance_pct"]), 4), "horizon": h, "price": price,
                           "scale_pct": x["scale_pct"]}
                numbers = {"probability": round(float(p), 4), "printed": printed_prob(p)}
                out.append(claim_row(f"L3_LEVEL_TOUCH_{h.upper()}", issued_at=now, issue_slot=slot, as_of=as_of,
                                     subject=subject, subject_key=f"{side:+d}:{float(z['edge']):.2f}",
                                     numbers=numbers, rule_version=version, eligible_reason="LEVEL_ZONE_SHOWN",
                                     horizon_ms=HORIZON_MS[h], **ids))
    from .rangecast import neither_probability
    for h, x in hz.items():
        if "q_joint" not in ((model.get("horizons") or {}).get(h) or {}):
            continue                                   # a statistics row built before the joint table
        for du in NEITHER_GRID_PCT:
            for dd in NEITHER_GRID_PCT:
                pu, pd_ = (touch_probability(model, h, x["scale_pct"], d) for d in (du, dd))
                p = neither_probability(model, h, x["scale_pct"], du, dd, p_up=pu, p_down=pd_)
                subject = {"level_up": round(price * (1 + du / 100.0), 2), "level_down": round(price * (1 - dd / 100.0), 2),
                           "up_pct": du, "down_pct": dd, "horizon": h, "price": price, "scale_pct": x["scale_pct"]}
                numbers = {"probability": round(float(p), 4), "printed": printed_prob(p),
                           "p_up": round(float(pu), 4), "p_down": round(float(pd_), 4)}
                out.append(claim_row(f"L3_NEITHER_{h.upper()}", issued_at=now, issue_slot=slot, as_of=as_of,
                                     subject=subject, subject_key=f"{du}:{dd}", numbers=numbers, rule_version=version,
                                     eligible_reason="DISTANCE_GRID", horizon_ms=HORIZON_MS[h], **ids))
    for h, x in hz.items():
        for d in TOUCH_GRID_PCT:
            p = touch_probability(model, h, x["scale_pct"], d)
            for side in (+1, -1):
                subject = {"side": side, "level": round(price * (1 + side * d / 100.0), 2), "distance_pct": d,
                           "horizon": h, "price": price, "scale_pct": x["scale_pct"]}
                numbers = {"probability": round(float(p), 4), "printed": printed_prob(p)}
                out.append(claim_row(f"L3_DISTANCE_TOUCH_{h.upper()}", issued_at=now, issue_slot=slot, as_of=as_of,
                                     subject=subject, subject_key=f"{side:+d}:{d}", numbers=numbers,
                                     rule_version=version, eligible_reason="DISTANCE_GRID",
                                     horizon_ms=HORIZON_MS[h], **ids))
    return out


def live_tercile(b: Bars, j: int) -> Optional[int]:
    """The 24h-volatility tercile of bar j against the previous 30 days (analogues.label_history)."""
    from .analogues import trailing_ranks
    from .hist_series import past_range_pct
    vol24 = past_range_pct(b, BARS_PER_DAY)
    r = trailing_ranks(vol24, np.array([j], dtype=np.int64))[0]
    return None if not math.isfinite(r) else int(min(math.floor(r * 3), 2))


def analog_claims(cfg, state: Optional[Mapping[str, Any]], stats: Optional[Mapping[str, Any]], b: Optional[Bars], *,
                  now: datetime, slot: datetime, context_pk: Optional[int] = None) -> list:
    """L2 «после похожих» for the live 1h / 4h label of the full hour `slot`. Every label with a
    history card is written: rows under the display minimum are kept as BASELINE_ONLY (the
    baseline cohort is every hour, as in history), and only SHOWN rows are a stated claim."""
    from .analogues import ANALOGUES_VERSION, OUTCOMES, lookup
    from .decision_format import MIN_N_SHOWN, analog_range, fmt_pp
    from .interpretation import COMPRESSION, FACTUAL, INTERPRETED, interpret, liquidation_episodes
    from .research_states import index_closing_at
    from .state_tape import iso
    if not state or not stats or b is None:
        return []
    ana = stats.get("analogues")
    j = index_closing_at(b, to_ms(slot))
    tercile = live_tercile(b, j) if j is not None else None
    liq = liquidation_episodes(state)
    ids = _stats_ids(stats)
    out = []
    for w in ("1h", "4h"):
        ctx = state.get(f"context_{w}")
        if not ctx or ctx.get("window_end") != iso(slot):
            continue                                   # never a reading of another bucket
        res = interpret(cfg, ctx, horizon=w, liquidation_episodes=liq)
        card = lookup(ana, w, res.get("key"))
        if card is None:
            continue
        for h in OUTCOMES[w]:
            cell = (card.get("outcomes") or {}).get(h) or {}
            base = cell.get("baseline")
            n = int(cell.get("n") or 0)
            if not n or base is None or cell.get("p_up") is None:
                continue
            # stated only where a surface prints it: a state that says something (the formatter's kinds),
            # at the window's own horizon, above the display minimum; NORMAL stays in the live baseline
            shown = res.get("kind") in (INTERPRETED, FACTUAL, COMPRESSION) and n >= MIN_N_SHOWN and h == w
            ci = (cell.get("ci95") or {}).get("direction")
            ratio, _ = analog_range(cell, "en")
            numbers = {"observed": round(float(cell["p_up"]), 4), "baseline": round(float(base["p_up"]), 4),
                       "diff_pp": round((float(cell["p_up"]) - float(base["p_up"])) * 100.0, 2), "n": n,
                       "interval_pp": None if not ci else [round(float(x) * 100.0, 2) for x in ci],
                       "days": int(cell.get("days") or 0), "verdicts": dict(cell.get("verdicts") or {}),
                       "range_ratio": None if cell.get("range_ratio") is None else round(float(cell["range_ratio"]), 4),
                       "range_ratio_shown": None if ratio is None else round(float(ratio), 4),
                       "range_interval_log": (cell.get("ci95") or {}).get("range"),
                       "printed": {"observed": f"{round(cell['p_up'] * 100):d}%",
                                   "baseline": f"{round(base['p_up'] * 100):d}%",
                                   "diff_pp": fmt_pp(cell["p_up"] - base["p_up"], "en"),
                                   "interval_pp": None if not ci else [fmt_pp(x, "en") for x in ci]}}
            subject = {"window": w, "key": card["key"], "live_key": res.get("key"), "horizon": h,
                       "tercile": tercile, "proxy_label": bool(card.get("proxy_label"))}
            out.append(claim_row(f"L2_STATE_ANALOG_{w.upper()}_{h.upper()}", issued_at=now, issue_slot=slot,
                                 as_of=slot, subject=subject, subject_key=f"{w}:{card['key']}", numbers=numbers,
                                 rule_version=f"{ANALOGUES_VERSION}+{state.get('context_version') or ''}".rstrip("+"),
                                 eligible_reason=SHOWN if shown else BASELINE_ONLY, horizon_ms=HORIZON_MS[h],
                                 context_pk=context_pk, **ids))
    return out


def dh3_p1_claim(b: Optional[Bars], oi: Optional[np.ndarray], *, now: datetime, slot: datetime,
                 cuts: Optional[Mapping[str, float]] = None) -> list:
    """The DH3-P1 cohort at the full hour `slot`: a quiet hour is written with its arm (STATE when OI
    built up over 4h, else COMPARATOR), so the live shift can be read against the record."""
    from . import research_states as RS
    if b is None or oi is None:
        return []
    j = RS.index_closing_at(b, to_ms(slot))
    if j is None:
        return []
    if cuts is None:
        from .research_evidence import load_cuts
        cuts = load_cuts()
    st = RS.oi_states(b, oi, j, cuts)
    if st["P1"] is None:
        return []                                      # not a quiet hour, or no 4h OI change
    arm = "STATE" if st["P1"] else "COMPARATOR"
    subject = {"arm": arm, "quiet_log_range": round(float(st["quiet"]), 6), "doi4_log": round(float(st["doi4"]), 6),
               "cuts": {"P1_QUIET_RANGE_MAX": cuts["P1_QUIET_RANGE_MAX"], "P1_DOI4_MIN": cuts["P1_DOI4_MIN"]}}
    numbers = {"claimed_shift_pct": round((math.exp(DH3_P1_RECORD["adjusted_shift_log"]) - 1) * 100, 1),
               **DH3_P1_RECORD}
    return [claim_row("L2_DH3_P1_RANGE_4H", issued_at=now, issue_slot=slot, as_of=slot, subject=subject,
                      subject_key="P1", numbers=numbers, rule_version=f"DH3_CUTS:{sha256_json(subject['cuts'])[:16]}",
                      eligible_reason="QUIET_HOUR_WITH_OI", horizon_ms=HORIZON_MS["4h"])]


def level_hold_claims(cand: Mapping[str, Any], *, now: datetime) -> list:
    """L2 at a level-touch evaluation: the first-touch hold rate after 1h / 4h vs the random level,
    when its history reaches the display minimum (below it the bot says «мало данных»)."""
    from .decision_format import MIN_N_SHOWN, fmt_pp
    from .levels import LEVEL_STATS_VERSION
    p = cand.get("payload") or {}
    hist = p.get("history") or {}
    real, ctrl = hist.get("real") or {}, hist.get("control") or {}
    n = int(real.get("n") or 0)
    if n < MIN_N_SHOWN:
        return []
    at = datetime.fromisoformat(p["at"])
    as_of = at + timedelta(milliseconds=TOUCH_ANCHOR_MS)
    out = []
    for h in ("1h", "4h"):
        r, c = real.get(h) or {}, ctrl.get(h) or {}
        if r.get("hold_rate") is None or c.get("hold_rate") is None:
            continue
        ci = (hist.get("ci95") or {}).get(h)
        numbers = {"observed": round(float(r["hold_rate"]), 4), "baseline": round(float(c["hold_rate"]), 4),
                   "diff_pp": round((float(r["hold_rate"]) - float(c["hold_rate"])) * 100.0, 2), "n": n,
                   "interval_pp": None if not ci else [round(float(x) * 100.0, 2) for x in ci],
                   "verdict": (hist.get("verdicts") or {}).get(h),
                   "printed": {"observed": f"{round(r['hold_rate'] * 100):d}%",
                               "baseline": f"{round(c['hold_rate'] * 100):d}%",
                               "diff_pp": fmt_pp(r["hold_rate"] - c["hold_rate"], "en"),
                               "interval_pp": None if not ci else [fmt_pp(x, "en") for x in ci]}}
        subject = {"level_kind": p.get("level_kind"), "level": p.get("level"), "side": int(p.get("side") or 1),
                   "period": p.get("period"), "touch_at": p["at"], "horizon": h}
        out.append(claim_row(f"L2_LEVEL_FIRST_TOUCH_HOLD_{h.upper()}", issued_at=now, issue_slot=at, as_of=as_of,
                             subject=subject, subject_key=str(cand["key"]), numbers=numbers,
                             rule_version=LEVEL_STATS_VERSION, eligible_reason=SHOWN, horizon_ms=HORIZON_MS[h]))
    return out


async def _oi_for(conn, cfg, b: Bars, *, now: datetime, capture: Mapping[str, Any]):
    """The Binance OI metrics aligned to the bars: the research inputs of this run when built, else
    the same read on its own (collection never depends on research presentation)."""
    from .research_evidence import _usable
    inputs = capture.get("evidence_inputs")
    if inputs is None:
        from .research_inputs import _metrics, _source
        sources = {"bars": _source(True, b.end_ms, to_ms(now), None)}
        oi, _ls = await _metrics(conn, b, now, sources)
        return oi if not (sources.get("oi") or {}).get("reason") and (sources.get("oi") or {}).get("present") else None
    return inputs.oi if _usable(inputs, "oi") is None else None


async def record_claims(conn, cfg, block: Mapping[str, Any], *, now: datetime, capture: Mapping[str, Any]) -> dict:
    """The hourly writer. Idempotent per (class, subject, hour); a group already written for the hour
    is not rebuilt. Never raises into the caller's alert run (run_market_alerts wraps it)."""
    slot = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rep = {"written": 0, "candidates": 0}
    if now - slot > WRITE_WINDOW or not block.get("available"):
        return rep
    have = {r["claim_class"] for r in await conn.fetch_slot_claims(issue_slot=slot, classes=list(CLASSES))}
    stats, b, model = capture.get("stats"), capture.get("bars"), capture.get("model")
    rows: list = []
    first_run = not have & set(HOURLY_GROUPS["touch"])
    if first_run:
        rows += touch_claims(block, model, now=now, slot=slot, stats=stats)
    if not have & set(HOURLY_GROUPS["analog"]):
        from .context import episodization_digest
        ctx = await conn.fetch_latest_context_state(symbol=cfg.symbol, episodization_digest=episodization_digest(cfg))
        if ctx is not None:
            rows += analog_claims(cfg, ctx["state"], stats, b, now=now, slot=slot, context_pk=ctx.get("context_pk"))
    # retried on every run of the write window, like the analogues: the feeds and the notifier both start
    # at :00:40, so the slot's OI can arrive after the first run (the claim's as-of stays the slot close)
    if not have & set(HOURLY_GROUPS["dh3_p1"]) and b is not None:
        oi = await _oi_for(conn, cfg, b, now=now, capture=capture)
        rows += dh3_p1_claim(b, oi, now=now, slot=slot)
    rep["candidates"] = len(rows)
    # one transaction per hour: an interrupted write leaves no partial group for the next run to skip
    async with conn.transaction():
        for r in rows:
            rep["written"] += int(await conn.insert_claim(r) is not None)
    return rep


async def record_level_hold(conn, cand: Mapping[str, Any], *, now: datetime) -> int:
    n = 0
    for r in level_hold_claims(cand, now=now):
        n += int(await conn.insert_claim(r) is not None)
    return n


# ---- scoring ---------------------------------------------------------------------------------------
def _tail_slice(closed_1m, start: datetime, end: datetime, index: Optional[Sequence[int]]):
    """The 1m rows inside [start, end): a bisect over the run's time index (the tail is in time
    order), so scoring hundreds of claims never walks the whole 35-day tail for each one."""
    if not closed_1m:
        return []
    if index is None:
        index = [to_ms(r["ts"]) for r in closed_1m]
    from bisect import bisect_left
    return closed_1m[bisect_left(index, to_ms(start)):bisect_left(index, to_ms(end))]


def _window(b: Bars, closed_1m, start: datetime, end: datetime, index: Optional[Sequence[int]] = None) -> Optional[dict]:
    from .market_alerts import _series_since
    series = _series_since(b, _tail_slice(closed_1m, start, end, index), start, end)
    if not series:
        return None
    minutes = sum(x[4] for x in series)
    last_ts, _hi, _lo, last_close, last_m = series[-1]
    last_end = last_ts + timedelta(minutes=last_m)
    return {"high": max(x[1] for x in series), "low": min(x[2] for x in series), "close": float(last_close),
            "coverage": minutes / ((end - start).total_seconds() / 60.0),
            "ends_at_horizon": (end - last_end) <= timedelta(minutes=5), "series": series}


def _close_at(b: Bars, t: datetime) -> Optional[float]:
    from .research_states import index_closing_at
    j = index_closing_at(b, to_ms(t))
    if j is None or not math.isfinite(b.close[j]):
        return None
    return float(b.close[j])


def evaluate(claim: Mapping[str, Any], b: Bars, closed_1m, *, now: datetime,
             index: Optional[Sequence[int]] = None) -> Optional[tuple]:
    """(status, realized) for a due claim, or None to try again later. Pure."""
    rule = claim["eval_rule"]["id"]
    start, end = claim["as_of"], claim["horizon_end"]
    s = claim["subject"]
    w = _window(b, closed_1m, start, end, index)
    late = now - end > NO_DATA_AFTER
    if rule == "TOUCH_V1":
        side, level = int(s["side"]), float(s["level"])
        if w is not None:
            hit = next((x[0] for x in w["series"] if (side > 0 and x[1] >= level) or (side < 0 and x[2] <= level)), None)
            if hit is not None:
                return "COMPLETE", {"touched": True, "first_touch": _iso(hit), "coverage": round(w["coverage"], 4)}
            if w["coverage"] >= COVERAGE_MIN:
                return "COMPLETE", {"touched": False, "high": w["high"], "low": w["low"],
                                    "coverage": round(w["coverage"], 4)}
        return ("NO_DATA", {"coverage": round(w["coverage"], 4) if w else 0.0}) if late else None
    if rule == "NEITHER_V1":
        up, dn = float(s["level_up"]), float(s["level_down"])
        if w is not None:
            hit = next((x[0] for x in w["series"] if x[1] >= up or x[2] <= dn), None)
            if hit is not None:
                return "COMPLETE", {"neither": False, "first_touch": _iso(hit), "coverage": round(w["coverage"], 4)}
            if w["coverage"] >= COVERAGE_MIN:
                return "COMPLETE", {"neither": True, "high": w["high"], "low": w["low"],
                                    "coverage": round(w["coverage"], 4)}
        return ("NO_DATA", {"coverage": round(w["coverage"], 4) if w else 0.0}) if late else None
    complete = w is not None and w["coverage"] >= COVERAGE_MIN
    if rule == "ANALOG_V1":
        c0 = _close_at(b, start)
        if complete and w["ends_at_horizon"] and c0:
            ret = (w["close"] / c0 - 1) * 100.0
            return "COMPLETE", {"return_pct": round(ret, 4), "went_up": ret > 0,
                                "up_pct": round(max((w["high"] / c0 - 1) * 100.0, 0.0), 4),
                                "down_pct": round(max((1 - w["low"] / c0) * 100.0, 0.0), 4),
                                "coverage": round(w["coverage"], 4)}
    elif rule == "LEVEL_HOLD_V1":
        if complete and w["ends_at_horizon"]:
            side, level = int(s["side"]), float(s["level"])
            return "COMPLETE", {"hold": side * (w["close"] - level) > 0, "close": w["close"],
                                "coverage": round(w["coverage"], 4)}
    elif rule == "DH3_P1_RANGE_4H_V1":
        c0 = _close_at(b, start)
        if complete and c0 and w["high"] > w["low"]:
            return "COMPLETE", {"range_4h_log": round(math.log((w["high"] - w["low"]) / c0), 6),
                                "coverage": round(w["coverage"], 4)}
    else:
        raise ValueError(f"unknown evaluation rule {rule!r}")
    return ("NO_DATA", {"coverage": round(w["coverage"], 4) if w else 0.0}) if late else None


async def score_claims(conn, b: Optional[Bars], closed_1m, *, now: datetime, limit: int = SCORE_LIMIT) -> dict:
    out = {"scored": 0, "no_data": 0, "pending": 0}
    if b is None:
        return out
    closed_1m = sorted(closed_1m or (), key=lambda r: r["ts"])
    index = [to_ms(r["ts"]) for r in closed_1m]
    for c in await conn.fetch_due_claims(now=now - SETTLE, limit=limit):
        res = evaluate(c, b, closed_1m, now=now, index=index)
        if res is None:
            out["pending"] += 1
            continue
        status, realized = res
        digest = sha256_json({"claim_pk": c["claim_pk"], "eval_rule_digest": c["eval_rule_digest"],
                              "status": status, "realized": realized})
        await conn.insert_claim_outcome(claim_pk=c["claim_pk"], eval_rule_digest=c["eval_rule_digest"],
                                        status=status, realized=realized, computed_at=now, outcome_digest=digest)
        out["no_data" if status == "NO_DATA" else "scored"] += 1
    return out


# ---- displays --------------------------------------------------------------------------------------
def shown_keys(surface: str, block: Optional[Mapping[str, Any]], *, market: Optional[Mapping[str, Any]] = None,
               alert: Optional[Mapping[str, Any]] = None) -> list:
    """(class, subject_key) pairs a surface printed from this block (what `decision_format` renders)."""
    out: list = []
    block = block or {}
    if surface != "alert" and not block.get("available"):
        return out
    lv = block.get("levels") or {}
    zones = [(z, +1) for z in lv.get("above") or ()] + [(z, -1) for z in lv.get("below") or ()]

    def zkey(z, side):
        return f"{side:+d}:{float(z['edge']):.2f}"
    if surface == "btc":                      # the nearest level each side, 24h (4h inside the 24h zone)
        for side_name, side in (("above", +1), ("below", -1)):
            z = (lv.get(side_name) or [None])[0]
            touch = (z or {}).get("touch") or {}
            h = next((x for x in ("24h", "4h") if touch.get(x) is not None), None)
            if h:
                out.append((f"L3_LEVEL_TOUCH_{h.upper()}", zkey(z, side)))
    elif surface == "levels":
        for z, side in zones:
            for h in ("4h", "24h"):
                if (z.get("touch") or {}).get(h) is not None:
                    out.append((f"L3_LEVEL_TOUCH_{h.upper()}", zkey(z, side)))
    elif surface in ("brief", "catchup"):
        from .decision_format import _brief_pick
        if not (block.get("event_zone") or {}).get("24h"):
            for side_name, side in (("above", +1), ("below", -1)):
                for z in _brief_pick(lv.get(side_name) or [], 2):
                    if (z.get("touch") or {}).get("24h") is not None:
                        out.append(("L3_LEVEL_TOUCH_24H", zkey(z, side)))
        from .decision_format import MIN_N_SHOWN
        from .interpretation import COMPRESSION, FACTUAL, INTERPRETED
        for w in ("1h", "4h"):
            res = ((market or {}).get("interpretation") or {}).get(w) or {}
            card = (block.get("analogues") or {}).get(w)
            cell = ((card or {}).get("outcomes") or {}).get(w) or {}
            if res.get("kind") in (INTERPRETED, FACTUAL, COMPRESSION) and int(cell.get("n") or 0) >= MIN_N_SHOWN \
                    and cell.get("baseline"):
                out.append((f"L2_STATE_ANALOG_{w.upper()}_{w.upper()}", f"{w}:{card['key']}"))
    elif surface == "risk":
        for h in ("1h", "4h", "24h"):
            if h in ((block.get("corridor") or {}).get("horizons") or {}):
                for d in (0.25, 0.5, 1.0, 2.0):
                    out += [(f"L3_DISTANCE_TOUCH_{h.upper()}", f"{s:+d}:{d}") for s in (+1, -1)]
    elif surface == "alert" and alert is not None:
        p = alert.get("payload") or {}
        if alert.get("kind") == "level":
            out.append(("L2_LEVEL_FIRST_TOUCH_HOLD_1H", str(alert["key"])))
            nxt = p.get("next")
            if nxt and (nxt.get("touch") or {}).get("24h") is not None and not (p.get("event_zone") or {}).get("24h"):
                out.append(("L3_LEVEL_TOUCH_24H", zkey(nxt, int(p.get("side") or 1))))
    return out


async def record_displays(conn, *, surface: str, shown: Iterable[tuple], now: datetime, slot: Optional[datetime] = None,
                          view_pk: Optional[int] = None, alert_pk: Optional[int] = None) -> int:
    """Link the shown claims of the hour (or of `slot`) to the surface. Best-effort, in a savepoint:
    a failure never touches the caller's reply or alert."""
    want = set(shown)
    if not want:
        return 0
    slot = slot or now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    try:
        tx = getattr(conn, "transaction", None)
        async def _do():
            have = await conn.fetch_slot_claims(issue_slot=slot, classes=sorted({c for c, _k in want}))
            rows = [{"claim_pk": r["claim_pk"], "surface": surface, "view_pk": view_pk, "alert_pk": alert_pk,
                     "shown_at": now} for r in have if (r["claim_class"], r["subject_key"]) in want]
            return await conn.insert_claim_displays(rows) if rows else 0
        if tx is None:
            return await _do()
        async with tx():
            return await _do()
    except Exception as exc:  # noqa: BLE001 - the journal never breaks a reply or an alert
        logger.warning("claim display link failed: %s", type(exc).__name__)
        return 0


# ---- report (pure) ----------------------------------------------------------------------------------
PROB_BINS = (0.0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0000001)
BOOT_B = 500
BOOT_SEED = 20261005


def _slot_id(row: Mapping[str, Any], horizon: str) -> int:
    return int(to_ms(row["as_of"]) // HORIZON_MS[horizon])


def _day(row: Mapping[str, Any]) -> int:
    return int(to_ms(row["as_of"]) // 86_400_000)


def _boot_diff(groups_a: Mapping[int, list], groups_b: Mapping[int, list], *, seed: int = BOOT_SEED,
               reps: int = BOOT_B) -> Optional[list]:
    """95% interval of mean(a) − mean(b) resampling clusters (shared cluster ids)."""
    keys = sorted(set(groups_a) | set(groups_b))
    if len(keys) < 5:
        return None
    rng = np.random.default_rng(seed)
    sa = np.array([sum(groups_a.get(k, ())) for k in keys], dtype=float)
    ca = np.array([len(groups_a.get(k, ())) for k in keys], dtype=float)
    sb = np.array([sum(groups_b.get(k, ())) for k in keys], dtype=float)
    cb = np.array([len(groups_b.get(k, ())) for k in keys], dtype=float)
    W = rng.multinomial(len(keys), np.full(len(keys), 1.0 / len(keys)), size=reps).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (W @ sa) / (W @ ca) - (W @ sb) / (W @ cb)
    d = d[np.isfinite(d)]
    if d.size < reps * 0.9:
        return None
    return [round(float(np.quantile(d, 0.025)), 6), round(float(np.quantile(d, 0.975)), 6)]


def _event(realized: Mapping[str, Any]) -> bool:
    """The event an L3 chance was about: touched (single level) or neither touched (two levels)."""
    return bool(realized.get("touched") if "touched" in realized else realized.get("neither"))


def _touch_report(rows: Sequence[Mapping[str, Any]], horizon: str) -> dict:
    done = [r for r in rows if r.get("status") == "COMPLETE"]
    out = {"n": len(rows), "scored": len(done), "n_eff": len({_slot_id(r, horizon) for r in done}),
           "shown": sum(1 for r in rows if r.get("shown")), "bins": []}
    if not done:
        return out
    p = np.array([float(r["numbers"]["probability"]) for r in done])
    y = np.array([1.0 if _event(r["realized"]) else 0.0 for r in done])
    base = float(y.mean())
    brier = float(np.mean((p - y) ** 2))
    ref = base * (1 - base)
    out.update(base_rate=round(base, 4), brier=round(brier, 5),
               brier_skill=None if ref <= 0 else round(1 - brier / ref, 4))
    for lo, hi in zip(PROB_BINS[:-1], PROB_BINS[1:]):
        sel = [r for r, pp in zip(done, p) if lo <= pp < hi]
        if not sel:
            continue
        ps = np.array([float(r["numbers"]["probability"]) for r in sel])
        ys = np.array([1.0 if _event(r["realized"]) else 0.0 for r in sel])
        out["bins"].append({"bin": [lo, min(hi, 1.0)], "n": len(sel), "n_eff": len({_slot_id(r, horizon) for r in sel}),
                            "predicted": round(float(ps.mean()), 4), "realized": round(float(ys.mean()), 4)})
    return out


def _analog_report(rows: Sequence[Mapping[str, Any]]) -> dict:
    done = [r for r in rows if r.get("status") == "COMPLETE"]
    out: dict = {"n": len(rows), "scored": len(done), "labels": {}}
    if not done:
        return out
    by_t: dict = {}
    for r in done:
        by_t.setdefault(r["subject"].get("tercile"), []).append(r)
    for key in sorted({r["subject"]["key"] for r in done}):
        state = [r for r in done if r["subject"]["key"] == key and r.get("eligible_reason") == SHOWN]
        if not state:
            continue
        mix = {}
        for r in state:
            mix[r["subject"].get("tercile")] = mix.get(r["subject"].get("tercile"), 0) + 1
        base_share, base_n = 0.0, 0
        for t_, k in mix.items():
            pool = by_t.get(t_) or []
            if not pool:
                base_share = None
                break
            base_share += (k / len(state)) * float(np.mean([1.0 if x["realized"]["went_up"] else 0.0 for x in pool]))
            base_n += len(pool)
        share = float(np.mean([1.0 if r["realized"]["went_up"] else 0.0 for r in state]))
        ga = {}
        for r in state:
            ga.setdefault(_day(r), []).append(1.0 if r["realized"]["went_up"] else 0.0)
        gb = {}
        for r in done:
            gb.setdefault(_day(r), []).append(1.0 if r["realized"]["went_up"] else 0.0)
        out["labels"][key] = {
            "n": len(state), "n_eff_days": len({_day(r) for r in state}), "live_share_up": round(share, 4),
            "live_baseline_share_up": None if base_share is None else round(base_share, 4), "baseline_n": base_n,
            "live_diff_pp": None if base_share is None else round((share - base_share) * 100.0, 2),
            "claimed_diff_pp": round(float(np.mean([r["numbers"]["diff_pp"] for r in state])), 2),
            "interval_pp_unweighted": (lambda iv: None if iv is None else [round(x * 100.0, 2) for x in iv])(
                _boot_diff(ga, gb))}
    return out


def _hold_report(rows: Sequence[Mapping[str, Any]]) -> dict:
    done = [r for r in rows if r.get("status") == "COMPLETE"]
    out = {"n": len(rows), "scored": len(done)}
    if done:
        out.update(live_hold=round(float(np.mean([1.0 if r["realized"]["hold"] else 0.0 for r in done])), 4),
                   claimed_observed=round(float(np.mean([r["numbers"]["observed"] for r in done])), 4),
                   claimed_random_level=round(float(np.mean([r["numbers"]["baseline"] for r in done])), 4),
                   n_eff_days=len({_day(r) for r in done}))
    return out


def _p1_report(rows: Sequence[Mapping[str, Any]]) -> dict:
    done = [r for r in rows if r.get("status") == "COMPLETE"]
    arms = {a: [r for r in done if r["subject"]["arm"] == a] for a in ("STATE", "COMPARATOR")}
    out = {"n": len(rows), "scored": len(done), "n_state": len(arms["STATE"]), "n_comparator": len(arms["COMPARATOR"]),
           "record_raw_shift_log": round(DH3_P1_RECORD["raw_mean_state"] - DH3_P1_RECORD["raw_mean_comparator"], 4),
           "record_adjusted_shift_log": round(DH3_P1_RECORD["adjusted_shift_log"], 4)}
    if arms["STATE"] and arms["COMPARATOR"]:
        ms = float(np.mean([r["realized"]["range_4h_log"] for r in arms["STATE"]]))
        mc = float(np.mean([r["realized"]["range_4h_log"] for r in arms["COMPARATOR"]]))

        def week(r):
            return int(to_ms(r["as_of"]) // (7 * 86_400_000))
        ga, gb = {}, {}
        for r in arms["STATE"]:
            ga.setdefault(week(r), []).append(r["realized"]["range_4h_log"])
        for r in arms["COMPARATOR"]:
            gb.setdefault(week(r), []).append(r["realized"]["range_4h_log"])
        out.update(live_mean_state=round(ms, 4), live_mean_comparator=round(mc, 4),
                   live_raw_shift_log=round(ms - mc, 4), interval_log=_boot_diff(ga, gb))
    return out


def claims_report(rows: Sequence[Mapping[str, Any]]) -> dict:
    """Per-cohort tables of the journal (read-only; `--beta-claims-report`). Counts are reported with
    their effective N; nothing here is a user-facing number until a class reaches its threshold."""
    out: dict = {"journal": JOURNAL_VERSION, "classes": {}}
    by_class: dict = {}
    for r in rows:
        by_class.setdefault(r["claim_class"], []).append(r)
    for cls, rs in sorted(by_class.items()):
        rule = CLASSES.get(cls, (None, None, None))[2]
        if rule in ("TOUCH_V1", "NEITHER_V1"):
            out["classes"][cls] = _touch_report(rs, cls.rsplit("_", 1)[1].lower())
        elif rule == "ANALOG_V1":
            out["classes"][cls] = _analog_report(rs)
        elif rule == "LEVEL_HOLD_V1":
            out["classes"][cls] = _hold_report(rs)
        elif rule == "DH3_P1_RANGE_4H_V1":
            out["classes"][cls] = _p1_report(rs)
        else:
            out["classes"][cls] = {"n": len(rs)}
    return out


# ---- live calibration of the touch chances (docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md §3) ------------
TOUCH_LIVE_COMPONENT = "touch_live_cal"
TOUCH_LIVE_DAYS = 120
LIVE_TOLERANCE = 0.05


def touch_classes(h: str, kind: str = "touch") -> tuple:
    if kind == "neither":
        return (f"L3_NEITHER_{h.upper()}",)
    return (f"L3_LEVEL_TOUCH_{h.upper()}", f"L3_DISTANCE_TOUCH_{h.upper()}")


def live_touch_bins(cells: Sequence[Mapping[str, Any]], h: str, *, kind: str = "touch", seed: int = BOOT_SEED,
                    reps: int = BOOT_B) -> list:
    """Per probability bin of horizon h, pooled over its level and distance classes: N, effective N
    (distinct horizon slots), mean stated chance, realized share, the difference and a UTC-day-clustered
    95 % interval of it."""
    from .rangecast import TOUCH_CAL_BINS
    mine = [c for c in cells if c["claim_class"] in touch_classes(h, kind)]
    out = []
    rng = np.random.default_rng(seed)
    for k, (lo, hi) in enumerate(zip(TOUCH_CAL_BINS[:-1], TOUCH_CAL_BINS[1:])):
        cs = [c for c in mine if int(c["bin"]) == k]
        n = sum(int(c["n"]) for c in cs)
        if not n:
            continue
        hits, psum = sum(int(c["hits"]) for c in cs), sum(float(c["psum"]) for c in cs)
        days: dict = {}
        for c in cs:
            d = days.setdefault(int(c["day"]), [0.0, 0.0])
            d[0] += int(c["hits"]) - float(c["psum"])
            d[1] += int(c["n"])
        sums = np.array([v[0] for v in days.values()])
        cnts = np.array([v[1] for v in days.values()])
        interval = None
        if len(days) >= 5:
            W = rng.multinomial(len(days), np.full(len(days), 1.0 / len(days)), size=reps).astype(float)
            with np.errstate(invalid="ignore", divide="ignore"):
                bd = (W @ sums) / (W @ cnts)
            bd = bd[np.isfinite(bd)]
            if bd.size:
                interval = [round(float(np.quantile(bd, 0.025)) * 100, 2), round(float(np.quantile(bd, 0.975)) * 100, 2)]
        out.append({"bin": [lo, min(hi, 1.0)], "n": n, "n_eff": len({int(c["slot"]) for c in cs}),
                    "predicted": round(psum / n, 4), "realized": round(hits / n, 4),
                    "diff_pp": round((hits - psum) / n * 100, 2), "interval_pp": interval})
    return out


def diverged_bins(bins: Sequence[Mapping[str, Any]]) -> list:
    """Live bins that broke the frozen rule: N_eff >= 30, |difference| > 5 pp and a day-clustered interval
    that excludes 0."""
    from .rangecast import TOUCH_CAL_MIN_NEFF
    out = []
    for x in bins:
        iv = x.get("interval_pp")
        if x["n_eff"] >= TOUCH_CAL_MIN_NEFF and abs(x["diff_pp"]) > LIVE_TOLERANCE * 100 and iv \
                and (iv[0] > 0 or iv[1] < 0):
            out.append(list(x["bin"]))
    return out


async def refresh_touch_calibration(conn, *, now: datetime) -> Optional[dict]:
    """Once an hour: the live bins of every horizon from the scored journal, and the bins that diverged.
    A divergence is sticky for the model specification (rangecast.RANGE_MODEL_VERSION)."""
    from .rangecast import RANGE_MODEL_VERSION, TOUCH_CAL_VERSION
    runtime = await conn.fetch_health()
    prev = runtime.get(TOUCH_LIVE_COMPONENT) or {}
    last = prev.get("last_success_at")
    if last is not None and now - last < timedelta(minutes=55):
        return None
    cells = await conn.touch_claim_cells(since=now - timedelta(days=TOUCH_LIVE_DAYS),
                                         classes=[c for h in HORIZON_MS for k in ("touch", "neither")
                                                  for c in touch_classes(h, k)])
    pd_ = prev.get("detail") or {}
    same = pd_.get("model") == RANGE_MODEL_VERSION
    detail = {"version": TOUCH_CAL_VERSION, "model": RANGE_MODEL_VERSION, "computed_at": _iso(now),
              "days": TOUCH_LIVE_DAYS, "horizons": {}, "diverged": {}, "neither": {}, "diverged_neither": {}}
    for kind, hkey, dkey in (("touch", "horizons", "diverged"), ("neither", "neither", "diverged_neither")):
        keep = pd_.get(dkey) if same else None
        for h in HORIZON_MS:
            bins = live_touch_bins(cells, h, kind=kind)
            detail[hkey][h] = {"bins": bins}
            old = [list(b) for b in ((keep or {}).get(h) or [])]
            detail[dkey][h] = old + [b for b in diverged_bins(bins) if b not in old]
    await conn.record_health(TOUCH_LIVE_COMPONENT, now=now, success=True, detail=detail)
    return detail


def touch_wording(holdout: Optional[Mapping[str, Any]], live: Optional[Mapping[str, Any]], h: str,
                  p: Optional[float], *, kind: str = "touch") -> dict:
    """Which wording a touch chance p of horizon h gets (design note §3):
    - `B` with the held-out line ('holdout') while the live bin is under its N_eff;
    - `B` with the live line ('live') once the live bin reaches it;
    - `fallback` («исторически в X % случаев») when the held-out bin did not pass, or the live bin diverged.
    `holdout` is the block's corridor holdout map, `live` the stored live detail."""
    from .rangecast import TOUCH_CAL_MIN_NEFF, touch_bin
    if p is None:
        return {"mode": "none"}
    b = touch_bin(float(p))
    hkey, lkey, dkey = ("neither_bins", "neither", "diverged_neither") if kind == "neither" \
        else ("touch_bins", "horizons", "diverged")
    hb = next((x for x in ((((holdout or {}).get(h) or {}).get(hkey) or {}).get("bins") or ())
               if list(x["bin"]) == b), None)
    lv = (live or {})
    diverged = [list(x) for x in ((lv.get(dkey) or {}).get(h) or ())]
    if b in diverged or hb is None or not hb.get("passed"):
        return {"mode": "fallback", "bin": b, "holdout": hb}
    lb = next((x for x in (((lv.get(lkey) or {}).get(h) or {}).get("bins") or ()) if list(x["bin"]) == b), None)
    if lb is not None and lb["n_eff"] >= TOUCH_CAL_MIN_NEFF:
        return {"mode": "B", "source": "live", "bin": b, "predicted": lb["predicted"], "realized": lb["realized"],
                "n_eff": lb["n_eff"]}
    return {"mode": "B", "source": "holdout", "bin": b, "predicted": hb["predicted"], "realized": hb["realized"],
            "n_eff": hb["n_eff"]}
