"""DIRECTIONAL_STATE_SEARCH_V2: one bounded discovery cycle on CORE BTCUSDT perpetual 2020-2024.

    python -m scripts.research.directional_state_search_v2.evaluate preflight   # outcome-blind support only
    python -m scripts.research.directional_state_search_v2.evaluate run --go    # the one cycle (after the design freeze)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np

from . import constants as K
from . import data as D
from . import features as F
from . import sample as SM
from . import session as SS
from . import stats as S

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs/research/DIRECTIONAL_STATE_SEARCH_V2_DESIGN.md"
LEDGER_PATH = ROOT / "docs/research/DIRECTIONAL_STATE_SEARCH_V2_LEDGER.json"
RESULT_JSON = ROOT / "docs/research/DIRECTIONAL_STATE_SEARCH_V2_RESULT.json"
RESULT_MD = ROOT / "docs/research/DIRECTIONAL_STATE_SEARCH_V2_RESULT.md"
B0 = ("RP4H", "RET_4H", "RV_4H")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_digest() -> str:
    h = hashlib.sha256()
    for p in sorted(Path(__file__).resolve().parent.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def tzdata_version() -> str:
    for base in ("/usr/share/zoneinfo", "/usr/lib/zoneinfo"):
        zi = Path(base) / "tzdata.zi"
        if zi.exists():
            return zi.read_text().splitlines()[0].replace("# version", "").strip()
    return "unknown:" + platform.platform()


# ------------------------------------------------------------------ frames
def build(bars: dict) -> dict:
    base = F.baseline(bars)
    core = SM.core_frame(bars)
    rows = SS.session_rows(bars)
    sess = {}
    for name, (idx, st) in rows.items():
        ok = np.isfinite(st) & np.isfinite(base["rp"][idx]) & np.isfinite(base["ret4"][idx]) \
            & np.isfinite(base["rv4"][idx]) & np.isfinite(base["r1"][idx])
        idx, st = idx[ok], st[ok]
        t = bars["open_ms"][idx] + K.BAR_MS
        blocks, year = SM.blocks_of(t)
        sess[name] = {"idx": idx, "state": st, "blocks": blocks, "year": year, "RP4H": base["rp"][idx],
                      "RET_4H": base["ret4"][idx], "RV_4H": base["rv4"][idx], "R_1H": base["r1"][idx]}
    return {"base": base, "core": core, "session": sess}


def candidate_arrays(fr: dict, cid: str, state: str, source: str, extra: tuple) -> dict:
    if source == "core":
        c = fr["core"]
        x = c["states"][state]
        cols = {k: c[k] for k in B0}
        cols.update({k: c["states"][k] for k in extra})
        y, blocks, year, idx = c["R_1H"], c["blocks"], c["year"], c["idx"]
    else:
        c = fr["session"][state]
        x = c["state"]
        cols = {k: c[k] for k in B0}
        y, blocks, year, idx = c["R_1H"], c["blocks"], c["year"], c["idx"]
    ok = np.isfinite(x) & np.isfinite(y)
    for v in cols.values():
        ok &= np.isfinite(v)
    return {"x": x[ok], "y": y[ok], "controls": {k: v[ok] for k, v in cols.items()}, "blocks": blocks[ok],
            "year": year[ok], "idx": idx[ok]}


# ------------------------------------------------------------------ preflight (outcome-blind)
def preflight() -> dict:
    bars = D.to_5m(D.load_core_1m())
    fr = build(bars)
    out = {"core_digest": D.core_digest(), "bars_5m": int(bars["open_ms"].size),
           "base_anchors": int(fr["core"]["idx"].size), "candidates": {}}
    for cid, fam, state, source, extra in K.CANDIDATES + tuple((v[0], "variant", v[2], "core", v[3]) for v in K.VARIANTS):
        a = candidate_arrays(fr, cid, state, source, extra)
        x = a["x"]
        out["candidates"][cid] = {
            "state": state, "n": int(x.size), "iso_weeks": int(np.unique(a["blocks"]).size),
            "by_year": {str(y): int((a["year"] == y).sum()) for y in sorted(set(a["year"].tolist()))},
            "state_quantiles": [float(v) for v in np.quantile(x, [0.01, 0.25, 0.5, 0.75, 0.99])],
            "distinct_values": int(np.unique(x).size),
            "spearman_with_controls": {k: S.spearman(x, v) for k, v in a["controls"].items()},
        }
    core = fr["core"]
    names = [c[2] for c in K.CANDIDATES if c[3] == "core"]
    mat = np.column_stack([core["states"][n] for n in names])
    ok = np.isfinite(mat).all(axis=1)
    out["state_rank_correlation"] = {"names": names,
                                     "matrix": np.corrcoef(np.column_stack([S.average_ranks_fast(mat[ok][:, j])
                                                                            for j in range(len(names))]), rowvar=False).round(4).tolist()}
    return out



# ------------------------------------------------------------------ the one cycle
def refuse_if_scored() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN")


def assert_design_frozen() -> str:
    if K.DESIGN_SHA256 == "PENDING":
        raise SystemExit("DESIGN_HASH_UNSET")
    if _sha(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    if _sha(LEDGER_PATH) != K.LEDGER_PRE_SHA256:
        raise SystemExit("LEDGER_PRE_HASH_MISMATCH")
    return K.DESIGN_SHA256


def parity(bars: dict, base: dict) -> dict:
    """The recorded discovery cell (close_pos_4h -> R_1H, anchors i >= 96) must be reproduced exactly."""
    n = bars["open_ms"].size
    i = np.flatnonzero(((bars["open_ms"] - K.PHASE_ORIGIN_MS) // K.BAR_MS) % 3 == 2)
    i = i[(i >= 96) & (i + K.HORIZON_1H < n)]
    i = i[np.isfinite(base["rp"][i]) & np.isfinite(base["r1"][i])]
    rho = S.spearman(base["rp"][i], base["r1"][i])
    if i.size != K.PARITY_N or abs(rho - K.PARITY_RP4H_SPEARMAN) > K.PARITY_TOL:
        raise SystemExit(f"PARITY_FAILED n={i.size} rho={rho}")
    return {"n": int(i.size), "rho": rho, "expected": K.PARITY_RP4H_SPEARMAN}


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_") and k != "residual_state"}


def evaluate_one(a: dict, extra: tuple, ginv, W: int, draws: np.ndarray) -> dict:
    x, y = a["x"], a["y"]
    inv = ginv(a["blocks"])
    ctrl = [a["controls"][k] for k in B0 + tuple(extra)]
    raw = S.estimate(y, x, [], inv, W, draws)
    inc = S.estimate(y, x, ctrl, inv, W, draws)
    years = []
    for yr in sorted(set(a["year"].tolist())):
        m = a["year"] == yr
        pr = S.partial_rank(y[m], x[m], [c[m] for c in ctrl])
        years.append({"year": int(yr), "n": int(m.sum()), "raw": S.spearman(x[m], y[m]), "incremental": pr["rho"]})
    sign = np.sign(inc["point"])
    same = sum(1 for r in years if r["incremental"] is not None and np.sign(r["incremental"]) == sign)
    return {
        "n": int(x.size), "iso_weeks": int(np.unique(a["blocks"]).size), "controls": list(B0 + tuple(extra)),
        "p_up_all": float(np.mean(y > 0)), "mean_bp_all": float(y.mean() * 1e4), "median_bp_all": float(np.median(y) * 1e4),
        "raw": _clean(raw), "incremental": _clean(inc), "incremental_p_two_sided": S.two_sided_p(inc["z"]),
        "years": years, "years_same_sign_as_incremental": same,
        "quintiles_state": S.quintiles(x, y), "quintiles_residual_state": S.quintiles(inc["residual_state"], y),
        "_inc_draws": inc["_draws"], "_resid": inc["residual_state"], "_ctrl": ctrl, "_inv": inv,
    }


def interaction(a: dict, ev: dict, W: int, draws: np.ndarray) -> dict:
    """Stage 2 (only for objects whose incremental interval excludes zero): does the state modify the RP4H effect?
    P = centered rank(state) * centered rank(RP4H); partial Spearman(P, R_1H | controls + state)."""
    x, y, rp = a["x"], a["y"], a["controls"]["RP4H"]
    rx, rr = S.average_ranks_fast(x), S.average_ranks_fast(rp)
    prod = (rx - rx.mean()) * (rr - rr.mean())
    est = S.estimate(y, prod, ev["_ctrl"] + [x], ev["_inv"], W, draws)
    q = np.quantile(x, [1 / 3, 2 / 3])
    terc = np.digitize(x, q)
    within = []
    for t in range(3):
        m = terc == t
        within.append({"tercile": t + 1, "n": int(m.sum()),
                       "rp4h_partial_given_ret4h_rv4h": S.partial_rank(y[m], rp[m], [a["controls"]["RET_4H"][m],
                                                                                     a["controls"]["RV_4H"][m]])["rho"]})
    return {"interaction": _clean(est), "rp4h_effect_by_state_tercile": within}


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for k, (cid, p) in enumerate(items):
        running = max(running, min(1.0, (m - k) * p))
        out[cid] = running
    return out


def run() -> dict:
    refuse_if_scored()
    design = assert_design_frozen()
    bars = D.to_5m(D.load_core_1m())
    fr = build(bars)
    par = parity(bars, fr["base"])
    core = fr["core"]
    gweeks = np.unique(core["blocks"])
    W = int(gweeks.size)
    draws = S.boot_matrix(W)

    def ginv(blocks):
        pos = np.searchsorted(gweeks, blocks)
        if np.any(pos >= W) or np.any(gweeks[np.minimum(pos, W - 1)] != blocks):
            raise SystemExit("WEEK_OUTSIDE_GLOBAL_INDEX")
        return pos

    reads, objects = [], {}
    def read(cell, kind, cid, state, est, extra=()):
        reads.append({"cell": cell, "kind": kind, "object": cid, "state": state, "target": "R_1H",
                      "controls": list(B0 + tuple(extra)) if kind != "raw" else [], "point": est.get("point"),
                      "lo": est.get("lo"), "hi": est.get("hi"), "z": est.get("z")})

    arrays = {}
    for cid, fam, state, source, extra in K.CANDIDATES:
        a = candidate_arrays(fr, cid, state, source, extra)
        arrays[cid] = a
        ev = evaluate_one(a, extra, ginv, W, draws)
        ev.update({"family": fam, "state": state, "source": source})
        objects[cid] = ev
        read(f"{cid}:raw", "raw", cid, state, ev["raw"])
        read(f"{cid}:incremental", "incremental", cid, state, ev["incremental"], extra)

    variants = {}
    for vid, parent, state, extra in K.VARIANTS:
        a = candidate_arrays(fr, vid, state, "core", extra)
        ev = evaluate_one(a, extra, ginv, W, draws)
        variants[vid] = {"parent": parent, "state": state, **{k: v for k, v in ev.items() if not k.startswith("_")}}
        read(f"{vid}:raw", "variant_raw", vid, state, ev["raw"])
        read(f"{vid}:incremental", "variant_incremental", vid, state, ev["incremental"], extra)

    sens = {}
    for sid, parent, state, extra in K.SENSITIVITIES:
        a = candidate_arrays(fr, sid, state, "core", extra)
        ev = evaluate_one(a, extra, ginv, W, draws)
        sens[sid] = {"parent": parent, "state": state, "controls": ev["controls"], "incremental": ev["incremental"],
                     "n": ev["n"], "years": ev["years"]}
        read(f"{sid}:incremental", "sensitivity", sid, state, ev["incremental"], extra)

    # placebo clocks for the session objects: the same statistic at every other anchor of the main grid
    pl_states = SS.placebo_states(bars["close"], core["idx"])
    placebo = {}
    for cid in ("F6a", "F6b"):
        state = objects[cid]["state"]
        x = pl_states[state]
        keep = np.isfinite(x) & ~np.isin(core["idx"], fr["session"][state]["idx"])
        a = {"x": x[keep], "y": core["R_1H"][keep], "controls": {k: core[k][keep] for k in B0},
             "blocks": core["blocks"][keep], "year": core["year"][keep]}
        inv = ginv(a["blocks"])
        est = S.estimate(a["y"], a["x"], [a["controls"][k] for k in B0], inv, W, draws)
        diff = S.summarize_draws(objects[cid]["incremental"]["point"] - est["point"], objects[cid]["_inc_draws"] - est["_draws"])
        placebo[cid] = {"n": int(a["x"].size), "placebo_incremental": _clean(est), "clock_minus_placebo": diff}
        read(f"{cid}:placebo", "placebo", cid, state + "@all_other_anchors", est)
        read(f"{cid}:clock_minus_placebo", "placebo_difference", cid, state, diff)
    session_holm = holm({cid: objects[cid]["incremental_p_two_sided"] for cid in ("F6a", "F6b")})

    # stage 2: interactions only for objects whose incremental interval excludes zero
    inter = {}
    for cid, ev in objects.items():
        inc = ev["incremental"]
        if inc["lo"] > 0 or inc["hi"] < 0:
            inter[cid] = interaction(arrays[cid], ev, W, draws)
            read(f"{cid}:x_RP4H", "interaction", cid, ev["state"] + " x RP4H", inter[cid]["interaction"])

    # search-exposure bar (rules §4) over m_ST plus every cell read in this cycle
    m = K.M_ST_CORE_DIRECTION_BEFORE + len(reads)
    from statistics import NormalDist
    z_bar = NormalDist().inv_cdf(1.0 - K.PROMOTION_FAMILYWISE_ALPHA / (2.0 * m))

    ranking = rank(objects, z_bar)
    for ev in objects.values():
        for k in [k for k in ev if k.startswith("_")]:
            ev.pop(k)
    result = {
        "program": K.PROGRAM, "mode": K.MODE, "exposure_class": K.EXPOSURE_CLASS, "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False, "design_sha256": design, "design_commit": K.DESIGN_COMMIT,
        "ledger_pre_sha256": K.LEDGER_PRE_SHA256, "evaluator_digest": code_digest(), "core_digest": D.core_digest(),
        "tzdata": tzdata_version(), "surface": "CORE_BTC_BINANCE_V0 BTCUSDT perpetual 2020-01-01..2024-12-31 (5m from 1m)",
        "parity": par, "global_iso_weeks": W, "bootstrap": {"draws": K.BOOT_DRAWS, "seed": K.BOOT_SEED,
                                                            "method": "ISO-week block bootstrap of fixed rank residuals"},
        "objects": objects, "variants": variants, "sensitivities": sens, "placebo": placebo,
        "session_holm_adjusted_p": session_holm, "interactions": inter,
        "blocked_families": K.BLOCKED_FAMILIES, "cells_read": len(reads), "m_for_bar": m, "z_bar": z_bar,
        "ranking": ranking, "reads": reads,
    }
    result = json.loads(json.dumps(result, default=_json_default))
    RESULT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    from .report import write_markdown, write_ledger
    write_markdown(result, RESULT_MD)
    write_ledger(result, LEDGER_PATH)
    print("cells", len(reads), "z_bar", round(z_bar, 3))
    return result


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def rank(objects: dict, z_bar: float) -> dict:
    """Frozen procedure (design §6). Eligible for a TOP-3 replication proposal: incremental interval excludes zero,
    the incremental point keeps its sign in >= 4 of 5 years, |z| >= z_bar (rules §4 search-exposure bar), and a
    question-fresh surface with the needed observables exists (K.REPLICATION). Eligible objects are ordered by
    |incremental point| in 0.002-wide bins (floor), within a bin by the pre-assigned grades (K.GRADES), then by |point|."""
    rows = []
    for cid, ev in objects.items():
        inc = ev["incremental"]
        excl = inc["lo"] > 0 or inc["hi"] < 0
        stable = ev["years_same_sign_as_incremental"] >= 4
        bar = inc["z"] is not None and abs(inc["z"]) >= z_bar
        surface = bool(K.REPLICATION.get(cid))
        rows.append({"id": cid, "state": ev["state"], "incremental_point": inc["point"], "abs_point": abs(inc["point"]),
                     "interval_excludes_zero": excl, "years_same_sign": ev["years_same_sign_as_incremental"],
                     "z": inc["z"], "clears_search_bar": bar, "replication_surface": surface,
                     "grades": K.GRADES[cid], "eligible": excl and stable and bar and surface})
    grade_score = lambda g: sum({"A": 0, "B": 1, "C": 2}[v] for v in g.values())
    rows.sort(key=lambda r: (not r["eligible"], -math.floor(r["abs_point"] / 0.002 + 1e-12), grade_score(r["grades"]),
                             -r["abs_point"]))
    top = [r["id"] for r in rows if r["eligible"]][:3]
    return {"rows": rows, "top3": top}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("preflight", "run"))
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    if a.step == "preflight":
        print(json.dumps(preflight(), indent=1, sort_keys=True))
        return
    if not a.go:
        raise SystemExit("refusing: the one cycle needs --go")
    run()


if __name__ == "__main__":
    main()
