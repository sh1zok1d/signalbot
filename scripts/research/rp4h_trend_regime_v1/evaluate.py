"""RP4H_TREND_REGIME_MODULATION_V1: does the RP4H reversal differ between trending and ranging regimes (CORE 2020-24)?

    python -m scripts.research.rp4h_trend_regime_v1.evaluate preflight   # outcome-blind (support, TS terciles)
    python -m scripts.research.rp4h_trend_regime_v1.evaluate run --go    # the one shot, after the owner's go
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from scripts.research.rp4h_bitmex_temporal_v1.parent import average_ranks_fast, partial_rank

from . import constants as K
from .sample import core_bars, core_sample

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs/research/RP4H_TREND_REGIME_MODULATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs/research/RP4H_TREND_REGIME_MODULATION_V1.json"
RESULT_MD = ROOT / "docs/research/RP4H_TREND_REGIME_MODULATION_V1.md"
PACKAGES = (Path(__file__).resolve().parent, ROOT / "scripts/research/rp4h_bitmex_temporal_v1",
            ROOT / "scripts/research/directional_state_search_v2")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_digest() -> str:
    h = hashlib.sha256()
    for pkg in PACKAGES:
        for p in sorted(pkg.glob("*.py")):
            h.update(f"{pkg.name}/{p.name}".encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def blocks_of(close_ms):
    ts = pd.to_datetime(close_ms, unit="ms", utc=True)
    iso = ts.isocalendar()
    return iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64), ts.year.to_numpy(dtype=np.int64)


def tercile_edges(ts: np.ndarray) -> list:
    return [float(v) for v in np.quantile(ts, [1 / 3, 2 / 3])]


def terciles(ts: np.ndarray, edges) -> np.ndarray:
    return np.digitize(ts, edges, right=False)        # 0 = ranging (low TS), 2 = trending (high TS)


def _partial(s, ix, ctrl):
    return partial_rank(s["r1"][ix], s["rp"][ix], [s[c][ix] for c in ctrl])["rho"]


def interaction(s, ix) -> float | None:
    rp, ts = s["rp"][ix], s["ts"][ix]
    rr, rt = average_ranks_fast(rp), average_ranks_fast(ts)
    prod = (rr - rr.mean()) * (rt - rt.mean())
    return partial_rank(s["r1"][ix], prod, [rp, ts, s["ret4"][ix], s["rv4"][ix]])["rho"]


def estimands(s: dict, ix: np.ndarray, terc: np.ndarray) -> dict:
    t = terc[ix]
    out = {}
    for k in range(3):
        sub = ix[t == k]
        out[f"rho_t{k + 1}_b0"] = _partial(s, sub, K.B0)
        out[f"rho_t{k + 1}_b1"] = _partial(s, sub, K.B1)
    d = lambda a, b: None if a is None or b is None else a - b
    out["delta_b0"] = d(out["rho_t3_b0"], out["rho_t1_b0"])
    out["delta_b1"] = d(out["rho_t3_b1"], out["rho_t1_b1"])
    out["interaction_b0"] = interaction(s, ix)
    return out


def bootstrap(s: dict, terc: np.ndarray, blocks: np.ndarray) -> dict:
    rng = np.random.default_rng(K.BOOT_SEED)
    _u, inv = np.unique(blocks, return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(inv.max() + 1)]
    w = len(groups)
    names = list(estimands(s, np.arange(min(5000, s["r1"].size)), terc).keys())
    draws = {k: np.full(K.BOOT_DRAWS, np.nan) for k in names}
    for dr in range(K.BOOT_DRAWS):
        ix = np.concatenate([groups[i] for i in rng.integers(0, w, size=w)])
        e = estimands(s, ix, terc)
        for k in names:
            draws[k][dr] = np.nan if e[k] is None else e[k]
        if dr % 250 == 0:
            print(f"bootstrap {dr}", flush=True)
    out = {}
    for k, v in draws.items():
        f = v[np.isfinite(v)]
        out[k] = {"lo": float(np.quantile(f, K.BOOT_LO)) if f.size else None,
                  "hi": float(np.quantile(f, K.BOOT_HI)) if f.size else None,
                  "se": float(np.std(f, ddof=1)) if f.size > 1 else None, "valid": int(f.size), "draws": K.BOOT_DRAWS}
    return out


def assign_route(delta: float | None, ci: dict) -> str:
    if delta is None or ci["valid"] < K.MIN_VALID_DRAWS or ci["lo"] is None:
        return K.ROUTE_INVALID
    if delta > 0 and ci["lo"] > 0:
        return K.ROUTE_DISCOVERED
    if delta < 0 and ci["hi"] < 0:
        return K.ROUTE_OPPOSITE
    return K.ROUTE_NONE


def z_bar() -> float:
    m = K.M_ST_BEFORE + len(K.UNIT_CELLS)
    return NormalDist().inv_cdf(1 - K.FAMILYWISE_ALPHA / (2 * m))


def support(s: dict) -> dict:
    blocks, year = blocks_of(s["close_ms"])
    edges = tercile_edges(s["ts"])
    terc = terciles(s["ts"], edges)
    return {"n": int(s["r1"].size), "iso_weeks": int(np.unique(blocks).size),
            "by_year": {str(y): int((year == y).sum()) for y in sorted(set(year.tolist()))},
            "ts_quantiles": [float(v) for v in np.quantile(s["ts"], [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99])],
            "ts_tercile_edges": edges, "n_by_tercile": [int((terc == k).sum()) for k in range(3)],
            "spearman_ts_vs_rp4h": float(np.corrcoef(average_ranks_fast(s["ts"]), average_ranks_fast(s["rp"]))[0, 1]),
            "spearman_ts_vs_ret4": float(np.corrcoef(average_ranks_fast(s["ts"]), average_ranks_fast(np.abs(s["ret4"])))[0, 1])}


def preflight() -> dict:
    s = core_sample(core_bars(), need_24h=True)
    return {"support": support(s), "design_sha256": _sha(DESIGN_PATH) if DESIGN_PATH.exists() else None,
            "z_bar": z_bar()}


def refuse_if_scored():
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN")


def assert_design_frozen() -> str:
    if K.DESIGN_SHA256 == "PENDING":
        raise SystemExit("DESIGN_HASH_UNSET")
    if _sha(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    return K.DESIGN_SHA256


def run() -> dict:
    refuse_if_scored()
    design = assert_design_frozen()
    s = core_sample(core_bars(), need_24h=True)
    sup = support(s)
    if (sup["n"], sup["iso_weeks"]) != (K.EXPECTED_N, K.EXPECTED_WEEKS) or \
            not np.allclose(sup["ts_tercile_edges"], K.TS_TERCILE_EDGES, rtol=0, atol=1e-12):
        raise SystemExit("SUPPORT_MISMATCH")
    blocks, year = blocks_of(s["close_ms"])
    terc = terciles(s["ts"], K.TS_TERCILE_EDGES)
    allix = np.arange(s["r1"].size)
    points = estimands(s, allix, terc)
    print(f"sample {sup['n']} weeks {sup['iso_weeks']}", flush=True)
    ci = bootstrap(s, terc, blocks)
    route = assign_route(points["delta_b0"], ci["delta_b0"])
    zb = z_bar()
    z = None if not ci["delta_b0"]["se"] else points["delta_b0"] / ci["delta_b0"]["se"]
    years = []
    for y in sorted(set(year.tolist())):
        e = estimands(s, np.flatnonzero(year == y), terc)
        years.append({"year": int(y), "n": int((year == y).sum()), **{k: e[k] for k in ("rho_t1_b0", "rho_t3_b0", "delta_b0")}})
    quint = {}
    for k, lab in ((0, "ranging_t1"), (2, "trending_t3")):
        m = terc == k
        x, yv = s["rp"][m], s["r1"][m]
        edges = np.quantile(x, [0.2, 0.4, 0.6, 0.8])
        b = np.digitize(x, edges)
        quint[lab] = [{"bin": q + 1, "n": int((b == q).sum()), "p_up": float(np.mean(yv[b == q] > 0)),
                       "mean_bp": float(yv[b == q].mean() * 1e4), "median_bp": float(np.median(yv[b == q]) * 1e4)}
                      for q in range(5)]
    result = {
        "unit": K.UNIT, "mode": K.MODE, "evidence_class": K.EVIDENCE_CLASS, "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False, "design_sha256": design, "design_commit": K.DESIGN_COMMIT,
        "evaluator_digest": code_digest(), "surface": "CORE_BTC_BINANCE_V0 BTCUSDT perpetual 2020-01-01..2024-12-31 (5m from 1m)",
        "support": sup, "ts_tercile_edges": K.TS_TERCILE_EDGES, "points": points, "intervals": ci, "route": route,
        "z_delta_b0": z, "z_bar": zb, "clears_search_bar": bool(z is not None and abs(z) >= zb),
        "years": years, "rp4h_quintiles_within_regime": quint,
        "bootstrap": {"draws": K.BOOT_DRAWS, "seed": K.BOOT_SEED, "min_valid": K.MIN_VALID_DRAWS},
        "not_read": ["BitMEX", "Bybit", "Binance 2025/2026", "other regime variables", "other horizons", "signed trend"],
    }
    RESULT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    from .report import write_markdown
    write_markdown(result, RESULT_MD)
    print(route, flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("preflight", "run"))
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    if a.step == "preflight":
        print(json.dumps(preflight(), indent=1, sort_keys=True))
        return
    if not a.go:
        raise SystemExit("refusing: the one-shot read needs --go after the owner's go")
    run()


if __name__ == "__main__":
    main()
