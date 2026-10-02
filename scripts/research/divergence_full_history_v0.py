"""DIVERGENCE_FULL_HISTORY_RESEARCH_V0 runner.

Frozen design: `docs/research/DIVERGENCE_FULL_HISTORY_RESEARCH_V0_DESIGN.json`.

Stages, never intermingled:
- `acquire`: verified download of the 2025-01-01..2026-08-14 surface (and the
  OI metrics archive from 2022-11-01); nothing at or after the E1-safe read
  horizon 2026-08-15T00:00Z is requested;
- `validation`: the one frozen evaluation of DISCOVERY 2023-2024 and
  VALIDATION 2025-2026 arm-level estimates; persisted before anything else;
- `research`: the POOLED FULL HISTORY view and the exploratory mechanism
  analysis, run only after the validation result exists.

The SEED-0001 detector is used unchanged. Its 2025 protected-surface guard is
substituted, inside a scoped context only, by the E1 holdout start.
"""

from __future__ import annotations

import concurrent.futures as cf
import contextlib
import csv
import datetime as dt
import hashlib
import http.client
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import divergence_full_history_v0_lib as F
from scripts.research import divergence_panel_feasibility_v0 as V0
from scripts.research import seed0001_feasibility as R
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
DESIGN_REL = "docs/research/DIVERGENCE_FULL_HISTORY_RESEARCH_V0_DESIGN.json"
MANIFEST_REL = "docs/research_data/DIVERGENCE_FULL_HISTORY_V0_BINANCE_UM/DATASET_MANIFEST.json"
VALIDATION_REL = "docs/research/DIVERGENCE_FULL_HISTORY_RESEARCH_V0_VALIDATION.json"
VALIDATION_EPISODES_REL = "docs/research/divergence_full_history_v0/VALIDATION_EPISODES.csv"
RESEARCH_REL = "docs/research/DIVERGENCE_FULL_HISTORY_RESEARCH_V0_RESEARCH.json"
ARCHIVE = "https://data.binance.vision/data/futures/um"
DATA_ROOT = R.DATA_ROOT
PANEL = V0.PANEL
ARMS = ("A", "B", "C", "D")
DAY_MS = 86_400_000
MONTHS_NEW = [f"{y}-{m:02d}" for y, m in [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 8)]]
DAILY_KLINE_DAYS = [f"2026-08-{d:02d}" for d in range(1, 15)]
BOOK_DAYS_NEW_FIRST, BOOK_DAYS_LAST = dt.date(2025, 1, 1), dt.date(2026, 8, 14)
METRICS_FIRST = dt.date(2022, 11, 1)
_DATE = re.compile(r"(20\d{2})-(\d{2})(?:-(\d{2}))?(?=\.zip)")

PRIMARY_OUTCOME = "Y1_48H"
OUTCOMES = ("Y1_48H", "Y2_48H", "Y1_96H", "Y2_96H", "NET_R1_48H", "NET_R2_48H", "FWD_R_48H", "FWD_R_96H",
            "MFE_R_48H", "MAE_R_48H", "MFE_R_96H", "MAE_R_96H", "T_MFE_H_48H", "T_MAE_H_48H")
BINARY = ("Y1_48H", "Y2_48H", "Y1_96H", "Y2_96H")
BOOTSTRAP_RESAMPLES = 4999
BOOTSTRAP_SEED = 20261007
MEOI = 0.15
MIN_A_FOR_ASSESSMENT = 30
MECHANISM_SUBSET = ("SUPPORT_EXCESS", "BOOK_IMB_AT_LOW", "SELL_PRESSURE_CHANGE", "FLOW_AFTER_LOW", "OI_CHG_LEG",
                    "OI_CHG_24H", "LIQ_PROXY", "ATR_PCT", "HTF_EMA168_DIST_ATR", "RET_7D", "NEW_LOW_30D_ATR", "MKT_RET24")


class ProtectedAccessError(RuntimeError):
    pass


@contextlib.contextmanager
def e1_safe_detector_guard():
    """Scoped substitution of the detector's 2025 guard by the E1 holdout start; restored on exit."""
    old = L.PROTECTED_START_MS
    L.PROTECTED_START_MS = F.E1_HOLDOUT_START_MS
    try:
        yield
    finally:
        L.PROTECTED_START_MS = old


# -------------------------------------------------------------- acquisition

def assert_url_allowed(url: str) -> None:
    m = _DATE.search(url)
    if not m:
        raise ProtectedAccessError(f"URL_HAS_NO_PERIOD:{url}")
    y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
    if d is None:
        if (y, mo) >= (2026, 8):
            raise ProtectedAccessError(f"MONTHLY_OBJECT_REACHES_E1_MONTH:{url}")
    elif dt.date(y, mo, int(d)) >= dt.date(2026, 8, 15):
        raise ProtectedAccessError(f"DAILY_OBJECT_AT_OR_AFTER_READ_HORIZON:{url}")
    if y >= 2027:
        raise ProtectedAccessError(f"FUTURE_OBJECT:{url}")


def urls(kind: str, symbol: str, period: str) -> str:
    if kind == "KLINES_1M":
        return f"{ARCHIVE}/monthly/klines/{symbol}/1m/{symbol}-1m-{period}.zip"
    if kind == "KLINES_1M_DAILY":
        return f"{ARCHIVE}/daily/klines/{symbol}/1m/{symbol}-1m-{period}.zip"
    if kind == "BOOKDEPTH":
        return f"{ARCHIVE}/daily/bookDepth/{symbol}/{symbol}-bookDepth-{period}.zip"
    if kind == "METRICS":
        return f"{ARCHIVE}/daily/metrics/{symbol}/{symbol}-metrics-{period}.zip"
    raise ValueError(kind)


def raw_path(kind: str, symbol: str, period: str) -> Path:
    return DATA_ROOT / "raw" / kind / symbol / urls(kind, symbol, period).rsplit("/", 1)[1]


def cache_path(symbol: str, day: str) -> Path:
    return DATA_ROOT / "book_cache" / symbol / f"{day}.npz"


def _get(url: str, timeout: float = 120.0) -> tuple[int, bytes]:
    assert_url_allowed(url)
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b""
            last = e
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError, OSError) as e:
            last = e
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"FETCH_FAILED:{url}:{last}")


def parse_book_csv(raw: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Same parsing as seed0001_feasibility.load_book: +-5% rows, first duplicate kept, both sides required."""
    df = pd.read_csv(io.BytesIO(raw), usecols=["timestamp", "percentage", "notional"])
    df["percentage"] = df["percentage"].astype(float)
    df = df[df["percentage"].isin([-float(L.BOOK_BAND_PCT), float(L.BOOK_BAND_PCT)])]
    df = df.drop_duplicates(subset=["timestamp", "percentage"], keep="first")
    wide = df.pivot(index="timestamp", columns="percentage", values="notional")
    both = wide.dropna()
    ts = pd.to_datetime(both.index, format="%Y-%m-%d %H:%M:%S", utc=True).asi8 // 1_000_000
    return (np.asarray(ts, dtype=np.int64), both[-float(L.BOOK_BAND_PCT)].to_numpy(dtype=float),
            both[float(L.BOOK_BAND_PCT)].to_numpy(dtype=float), len(wide) - len(both))


def _acquire(kind: str, symbol: str, period: str) -> dict:
    url = urls(kind, symbol, period)
    row = {"KIND": kind, "SYMBOL": symbol, "PERIOD": period}
    path = raw_path(kind, symbol, period)
    if kind == "BOOKDEPTH" and cache_path(symbol, period).exists():
        meta = json.loads(cache_path(symbol, period).with_suffix(".json").read_text())
        return {**row, **meta}
    status, body = _get(url + ".CHECKSUM")
    if status == 404:
        return {**row, "STATUS": "MISSING_IN_ARCHIVE"}
    published = body.decode().split()[0]
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == published:
        data = path.read_bytes()
    else:
        status, data = _get(url)
        if status == 404:
            return {**row, "STATUS": "MISSING_IN_ARCHIVE"}
    digest = hashlib.sha256(data).hexdigest()
    if digest != published:
        raise RuntimeError(f"CHECKSUM_MISMATCH:{url}")
    out = {**row, "STATUS": "VERIFIED", "SHA256": digest, "BYTES": len(data)}
    if kind == "BOOKDEPTH":
        ts, bid, ask, dropped = parse_book_csv(_zip_member(data))
        cp = cache_path(symbol, period)
        cp.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cp, ts=ts, bid=bid, ask=ask)
        out["CACHE"] = "npz (raw zip deleted after verification to save disk; re-downloadable by SHA256)"
        out["SNAPSHOTS_WITHOUT_BOTH_SIDES"] = dropped
        cp.with_suffix(".json").write_text(json.dumps({k: v for k, v in out.items() if k not in row}))
        if path.exists():
            path.unlink()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return out


def _zip_member(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        if len(names) != 1:
            raise RuntimeError(f"ZIP_MEMBERS:{names}")
        return z.read(names[0])


def metrics_days() -> list[str]:
    n = (BOOK_DAYS_LAST - METRICS_FIRST).days + 1
    return [(METRICS_FIRST + dt.timedelta(days=k)).isoformat() for k in range(n)]


def new_book_days() -> list[str]:
    n = (BOOK_DAYS_LAST - BOOK_DAYS_NEW_FIRST).days + 1
    return [(BOOK_DAYS_NEW_FIRST + dt.timedelta(days=k)).isoformat() for k in range(n)]


def acquire(workers: int = 8) -> dict:
    jobs = [("KLINES_1M", s, m) for s in PANEL for m in MONTHS_NEW]
    jobs += [("KLINES_1M_DAILY", s, d) for s in PANEL for d in DAILY_KLINE_DAYS]
    jobs += [("BOOKDEPTH", s, d) for s in PANEL for d in new_book_days()]
    jobs += [("METRICS", s, d) for s in PANEL for d in metrics_days()]
    for kind, s, p in jobs:
        assert_url_allowed(urls(kind, s, p))
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda j: _acquire(*j), jobs))
    rows.sort(key=lambda r: (r["KIND"], r["SYMBOL"], r["PERIOD"]))
    if any(r["KIND"].startswith("KLINES") and r["STATUS"] != "VERIFIED" for r in rows):
        raise RuntimeError("KLINE_OBJECT_MISSING")
    body = {
        "DATASET_ID": "DIVERGENCE_FULL_HISTORY_V0_BINANCE_UM", "DESIGN": DESIGN_REL, "MARKET": "USD_M_FUTURES",
        "INSTRUMENTS": list(PANEL),
        "READ_HORIZON_EXCLUSIVE_UTC": L.iso_utc(F.READ_HORIZON_MS),
        "E1_HOLDOUT_UTC": [L.iso_utc(F.E1_HOLDOUT_START_MS), L.iso_utc(F.E1_HOLDOUT_END_MS)],
        "OBJECT_COUNTS": dict(Counter(f"{r['KIND']}|{r['SYMBOL']}|{r['STATUS']}" for r in rows)),
        "MISSING_IN_ARCHIVE": [f"{r['KIND']}|{r['SYMBOL']}|{r['PERIOD']}" for r in rows if r["STATUS"] != "VERIFIED"],
        "OBJECTS": [{k: r[k] for k in ("KIND", "SYMBOL", "PERIOD", "STATUS", "SHA256", "BYTES") if k in r} for r in rows],
        "E1_INTERVAL_BYTES_READ": False,
    }
    body["CANONICAL_MANIFEST_DIGEST"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    out = REPO / MANIFEST_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    return body


# -------------------------------------------------------------------- loaders

def _pinned() -> dict:
    pins = {}
    for rel in (R.MANIFEST_REL, V0.MANIFEST_REL, MANIFEST_REL):
        for o in json.loads((REPO / rel).read_text())["OBJECTS"]:
            if o.get("STATUS") == "VERIFIED":
                pins[(o["KIND"], o["SYMBOL"], o["PERIOD"])] = o["SHA256"]
    return pins


def load_minutes(symbol: str, pins: dict) -> dict:
    frames = []
    for kind, periods in (("KLINES_1M", R.KLINE_MONTHS + MONTHS_NEW), ("KLINES_1M_DAILY", DAILY_KLINE_DAYS)):
        for p in periods:
            path = raw_path(kind, symbol, p)
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != pins[(kind, symbol, p)]:
                raise RuntimeError(f"KLINE_SHA256_MISMATCH:{symbol}:{p}")
            df = pd.read_csv(io.BytesIO(_zip_member(data)), header=None, dtype=str)
            if not df.iloc[0, 0].isdigit():
                df = df.iloc[1:]
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    t = df[0].astype(np.int64).to_numpy()
    if np.any(np.diff(t) <= 0):
        raise RuntimeError(f"MINUTES_NOT_STRICTLY_INCREASING:{symbol}")
    F.assert_read_allowed(int(t[0]), int(t[-1]) + F.MINUTE_MS)
    return {"t": t, "open": df[1].astype(float).to_numpy(), "high": df[2].astype(float).to_numpy(),
            "low": df[3].astype(float).to_numpy(), "close": df[4].astype(float).to_numpy(),
            "volume": df[5].astype(float).to_numpy(), "taker_buy": df[9].astype(float).to_numpy()}


def load_book(symbol: str, grid: np.ndarray) -> tuple[dict, dict]:
    ts_all, bid_all, ask_all, missing = [], [], [], []
    for day in R.book_days() + new_book_days():
        cp = cache_path(symbol, day)
        if cp.exists():
            z = np.load(cp)
            ts, bid, ask = z["ts"], z["bid"], z["ask"]
        else:
            path = raw_path("BOOKDEPTH", symbol, day)
            if not path.exists():
                missing.append(day)
                continue
            ts, bid, ask, _ = parse_book_csv(_zip_member(path.read_bytes()))
        ts_all.append(ts); bid_all.append(bid); ask_all.append(ask)
    ts = np.concatenate(ts_all)
    order = np.argsort(ts, kind="stable")
    F.assert_read_allowed(int(ts.min()), int(ts.max()) + 1)
    book = L.book_hourly_imbalance(ts[order], np.concatenate(bid_all)[order], np.concatenate(ask_all)[order], grid)
    return book, {"DAYS_MISSING": missing}


def load_oi(symbol: str, pins: dict) -> tuple[dict, dict]:
    t_all, v_all, missing = [], [], []
    for day in metrics_days():
        path = raw_path("METRICS", symbol, day)
        if not path.exists():
            missing.append(day)
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pins[("METRICS", symbol, day)]:
            raise RuntimeError(f"METRICS_SHA256_MISMATCH:{symbol}:{day}")
        df = pd.read_csv(io.BytesIO(_zip_member(data)), usecols=["create_time", "sum_open_interest"])
        ct = pd.to_datetime(df["create_time"], format="%Y-%m-%d %H:%M:%S", utc=True).astype("int64") // 1_000_000
        t_all.append(ct.to_numpy() + 5 * F.MINUTE_MS)
        v_all.append(df["sum_open_interest"].astype(float).to_numpy())
    t = np.concatenate(t_all)
    v = np.concatenate(v_all)
    order = np.argsort(t, kind="stable")
    t, v = t[order], v[order]
    keep = np.r_[True, np.diff(t) > 0]
    F.assert_read_allowed(int(t.min()), int(t.max()))
    return {"available_ms": t[keep], "value": v[keep]}, {"DAYS_MISSING": missing, "RECORDS": int(keep.sum())}


# ------------------------------------------------------------------ pipeline

def symbol_pipeline(symbol: str, pins: dict, v0_digests: dict, *, with_features_inputs: bool) -> dict:
    minutes = load_minutes(symbol, pins)
    bars = L.hourly_bars(minutes["t"], minutes["open"], minutes["high"], minutes["low"], minutes["close"],
                         minutes["volume"], minutes["taker_buy"])
    book, book_meta = load_book(symbol, bars["open_time_ms"])
    with e1_safe_detector_guard():
        disc = L.detect(bars, book, decision_start_ms=F.DISCOVERY_FIRST_DECISION_MS,
                        decision_last_ms=F.DISCOVERY_LAST_DECISION_MS)
        val = L.detect(bars, book, decision_start_ms=F.VALIDATION_FIRST_DECISION_MS,
                       decision_last_ms=F.VALIDATION_LAST_DECISION_MS)
        L.assert_outcome_blind(disc["EPISODES"] + val["EPISODES"])
        audit = R.pit_audit(bars, book, val["EPISODES"])
    disc_digest = hashlib.sha256("\n".join(L.episode_digest_rows(disc["EPISODES"], symbol)).encode()).hexdigest()
    if disc_digest != v0_digests[symbol]:
        raise RuntimeError(f"DISCOVERY_EPISODES_NOT_REPRODUCED:{symbol}")
    episodes = []
    for slice_name, out in (("DISCOVERY", disc), ("VALIDATION", val)):
        for ep in out["EPISODES"]:
            row = {**ep, "SYMBOL": symbol, "SLICE": slice_name, "EPISODE_ID": f"{symbol}-{ep['DECISION_TIME_UTC']}"}
            row.update(F.episode_outcomes(minutes, ep))
            episodes.append(row)
    result = {"EPISODES": episodes,
              "META": {"FUNNEL_DISCOVERY": disc["FUNNEL"], "FUNNEL_VALIDATION": val["FUNNEL"],
                       "BOOK_DAYS_MISSING": book_meta["DAYS_MISSING"], "PIT_AUDIT_VALIDATION": audit,
                       "INCOMPLETE_HOURS": int((~bars["complete"]).sum()), "DISCOVERY_DIGEST": disc_digest}}
    if with_features_inputs:
        oi, oi_meta = load_oi(symbol, pins)
        result["FEATURE_INPUTS"] = {"bars": bars, "ind": L.indicators(bars), "ema168": F.ema_by_segment(bars, F.HTF_EMA_BARS),
                                    "book_imb": book["imbalance"], "oi": oi}
        result["META"]["OI"] = oi_meta
    return result


# ---------------------------------------------------------------- estimation

def design(eps: list[dict], *, symbol_fe: bool = True, covariates: bool = True, slice_fe: bool = False,
           extra: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
    arms = np.array([e["ARM"] for e in eps])
    cols = [np.ones(len(eps)), arms == "A", arms == "B", arms == "C"]
    names = ["1", "A", "B", "C"]
    if symbol_fe:
        syms = np.array([e["SYMBOL"] for e in eps])
        for s in [s for s in PANEL if (syms == s).any()][1:]:
            cols.append(syms == s); names.append(f"SYM_{s}")
    if slice_fe:
        cols.append(np.array([e["SLICE"] == "VALIDATION" for e in eps])); names.append("SLICE_VALIDATION")
    if covariates:
        hour = np.array([e["TOD_HOUR_UTC"] for e in eps], dtype=float)
        cols += [np.log(np.array([e["RV24"] for e in eps], dtype=float)), np.sin(2 * np.pi * hour / 24),
                 np.cos(2 * np.pi * hour / 24), np.array([e["DECLINE_ATR"] for e in eps], dtype=float),
                 np.array([e["NETFLOW24"] for e in eps], dtype=float), np.array([e["RISK_ATR"] for e in eps], dtype=float)]
        names += ["LOG_RV24", "TOD_SIN", "TOD_COS", "DECLINE_ATR", "NETFLOW24", "RISK_ATR"]
    for name in extra or []:
        cols.append(np.array([e[name] for e in eps], dtype=float)); names.append(name)
    return np.column_stack(cols).astype(float), names


def contrasts(names: list[str]) -> dict:
    def vec(**w):
        v = np.zeros(len(names))
        for k, x in w.items():
            v[names.index(k)] = x
        return v
    return {"A_MINUS_B": vec(A=1, B=-1), "INTERACTION": vec(A=1, B=-1, C=-1), "A_MINUS_D": vec(A=1),
            "C_MINUS_D": vec(C=1)}


def arm_model(eps: list[dict], outcome: str, *, symbol_fe=True, covariates=True, slice_fe=False, clusters="WEEK_BLOCK") -> dict:
    rows = [e for e in eps if e.get(outcome) is not None and not (isinstance(e[outcome], float) and math.isnan(e[outcome]))]
    counts = Counter(e["ARM"] for e in rows)
    if any(counts.get(a, 0) < 2 for a in ARMS):
        return {"N": len(rows), "ARM_COUNTS": dict(counts), "ESTIMABLE": False}
    X, names = design(rows, symbol_fe=symbol_fe, covariates=covariates, slice_fe=slice_fe)
    y = np.array([float(e[outcome]) for e in rows])
    fit = F.ols_cr1(X, y, [e[clusters] for e in rows])
    out = {"N": len(rows), "ARM_COUNTS": dict(sorted(counts.items())), "CLUSTERS": fit["G"], "ESTIMABLE": True}
    for k, c in contrasts(names).items():
        out[k] = F.contrast(fit, c)
    return out


def arm_summary(eps: list[dict]) -> dict:
    out = {}
    for a in ARMS:
        sel = [e for e in eps if e["ARM"] == a]
        row = {"N": len(sel), "DATES": len({e["DECISION_DATE_UTC"] for e in sel}),
               "WEEK_CLUSTERS": len({e["WEEK_BLOCK"] for e in sel})}
        for y in BINARY:
            row[f"{y}_WLN"] = dict(Counter(e[f"{y}_WLN"] for e in sel))
            vals = [e[y] for e in sel if e[y] is not None]
            row[f"{y}_RATE"] = float(np.mean(vals)) if vals else None
        for y in ("NET_R1_48H", "FWD_R_48H", "FWD_R_96H", "MFE_R_48H", "MAE_R_48H", "T_MFE_H_48H", "T_MAE_H_48H",
                  "FWD_RET_48H"):
            vals = np.array([e[y] for e in sel if e[y] is not None], dtype=float)
            row[y] = {"MEAN": float(vals.mean()), "MEDIAN": float(np.median(vals))} if vals.size else None
        out[a] = row
    return out


def slice_report(eps: list[dict]) -> dict:
    X, names = design(eps)
    y = np.array([float(e[PRIMARY_OUTCOME]) for e in eps])
    rep = {
        "COUNTS_BY_SYMBOL": {s: dict(sorted(Counter(e["ARM"] for e in eps if e["SYMBOL"] == s).items())) for s in PANEL},
        "ARM_SUMMARY": arm_summary(eps),
        "MODELS": {o: arm_model(eps, o) for o in OUTCOMES},
        "PRIMARY_BOOTSTRAP_A_MINUS_B": F.week_bootstrap(X, y, [e["WEEK_BLOCK"] for e in eps], contrasts(names)["A_MINUS_B"],
                                                        resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED),
        "BY_SYMBOL": {}, "BY_HALF_YEAR": {},
    }
    for s in PANEL:
        sub = [e for e in eps if e["SYMBOL"] == s]
        rep["BY_SYMBOL"][s] = {o: arm_model(sub, o, symbol_fe=False, covariates=False) for o in ("Y1_48H", "FWD_R_48H")}
    for blk in sorted({e["EPOCH"] for e in eps}):
        sub = [e for e in eps if e["EPOCH"] == blk]
        rep["BY_HALF_YEAR"][blk] = {o: arm_model(sub, o, covariates=False) for o in ("Y1_48H", "FWD_R_48H")}
    for group in ("BY_SYMBOL", "BY_HALF_YEAR"):
        for key in ("A_MINUS_B", "INTERACTION"):
            ests = [(v["Y1_48H"][key]["ESTIMATE"], v["Y1_48H"][key]["SE_CR1"]) for v in rep[group].values()
                    if v["Y1_48H"].get("ESTIMABLE")]
            rep[f"{group}_HETEROGENEITY_{key}"] = F.heterogeneity_q(ests)
    return rep


def labels(val: dict, disc: dict) -> dict:
    out = {}
    a = val["ARM_SUMMARY"]["A"]
    for key in ("A_MINUS_B", "INTERACTION"):
        m = val["MODELS"][PRIMARY_OUTCOME]
        if not m.get("ESTIMABLE") or a["N"] < MIN_A_FOR_ASSESSMENT or a["WEEK_CLUSTERS"] < MIN_A_FOR_ASSESSMENT:
            out[key] = ["INCONCLUSIVE_SAMPLE"]
            continue
        est, ci = m[key]["ESTIMATE"], m[key]["CI95"]
        d_est = disc["MODELS"][PRIMARY_OUTCOME][key]["ESTIMATE"]
        tags = ["SAME_DIRECTION" if np.sign(est) == np.sign(d_est) else "OPPOSITE_DIRECTION",
                "COMPATIBLE_WITH_ZERO" if ci[0] <= 0 <= ci[1] else "DISTINGUISHABLE_FROM_ZERO",
                "AT_OR_ABOVE_MEOI" if est >= MEOI else "BELOW_MEOI"]
        if est < 0.05 and ci[1] < MEOI:
            tags.append("ECONOMICALLY_SMALL")
        het = val[f"BY_SYMBOL_HETEROGENEITY_{key}"]
        tags.append("HETEROGENEOUS_ACROSS_SYMBOLS" if het["P"] is not None and het["P"] < 0.05
                    else "NO_DETECTED_SYMBOL_HETEROGENEITY")
        out[key] = tags
    return out


def _common(stage: str) -> tuple[dict, dict, dict]:
    design_bytes = (REPO / DESIGN_REL).read_bytes()
    dsg = json.loads(design_bytes)
    for rel, digest in dsg["CODE_IDENTITY"].items():
        if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"CODE_IDENTITY_MISMATCH:{rel}")
    for rel, digest in dsg["FROZEN_ARTIFACTS"].items():
        if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"FROZEN_ARTIFACT_CHANGED:{rel}")
    v0 = json.loads((REPO / V0.REPORT_REL).read_text())
    return dsg, {s: v0["PER_SYMBOL"][s]["EPISODE_DIGEST"] for s in PANEL}, {"DESIGN_SHA256": hashlib.sha256(design_bytes).hexdigest(), "STAGE": stage}


def _jsonable(v):
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def run_validation() -> dict:
    if (REPO / VALIDATION_REL).exists():
        raise RuntimeError("VALIDATION_ALREADY_EVALUATED: the validation slice is evaluated once")
    dsg, v0_digests, ident = _common("VALIDATION")
    pins = _pinned()
    eps, meta = [], {}
    for s in PANEL:
        r = symbol_pipeline(s, pins, v0_digests, with_features_inputs=False)
        eps += r["EPISODES"]
        meta[s] = r["META"]
    disc = [e for e in eps if e["SLICE"] == "DISCOVERY"]
    val = [e for e in eps if e["SLICE"] == "VALIDATION"]
    rep_val, rep_disc = slice_report(val), slice_report(disc)
    out_rows = sorted(val, key=lambda e: (e["SYMBOL"], e["DECISION_TIME_MS"]))
    path = REPO / VALIDATION_EPISODES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(out_rows[0].keys())
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for e in out_rows:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in e.items()})
    report = {
        "REPORT": "DIVERGENCE_FULL_HISTORY_RESEARCH_V0_VALIDATION", **ident,
        "LABELS_OF_SLICES": {"DISCOVERY": "DISCOVERY / PREVIOUSLY OBSERVED", "VALIDATION": "VALIDATION / PREVIOUSLY UNSEEN"},
        "USABLE_DECISIONS_UTC": {"DISCOVERY": [L.iso_utc(F.DISCOVERY_FIRST_DECISION_MS), L.iso_utc(F.DISCOVERY_LAST_DECISION_MS)],
                                 "VALIDATION": [L.iso_utc(F.VALIDATION_FIRST_DECISION_MS), L.iso_utc(F.VALIDATION_LAST_DECISION_MS)]},
        "READ_HORIZON_EXCLUSIVE_UTC": L.iso_utc(F.READ_HORIZON_MS),
        "E1_HOLDOUT_UTC": [L.iso_utc(F.E1_HOLDOUT_START_MS), L.iso_utc(F.E1_HOLDOUT_END_MS)],
        "PER_SYMBOL_META": meta,
        "VALIDATION": rep_val, "DISCOVERY": rep_disc,
        "VALIDATION_LABELS": labels(rep_val, rep_disc),
        "VALIDATION_EPISODES_CSV": VALIDATION_EPISODES_REL,
        "VALIDATION_EPISODES_SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "EVALUATED_ONCE": True, "E1_INTERVAL_TOUCHED": False, "PROSPECTIVE_ACTIVATED": False, "SEED0003_CREATED": False,
        "RUNNER_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (REPO / VALIDATION_REL).write_text(json.dumps(report, indent=1, sort_keys=True, default=_jsonable) + "\n")
    return report


# ---------------------------------------------------------------- research stage

def standardized(eps: list[dict], names) -> None:
    for n in names:
        vals = np.array([e[n] for e in eps], dtype=float)
        ok = ~np.isnan(vals)
        mu, sd = vals[ok].mean(), vals[ok].std(ddof=1)
        for e, v in zip(eps, vals):
            e[f"Z_{n}"] = (v - mu) / sd if sd > 0 and not math.isnan(v) else float("nan")


def within_support_models(eps: list[dict]) -> dict:
    sup = [e for e in eps if e["ARM"] in ("A", "B")]
    for e in sup:
        e["DIV"] = 1.0 if e["ARM"] == "A" else 0.0
        for fam in ("RSI_FAMILY", "MACD_FAMILY", "CVD_FAMILY"):
            e[f"F_{fam}"] = 1.0 if e[fam] else 0.0
    zfeat = [f"Z_{n}" for n in MECHANISM_SUBSET]
    complete = [e for e in sup if all(not math.isnan(e[z]) for z in zfeat) and not math.isnan(e["DEEPER_STATE_FLOW_OI"])]

    def fit(rows, extra, outcome=PRIMARY_OUTCOME):
        X, names = design(rows, covariates=True, slice_fe=True, extra=extra)
        drop = [names.index(n) for n in ("A", "B", "C")]
        keep = [k for k in range(len(names)) if k not in drop]
        X, names = X[:, keep], [names[k] for k in keep]
        y = np.array([float(e[outcome]) for e in rows])
        f = F.ols_cr1(X, y, [e["WEEK_BLOCK"] for e in rows])
        res = {"N": len(rows), "CLUSTERS": f["G"]}
        for n in extra:
            c = np.zeros(len(names)); c[names.index(n)] = 1.0
            res[n] = F.contrast(f, c)
        return res

    return {
        "POPULATION": "support episodes (A and B), pooled, slice and symbol fixed effects, SEED-0001 covariates, CR1 by week",
        "M0_DIV_ALL": fit(sup, ["DIV"]),
        "M0_DIV_COMPLETE_CASES": fit(complete, ["DIV"]),
        "M1_DIV_PLUS_MECHANISM": fit(complete, ["DIV"] + zfeat),
        "M2_FAMILIES": fit(sup, ["F_RSI_FAMILY", "F_MACD_FAMILY", "F_CVD_FAMILY"]),
        "M2_FAMILIES_PLUS_MECHANISM": fit(complete, ["F_RSI_FAMILY", "F_MACD_FAMILY", "F_CVD_FAMILY"] + zfeat),
        "M3_DEEPER_STATE_ALONE": fit(complete, ["DEEPER_STATE_FLOW_OI"]),
        "M3_DIV_PLUS_DEEPER_STATE": fit(complete, ["DIV", "DEEPER_STATE_FLOW_OI"]),
        "M0_NET_R": fit(sup, ["DIV"], outcome="NET_R1_48H"),
        "COMPLETE_CASES": len(complete),
    }


def failure_states(eps: list[dict], arm: str) -> dict:
    rows = [e for e in eps if e["ARM"] == arm]
    out, pvals = {}, {}
    for n in F.FEATURES:
        sub = [e for e in rows if not math.isnan(e[f"Z_{n}"])]
        if len(sub) < 20:
            out[n] = {"N": len(sub), "ESTIMABLE": False}
            continue
        X, names = design(sub, covariates=False, slice_fe=True, extra=[f"Z_{n}"])
        keep = [k for k, nm in enumerate(names) if nm not in ("A", "B", "C")]
        X, names = X[:, keep], [names[k] for k in keep]
        y = np.array([float(e[PRIMARY_OUTCOME]) for e in sub])
        f = F.ols_cr1(X, y, [e["WEEK_BLOCK"] for e in sub])
        c = np.zeros(len(names)); c[names.index(f"Z_{n}")] = 1.0
        out[n] = {"N": len(sub), **F.contrast(f, c)}
        pvals[n] = out[n]["P_TWO_SIDED"]
    adj = F.holm(pvals)
    for n, p in adj.items():
        out[n]["P_HOLM"] = p
    return out


def run_research() -> dict:
    if not (REPO / VALIDATION_REL).exists():
        raise RuntimeError("VALIDATION_NOT_EVALUATED: the validation result must exist first")
    dsg, v0_digests, ident = _common("RESEARCH")
    vrep = json.loads((REPO / VALIDATION_REL).read_text())
    pins = _pinned()
    eps, inputs, meta = [], {}, {}
    for s in PANEL:
        r = symbol_pipeline(s, pins, v0_digests, with_features_inputs=True)
        eps += r["EPISODES"]
        inputs[s] = r["FEATURE_INPUTS"]
        meta[s] = r["META"].get("OI")
    val_rows = sorted([e for e in eps if e["SLICE"] == "VALIDATION"], key=lambda e: (e["SYMBOL"], e["DECISION_TIME_MS"]))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(val_rows[0].keys()), lineterminator="\n")
    w.writeheader()
    for e in val_rows:
        w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in e.items()})
    if hashlib.sha256(buf.getvalue().encode()).hexdigest() != vrep["VALIDATION_EPISODES_SHA256"]:
        raise RuntimeError("VALIDATION_EPISODES_NOT_REPRODUCED")
    market_close = {s: F.close_by_decision_time(inputs[s]["bars"]) for s in PANEL}
    for e in eps:
        fi = inputs[e["SYMBOL"]]
        e.update(F.episode_features(fi["bars"], fi["ind"], fi["ema168"], fi["book_imb"], fi["oi"], market_close, e))
        e["DEEPER_STATE_FLOW_OI"] = F.deeper_state_flow_oi(e)
        e["YEAR"] = e["DECISION_TIME_UTC"][:4]
    standardized(eps, F.FEATURES)
    pooled = {o: arm_model(eps, o, slice_fe=True) for o in OUTCOMES}
    diff = {}
    for o in ("Y1_48H", "NET_R1_48H", "FWD_R_48H"):
        rows = [e for e in eps if e.get(o) is not None]
        X, names = design(rows, slice_fe=True)
        v = np.array([e["SLICE"] == "VALIDATION" for e in rows], dtype=float)
        arms = np.array([e["ARM"] for e in rows])
        X = np.column_stack([X, v * (arms == "A"), v * (arms == "B"), v * (arms == "C")])
        names = names + ["VxA", "VxB", "VxC"]
        f = F.ols_cr1(X, np.array([float(e[o]) for e in rows]), [e["WEEK_BLOCK"] for e in rows])
        c_ab = np.zeros(len(names)); c_ab[names.index("VxA")], c_ab[names.index("VxB")] = 1, -1
        c_int = c_ab.copy(); c_int[names.index("VxC")] = -1
        diff[o] = {"VALIDATION_MINUS_DISCOVERY_A_MINUS_B": F.contrast(f, c_ab),
                   "VALIDATION_MINUS_DISCOVERY_INTERACTION": F.contrast(f, c_int)}
    by_year = {y: {o: arm_model([e for e in eps if e["YEAR"] == y], o) for o in ("Y1_48H", "NET_R1_48H")}
               for y in sorted({e["YEAR"] for e in eps})}
    by_symbol = {s: {o: arm_model([e for e in eps if e["SYMBOL"] == s], o, symbol_fe=False, slice_fe=True)
                     for o in ("Y1_48H", "NET_R1_48H")} for s in PANEL}
    het = {}
    for name, group in (("YEARS", by_year), ("SYMBOLS", by_symbol)):
        for key in ("A_MINUS_B", "INTERACTION"):
            het[f"{name}_{key}"] = F.heterogeneity_q([(v["Y1_48H"][key]["ESTIMATE"], v["Y1_48H"][key]["SE_CR1"])
                                                      for v in group.values() if v["Y1_48H"].get("ESTIMABLE")])
    smd = {}
    for scope in ("DISCOVERY", "VALIDATION", "POOLED"):
        rows = eps if scope == "POOLED" else [e for e in eps if e["SLICE"] == scope]
        smd[scope] = {n: {"A_VS_B": F.smd([e[n] for e in rows if e["ARM"] == "A"], [e[n] for e in rows if e["ARM"] == "B"]),
                          "MISSING_SHARE": float(np.mean([math.isnan(e[n]) for e in rows]))} for n in F.FEATURES}
    report = {
        "REPORT": "DIVERGENCE_FULL_HISTORY_RESEARCH_V0_RESEARCH", **ident,
        "LABEL": "POOLED FULL HISTORY + EXPLORATORY MECHANISM ANALYSIS; never independent replication or confirmation",
        "VALIDATION_RESULT_SHA256": hashlib.sha256((REPO / VALIDATION_REL).read_bytes()).hexdigest(),
        "POOLED_MODELS": pooled, "SLICE_DIFFERENCE": diff,
        "BY_YEAR": by_year, "BY_SYMBOL_POOLED": by_symbol, "HETEROGENEITY": het,
        "POOLED_ARM_SUMMARY": arm_summary(eps),
        "FEATURE_SMD_AND_MISSINGNESS": smd,
        "WITHIN_SUPPORT_MODELS": within_support_models(eps),
        "FAILURE_STATES_WITHIN_A": failure_states(eps, "A"),
        "FAILURE_STATES_WITHIN_B": failure_states(eps, "B"),
        "OI_META": meta,
        "E1_INTERVAL_TOUCHED": False, "PROSPECTIVE_ACTIVATED": False, "SEED0003_CREATED": False,
        "RUNNER_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (REPO / RESEARCH_REL).write_text(json.dumps(report, indent=1, sort_keys=True, default=_jsonable) + "\n")
    return report


def main(argv: list[str]) -> int:
    cmd = argv[:1]
    if cmd == ["acquire"]:
        m = acquire()
        print(json.dumps({"OBJECT_COUNTS": m["OBJECT_COUNTS"], "MISSING": len(m["MISSING_IN_ARCHIVE"])}, sort_keys=True))
        return 0
    if cmd == ["validation"]:
        r = run_validation()
        print(json.dumps({"VALIDATION_LABELS": r["VALIDATION_LABELS"]}))
        return 0
    if cmd == ["research"]:
        run_research()
        print(json.dumps({"RESEARCH": RESEARCH_REL}))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
