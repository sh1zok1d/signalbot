"""Level race at structural first touches — HIST line (FORECAST_LAYER_DECISION_V1 §6a).

ОПГ-2 module (ORCHESTRATION_V1 §4). Pure functions, no I/O except `load_hist_table`.
Design: docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.md (frozen 997ba986), §0 and §2.1.
Research twin: scripts/research/level_race_forecast_v1 (parity-tested).

Three outcomes inside the original 4h window of a #352 first touch: the barrier price beyond the
level (in the approach direction) first, the other barrier first, neither. User text speaks only
of the upper and lower price; BREAK/REJECT never appear.

The model states (L3_*, FALLBACK) are not here yet: they come with the model freeze and are
enabled only by `level_race.model_states_enabled`.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np

LEVEL_RACE_VERSION = "LEVEL_RACE_HIST_V1"
RULE_ID = "LEVEL_RACE_4H_V1"
HIST_CLASSES = {"T0": "L2_LEVEL_RACE_HIST_T0_4H", "T15": "L2_LEVEL_RACE_HIST_T15_4H"}
TEMPLATES = {"full": "LR_HIST_V1", "push": "LR_PUSH_HIST_V1", "low_n": "LR_HIST_LOW_N_V1"}
MODEL_STATES_SETTING = "level_race.model_states_enabled"
HIST_TABLE_PATH = Path(__file__).resolve().parents[1] / "docs/research/LEVEL_RACE_HIST_TABLE_V1.json"
HIST_TABLE_SHA256 = "4f57c80065ba17482ea7cae8aa8ac732a9f3897fa58a93bb86d26ddb9224805b"   # body (cells, ladder, …)
# sha256 of the whole file bytes, provenance included (red team 2026-10-08: the body digest alone
# let provenance, e.g. the years shown as «2020–2024», be rewritten unnoticed).
HIST_FILE_SHA256 = "e8a3224be08c40fc10c57280aca2b2dedc64b9f9adbbf591fb34f5dd030e20a4"

BAR_MS = 300_000
ZONE_HALF = 0.0015             # #352 primary half-width (= beta.levels.ZONE_TOL_PCT / 100)
CORRIDOR_Z = 1.2816
BARRIER_FRACTION = 0.5
WINDOW_BARS = 48               # bars j+1 .. j+48
T15_OFFSET = 2                 # T15 = close of bar j+2
TAU = {"T0": 48, "T15": 46}
SCALE_BARS = 288
MIN_PRESENT = 0.9
X_MIN, X_MAX = 1e-8, 0.5
PROB_FLOOR = 0.001
BAND_EDGES = (0.35, 0.55)      # B0_beyond at T15 (table V1)
FAMILY_OF = {"PMH": "MONTH", "PML": "MONTH", "PWH": "WEEK", "PWL": "WEEK", "PDH": "DAY", "PDL": "DAY"}
STRUCT_SIDE = {"PMH": 1, "PWH": 1, "PDH": 1, "PML": -1, "PWL": -1, "PDL": -1}


# ---- volatility and barriers -------------------------------------------------------------------
def sigma_before(close: np.ndarray, j: int) -> Optional[float]:
    """Sample SD (ddof 1) of the 288 5m log returns ending at bar j-1 (#352 `sigma_before_touch`)."""
    if j - SCALE_BARS - 1 < 0:
        return None
    c = np.asarray(close[j - SCALE_BARS - 1:j], dtype=float)
    r = np.log(c[1:] / c[:-1])
    r = r[np.isfinite(r)]
    if r.size < MIN_PRESENT * SCALE_BARS or r.size < 2:
        return None
    return float(np.std(r, ddof=1))


def barrier_x(sigma: float) -> float:
    return BARRIER_FRACTION * CORRIDOR_Z * float(sigma) * math.sqrt(WINDOW_BARS)


def geometry(zone_low: float, zone_high: float, sigma: float, approach_side: int) -> Optional[dict]:
    """Upper / lower barrier prices and which of them lies beyond the level (internal)."""
    x = barrier_x(sigma)
    if not (X_MIN < x < X_MAX) or approach_side not in (1, -1):
        return None
    return {"x": x, "p_up": zone_high * (1.0 + x), "p_dn": zone_low * (1.0 - x), "beyond_is_up": approach_side > 0}


event_geometry = geometry


def window_end_ms(touch_open_ms: int) -> int:
    """Close time of bar j+48 (render in the user's time zone with the product formatter)."""
    return int(touch_open_ms) + (WINDOW_BARS + 1) * BAR_MS


# ---- B0 --------------------------------------------------------------------------------------
def _series(x: float, s: float) -> tuple[float, float]:
    up = ne = 0.0
    for n in range(1, 20001):
        e = math.exp(-(n * math.pi) ** 2 * s / 2.0)
        if e < 1e-15:
            break
        sn = math.sin(n * math.pi * x)
        up += 2.0 * (-1.0) ** n / (n * math.pi) * sn * e
        if n % 2 == 1:
            ne += 4.0 / (n * math.pi) * sn * e
    return up, ne


def b0_race(price: float, p_up: float, p_dn: float, sigma: float, tau_bars: float) -> tuple[float, float, float]:
    """(upper first, lower first, neither): driftless first passage in log price, floored."""
    w = math.log(p_up) - math.log(p_dn)
    z = math.log(price) - math.log(p_dn)
    if z >= w:
        p = (1.0, 0.0, 0.0)
    elif z <= 0:
        p = (0.0, 1.0, 0.0)
    else:
        xr = z / w
        s = sigma * sigma * tau_bars / (w * w)
        us, ne = _series(xr, s)
        ds, _ = _series(1.0 - xr, s)
        p = (min(max(xr + us, 0.0), 1.0), min(max(1.0 - xr + ds, 0.0), 1.0), min(max(ne, 0.0), 1.0))
    q = [max(v, PROB_FLOOR) for v in p]
    t = sum(q)
    return (q[0] / t, q[1] / t, q[2] / t)


# ---- HIST table ------------------------------------------------------------------------------
def load_hist_table(path: Path = HIST_TABLE_PATH) -> dict:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != HIST_FILE_SHA256:
        raise RuntimeError("level race HIST table file digest mismatch")
    table = json.loads(raw.decode("utf-8"))
    body = {k: table[k] for k in table if k not in ("table_sha256", "provenance")}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if digest != table["table_sha256"] or digest != HIST_TABLE_SHA256:
        raise RuntimeError("level race HIST table digest mismatch")
    return table


def band_of(b0_beyond: float) -> str:
    lo, hi = BAND_EDGES
    return "F1" if b0_beyond < lo else ("F2" if b0_beyond < hi else "F3")


def cell_key(landmark: str, kind: str, b0_beyond: Optional[float] = None) -> str:
    fam = FAMILY_OF[kind]
    side = "H" if STRUCT_SIDE[kind] > 0 else "L"
    if landmark == "T0":
        return f"T0|{fam}|{side}"
    return f"T15|{fam}|{side}|{band_of(float(b0_beyond))}"


def t15_eligible(high: Sequence[float], low: Sequence[float], j: int, geo: Mapping[str, Any]) -> bool:
    """No barrier (and no bar reaching both) on j+1, j+2. Otherwise there is no T15 line."""
    for k in (j + 1, j + 2):
        h, lo_ = float(high[k]), float(low[k])
        if not (math.isfinite(h) and math.isfinite(lo_)):
            return False
        if h >= geo["p_up"] or lo_ <= geo["p_dn"]:
            return False
    return True


def hist_line(table: Mapping[str, Any], *, landmark: str, kind: str, price: float, geo: Mapping[str, Any],
              sigma: float) -> dict:
    """Everything a surface and the L2 journal need for one HIST statement.

    `price` = close of bar j (T0) or j+2 (T15). Shares are mapped from beyond/back to upper/lower.
    Returns template id, the mapped numbers (fractions; the renderer rounds), ladder level and cell.
    """
    up, dn, ne = b0_race(price, geo["p_up"], geo["p_dn"], sigma, TAU[landmark])
    b0_beyond = up if geo["beyond_is_up"] else dn
    key = cell_key(landmark, kind, b0_beyond)
    lad = table["ladder"][key]
    out = {"class": HIST_CLASSES[landmark], "rule_id": RULE_ID, "table_version": table["version"],
           "table_sha256": table["table_sha256"], "cell": key, "ladder_level": lad["level"],
           "source_cell": lad["source"], "p_up": geo["p_up"], "p_dn": geo["p_dn"],
           "beyond_is_up": geo["beyond_is_up"], "event_b0": {"up": up, "dn": dn, "neither": ne},
           "out_of_corridor": not (geo["p_dn"] < price < geo["p_up"])}
    # Display rule (architect, 2026-10-08): at T0 a close already outside (P_DN, P_UP) gives no
    # line; the L2 journal record is still written with this flag.
    out["display"] = not (landmark == "T0" and out["out_of_corridor"])
    c = table["cells"][lad["source"]]
    out["n"] = c["n"]
    if lad["level"] == "LOW_N":
        out["template"] = TEMPLATES["low_n"]
        return out
    h, b, k = c["h"], c["b"], c["k_pp"]
    m = (lambda d: {"up": d["BEYOND"], "dn": d["BACK"], "neither": d["NEITHER"]}) if geo["beyond_is_up"] else \
        (lambda d: {"up": d["BACK"], "dn": d["BEYOND"], "neither": d["NEITHER"]})
    lo_hi = {o: [int(round(v[0])), int(round(v[1]))] for o, v in c["diff_ci95_pp"].items()}
    hm, bm = m(h), m(b)
    printed_h, printed_b = percents(hm), percents(bm)
    # The shown difference equals the shown percentages (architect, 2026-10-08).
    d_pp = {o: printed_h[o] - printed_b[o] for o in ("up", "dn", "neither")}
    out.update({"template": TEMPLATES["full"], "push_template": TEMPLATES["push"],
                "h": hm, "b": bm, "printed_h": printed_h, "printed_b": printed_b, "k_pp": m(k),
                "d_pp": d_pp, "ci95_pp": m(lo_hi), "weeks": c["weeks"]})
    return out


def t15_visible(highs_closed: Sequence[float], lows_closed: Sequence[float], price_now: float,
                geo: Mapping[str, Any], *, now_ms: int, end_ms: int, was_hidden: bool = False) -> bool:
    """T15 line visibility (architect, 2026-10-08): visible until `end_ms` while the race is
    unresolved. `highs_closed` / `lows_closed` are the closed bars from j+3 up to now. Hidden once a
    barrier is reached on a closed bar or the current price is beyond P_UP / P_DN; never returns."""
    if was_hidden or now_ms >= end_ms:
        return False
    for h, lo_ in zip(highs_closed, lows_closed):
        if float(h) >= geo["p_up"] or float(lo_) <= geo["p_dn"]:
            return False
    return geo["p_dn"] < float(price_now) < geo["p_up"]


def percents(fracs: Mapping[str, float]) -> dict:
    """Integers summing to 100 by largest remainder, in the order up, dn, neither."""
    keys = ("up", "dn", "neither")
    raw = [100.0 * float(fracs[k]) for k in keys]
    base = [int(math.floor(v)) for v in raw]
    rest = 100 - sum(base)
    order = sorted(range(3), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:rest]:
        base[i] += 1
    return dict(zip(keys, base))


# ---- model states: frozen raw predictors (LEVEL_RACE_MODEL_V1; used only when
#      level_race.model_states_enabled = true; calibration lives in beta.level_race_calibration) ----
MODEL_PATH = Path(__file__).resolve().parents[1] / "docs/research/LEVEL_RACE_MODEL_V1.json"
MODEL_FILE_SHA256 = "454109c8b2532906d54045b3f8fe3362afb0fb684cab18053ada1265d5480d3a"
OFFSET_CLIP = 1e-4


def load_model(path: Path = MODEL_PATH) -> dict:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != MODEL_FILE_SHA256:
        raise RuntimeError("level race model file digest mismatch")
    return json.loads(raw.decode("utf-8"))


def _lg(p: float) -> float:
    p = min(max(float(p), OFFSET_CLIP), 1 - OFFSET_CLIP)
    return math.log(p / (1 - p))


def _sig(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _term(term: str, *, landmark: str, kind: Optional[str], sigma: float, edges, ovmm_z: Optional[float]) -> float:
    if term == "1":
        return 1.0
    if term == "T15":
        return 1.0 if landmark == "T15" else 0.0
    if term == "FAM_WM":
        return 0.0 if FAMILY_OF[kind] == "DAY" else 1.0
    if term == "WEEK":
        return 1.0 if FAMILY_OF[kind] == "WEEK" else 0.0
    if term == "MONTH":
        return 1.0 if FAMILY_OF[kind] == "MONTH" else 0.0
    if term == "SIDE":
        return float(STRUCT_SIDE[kind])
    if term == "SIGMA_T":
        return -1.0 if sigma < edges[0] else (0.0 if sigma < edges[1] else 1.0)
    if term == "OVMM":
        return float(ovmm_z) if landmark == "T15" else 0.0
    raise KeyError(term)


def _floor3(p: Sequence[float]) -> tuple:
    q = [max(float(v), PROB_FLOOR) for v in p]
    t = sum(q)
    return (q[0] / t, q[1] / t, q[2] / t)


def two_head(spec: Mapping[str, Any], b0_beyond_back_neither: Sequence[float], *, landmark: str,
             kind: Optional[str], sigma: float, ovmm: Optional[float] = None) -> tuple:
    """Raw (beyond, back, neither) of a frozen two-head model offset by B0 (design §2.3)."""
    bb, bk, bn = (float(v) for v in b0_beyond_back_neither)
    res = bb + bk
    edges = spec["sigma_tercile_edges"]
    oz = None
    if "OVMM" in spec["spec_b"]:
        if landmark == "T15" and ovmm is None:
            raise ValueError("C1 needs the cross-venue move at T15")
        mu, sd = spec["c1_moments"]
        oz = None if ovmm is None else (float(ovmm) - mu) / sd
    xr = sum(b * _term(t, landmark=landmark, kind=kind, sigma=sigma, edges=edges, ovmm_z=oz)
             for t, b in zip(spec["spec_r"], spec["beta_r"]))
    xb = sum(b * _term(t, landmark=landmark, kind=kind, sigma=sigma, edges=edges, ovmm_z=oz)
             for t, b in zip(spec["spec_b"], spec["beta_b"]))
    pr = _sig(_lg(res) + xr)
    pb = _sig(_lg(bb / res) + xb)
    return _floor3((pr * pb, pr * (1 - pb), 1 - pr))


def raw_forecasts(model: Mapping[str, Any], *, landmark: str, kind: str, price: float, geo: Mapping[str, Any],
                  sigma: float, ovmm: Optional[float] = None) -> dict:
    """Raw three-outcome vectors at one landmark, in (up, dn, neither) order for display and in
    (beyond, back, neither) = (BREAK, REJECT, NEITHER) order for the calibrator and journal:
    B0, the champion M1, G1@event (the fallback raw, «обычно» of the model states) and C1 (shadow)."""
    up, dn, ne = b0_race(price, geo["p_up"], geo["p_dn"], sigma, TAU[landmark])
    b0 = (up, dn, ne) if geo["beyond_is_up"] else (dn, up, ne)
    out = {"b0": _floor3(b0),
           "m1": two_head(model["M1"], b0, landmark=landmark, kind=kind, sigma=sigma),
           "g1": two_head(model["G1"], b0, landmark=landmark, kind=None, sigma=sigma)}
    if landmark == "T0" or ovmm is not None:
        out["c1"] = two_head(model["C1"], b0, landmark=landmark, kind=kind, sigma=sigma, ovmm=ovmm)
    to_ud = (lambda p: {"up": p[0], "dn": p[1], "neither": p[2]}) if geo["beyond_is_up"] else \
            (lambda p: {"up": p[1], "dn": p[0], "neither": p[2]})
    return {"break_order": out, "display": {k: to_ud(v) for k, v in out.items()}}
