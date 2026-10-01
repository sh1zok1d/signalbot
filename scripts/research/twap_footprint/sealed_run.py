"""Sealed end-to-end TWAP run (DECISION_LAYER_RESEARCH_PROGRAM_V0 §8).

Stages, in order. Each stage writes its state under the run directory; the
scientific stages refuse to run before the sealed spec exists and its digest
matches.

  calibrate  Phase 0: grid recall / shuffled false positives on 2024-06; selection.
  detect     Phase 0: chosen detector over every month of both surfaces.
  counts     Phase 0: exclusions, the four counts, feasibility gates (no outcomes).
  freeze     Phase 1: write TWAP_SEALED_SPEC_V1.json (commit is done by the operator).
  h1         Phase 2: post-detection flow gate.
  price      Phase 3: H2 1h/6h, H3, Holm, floor, heterogeneity (only if H1 passed).
  replicate  Phase 4: replication cells (only cells that passed discovery).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from scripts.research.twap_footprint import detector as det
from scripts.research.twap_footprint.ingest import month_list

REPO = Path(__file__).resolve().parents[3]
SPEC_PATH = REPO / "docs/research/TWAP_SEALED_SPEC_V1.json"
MIN = 60_000
HOUR = 3_600_000
DAY = 86_400_000

GRID_TAU = (250, 500)
GRID_K = (20, 40)
GRID_DUR_MIN = (15, 30)
CAL_MONTH = "2024-06"
RECALL_SEED = 20261002
SHUFFLE_SEEDS = (20261003, 20261004, 20261005, 20261006, 20261007)
N_INJECT = 200
SURFACES = {
    "DISCOVERY": ("2020-01", "2024-12"),
    "REPLICATION": ("2017-08", "2019-12"),
}
BOOT_B = 10_000
BOOT_SEED = 20261002
HET_B = 2_000
HET_SEED = 20261008
REFERENCE_DAYS = 30
CONTROLS_PER_ANCHOR = 5
EXCLUSION_RADIUS_MS = 6 * HOUR
FLOOR_LOG = 0.001          # 10 bps
H1_RATIO_MIN = 1.10
ALPHA = 0.05


def _load_prints(run: Path, ym: str) -> dict:
    df = pd.read_parquet(run / "months" / f"prints_{ym}.parquet")
    return {c: df[c].to_numpy() for c in df.columns}


def _load_minutes(run: Path, months: list[str]) -> pd.DataFrame:
    parts = [pd.read_parquet(run / "months" / f"minutes_{ym}.parquet") for ym in months]
    return pd.concat(parts, ignore_index=True).sort_values("minute").reset_index(drop=True)


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")


# ----------------------------------------------------------------------------- calibrate
def calibrate(run: Path) -> dict:
    prints = _load_prints(run, CAL_MONTH)
    minutes = _load_minutes(run, [CAL_MONTH])
    mins = minutes["minute"].to_numpy() * MIN
    closes = minutes["close"].to_numpy()

    def price_at(t):
        i = int(np.searchsorted(mins, t - MIN, side="right")) - 1
        return float(closes[max(i, 0)])

    t0, t1 = int(prints["time"].min()), int(prints["time"].max())
    days = (t1 - t0) / DAY
    inj = det.make_injections(N_INJECT, RECALL_SEED, t0, t1, price_at)
    out = {"CAL_MONTH": CAL_MONTH, "DAYS": days, "CANDIDATES": []}
    for tau in GRID_TAU:
        real = det.build_all(prints, tau)
        shuf = [det.build_all(det.shuffle_within_hour(prints, s), tau) for s in SHUFFLE_SEEDS]
        rec = det.build_all(det.inject(prints, inj), tau)
        for k in GRID_K:
            for dmin in GRID_DUR_MIN:
                dms = dmin * MIN
                n_real = len(det.merge_episodes(det.qualified(real, k, dms)))
                n_sh = [len(det.merge_episodes(det.qualified(c, k, dms))) for c in shuf]
                q_rec = det.qualified(rec, k, dms)
                hits = sum(det.injection_detected(i, q_rec) for i in inj)
                mean_sh = float(np.mean(n_sh))
                out["CANDIDATES"].append({
                    "TAU_MS": tau, "K": k, "MIN_DURATION_MIN": dmin,
                    "REAL_EPISODES_CAL_MONTH": n_real, "SHUFFLED_EPISODES": n_sh,
                    "FP_PER_DAY": mean_sh / days,
                    "FP_RATIO": (mean_sh / n_real) if n_real > 0 else None,
                    "RECALL": hits / N_INJECT,
                })
    adm = [c for c in out["CANDIDATES"] if c["FP_RATIO"] is not None and c["RECALL"] >= 0.80 and c["FP_RATIO"] <= 0.10]
    for c in out["CANDIDATES"]:
        c["ADMISSIBLE"] = c in adm
    if not adm:
        out["SELECTED"] = None
        out["STATUS"] = "FEASIBILITY_FAILED"
        out["REASON"] = "DETECTOR_NOT_SPECIFIC"
    else:
        adm.sort(key=lambda c: (c["FP_PER_DAY"], -c["RECALL"], c["TAU_MS"], -c["K"], -c["MIN_DURATION_MIN"]))
        out["SELECTED"] = {k: adm[0][k] for k in ("TAU_MS", "K", "MIN_DURATION_MIN")}
        out["STATUS"] = "SELECTED"
    _write(run / "calibration.json", out)
    return out



# ----------------------------------------------------------------------------- detect
def _surface_months(surface: str) -> list[str]:
    a, b = SURFACES[surface]
    return month_list(a, b)


def _surface_bounds(surface: str) -> tuple[int, int]:
    a, b = SURFACES[surface]
    start = int(pd.Timestamp(a + "-01", tz="UTC").value // 1_000_000)
    end = int((pd.Timestamp(b + "-01", tz="UTC") + pd.offsets.MonthBegin(1)).value // 1_000_000)
    return start, end


def _neighbor(ym: str, delta: int) -> str:
    y, m = int(ym[:4]), int(ym[5:]) + delta
    while m < 1:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return f"{y:04d}-{m:02d}"


def detect(run: Path, surfaces=tuple(SURFACES)) -> dict:
    cal = json.loads((run / "calibration.json").read_text())
    sel = cal["SELECTED"]
    tau, k, dms = sel["TAU_MS"], sel["K"], sel["MIN_DURATION_MIN"] * MIN
    available = {p.stem.replace("prints_", "") for p in (run / "months").glob("prints_*.parquet")}
    summary = {"SELECTED": sel, "SURFACES": {}}
    cache = run / "detect_cache"
    cache.mkdir(exist_ok=True)
    for surface in surfaces:
        episodes = []
        for ym in _surface_months(surface):
            if ym not in available:
                summary.setdefault("MISSING_MONTHS", []).append(ym)
                continue
            done = cache / f"{surface}_{ym}_tau{tau}_k{k}_d{sel['MIN_DURATION_MIN']}.json"
            if done.exists():                      # resume after an interrupted run
                episodes.extend(json.loads(done.read_text()))
                continue
            m0 = int(pd.Timestamp(ym + "-01", tz="UTC").value // 1_000_000)
            m1 = int((pd.Timestamp(ym + "-01", tz="UTC") + pd.offsets.MonthBegin(1)).value // 1_000_000)
            parts = []
            prev, nxt = _neighbor(ym, -1), _neighbor(ym, 1)
            if prev in available:
                pp = _load_prints(run, prev)
                sel_ = pp["time"] >= m0 - EXCLUSION_RADIUS_MS
                parts.append({c: v[sel_] for c, v in pp.items()})
            parts.append(_load_prints(run, ym))
            if nxt in available and int(nxt[:4]) < 2025:
                pn = _load_prints(run, nxt)
                sel_ = pn["time"] < m1 + EXCLUSION_RADIUS_MS
                parts.append({c: v[sel_] for c, v in pn.items()})
            pr = {c: np.concatenate([p_[c] for p_ in parts]) for c in parts[0]}
            chains = det.build_all(pr, tau)
            eps = det.merge_episodes(det.qualified(chains, k, dms))
            month_eps = []
            for e in eps:
                if m0 <= e["T"] < m1:
                    e["month"] = ym
                    month_eps.append(e)
            tmp = done.with_suffix(".tmp")
            _write(tmp, month_eps)
            tmp.replace(done)                      # atomic: a cut write never looks done
            episodes.extend(month_eps)
            print(surface, ym, len(month_eps), flush=True)
        episodes.sort(key=lambda e: e["T"])
        pd.DataFrame(episodes).to_parquet(run / f"episodes_{surface}.parquet", index=False)
        summary["SURFACES"][surface] = {"N_DETECTED": len(episodes)}
    _write(run / f"detect_{'_'.join(surfaces)}.json", summary)
    return summary


# ----------------------------------------------------------------------------- minutes / matching helpers
class Minutes:
    """Minute aggregates on a dense grid. A minute with no aggTrade is a gap."""

    def __init__(self, run: Path, months: list[str]):
        df = _load_minutes(run, months)
        self.m0 = int(df["minute"].iloc[0])
        n = int(df["minute"].iloc[-1]) - self.m0 + 1
        idx = df["minute"].to_numpy() - self.m0
        self.n = np.zeros(n, dtype=np.int64); self.n[idx] = df["n"].to_numpy()
        self.buy = np.zeros(n); self.buy[idx] = df["buy_usd"].to_numpy()
        self.sell = np.zeros(n); self.sell[idx] = df["sell_usd"].to_numpy()
        close = np.full(n, np.nan); close[idx] = df["close"].to_numpy()
        self.close = pd.Series(close).ffill().to_numpy()          # last trade at or before
        self.gap_cum = np.r_[0, np.cumsum(self.n == 0)]
        self.buy_cum = np.r_[0.0, np.cumsum(self.buy)]
        self.sell_cum = np.r_[0.0, np.cumsum(self.sell)]
        lr = np.r_[np.nan, np.diff(np.log(self.close))]
        self.lr2_cum = np.r_[0.0, np.cumsum(np.nan_to_num(lr) ** 2)]

    def mi(self, t_ms):                       # minute index of the minute starting at t (t on a boundary)
        return np.asarray(t_ms) // MIN - self.m0

    def complete(self, a_ms, b_ms):           # no gap minute in [a, b)
        a, b = self.mi(a_ms), self.mi(b_ms)
        ok = (a >= 0) & (b <= len(self.n))
        a = np.clip(a, 0, len(self.n)); b = np.clip(b, 0, len(self.n))
        return ok & ((self.gap_cum[b] - self.gap_cum[a]) == 0)

    def price(self, t_ms):                    # last trade price at or before t (t on a boundary)
        i = np.clip(self.mi(t_ms) - 1, 0, len(self.close) - 1)
        return self.close[i]

    def flow(self, a_ms, b_ms, side):         # taker notional of one side in [a, b)
        a, b = self.mi(a_ms), self.mi(b_ms)
        return np.where(np.asarray(side) > 0, self.buy_cum[b] - self.buy_cum[a], self.sell_cum[b] - self.sell_cum[a])

    def net(self, a_ms, b_ms):
        a, b = self.mi(a_ms), self.mi(b_ms)
        return (self.buy_cum[b] - self.buy_cum[a]) - (self.sell_cum[b] - self.sell_cum[a])

    def rv(self, a_ms, b_ms):
        a, b = self.mi(a_ms), self.mi(b_ms)
        return np.sqrt(self.lr2_cum[b] - self.lr2_cum[a + 1])   # returns of minutes a+1..b-1 vs previous close


def ceil_min(t):
    return (np.asarray(t) // MIN + 1) * MIN


def match_vars(M: Minutes, t):
    t = np.asarray(t)
    hour = (t // HOUR) % 24
    rv = M.rv(t - 61 * MIN, t)
    net = M.net(t - 60 * MIN, t)
    ret = np.log(M.price(t) / M.price(t - 60 * MIN))
    return hour, rv, net, np.where(ret > 0, 1, -1)


def day_thresholds(grid_t, rv, net):
    """Per UTC day: terciles of RV60 and quintiles of NET60 over grid points in [d-30d, d)."""
    days = grid_t // DAY
    out = {}
    order = np.argsort(grid_t)
    gt, rvv, nv = grid_t[order], rv[order], net[order]
    for d in np.unique(days):
        lo = np.searchsorted(gt, (d - REFERENCE_DAYS) * DAY); hi = np.searchsorted(gt, d * DAY)
        if hi - lo < 1000:
            continue
        out[int(d)] = (np.quantile(rvv[lo:hi], [1 / 3, 2 / 3]), np.quantile(nv[lo:hi], [0.2, 0.4, 0.6, 0.8]))
    return out


def cells(t, hour, rv, net, sign, thr):
    res = []
    for ti, h, r, n, s in zip(np.asarray(t), hour, rv, net, sign):
        th = thr.get(int(ti // DAY))
        if th is None or not np.isfinite(r):
            res.append(None)
            continue
        res.append((int(h), int(np.searchsorted(th[0], r, side="right")), int(np.searchsorted(th[1], n, side="right")), int(s)))
    return res


def build_pool(M: Minutes, surface: str, all_T: np.ndarray, horizon_ms: int = 6 * HOUR):
    start, end = _surface_bounds(surface)
    grid = np.arange(start + 61 * MIN, end - horizon_ms, 5 * MIN, dtype=np.int64)
    ok = M.complete(grid - 61 * MIN, grid + horizon_ms)
    hour, rv, net, sign = match_vars(M, grid)
    thr = day_thresholds(grid[ok], rv[ok], net[ok])
    allT = np.sort(all_T)
    lo = np.searchsorted(allT, grid - EXCLUSION_RADIUS_MS); hi = np.searchsorted(allT, grid + EXCLUSION_RADIUS_MS, side="right")
    clean = (hi - lo) == 0
    ref_ok = grid >= start + REFERENCE_DAYS * DAY
    keep = ok & clean & ref_ok
    c = cells(grid[keep], hour[keep], rv[keep], net[keep], sign[keep], thr)
    pool = {}
    for g, cc in zip(grid[keep], c):
        if cc is not None:
            pool.setdefault(cc, []).append(int(g))
    pool = {kk: np.array(v, dtype=np.int64) for kk, v in pool.items()}
    return pool, thr


def match(anchors_t, anchor_cells, pool):
    """Up to 5 nearest-in-time controls per anchor, without replacement, anchors in time order.
    Returns one control list per anchor, in the input order (anchors may share a time)."""
    used = {kk: np.zeros(len(v), dtype=bool) for kk, v in pool.items()}
    out = [[] for _ in anchors_t]
    order = sorted(range(len(anchors_t)), key=lambda i: (anchors_t[i], i))
    for i_ in order:
        t, cc = anchors_t[i_], anchor_cells[i_]
        if cc is None or cc not in pool:
            continue
        arr, u = pool[cc], used[cc]
        i = int(np.searchsorted(arr, t))
        lo, hi, picked = i - 1, i, []
        while len(picked) < CONTROLS_PER_ANCHOR and (lo >= 0 or hi < len(arr)):
            dl = t - arr[lo] if lo >= 0 else None
            dh = arr[hi] - t if hi < len(arr) else None
            if dh is None or (dl is not None and dl <= dh):
                if not u[lo]:
                    picked.append(lo)
                lo -= 1
            else:
                if not u[hi]:
                    picked.append(hi)
                hi += 1
        for j in picked:
            u[j] = True
        out[i_] = [int(arr[j]) for j in picked]
    return out


# ----------------------------------------------------------------------------- counts (phase 0, no outcomes)
def counts(run: Path) -> dict:
    res = {"SURFACES": {}}
    for surface in SURFACES:
        eps = pd.read_parquet(run / f"episodes_{surface}.parquet").to_dict("records")
        start, end = _surface_bounds(surface)
        months = _surface_months(surface)
        M = Minutes(run, months)
        kept, dropped = det.apply_refractory(eps)
        log = [{"T": e["T"], "side": e["side"], "exclusion": "REFRACTORY"} for e in dropped]
        rows = []
        for e in kept:
            t0 = int(ceil_min(e["T"]))
            reasons = []
            if t0 < start + REFERENCE_DAYS * DAY:
                reasons.append("NO_REFERENCE")
            if t0 + 60 * MIN > end:
                reasons.append("SURFACE_END")
            elif not M.complete(np.array([t0 - 61 * MIN]), np.array([t0 + 60 * MIN]))[0]:
                reasons.append("DATA_GAP")
            persist = not reasons
            h6 = persist and (t0 + 6 * HOUR <= end) and bool(M.complete(np.array([t0]), np.array([t0 + 6 * HOUR]))[0])
            e_end = float(e["end"])
            end_ok = persist and e_end + 0 <= end and bool(M.complete(np.array([int(e["start"]) // MIN * MIN]), np.array([int(ceil_min(e_end))]))[0])
            e0 = int(ceil_min(e_end))
            post = end_ok and (e0 + 60 * MIN <= end) and bool(M.complete(np.array([e0 - 61 * MIN]), np.array([e0 + 60 * MIN]))[0])
            row = {"T": int(e["T"]), "t0": t0, "side": int(e["side"]), "start": int(e["start"]), "end": e_end, "e0": e0,
                   "persistence_eligible": persist, "h6_eligible": h6, "end_identified": end_ok,
                   "post_end_1h_complete": post, "exclusions": ";".join(reasons),
                   "chains": int(e["chains"]), "slices": int(e["slices"]), "period_ms": float(e["period_ms"]),
                   "key_types": e["key_types"]}
            rows.append(row)
            for r_ in reasons:
                log.append({"T": int(e["T"]), "side": int(e["side"]), "exclusion": r_})
        df = pd.DataFrame(rows)
        df.to_parquet(run / f"anchors_{surface}.parquet", index=False)
        pd.DataFrame(log).to_csv(run / f"exclusions_{surface}.csv", index=False)
        pe = df[df.persistence_eligible] if len(df) else df
        res["SURFACES"][surface] = {
            "N_DETECTED": len(eps),
            "N_AFTER_REFRACTORY": len(kept),
            "N_PERSISTENCE_ELIGIBLE": int(len(pe)),
            "PERSISTENCE_ELIGIBLE_DISTINCT_DAYS": int(pe["T"].floordiv(DAY).nunique()) if len(pe) else 0,
            "N_END_IDENTIFIED": int(df.end_identified.sum()) if len(df) else 0,
            "N_POST_END_1H_COMPLETE": int(df.post_end_1h_complete.sum()) if len(df) else 0,
            "N_H6_ELIGIBLE": int(df.h6_eligible.sum()) if len(df) else 0,
            "BY_SIDE": {str(s): int((pe.side == s).sum()) for s in (1, -1)} if len(pe) else {},
            "BY_YEAR": {str(y): int(v) for y, v in pd.to_datetime(pe["T"], unit="ms").dt.year.value_counts().sort_index().items()} if len(pe) else {},
            "EXCLUSIONS": pd.Series([l["exclusion"] for l in log]).value_counts().to_dict() if log else {},
        }
    d = res["SURFACES"]["DISCOVERY"]; r = res["SURFACES"]["REPLICATION"]
    gates = {
        "DISCOVERY_SUPPORT": d["N_PERSISTENCE_ELIGIBLE"] >= 300 and d["PERSISTENCE_ELIGIBLE_DISTINCT_DAYS"] >= 100,
        "H3_SUPPORT": d["N_POST_END_1H_COMPLETE"] >= 150,
        "REPLICATION_SUPPORT": r["N_PERSISTENCE_ELIGIBLE"] >= 100,
    }
    res["GATES"] = gates
    res["STATUS"] = "FEASIBLE" if gates["DISCOVERY_SUPPORT"] else "FEASIBILITY_FAILED"
    if not gates["DISCOVERY_SUPPORT"]:
        res["REASON"] = "SUPPORT"
    _write(run / "counts.json", res)
    return res



# ----------------------------------------------------------------------------- unconditional SD (outcome-blind)
def unconditional_sd(run: Path, surface: str, horizon_ms: int) -> float:
    """SD of h-horizon log returns on the 5-minute grid of the whole surface.
    Not conditioned on any episode: it is market data, not a hypothesis outcome."""
    M = Minutes(run, _surface_months(surface))
    start, end = _surface_bounds(surface)
    g = np.arange(start + MIN, end - horizon_ms, 5 * MIN, dtype=np.int64)
    ok = M.complete(g, g + horizon_ms)
    r = np.log(M.price(g[ok] + horizon_ms) / M.price(g[ok]))
    return float(np.std(r))


def het_assessable(n_by_year: dict, sd_h: float) -> dict:
    sd_ep = sd_h * math.sqrt(1 + 1 / CONTROLS_PER_ANCHOR)
    ns = sorted(v for v in n_by_year.values() if v > 0)
    if len(ns) < 3:
        return {"STATUS": "NOT_ASSESSABLE", "REASON": "FEWER_THAN_3_YEARS", "POWER": None}
    se = sd_ep * math.sqrt(1 / ns[0] + 1 / ns[1])
    z = FLOOR_LOG / se - NormalDist().inv_cdf(1 - ALPHA / 2)
    pw = NormalDist().cdf(z)
    return {"STATUS": "ASSESSABLE" if pw >= 0.5 else "NOT_ASSESSABLE", "POWER": pw, "SD_EPISODE": sd_ep,
            "N_TWO_SMALLEST_YEARS": ns[:2]}


# ----------------------------------------------------------------------------- freeze (phase 1)
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(run: Path) -> dict:
    cal = json.loads((run / "calibration.json").read_text())
    cnt = json.loads((run / "counts.json").read_text())
    if cnt["STATUS"] != "FEASIBLE":
        raise SystemExit("not feasible; nothing to freeze")
    ingest = [json.loads(l) for l in (run / "ingest_log.jsonl").read_text().splitlines() if l.strip()]
    data = {r["ym"]: r["sha256"] for r in ingest}
    anchors = pd.read_parquet(run / "anchors_DISCOVERY.parquet")
    pe = anchors[anchors.persistence_eligible]
    years = pd.to_datetime(pe["T"], unit="ms").dt.year.value_counts().to_dict()
    post = anchors[anchors.post_end_1h_complete]
    years_post = pd.to_datetime(post["T"], unit="ms").dt.year.value_counts().to_dict()
    h6 = anchors[anchors.h6_eligible]
    years_h6 = pd.to_datetime(h6["T"], unit="ms").dt.year.value_counts().to_dict()
    sd1 = unconditional_sd(run, "DISCOVERY", HOUR)
    sd6 = unconditional_sd(run, "DISCOVERY", 6 * HOUR)
    code = {str(f.relative_to(REPO)): _sha(f) for f in sorted((REPO / "scripts/research/twap_footprint").glob("*.py"))}
    spec = {
        "SPEC": "TWAP_SEALED_SPEC_V1",
        "AUTHORITY": "docs/research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md section 8 (PRs #285, #286)",
        "PLAN_FILE_SHA256": _sha(REPO / "docs/research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md"),
        "CODE_SHA256": code,
        "DATA_MONTH_ZIP_SHA256": data,
        "CALIBRATION": cal,
        "SELECTED_DETECTOR": cal["SELECTED"],
        "COUNTS_AND_GATES": cnt,
        "IMPLEMENTATION_DETAILS_FROZEN_BEFORE_OUTCOMES": {
            "PRINT": "all aggTrades of one taker side in the same ms, summed; kept if notional >= $1,000",
            "KEYS": "exact quantity (1e-8 units) and round(notional / $10)",
            "CHAIN_SEED": "triplet z<y<x with |(x-y)-(y-z)| <= tau, gaps in [2 s, 300 s]",
            "CHAIN_EXTENSION": "gap within tau of last+P, or of last+2P when the previous gap was not a miss; best = most slices; period = running mean over gap units",
            "TWAP_END": "last slice + 3 x period",
            "DETECTION_BUFFER": "each month is detected on [month start - 6 h, month end + 6 h]; episodes kept by T in month",
            "EPISODE_MERGE": "overlapping same-side qualified chains; T = earliest qualifying print; end = latest chain end",
            "REFRACTORY": "same side, 6 h after each kept T",
            "ANCHOR": "t0 = first minute boundary strictly after T; e0 = first minute boundary strictly after the declared end",
            "PRICE": "last trade price at or before the time (minute close, carried forward)",
            "DATA_GAP": "a minute with no aggTrade inside a required window",
            "PERSISTENCE_ELIGIBLE": "t0 >= surface start + 30 d; [t0-61m, t0+60m) complete; t0+60m <= surface end",
            "H6_ELIGIBLE": "persistence eligible and [t0, t0+6h) complete within the surface",
            "END_IDENTIFIED": "persistence eligible; [chain start, e0) complete; end within surface",
            "POST_END_1H_COMPLETE": "end identified and [e0-61m, e0+60m) complete within surface",
            "CONTROL_POOL": "5-minute grid of the surface; >= 30 d after surface start; [g-61m, g+6h) complete; no detected episode T (both sides, before refractory) within +-6 h",
            "MATCH_CELL": "UTC hour x RV60 tercile x NET60 quintile x sign(ret60); thresholds per UTC day from grid values in [d-30d, d)",
            "RV60": "sqrt(sum of squared 1-minute log returns over the 60 minutes before the anchor)",
            "NET60": "taker buy minus taker sell notional over the 60 minutes before the anchor",
            "RET60_SIGN": "+1 if log(price(t)/price(t-60m)) > 0 else -1",
            "CONTROLS": "up to 5 nearest in time, without replacement, anchors processed in time order; one matching run for t0 anchors (H1, H2) and one for e0 anchors (H3)",
            "NO_CONTROL": "anchor with zero controls is excluded from that test",
            "H1_VALUE": "log((episode same-side notional in [t0, t0+60m) + 1) / (mean control same-side notional + 1)); side = episode side",
            "H2_VALUE": "side * log(p(t0+h)/p(t0)) - mean over controls of side * log(p(g+h)/p(g)), h in {1h, 6h}; 6h only for H6-eligible anchors",
            "H3_VALUE": "side * log(p(e0+1h)/p(e0)) - mean over controls (matched at e0) of the same",
            "BOOTSTRAP": "UTC-day blocks of the anchor, resampled with replacement; numpy default_rng(seed) per test",
            "P_ONE_SIDED": "(1 + #{(b - m) >= m}) / (B + 1) for H1 (direction: positive)",
            "P_TWO_SIDED": "(1 + #{|b - m| >= |m|}) / (B + 1)",
            "P_REPLICATION": "(1 + #{s(b - m) >= s m}) / (B + 1), s = sign of the discovery estimate",
            "HOLM": "m = 3 cells always (H2_1h, H2_6h, H3); a cell not run counts as p = 1",
            "HETEROGENEITY_BLOCKS": "26-week blocks from the surface start; each block belongs to the year of its start; permutation shuffles block-to-year assignment keeping each year's block count",
            "HETEROGENEITY_ASSESSABILITY": "outcome-blind: per-episode SD = unconditional h-return SD x sqrt(1 + 1/5); difference = 10 bps between the two smallest years; two-sided alpha 0.05; NOT_ASSESSABLE if power < 0.50",
            "REPLICATION_H1": "computed on the replication surface and reported descriptively, only if the replication support gate passes; replication classification uses the frozen cell rule only",
            "REPLICATION_GATE_FAILED": "no replication outcome (flow or price) is computed; replication status INFERENCE_INSUFFICIENT; no substitute surface",
            "HETEROGENEITY_POWER_PROXY": "the V1 '2x difference between epochs' is operationalised as floor (10 bps) versus 2 x floor (20 bps) in the two smallest years, i.e. a 10 bps difference, two-sample z approximation",
        },
        "UNCONDITIONAL_SD_DISCOVERY": {"H1": sd1, "H6": sd6},
        "HETEROGENEITY_ASSESSABILITY_PLANNED": {
            "H2_1h": het_assessable({int(k): int(v) for k, v in years.items()}, sd1),
            "H2_6h": het_assessable({int(k): int(v) for k, v in years_h6.items()}, sd6),
            "H3": het_assessable({int(k): int(v) for k, v in years_post.items()}, sd1),
        },
        "SCIENTIFIC_OUTCOMES_OPENED_AT_FREEZE": False,
    }
    _write(SPEC_PATH, spec)
    return {"SPEC_PATH": str(SPEC_PATH), "SHA256": _sha(SPEC_PATH)}


def _assert_frozen(run: Path) -> dict:
    rec = run / "freeze_record.json"
    if not rec.exists() or not SPEC_PATH.exists():
        raise SystemExit("sealed spec is not frozen")
    r = json.loads(rec.read_text())
    if _sha(SPEC_PATH) != r["SHA256"]:
        raise SystemExit("sealed spec changed after freeze")
    return json.loads(SPEC_PATH.read_text())


# ----------------------------------------------------------------------------- statistics
def day_bootstrap(values: np.ndarray, days: np.ndarray, B: int, seed: int) -> np.ndarray:
    ud, inv = np.unique(days, return_inverse=True)
    sums = np.bincount(inv, weights=values); cnts = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ud), size=(B, len(ud)))
    return sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)


def p_one_sided(b, m, s=1.0):
    return float((1 + np.sum(s * (b - m) >= s * m)) / (len(b) + 1))


def p_two_sided(b, m):
    return float((1 + np.sum(np.abs(b - m) >= abs(m))) / (len(b) + 1))


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(items); out = {}; prev = 0.0; stop = False
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(prev, (m - i) * p)); prev = adj
        out[k] = adj
    return out


def heterogeneity(values: np.ndarray, t: np.ndarray, days: np.ndarray, surface: str, pooled: float) -> dict:
    start, _ = _surface_bounds(surface)
    years = pd.to_datetime(t, unit="ms").year.to_numpy()
    ys = sorted(set(years.tolist()))
    est = {int(y): float(values[years == y].mean()) for y in ys}
    sd_obs = float(np.std(list(est.values()), ddof=1)) if len(ys) >= 2 else 0.0
    block = (t - start) // (26 * 7 * DAY)
    ub = np.unique(block)
    block_year = {int(b): int(pd.Timestamp(start + int(b) * 26 * 7 * DAY, unit="ms").year) for b in ub}
    slots = [block_year[int(b)] for b in ub]
    rng = np.random.default_rng(HET_SEED)
    exceed = 0
    for _ in range(HET_B):
        perm = rng.permutation(slots)
        ymap = {int(b): int(y) for b, y in zip(ub, perm)}
        py = np.array([ymap[int(b)] for b in block])
        means = [values[py == y].mean() for y in ys if (py == y).any()]
        if len(means) >= 2 and np.std(means, ddof=1) >= sd_obs:
            exceed += 1
    p_het = (1 + exceed) / (HET_B + 1)
    sgn = 1.0 if pooled > 0 else -1.0
    opp = {}
    for y in ys:
        m = years == y
        if m.sum() < 2:
            continue
        b = day_bootstrap(values[m], days[m], HET_B, HET_SEED + int(y))
        opp[int(y)] = p_one_sided(b, est[y], -sgn)
    any_opp = any(v < ALPHA for v in opp.values())
    if p_het < ALPHA and any_opp:
        outcome = "HETEROGENEOUS_UNEXPLAINED"
    elif p_het < ALPHA:
        outcome = "PASS_MAGNITUDE_VARIES_BY_EPOCH"
    else:
        outcome = "PASS"
    return {"YEARLY": est, "SD_YEARLY": sd_obs, "P_HET": p_het, "P_OPPOSITE_BY_YEAR": opp, "OUTCOME": outcome}


# ----------------------------------------------------------------------------- outcomes
def _prepare(run: Path, surface: str, spec: dict):
    anchors = pd.read_parquet(run / f"anchors_{surface}.parquet")
    eps_all = pd.read_parquet(run / f"episodes_{surface}.parquet")
    M = Minutes(run, _surface_months(surface))
    pool, thr = build_pool(M, surface, eps_all["T"].to_numpy())
    return anchors, M, pool, thr


def _anchor_cells(M, t, thr):
    hour, rv, net, sign = match_vars(M, np.asarray(t))
    return cells(np.asarray(t), hour, rv, net, sign, thr)


def _assert_replication_supported(spec: dict, surface: str) -> None:
    if surface == "REPLICATION" and not spec["COUNTS_AND_GATES"]["GATES"]["REPLICATION_SUPPORT"]:
        raise SystemExit("replication support gate failed: INFERENCE_INSUFFICIENT, no replication outcome is computed")


def h1(run: Path, surface: str = "DISCOVERY") -> dict:
    spec = _assert_frozen(run)
    _assert_replication_supported(spec, surface)
    anchors, M, pool, thr = _prepare(run, surface, spec)
    a = anchors[anchors.persistence_eligible].reset_index(drop=True)
    cl = _anchor_cells(M, a.t0, thr)
    ctr = match(a.t0.tolist(), cl, pool)
    vals, days, ts = [], [], []
    no_ctrl = 0
    for t0, side, cs in zip(a.t0, a.side, ctr):
        if not cs:
            no_ctrl += 1
            continue
        x = float(M.flow(np.array([t0]), np.array([t0 + 60 * MIN]), np.array([side]))[0])
        c = M.flow(np.array(cs), np.array(cs) + 60 * MIN, np.full(len(cs), side)).mean()
        vals.append(math.log((x + 1) / (c + 1))); days.append(int(t0) // DAY); ts.append(int(t0))
    v = np.array(vals); d = np.array(days)
    m = float(v.mean())
    b = day_bootstrap(v, d, BOOT_B, BOOT_SEED)
    p = p_one_sided(b, m, 1.0)
    ratio = math.exp(m)
    res = {"SURFACE": surface, "N": int(len(v)), "N_NO_CONTROL": no_ctrl, "DAYS": int(len(set(days))),
           "MEAN_LOG_RATIO": m, "RATIO": ratio, "CI95_RATIO": [math.exp(float(np.quantile(b, 0.025))), math.exp(float(np.quantile(b, 0.975)))],
           "P_ONE_SIDED": p, "PASS": bool(p < ALPHA and ratio >= H1_RATIO_MIN)}
    _write(run / f"h1_{surface}.json", res)
    return res


def _cell_values(M, anchors_t, sides, ctr, h_ms):
    vals, days, ts = [], [], []
    for t, s, cs in zip(anchors_t, sides, ctr):
        if not cs:
            continue
        x = s * math.log(float(M.price(np.array([t + h_ms]))[0]) / float(M.price(np.array([t]))[0]))
        cs = np.array(cs)
        c = (s * np.log(M.price(cs + h_ms) / M.price(cs))).mean()
        vals.append(x - c); days.append(int(t) // DAY); ts.append(int(t))
    return np.array(vals), np.array(days), np.array(ts)


def price_cells(run: Path, surface: str = "DISCOVERY", only_cells=None) -> dict:
    spec = _assert_frozen(run)
    _assert_replication_supported(spec, surface)
    h1res = json.loads((run / "h1_DISCOVERY.json").read_text())
    if surface == "DISCOVERY" and not h1res["PASS"]:
        raise SystemExit("H1 failed: price outcomes are never computed")
    anchors, M, pool, thr = _prepare(run, surface, spec)
    a = anchors[anchors.persistence_eligible].reset_index(drop=True)
    ctr = match(a.t0.tolist(), _anchor_cells(M, a.t0, thr), pool)
    out = {"SURFACE": surface, "CELLS": {}}
    h6 = a.h6_eligible.to_numpy()
    plan = {"H2_1h": ("t0", HOUR, a, ctr),
            "H2_6h": ("t0", 6 * HOUR, a[h6], [c for c, k_ in zip(ctr, h6) if k_])}
    h3_ok = spec["COUNTS_AND_GATES"]["GATES"]["H3_SUPPORT"] if surface == "DISCOVERY" else True
    post = anchors[anchors.post_end_1h_complete].reset_index(drop=True)
    if h3_ok:
        ctr3 = match(post.e0.tolist(), _anchor_cells(M, post.e0, thr), pool)
        plan["H3"] = ("e0", HOUR, post, ctr3)
    for cell, (col, h, frame, cmap) in plan.items():
        if only_cells is not None and cell not in only_cells:
            continue
        v, d, t = _cell_values(M, frame[col].tolist(), frame.side.tolist(), cmap, h)
        m = float(v.mean()) if len(v) else float("nan")
        b = day_bootstrap(v, d, BOOT_B, BOOT_SEED) if len(v) else np.array([np.nan])
        out["CELLS"][cell] = {"N": int(len(v)), "DAYS": int(len(set(d.tolist()))), "MEAN": m, "MEAN_BPS": m * 1e4,
                              "CI95_BPS": [float(np.quantile(b, 0.025)) * 1e4, float(np.quantile(b, 0.975)) * 1e4],
                              "P_TWO_SIDED": p_two_sided(b, m), "_v": v, "_d": d, "_t": t, "_b": b}
    if surface == "DISCOVERY":
        ps = {c: out["CELLS"][c]["P_TWO_SIDED"] if c in out["CELLS"] else 1.0 for c in ("H2_1h", "H2_6h", "H3")}
        adj = holm(ps)
        if not h3_ok:
            out["CELLS"]["H3"] = {"STATUS": "INFERENCE_INSUFFICIENT"}
        for c, r in out["CELLS"].items():
            if "MEAN" not in r:
                continue
            r["P_HOLM"] = adj[c]
            r["PASS_HOLM_AND_FLOOR"] = bool(adj[c] < ALPHA and abs(r["MEAN"]) >= FLOOR_LOG)
            if r["PASS_HOLM_AND_FLOOR"]:
                r["HETEROGENEITY"] = heterogeneity(r["_v"], r["_t"], r["_d"], surface, r["MEAN"])
                r["HETEROGENEITY"]["ASSESSABILITY"] = spec["HETEROGENEITY_ASSESSABILITY_PLANNED"][c]
                het = r["HETEROGENEITY"]["OUTCOME"]
                r["SUPPORTED"] = het != "HETEROGENEOUS_UNEXPLAINED"
            else:
                r["SUPPORTED"] = False
    else:
        disc = json.loads((run / "price_DISCOVERY.json").read_text())
        for c, r in out["CELLS"].items():
            if "MEAN" not in r:
                continue
            s = 1.0 if disc["CELLS"][c]["MEAN"] > 0 else -1.0
            r["P_ONE_SIDED_DISCOVERY_DIRECTION"] = p_one_sided(r["_b"], r["MEAN"], s)
            r["REPLICATES"] = bool(np.sign(r["MEAN"]) == s and r["P_ONE_SIDED_DISCOVERY_DIRECTION"] < ALPHA and abs(r["MEAN"]) >= FLOOR_LOG)
    for r in out["CELLS"].values():
        for k_ in ("_v", "_d", "_t", "_b"):
            r.pop(k_, None)
    _write(run / f"price_{surface}.json", out)
    return out


if __name__ == "__main__":
    stage, run = sys.argv[1], Path(sys.argv[2])
    if stage == "detect_one":
        print(json.dumps(detect(run, (sys.argv[3],)), indent=1, default=str)); sys.exit()
    if stage == "h1_rep":
        print(json.dumps(h1(run, "REPLICATION"), indent=1, default=str)); sys.exit()
    if stage == "price_rep":
        print(json.dumps(price_cells(run, "REPLICATION", only_cells=sys.argv[3].split(",")), indent=1, default=str)); sys.exit()
    fn = {"calibrate": calibrate, "detect": detect, "counts": counts, "freeze": freeze, "h1": h1, "price": price_cells}[stage]
    print(json.dumps(fn(run), indent=1, default=str))
