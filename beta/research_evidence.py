"""Research evidence engine: which closed research units speak to the current market, and what
they found (owner task 2026-10-04; docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md).

One structured layer between the research record and every user surface. It receives the
current market state (`EvidenceInputs`), recognises the frozen state of each live-relevant
finding (`beta/research_states.py`, cut points `config/beta_research_cuts.json`), and returns
`ResearchEvidenceMatch` records: what the state is now, when it was matched, what the research
found after such states, against what comparator, on how many cases, whether it replicated,
and what limits it. Surfaces render only what this layer returns.

Rules (owner task §5–§9):
- a finding is matched only on its exact frozen state from fresh data; a missing or stale source
  never becomes evidence: the finding is listed as unavailable with the reason;
- hierarchy CONFIRMED > DISCOVERY > WEAK > NOT_CONFIRMED (> SIDE_FINDING); UNDERPOWERED is never
  used; at most one finding per topic on a surface; a NOT_CONFIRMED finding vetoes any supporting
  claim of the same mechanism;
- DISCOVERY is always worded as a hypothesis, WEAK as an effect below our materiality bar;
  nothing here turns a discovery into «Проверено»;
- nothing here changes a corridor, a touch probability, a tracked forecast, a detector threshold,
  an episode rule or push gating: the engine only reads the block those produce.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

import numpy as np

from . import research_states as RS
from .hist_series import BAR_MS, Bars, from_ms

EVIDENCE_VERSION = "BETA_RESEARCH_EVIDENCE_V1"
CUTS_PATH = Path(__file__).resolve().parent.parent / "config" / "beta_research_cuts.json"
HOUR_MS = RS.HOUR_MS
DAY_MS = RS.DAY_MS
STATUS_RANK = {"CONFIRMED": 0, "DISCOVERY": 1, "WEAK": 2, "NOT_CONFIRMED": 3, "SIDE_FINDING": 4}
USABLE = tuple(STATUS_RANK)
DIRECTIONS = ("SUPPORTS", "REFUTES", "DESCRIPTIVE")
TOPICS = ("RANGE_1H", "RANGE_4H", "RANGE_24H", "DIRECTION_4H", "LEVEL_HOLD", "CONTINUATION", "REVERSAL",
          "CALENDAR", "CALENDAR_VOL")
SURFACES = ("btc", "catchup", "brief", "risk", "levels", "level_alert", "move_alert", "details")
MAIN_SURFACES = ("btc", "catchup", "brief", "risk", "level_alert", "move_alert")
DEFAULT_LOOKBACK_H = 8
# Findings that stay in /research only, with the reason (audit, docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md)
NOT_LIVE = {
    "D11": "EVENT_ZONE_RULE",                 # BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1 §9: no size around CPI/FOMC
    "DIVERGENCE": "NOT_LIVE_REPRODUCIBLE",    # ±5 % book support: the public REST book is 1000 levels
    "DIVERGENCE-RSI": "EXPLORATORY_ONLY",
    "MARKET-05": "OBSERVABLE_NOT_SHOWN",      # the bot shows no ETH
    "MARKET-06": "OBSERVABLE_NOT_SHOWN",      # the bot shows no OKX spot
    "R03-B2": "MULTI_ASSET_FORBIDDEN",
    "TWAP": "OBSERVABLE_NOT_SHOWN",
    "C012": "UNDERPOWERED",
}
# Sources each live state needs (for the unavailable list and provenance).
STATE_SOURCES = {
    "D7_HOUR": ("d7",), "D2_HIGH_RV_DAY": ("bars_daily",), "P3_CROWD": ("ls_ratio",),
    "P1_LEVERAGE_LOADING": ("bars", "oi"), "P2_DELEVERAGING": ("oi",), "O1_IMPLIED_ABOVE_REALIZED": ("dvol", "bars"),
    "O2_DVOL_JUMP": ("dvol",), "O3_UP_VOL": ("dvol", "bars"), "L1_THIN_BOOK": ("depth",), "L2_BOOK_SKEW": ("depth",),
    "L3_BOOK_NOT_RECOVERED": ("depth", "bars"), "S1_STRESS_LEADER": ("stress",), "S3_LARGE_PRINTS": ("stress",),
    "V1_SESSION_EXTREME": ("bars",), "V2_KEY_LEVEL_TOUCH": ("bars",), "V3_RETEST": ("bars",),
    "L_CONFLUENCE": ("bars",), "L_STALE": ("bars",), "L_SPOT_APPROACH": ("spot", "bars"),
    "B2_SPOT_SHARE_MOVE": ("spot", "bars"), "H03_IMPULSE": ("bars",), "H02_FAILED_BREAKOUT": ("bars",),
    "H04_TREND_PULLBACK": ("bars",), "H05_TAKER_SKEW": ("flow15",), "M02_OI_CONFIRMED_IMPULSE": ("bars", "oi"),
    "M01_OI_STALLED_IMPULSE": ("bars", "oi"), "R03_WEEKEND": ("calendar",), "R03_EXPIRY_HOUR": ("calendar",),
    "R03_EXPIRY_PIN": ("calendar",), "R03_US_OPEN_CLOSE": ("calendar",), "D12_US_CLOCK_WEEK": ("calendar",),
    "H01_COMPRESSION": ("labels",),
}
KEY_LEVEL_KINDS = ("PMH", "PML", "PWH", "PWL", "PDH", "PDL", "POC_PD", "ROUND")
PUSH_KINDS = ("PDH", "PDL", "PWH", "PWL", "PMH", "PML")


@lru_cache(maxsize=1)
def load_cuts(path: str = str(CUTS_PATH)) -> dict:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    return dict(body["cuts"])


@dataclass(frozen=True)
class ResearchEvidenceMatch:
    finding_id: str
    status: str
    live_state: dict                 # {"key", "arm", "values"}: the recognised state and its live numbers
    matched_at: str                  # ISO UTC: the research decision time of the state
    valid_until: str                 # matched_at + the finding's horizon
    scope: dict                      # {"ru", "en"}: what the finding covered (data)
    historical_effect: dict          # {"ru", "en"}
    comparator: dict
    sample_size: Optional[int]
    replication_status: dict
    relevance: str                   # STATE_EXACT | CONDITIONAL (would apply if price reaches a level) | CONTEXT
    interpretation_direction: str    # SUPPORTS | REFUTES | DESCRIPTIVE
    limitations: dict
    topic: str
    mechanism: str
    surfaces: tuple
    provenance: tuple                # ({"source", "as_of"}, …)
    record: str
    priority: int = 50
    vetoed_by: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["surfaces"] = list(self.surfaces)
        d["provenance"] = [dict(p) for p in self.provenance]
        return d


@dataclass
class EvidenceInputs:
    """The current market state, by source. Arrays are aligned to `bars` (index j = known at the
    close of bar j). A None source is missing; `sources` records each source's newest data time
    and whether it is usable (fresh and, for the REST metrics tail, definition-checked)."""
    now_ms: int
    bars: Optional[Bars] = None
    oi: Optional[np.ndarray] = None
    ls: Optional[np.ndarray] = None
    dvol_at: Optional[dict] = None
    book: Optional[dict] = None
    spot: Optional[dict] = None
    stress: Sequence[Mapping] = ()
    flow15: Optional[dict] = None
    daily_rv: Optional[Sequence[tuple]] = None
    regime: Optional[Mapping] = None
    levels: Sequence[Mapping] = ()
    events: Sequence[Mapping] = ()
    weekend: bool = False
    labels: Optional[Mapping] = None
    sources: dict = field(default_factory=dict)


# ---- registry ------------------------------------------------------------------------------
def live_findings(findings: Optional[Iterable[Mapping]] = None) -> dict:
    from .research_link import load_findings
    fs = load_findings() if findings is None else findings
    return {f["id"]: f for f in fs if f.get("live") and f["status"] in USABLE}


def _txt(f: Mapping, key: str) -> dict:
    lv = f["live"]
    return {"ru": lv.get(f"{key}_ru") or "", "en": lv.get(f"{key}_en") or ""}


def _iso(ms: int) -> str:
    return from_ms(int(ms)).isoformat()


def _match(f: Mapping, *, key: str, values: Mapping[str, Any], at_ms: int, sources: Mapping,
           arm: Optional[str] = None, relevance: str = "STATE_EXACT", alt: bool = False) -> ResearchEvidenceMatch:
    lv = f["live"]
    effect = _txt(f, "effect_alt" if alt else "effect")
    prov = tuple({"source": s, "as_of": (sources.get(s) or {}).get("as_of")}
                 for s in STATE_SOURCES.get(lv["state"], ()))
    return ResearchEvidenceMatch(
        finding_id=f["id"], status=f["status"], live_state={"key": key, "arm": arm, "values": dict(values)},
        matched_at=_iso(at_ms), valid_until=_iso(at_ms + int(lv["horizon_h"]) * HOUR_MS),
        scope={"ru": f["data"], "en": f["data"]}, historical_effect=effect, comparator=_txt(f, "comparator"),
        sample_size=lv.get("n"), replication_status=_txt(f, "replication"), relevance=relevance,
        interpretation_direction=lv["direction"], limitations=_txt(f, "limitations"), topic=lv["topic"],
        mechanism=lv["mechanism"], surfaces=tuple(lv["surfaces"]), provenance=prov, record=f["record"],
        priority=int(f.get("priority", 50)))


def _usable(inputs: EvidenceInputs, *names: str) -> Optional[str]:
    """None when every source is present and usable, else the first reason."""
    for n in names:
        s = inputs.sources.get(n)
        if not s or not s.get("present"):
            return f"NO_DATA:{n}"
        if s.get("reason"):
            return f"{s['reason']}:{n}"
    return None


# ---- the matchers -----------------------------------------------------------------------------
def _hour_indices(b: Bars, now_ms: int, lookback_h: int) -> list:
    out = []
    last = now_ms - now_ms % HOUR_MS
    for k in range(lookback_h + 1):
        j = RS.index_closing_at(b, last - k * HOUR_MS)
        if j is not None and math.isfinite(b.close[j]):
            out.append(j)
    return sorted(out)


def _kyiv_hm(ms: int) -> str:
    from .i18n import fmt_kyiv_hm
    return fmt_kyiv_hm(from_ms(ms))


def evaluate(inputs: EvidenceInputs, *, findings: Optional[Iterable[Mapping]] = None,
             cuts: Optional[Mapping[str, float]] = None, lookback_h: int = DEFAULT_LOOKBACK_H) -> dict:
    """Every live-relevant finding whose frozen state holds now or held within `lookback_h`, and
    every live-relevant finding that could not be checked (with the reason). JSON-safe."""
    fs = live_findings(findings)
    cuts = dict(load_cuts() if cuts is None else cuts)
    now = int(inputs.now_ms)
    b = inputs.bars
    matches: list = []
    unavailable: dict = {}
    checked: set = set()

    def miss(fid: str, reason: str) -> None:
        if fid in fs:
            unavailable.setdefault(fid, reason)

    def add(fid: str, **kw) -> None:
        if fid in fs:
            matches.append(_match(fs[fid], sources=inputs.sources, **kw))

    def check(fid: str) -> bool:
        if fid in fs:
            checked.add(fid)
            return True
        return False

    sigma = RS.rolling_sigma(b.close) if b is not None and b.n else None
    hours = _hour_indices(b, now, lookback_h) if b is not None and b.n else []

    # D7 (CONFIRMED): the last completed hour's D7 state, as the D7 job stored it
    if check("D7"):
        reg = inputs.regime
        if reg is None:
            miss("D7", "NO_DATA:d7")
        elif reg.get("shown") and reg.get("hour_end"):
            end_ms = int(datetime.fromisoformat(reg["hour_end"]).timestamp() * 1000)
            if now - end_ms < HOUR_MS:
                add("D7", key="D7_HOUR", values={"hour_start": _kyiv_hm(end_ms - HOUR_MS), "hour_end": _kyiv_hm(end_ms)},
                    at_ms=end_ms)

    # D2 (CONFIRMED): today's RULE_1 decision (00:05 UTC) from the daily RV series
    if check("D2"):
        why = _usable(inputs, "bars_daily")
        st = RS.d2_state(inputs.daily_rv) if not why else None
        today = now - now % DAY_MS
        if why:
            miss("D2", why)
        elif st is None or st["day_ms"] != today:
            miss("D2", "INSUFFICIENT_HISTORY:bars_daily")
        elif st["state"] and now >= today + 5 * 60_000:
            add("D2", key="D2_HIGH_RV_DAY", values={"rv_pct": st["rv"] * 100, "p90_pct": st["p90"] * 100},
                at_ms=today + 5 * 60_000)

    # DH3-P1 / P2 (OI) and P3 (crowd) at the full hours of the window
    for fid in ("DH3-P1", "DH3-P2", "DH3-P3"):
        check(fid)
    why_oi = _usable(inputs, "oi")
    why_ls = _usable(inputs, "ls_ratio")
    if why_oi:
        miss("DH3-P1", why_oi)
        miss("DH3-P2", why_oi)
    if why_ls:
        miss("DH3-P3", why_ls)
    for j in hours:
        T = RS.decision_ms(b, j)
        if not why_oi and inputs.oi is not None:
            st = RS.oi_states(b, inputs.oi, j, cuts)
            if st["P1"]:
                add("DH3-P1", key="P1_LEVERAGE_LOADING", at_ms=T,
                    values={"doi4_pct": (math.exp(st["doi4"]) - 1) * 100, "range4_pct": math.exp(st["quiet"]) * 100})
            if st["P2"]:
                add("DH3-P2", key="P2_DELEVERAGING", at_ms=T, values={"doi1_pct": (math.exp(st["doi1"]) - 1) * 100})
        if not why_ls and inputs.ls is not None:
            z = RS.crowd_z(b, inputs.ls, j)
            arm = RS.crowd_state(z, cuts)
            if arm in ("CROWD_LONG", "CROWD_SHORT"):
                add("DH3-P3", key="P3_CROWD", arm=arm, alt=(arm == "CROWD_SHORT"), at_ms=T,
                    values={"z": z, "ratio": float(inputs.ls[j])})
    if hours and not why_oi and inputs.oi is not None and not math.isfinite(inputs.oi[hours[-1]]):
        miss("DH3-P1", "STALE:oi")
        miss("DH3-P2", "STALE:oi")
    if hours and not why_ls and inputs.ls is not None and RS.crowd_z(b, inputs.ls, hours[-1]) is None:
        miss("DH3-P3", "STALE_OR_SHORT_HISTORY:ls_ratio")

    # DH3-O1/O2/O3 (DVOL)
    for fid in ("DH3-O1", "DH3-O2", "DH3-O3"):
        check(fid)
    why = _usable(inputs, "dvol")
    if why:
        for fid in ("DH3-O1", "DH3-O2", "DH3-O3"):
            miss(fid, why)
    else:
        last_ok = False
        for j in hours:
            st = RS.dvol_states(b, inputs.dvol_at or {}, sigma, j, cuts)
            if st is None:
                continue
            last_ok = last_ok or j == hours[-1]
            T = RS.decision_ms(b, j)
            if st["O1"]:
                add("DH3-O1", key="O1_IMPLIED_ABOVE_REALIZED", at_ms=T, values={"dvol": st["dvol"]})
            if st["O2"]:
                add("DH3-O2", key="O2_DVOL_JUMP", at_ms=T,
                    values={"dvol": st["dvol"], "jump_pct": (math.exp(st["dvol_jump"]) - 1) * 100})
            if st["O3"]:
                add("DH3-O3", key="O3_UP_VOL", at_ms=T, values={"dvol": st["dvol"], "corr": st["corr"]})
        if hours and not last_ok:
            for fid in ("DH3-O1", "DH3-O2", "DH3-O3"):
                miss(fid, "STALE:dvol")

    # DH3-L1/L2/L3 (±1 % book)
    for fid in ("DH3-L1", "DH3-L2", "DH3-L3"):
        check(fid)
    why = _usable(inputs, "depth")
    if why:
        for fid in ("DH3-L1", "DH3-L2", "DH3-L3"):
            miss(fid, why)
    else:
        book = inputs.book
        last_ok = False
        for j in hours:
            st = RS.depth_states(b, book, j, cuts)
            if st["asym"] is not None and j == hours[-1]:
                last_ok = True
            T = RS.decision_ms(b, j)
            if st["L1"]:
                add("DH3-L1", key="L1_THIN_BOOK", at_ms=T, values={"ratio_pct": st["depth_ratio"] * 100})
            if st["L2"] in ("BID_HEAVY", "ASK_HEAVY"):
                add("DH3-L2", key="L2_BOOK_SKEW", arm=st["L2"], alt=(st["L2"] == "ASK_HEAVY"), at_ms=T,
                    values={"bid_usd": float(book["bid1"][j]), "ask_usd": float(book["ask1"][j])})
        if hours and not last_ok:
            miss("DH3-L1", "STALE_OR_NOT_COVERED:depth")
            miss("DH3-L2", "STALE_OR_NOT_COVERED:depth")
        first = max(0, b.n - (lookback_h + 1) * 12 - RS.RECOVERY_LAG_BARS - RS.MOVE_REFRACTORY_BARS - 3)
        for i, d, _ratio in RS.sharp_moves(b, sigma, first=max(first - 400, 0)):
            if i < first:
                continue
            rec = RS.book_recovery(book, i, cuts)
            if rec and rec["L3"] and now - RS.decision_ms(b, rec["j"]) <= lookback_h * HOUR_MS:
                add("DH3-L3", key="L3_BOOK_NOT_RECOVERED", at_ms=RS.decision_ms(b, rec["j"]),
                    values={"recovery_pct": rec["recovery"] * 100, "direction": d,
                            "move_end": _kyiv_hm(RS.decision_ms(b, i))})

    # DH3-S1/S3 (stress hours)
    for fid in ("DH3-S1", "DH3-S3"):
        check(fid)
    why = _usable(inputs, "stress")
    if why:
        miss("DH3-S1", why)
        miss("DH3-S3", why)
    else:
        for row in inputs.stress or ():
            hour = int(row["hour_ms"])
            T = hour + HOUR_MS
            if now - T > lookback_h * HOUR_MS:
                continue
            st = RS.stress_states(row, cuts)
            if st is None:
                continue
            if st["S1"]:
                add("DH3-S1", key="S1_STRESS_LEADER", arm=st["S1"], alt=(st["S1"] == "PERP_LED"), at_ms=T,
                    values={"hour": _kyiv_hm(hour), "range_pct": (math.exp(float(row["perp_log_range"])) - 1) * 100})
            if st["S3"]:
                add("DH3-S3", key="S3_LARGE_PRINTS", at_ms=T, values={"hour": _kyiv_hm(hour), "n": st["n_large_perp"]})

    # price-path states (bars only)
    if b is not None and b.n > RS.SCALE_BARS:
        _price_states(inputs, b, sigma, now, lookback_h, fs, add, miss, check, cuts)
    else:
        for fid in ("H03", "H02", "H04", "MARKET-01", "MARKET-02", "DH2-B2", "DH3-V1", "DH3-V2", "DH3-V3",
                    "DH1-L2", "DH2-L1", "DH2-L3"):
            check(fid)
            miss(fid, "NO_DATA:bars")

    # H05 (taker flow, Stage-1 1m base volumes)
    if check("H05"):
        why = _usable(inputs, "flow15")
        fl = inputs.flow15
        st = RS.h05_state(fl["bucket_ms"], fl["buy"], fl["total"]) if not why and fl else None
        if why:
            miss("H05", why)
        elif st is None:
            miss("H05", "INSUFFICIENT_HISTORY:flow15")
        elif st["state"] and now - st["T_ms"] <= lookback_h * HOUR_MS:
            best = st["best"]
            add("H05", key="H05_TAKER_SKEW", arm="BUY" if best["imbalance"] > 0 else "SELL", at_ms=st["T_ms"],
                values={"window_min": best["window_min"], "top_pct": (1 - best["pctl"]) * 100,
                        "imbalance_pct": best["imbalance"] * 100})

    # calendar states
    _calendar_states(inputs, now, add, check)

    # label contexts (the 1h / 4h interpretation already on the view)
    if check("H01") or check("MARKET-02"):
        for h, res in ((inputs.labels or {}).items()):
            key = (res or {}).get("key")
            end = (res or {}).get("inputs", {}).get("window_end")
            at = int(datetime.fromisoformat(end).timestamp() * 1000) if end else now
            if key in ("compression", "compression_oi_na"):
                add("H01", key="H01_COMPRESSION", at_ms=at, relevance="CONTEXT", values={"window": h})
            elif key in ("long_build", "short_build") and h == "1h":
                add("MARKET-02", key="M02_OI_CONFIRMED_IMPULSE", arm=key, at_ms=at, relevance="CONTEXT",
                    values={"window": h, "label": key})

    for fid in fs:
        if fid not in checked:
            unavailable.setdefault(fid, "NO_MATCHER")
    matches = _dedupe(matches)
    _apply_veto(matches)
    matched_ids = {m.finding_id for m in matches}
    return {"version": EVIDENCE_VERSION, "as_of": _iso(now), "lookback_h": lookback_h,
            "matches": [m.to_dict() for m in matches],
            "unavailable": [{"finding_id": k, "reason": v} for k, v in sorted(unavailable.items())
                            if k not in matched_ids],
            "not_live": [{"finding_id": k, "reason": v} for k, v in sorted(NOT_LIVE.items())],
            "checked": sorted(checked)}


def _price_states(inputs, b, sigma, now, lookback_h, fs, add, miss, check, cuts) -> None:
    from .levels import period_keys
    horizon_ms = lookback_h * HOUR_MS
    first_bar = max(0, b.n - lookback_h * 12)

    # H03 / H04 at the last 15-minute boundary
    t15, c15 = RS.grid15_closes(b)
    for fid, fn, key in (("H03", RS.h03_state, "H03_IMPULSE"), ("H04", RS.h04_state, "H04_TREND_PULLBACK")):
        if not check(fid):
            continue
        st = fn(t15, c15)
        if st is None:
            miss(fid, "INSUFFICIENT_HISTORY:bars")
        elif st["state"] and now - st["T_ms"] <= horizon_ms:
            best = st["best"]
            if key == "H03_IMPULSE":
                add(fid, key=key, at_ms=st["T_ms"], arm="UP" if best["ret"] > 0 else "DOWN",
                    values={"window_min": best["window_min"], "ret_pct": (math.exp(best["ret"]) - 1) * 100,
                            "top_pct": (1 - best["pctl"]) * 100})
            else:
                add(fid, key=key, at_ms=st["T_ms"], arm="UP" if best["direction"] > 0 else "DOWN",
                    values={"lookback_h": best["lookback_min"] // 60, "depth_pct": best["depth"] * 100})

    # H02: the newest failed breakout bar in the window
    if check("H02"):
        for i in range(b.n - 1, first_bar - 1, -1):
            st = RS.h02_state(b, i)
            if st:
                add("H02", key="H02_FAILED_BREAKOUT", at_ms=RS.decision_ms(b, i), arm="UP" if st["side"] > 0 else "DOWN",
                    values={"lookback_min": st["lookback_min"]})
                break

    # MARKET-01 / 02: decisions at the 5m boundaries of the window
    if check("MARKET-01") | check("MARKET-02"):
        why = _usable(inputs, "oi")
        if why or inputs.oi is None:
            miss("MARKET-01", why or "NO_DATA:oi")
            miss("MARKET-02", why or "NO_DATA:oi")
        else:
            for tj in range(b.n - 1, max(first_bar, 0) - 1, -1):
                st = RS.market_0102_state(b, inputs.oi, tj)
                if st and st.get("oi_expansion"):
                    fid = "MARKET-02" if st["confirmed"] else "MARKET-01"
                    add(fid, key="M02_OI_CONFIRMED_IMPULSE" if st["confirmed"] else "M01_OI_STALLED_IMPULSE",
                        arm="UP" if st["direction"] > 0 else "DOWN", at_ms=RS.decision_ms(b, tj),
                        values={"impulse_pct": (math.exp(st["impulse"]) - 1) * 100,
                                "continuation": st["continuation_ratio"]})
                    break

    # DH1 sharp moves: DH2-B2 (spot share)
    if check("DH2-B2"):
        why = _usable(inputs, "spot")
        if why:
            miss("DH2-B2", why)
        else:
            for i, d, ratio in RS.sharp_moves(b, sigma, first=max(first_bar - 400, 0)):
                if i < first_bar:
                    continue
                hi = RS.spot_share_high(b, inputs.spot, i)
                if hi:
                    add("DH2-B2", key="B2_SPOT_SHARE_MOVE", arm="UP" if d > 0 else "DOWN",
                        at_ms=RS.decision_ms(b, i), values={"move_end": _kyiv_hm(RS.decision_ms(b, i))})

    # level states: first touches of key levels in the window, session extremes, retests
    _level_states(inputs, b, sigma, now, lookback_h, add, miss, check)


def _levels_at(b: Bars, j: int) -> list:
    """The product's levels as of bar j's close (as DH1 events.confluent reads them)."""
    from .levels import compute_levels
    a = max(0, j + 1 - 62 * 288)
    sub = b.slice(a, j + 1)
    price = float(b.close[j])
    if not math.isfinite(price):
        return []
    return compute_levels(sub, now_ms=RS.decision_ms(b, j), price=price)


def _level_states(inputs, b, sigma, now, lookback_h, add, miss, check) -> None:
    first_bar = max(0, b.n - lookback_h * 12)
    for fid in ("DH3-V1", "DH3-V2", "DH3-V3", "DH1-L2", "DH2-L1", "DH2-L3"):
        check(fid)
    day_ms = now - now % DAY_MS
    day_first = (day_ms - b.t0) // BAR_MS
    # key levels of today's period (the product's levels at now): first touches in the window
    levels = list(inputs.levels or ())
    lv_pairs = [(lv["kind"], float(lv["price"])) for lv in levels]
    spot_why = _usable(inputs, "spot")
    if spot_why:
        miss("DH2-L1", spot_why)
    from .market_alerts import _period, _period_start
    for lv in levels:
        kind = lv["kind"]
        price = float(lv["price"])
        if kind in PUSH_KINDS:
            side = +1 if kind.endswith("H") else -1
            start = int(_period_start(_period(kind), from_ms(now)).timestamp() * 1000)
            a = max(0, (start - b.t0) // BAR_MS)
            if a >= b.n or not math.isfinite(b.open[a]) or side * (price - b.open[a]) <= 0:
                continue
            j = RS.first_touch(b, a, b.n - 1, price, side)
            if j is None or j < first_bar:
                continue
            T = RS.decision_ms(b, j)
            name = {"kind": kind, "price": price, "side": side, "touch": _kyiv_hm(T - BAR_MS)}
            add("DH3-V2", key="V2_KEY_LEVEL_TOUCH", at_ms=T, values=name)
            pairs_at = [(x["kind"], float(x["price"])) for x in _levels_at(b, j)]
            if RS.confluent(pairs_at, kind, price):
                add("DH1-L2", key="L_CONFLUENCE", at_ms=T, values=name)
            if RS.stale_level(b, j, price):
                add("DH2-L3", key="L_STALE", at_ms=T, values=name)
            if not spot_why:
                flow = RS.spot_flow(inputs.spot, j - RS.APPROACH_BARS + 1, j, side)
                if flow is not None and flow > 0:
                    add("DH2-L1", key="L_SPOT_APPROACH", at_ms=T, values=name)
            if kind in ("PDH", "PDL") and day_first >= 0:
                rt = RS.retest_state(b, sigma, price, side, int(day_first), b.n - 1)
                if rt["retest"] is not None and rt["retest"] >= first_bar:
                    add("DH3-V3", key="V3_RETEST", at_ms=RS.decision_ms(b, rt["retest"]), values=name)
        elif kind.endswith(("_H", "_L")) and lv.get("ended_ms") and not kind.startswith(("LIQ", "VWAP")):
            side = +1 if kind.endswith("_H") else -1
            z = (int(lv["ended_ms"]) - b.t0) // BAR_MS
            c_end = b.close[int(z) - 1] if 0 < z <= b.n else float("nan")
            if not math.isfinite(c_end) or side * (price - c_end) <= 0:    # DH3 session_events: beyond the close
                continue
            j = RS.first_touch(b, int(z), int(z) + RS.SESSION_WINDOW_BARS - 1, price, side)
            if j is not None and j >= first_bar:
                add("DH3-V1", key="V1_SESSION_EXTREME", at_ms=RS.decision_ms(b, j),
                    values={"kind": kind, "price": price, "side": side})


def _calendar_states(inputs, now, add, check) -> None:
    from zoneinfo import ZoneInfo
    if check("R03-C1") and inputs.weekend:
        add("R03-C1", key="R03_WEEKEND", at_ms=now - now % DAY_MS, relevance="CONTEXT", values={})
    kinds = {e.get("kind") for e in inputs.events or ()}
    exp = sorted(k for k in kinds if str(k).startswith("EXPIRY_"))
    if check("R03-A1") and exp:
        add("R03-A1", key="R03_EXPIRY_HOUR", at_ms=now - now % DAY_MS, relevance="CONTEXT", values={"kind": exp[0]})
    if check("R03-A4") and exp:
        add("R03-A4", key="R03_EXPIRY_PIN", at_ms=now - now % DAY_MS, relevance="CONTEXT", values={"kind": exp[0]})
    wd = int(((now // DAY_MS) + 3) % 7)                 # Monday = 0 (UTC)
    if check("R03-C2-C4") and wd in (0, 4):
        add("R03-C2-C4", key="R03_US_OPEN_CLOSE", at_ms=now - now % DAY_MS, relevance="CONTEXT",
            arm="MONDAY_OPEN" if wd == 0 else "FRIDAY_CLOSE", values={})
    if check("D12"):
        ny = ZoneInfo("America/New_York")
        d = from_ms(now).astimezone(timezone.utc)
        for back in range(0, 7):
            day = (d - timedelta(days=back)).replace(hour=12, minute=0, second=0, microsecond=0)
            prev = day - timedelta(days=1)
            if day.astimezone(ny).utcoffset() != prev.astimezone(ny).utcoffset():
                add("D12", key="D12_US_CLOCK_WEEK", at_ms=int(day.replace(hour=0).timestamp() * 1000),
                    relevance="CONTEXT", values={"days_ago": back})
                break


# ---- hierarchy ---------------------------------------------------------------------------------
def _dedupe(matches: list) -> list:
    """One match per finding (and arm): the newest."""
    best: dict = {}
    for m in matches:
        k = (m.finding_id, m.live_state.get("arm"))
        if k not in best or m.matched_at > best[k].matched_at:
            best[k] = m
    one: dict = {}
    for m in best.values():
        if m.finding_id not in one or m.matched_at > one[m.finding_id].matched_at:
            one[m.finding_id] = m
    return list(one.values())


def _apply_veto(matches: list) -> None:
    """A NOT_CONFIRMED match vetoes every SUPPORTS match of the same mechanism (replaced in place)."""
    refuted = {m.mechanism: m.finding_id for m in matches if m.status == "NOT_CONFIRMED"}
    for k, m in enumerate(matches):
        if m.interpretation_direction == "SUPPORTS" and m.mechanism in refuted and m.status != "NOT_CONFIRMED":
            matches[k] = ResearchEvidenceMatch(**{**asdict(m), "surfaces": tuple(m.surfaces),
                                                  "provenance": tuple(m.provenance),
                                                  "vetoed_by": refuted[m.mechanism]})


def rank_key(m: Mapping[str, Any]) -> tuple:
    return (STATUS_RANK.get(m["status"], 9), 0 if m["relevance"] == "STATE_EXACT" else 1, int(m.get("priority", 50)),
            -_ts(m["matched_at"]), m["finding_id"])


def _ts(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def current(matches: Iterable[Mapping[str, Any]], *, now: datetime) -> list:
    """Matches whose research window is still running at `now`."""
    return [m for m in matches if datetime.fromisoformat(m["valid_until"]) > now]


def select(evidence: Optional[Mapping[str, Any]], surface: str, *, limit: int = 2, now: Optional[datetime] = None,
           since: Optional[datetime] = None, topics: Optional[Sequence[str]] = None) -> list:
    """The findings a surface shows: usable, not vetoed, at most one per topic, by the hierarchy.
    `now`: only matches still running; `since`: only matches at or after it (a /catchup window)."""
    if not evidence:
        return []
    ms = [m for m in evidence.get("matches") or () if surface in m["surfaces"] and m["status"] in USABLE
          and not m.get("vetoed_by")]
    if now is not None:
        ms = current(ms, now=now)
    if since is not None:
        ms = [m for m in ms if datetime.fromisoformat(m["matched_at"]) >= since]
    if topics is not None:
        ms = [m for m in ms if m["topic"] in topics]
    out, seen = [], set()
    for m in sorted(ms, key=rank_key):
        if m["topic"] in seen:
            continue
        seen.add(m["topic"])
        out.append(m)
        if len(out) >= limit:
            break
    return out


# ---- conditional evidence for /levels (what applies if price reaches a level) -------------------
def level_conditionals(b: Optional[Bars], zone: Mapping[str, Any], *, now_ms: int,
                       findings: Optional[Iterable[Mapping]] = None) -> list:
    """For a /levels zone not yet reached: the findings that would describe its touch. A session
    extreme within 24h of its session (DH3-V1), a zone of several levels (DH1-L2), a key level not
    traded for 24h (DH2-L3), a PDH/PDL already touched today and left by at least X (DH3-V3)."""
    fs = live_findings(findings)
    if b is None or not b.n:
        return []
    out = []
    members = list(zone.get("members") or ())
    kinds = [m["kind"] for m in members if not str(m["kind"]).startswith("LIQ")]
    sigma = None
    side = +1 if float(zone.get("distance_pct") or 0) > 0 else -1
    fresh = [m for m in members if m["kind"] in KEY_LEVEL_KINDS
             and not _touched_in_period(b, m["kind"], float(m["price"]), side, now_ms)]
    for m in members:
        kind, price = m["kind"], float(m["price"])
        if kind in ("PDH", "PDL") and "DH3-V3" in fs:
            sigma = RS.rolling_sigma(b.close) if sigma is None else sigma
            day_first = (now_ms - now_ms % DAY_MS - b.t0) // BAR_MS
            lside = +1 if kind == "PDH" else -1
            day_open = b.open[int(day_first)] if 0 <= day_first < b.n else float("nan")
            if lside == side and math.isfinite(day_open) and lside * (price - day_open) > 0:
                rt = RS.retest_state(b, sigma, price, lside, int(day_first), b.n - 1)
                if rt["retreat"] is not None and rt["retest"] is None:
                    out.append(_match(fs["DH3-V3"], key="V3_RETEST", arm="PENDING", at_ms=now_ms,
                                      relevance="CONDITIONAL", sources={}, values={"kind": kind, "price": price}).to_dict())
        if kind.endswith(("_H", "_L")) and kind.split("_")[0] in ("ASIA", "EU", "US") and "DH3-V1" in fs \
                and (side > 0) == kind.endswith("_H") and not _session_touched(b, kind, price, now_ms):
            out.append(_match(fs["DH3-V1"], key="V1_SESSION_EXTREME", arm="PENDING", at_ms=now_ms,
                              relevance="CONDITIONAL", sources={}, values={"kind": kind, "price": price}).to_dict())
        if m in fresh and "DH2-L3" in fs and RS.stale_level(b, b.n, price):
            out.append(_match(fs["DH2-L3"], key="L_STALE", arm="PENDING", at_ms=now_ms, relevance="CONDITIONAL",
                              sources={}, values={"kind": kind, "price": price}).to_dict())
    if fresh and len(set(kinds)) >= 2 and "DH1-L2" in fs:
        out.append(_match(fs["DH1-L2"], key="L_CONFLUENCE", arm="PENDING", at_ms=now_ms, relevance="CONDITIONAL",
                          sources={}, values={"kinds": sorted(set(kinds))}).to_dict())
    best: dict = {}
    for m in out:
        best.setdefault(m["finding_id"], m)
    return sorted(best.values(), key=rank_key)


def _touched_in_period(b: Bars, kind: str, price: float, side: int, now_ms: int) -> bool:
    """Whether a key level has already been traded in its period (its next touch is then not a
    first touch). PD*/POC/ROUND: the UTC day; PW*: the week; PM*: the month."""
    from .market_alerts import _period, _period_start
    pname = _period(kind) if kind[:2] in ("PD", "PW", "PM") else "day"
    start = int(_period_start(pname, from_ms(now_ms)).timestamp() * 1000)
    a = max(0, (start - b.t0) // BAR_MS)
    return a < b.n and RS.first_touch(b, int(a), b.n - 1, price, side) is not None


def _session_touched(b: Bars, kind: str, price: float, now_ms: int) -> bool:
    from .levels import SESSIONS
    sess = kind.split("_")[0]
    h1, m1 = SESSIONS[sess][2], SESSIONS[sess][3]
    end = now_ms - now_ms % DAY_MS + (h1 * 60 + m1) * 60_000
    if end > now_ms:
        end -= DAY_MS
    z = (end - b.t0) // BAR_MS
    side = +1 if kind.endswith("_H") else -1
    return 0 <= z < b.n and RS.first_touch(b, int(z), b.n - 1, price, side) is not None


# ---- alerts ------------------------------------------------------------------------------------
def for_level_touch(evidence: Optional[Mapping[str, Any]], b: Optional[Bars], payload: Mapping[str, Any], *,
                    levels: Sequence[Mapping], now_ms: int, findings: Optional[Iterable[Mapping]] = None) -> list:
    """Evidence for a level alert, from what is known at the touch: the touched level is a key level
    (DH3-V2), coincides with other levels (DH1-L2), was not traded for 24h (DH2-L3). The touch bar
    itself may still be open, so states that need it closed are left to /btc and /catchup."""
    fs = live_findings(findings)
    out = []
    kind, price, side = payload["level_kind"], float(payload["level"]), int(payload.get("side") or 1)
    at_ms = int(datetime.fromisoformat(payload["at"]).timestamp() * 1000)
    name = {"kind": kind, "price": price, "side": side}
    if "DH3-V2" in fs:
        out.append(_match(fs["DH3-V2"], key="V2_KEY_LEVEL_TOUCH", at_ms=at_ms, values=name, sources={}).to_dict())
    pairs = [(lv["kind"], float(lv["price"])) for lv in levels or ()]
    if "DH1-L2" in fs and RS.confluent(pairs, kind, price):
        out.append(_match(fs["DH1-L2"], key="L_CONFLUENCE", at_ms=at_ms, values=name, sources={}).to_dict())
    if "DH2-L3" in fs and b is not None and b.n:
        j = min(b.n, max(0, (at_ms - at_ms % BAR_MS - b.t0) // BAR_MS))
        if RS.stale_level(b, int(j), price):
            out.append(_match(fs["DH2-L3"], key="L_STALE", at_ms=at_ms, values=name, sources={}).to_dict())
    return out


def for_move(evidence: Optional[Mapping[str, Any]], payload: Mapping[str, Any]) -> list:
    """Evidence for a sharp-move alert: matches of the move-alert surface from the block's own
    evaluation that are running at the move's end (H03, D7, DH2-B2 when their states hold)."""
    at = datetime.fromisoformat(payload["at"])
    return [m for m in current((evidence or {}).get("matches") or (), now=at)
            if "move_alert" in m["surfaces"] and m["status"] in USABLE]
