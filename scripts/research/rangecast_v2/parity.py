"""Numerical parity of the shadow path with the research path (no outcome is read).

    python -m scripts.research.rangecast_v2.parity

1. The development-fold model of 2024 (fit on 2020-2023 rows exactly as the evaluation harness fit W_L1):
   the harness probabilities at hourly anchors against `rangecast_v2.state_at` (the 30-day live slice the
   shadow adapter uses) at the same anchors, and the vectorized path against `state_at` at 5-minute anchors.
2. The frozen artifact: the vectorized path against the adapter (`rangecast_shadow.paired_forecast`) at
   5-minute anchors of 2026 (probabilities only).
Writes docs/research/RANGECAST_V2_SHADOW_PARITY.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from beta import rangecast as rc
from beta import rangecast_shadow as sh
from beta import rangecast_v2 as v2
from beta.calendar_events import load_calendar
from beta.hist_series import BAR_MS

from . import evaluate as E

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/RANGECAST_V2_SHADOW_PARITY.json"
GRID = sh.TOUCH_GRID_PCT
TOL = 1e-9


def _probs_state(m, st, rows=None):
    sel = slice(None) if rows is None else rows
    s = {k: np.asarray(v)[sel] for k, v in st.items()}
    n = len(next(iter(s.values())))
    P = np.stack([np.stack([v2.touch_prob(m, s, side, np.full(n, d)) for side in ("up", "down")], 1) for d in GRID], 1)
    N = np.stack([v2.neither_prob(m, s, np.full(n, du), np.full(n, dd)) for du in sh.NEITHER_GRID_PCT
                  for dd in sh.NEITHER_GRID_PCT], 1)
    return P, N


def main() -> dict:
    S = E.Surface()
    rng = np.random.default_rng(20261012)
    out = {"tolerance_abs": TOL, "fold_2024": {}, "artifact": {}}
    for h in ("1h", "4h", "24h"):
        H = S.horizon(h)
        tg = H["tg"]
        train, test = S.split(h, E.ms(2024), E.ms(2025))
        c = S.close_ms[train]
        w = 0.5 ** ((c.max() - c) / 86_400_000 / E.HALF_LIFE_DAYS)
        Ftr, ctr = E._level_inputs(S, h, train)
        mh = v2.fit_level("L1", Ftr, ctr, tg["up"][train], tg["down"][train], weights=w)
        mh["horizon"] = h
        model = {"horizons": {h: mh}}
        # (a) harness path at hourly anchors vs state_at at the same anchors
        Fte, cte = E._level_inputs(S, h, test)
        st_vec = v2.state(mh, Fte, cte)
        pick = np.sort(rng.choice(test.size, 300, replace=False))
        P_vec, N_vec = _probs_state(mh, st_vec, pick)
        st_live = [v2.state_at(model, S.b, int(test[k]), h, events=S.events) for k in pick]
        st_live = {key: np.array([s[key] for s in st_live]) for key in st_live[0]}
        P_live, N_live = _probs_state(mh, st_live)
        # (b) every 5-minute offset: vectorized features at arbitrary bars vs state_at
        lo, hi = E.ms(2024), E.ms(2025)
        bars = np.flatnonzero((S.close_ms >= lo) & (S.close_ms < hi))
        bars = np.sort(rng.choice(bars, 300, replace=False))
        bars = bars[np.all([np.isfinite(S.F[n][bars]) for n in mh["features"]], axis=0)]
        cal = v2.calendar_columns(S.b, bars, h, S.events, weekend=H["weekend"])
        st5 = v2.state(mh, {k: v[bars] for k, v in S.F.items()}, cal)
        P5, N5 = _probs_state(mh, st5)
        st5l = [v2.state_at(model, S.b, int(j), h, events=S.events) for j in bars]
        st5l = {key: np.array([s[key] for s in st5l]) for key in st5l[0]}
        P5l, N5l = _probs_state(mh, st5l)
        out["fold_2024"][h] = {
            "hourly_anchors": int(pick.size), "five_minute_anchors": int(bars.size),
            "five_minute_offsets_covered": sorted({int((S.close_ms[j] // BAR_MS) % 12) * 5 for j in bars}),
            "max_abs_touch_hourly": float(np.max(np.abs(P_vec - P_live))),
            "max_abs_neither_hourly": float(np.max(np.abs(N_vec - N_live))),
            "max_abs_touch_5m": float(np.max(np.abs(P5 - P5l))), "max_abs_neither_5m": float(np.max(np.abs(N5 - N5l)))}
        print(h, out["fold_2024"][h], flush=True)
    # (c) the frozen artifact through the adapter, 5-minute anchors in 2026 (no outcome needed or read)
    art = sh.load_frozen_model()
    cal_file = load_calendar()
    bars = np.flatnonzero((S.close_ms >= E.ms(2026)) & (S.close_ms < E.ms(2026, 10, 11)))
    bars = bars[np.isfinite(S.b.close[bars])]
    bars = np.sort(rng.choice(bars, 120, replace=False))
    worst = {"touch": 0.0, "neither": 0.0, "checked": 0, "skipped": {}}
    for j in bars:
        close = int(S.close_ms[j])
        now = datetime.fromtimestamp(close / 1000, tz=timezone.utc) + timedelta(minutes=1)
        sub = S.b.slice(0, int(j) + 1)                         # the snapshot ends at the anchor bar
        snap = sh.Snapshot(bars=sub, price=float(S.b.close[j]), price_ts=now - timedelta(minutes=1), now=now,
                           calendar=cal_file)
        rec = sh.paired_forecast(snap, v1_model=None, v2_model=art)
        for h, x in rec["horizons"].items():
            r2 = x["v2"]
            if r2["status"] != sh.OK:
                worst["skipped"][r2["status"]] = worst["skipped"].get(r2["status"], 0) + 1
                continue
            mh = art["horizons"][h]
            cal = v2.calendar_columns(S.b, np.array([j]), h, S.events)
            st = v2.state(mh, {k: v[[j]] for k, v in S.F.items()}, cal)
            for t in r2["touch"]:
                p = float(v2.touch_prob(mh, st, "up" if t["side"] > 0 else "down", np.array([t["distance_pct"]]))[0])
                worst["touch"] = max(worst["touch"], abs(round(p, sh.PROB_DECIMALS) - t["probability"]))
            for q in r2["neither"]:
                p = float(v2.neither_prob(mh, st, np.array([q["up_pct"]]), np.array([q["down_pct"]]))[0])
                worst["neither"] = max(worst["neither"], abs(round(p, sh.PROB_DECIMALS) - q["probability"]))
            worst["checked"] += 1
    out["artifact"] = {"anchors": int(bars.size), "horizon_records_checked": worst["checked"],
                       "skipped_by_status": worst["skipped"], "max_abs_touch": worst["touch"],
                       "max_abs_neither": worst["neither"], "note": "adapter output rounded to 6 decimals; "
                       "compared with the vectorized path rounded the same way"}
    print("artifact", out["artifact"], flush=True)
    out["passed"] = bool(all(v <= TOL for r in out["fold_2024"].values() for k, v in r.items() if k.startswith("max_abs"))
                         and out["artifact"]["max_abs_touch"] <= 1e-12 and out["artifact"]["max_abs_neither"] <= 1e-12)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    main()
