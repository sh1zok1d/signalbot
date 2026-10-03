"""SEED-0001 outcome-blind feasibility / count pass.

Runs the frozen detector (`seed0001_regular_divergence_lib`) on Binance UM
BTCUSDT and ETHUSDT 1h bars (from 1m klines, 2022-11..2024-12) and daily
`bookDepth` (2023-01-01..2024-12-31), then reports counts, dependence
structure, covariate support, power and the frozen feasibility verdict.

It never computes a future return, +1R/-1R, +2R/-1R, MFE/MAE or any
post-decision price field. A URL that names 2025 or later is rejected before
any network call.

    python -m scripts.research.seed0001_feasibility acquire
    python -m scripts.research.seed0001_feasibility run
"""

from __future__ import annotations

import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import http.client
import io
import json
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

from scripts.research import gv0r02_feasibility_compiler_v1 as compiler_v1
from scripts.research import seed0001_feasibility_lib as F
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
PREREG_REL = "docs/research/SEED0001_REGULAR_DIVERGENCE_PREREG.json"
DATA_ROOT = REPO / "artifacts/research_data/SEED0001_BINANCE_UM_V0"
DATASET_ID = "SEED0001_BINANCE_UM_1H_BOOKDEPTH_V0"
MANIFEST_REL = f"docs/research_data/{DATASET_ID}/DATASET_MANIFEST.json"
REPORT_REL = "docs/research/SEED0001_FEASIBILITY_REPORT.json"
EPISODES_DIR_REL = "docs/research/seed0001"
ARCHIVE = "https://data.binance.vision/data/futures/um"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
PRIMARY = "BTCUSDT"
KLINE_MONTHS = [f"{y}-{m:02d}" for y, m in [(2022, 11), (2022, 12)] + [(y, m) for y in (2023, 2024) for m in range(1, 13)]]
BOOK_FIRST_DAY = dt.date(2023, 1, 1)
BOOK_LAST_DAY = dt.date(2024, 12, 31)
DECISION_START_MS = 1_672_531_200_000      # 2023-01-01T00:00:00Z
DECISION_LAST_MS = 1_735_344_000_000       # 2024-12-28T00:00:00Z
PIT_AUDIT_PER_SYMBOL = 30
_PERIOD = re.compile(r"(20\d{2})-(\d{2})(?:-(\d{2}))?")


class ProtectedAccessError(RuntimeError):
    pass


def assert_url_allowed(url: str) -> None:
    periods = _PERIOD.findall(url)
    if not periods:
        raise ProtectedAccessError(f"URL_HAS_NO_PERIOD:{url}")
    for year, _month, _day in periods:
        if int(year) >= 2025:
            raise ProtectedAccessError(f"PROTECTED_URL_REJECTED_BEFORE_FETCH:{url}")
    if "2025" in url or "2026" in url:
        raise ProtectedAccessError(f"PROTECTED_URL_REJECTED_BEFORE_FETCH:{url}")


def book_days() -> list[str]:
    n = (BOOK_LAST_DAY - BOOK_FIRST_DAY).days + 1
    return [(BOOK_FIRST_DAY + dt.timedelta(days=k)).isoformat() for k in range(n)]


def kline_url(symbol: str, ym: str) -> str:
    return f"{ARCHIVE}/monthly/klines/{symbol}/1m/{symbol}-1m-{ym}.zip"


def book_url(symbol: str, day: str) -> str:
    return f"{ARCHIVE}/daily/bookDepth/{symbol}/{symbol}-bookDepth-{day}.zip"


def pinned_kline_sha256() -> dict[str, dict[str, str]]:
    c012 = json.loads((REPO / "docs/research_data/C012_DISCOVERY_BTC_1M_V0/MANIFEST.json").read_text())
    btc = {m["MONTH"]: m["SOURCE_ZIP_SHA256"] for m in c012["MONTHS"]}
    inv = json.loads((REPO / "docs/research_data/CORE_ETH_BINANCE_V0/SOURCE_INVENTORY.json").read_text())
    eth = {r["source_period"]: r["checksum_sha256"] for r in inv["checksum_records"] if r["archive_class"] == "monthly"}
    return {"BTCUSDT": {m: btc[m] for m in KLINE_MONTHS}, "ETHUSDT": {m: eth[m] for m in KLINE_MONTHS}}


# ------------------------------------------------------------------ acquisition

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


def _acquire_one(kind: str, symbol: str, period: str, pinned: str | None) -> dict:
    url = kline_url(symbol, period) if kind == "KLINES_1M" else book_url(symbol, period)
    path = DATA_ROOT / "raw" / kind / symbol / url.rsplit("/", 1)[1]
    row = {"KIND": kind, "SYMBOL": symbol, "PERIOD": period, "URL": url}
    status, body = _get(url + ".CHECKSUM")
    if status == 404:
        return {**row, "STATUS": "MISSING_IN_ARCHIVE"}
    published = body.decode().split()[0]
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == published:
        data = path.read_bytes()
    else:
        status, data = _get(url)
        if status == 404:
            return {**row, "STATUS": "MISSING_IN_ARCHIVE", "CHECKSUM_PUBLISHED": published}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    if digest != published:
        raise RuntimeError(f"CHECKSUM_MISMATCH:{url}")
    if pinned is not None and digest != pinned:
        raise RuntimeError(f"PINNED_SHA256_MISMATCH:{url}")
    return {**row, "STATUS": "VERIFIED", "SHA256": digest, "BYTES": len(data),
            "PINNED_SHA256_MATCH": None if pinned is None else True}


def acquire(workers: int = 8) -> dict:
    pinned = pinned_kline_sha256()
    jobs = [("KLINES_1M", s, m, pinned[s][m]) for s in SYMBOLS for m in KLINE_MONTHS]
    jobs += [("BOOKDEPTH", s, d, None) for s in SYMBOLS for d in book_days()]
    for kind, symbol, period, _ in jobs:  # every URL is checked before the first fetch
        assert_url_allowed(kline_url(symbol, period) if kind == "KLINES_1M" else book_url(symbol, period))
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda j: _acquire_one(*j), jobs))
    rows.sort(key=lambda r: (r["KIND"], r["SYMBOL"], r["PERIOD"]))
    if any(r["KIND"] == "KLINES_1M" and r["STATUS"] != "VERIFIED" for r in rows):
        raise RuntimeError("KLINE_MONTH_MISSING")
    body = {
        "DATASET_ID": DATASET_ID,
        "PREREG": PREREG_REL,
        "MARKET": "USD_M_FUTURES",
        "INSTRUMENTS": list(SYMBOLS),
        "KLINE_MONTHS": [KLINE_MONTHS[0], KLINE_MONTHS[-1]],
        "BOOKDEPTH_DAYS": [BOOK_FIRST_DAY.isoformat(), BOOK_LAST_DAY.isoformat()],
        "KLINES_PINNED_AGAINST": {"BTCUSDT": "docs/research_data/C012_DISCOVERY_BTC_1M_V0/MANIFEST.json",
                                  "ETHUSDT": "docs/research_data/CORE_ETH_BINANCE_V0/SOURCE_INVENTORY.json"},
        "OBJECT_COUNTS": dict(Counter(f"{r['KIND']}|{r['SYMBOL']}|{r['STATUS']}" for r in rows)),
        "MISSING_IN_ARCHIVE": [f"{r['SYMBOL']}|{r['PERIOD']}" for r in rows if r["STATUS"] != "VERIFIED"],
        "OBJECTS": [{k: r[k] for k in ("KIND", "SYMBOL", "PERIOD", "STATUS", "SHA256", "BYTES") if k in r} for r in rows],
        "PROTECTED_2025_BYTES_FETCHED": False,
        "PROTECTED_2026_BYTES_FETCHED": False,
        "TIMESTAMP_SEMANTICS": ("klines: open_time_ms is the UTC open of the 1m bar. bookDepth: timestamp is the UTC "
                                "snapshot time; percentage +-5 notional is cumulative within 5% of price."),
    }
    body["CANONICAL_MANIFEST_DIGEST"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    out = REPO / MANIFEST_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    return body


# ---------------------------------------------------------------------- parsing

def _read_zip_csv(path: Path) -> bytes:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != 1:
            raise RuntimeError(f"ZIP_MEMBERS:{path.name}:{names}")
        return z.read(names[0])


def load_bars(symbol: str) -> dict:
    frames = []
    for ym in KLINE_MONTHS:
        raw = _read_zip_csv(DATA_ROOT / "raw/KLINES_1M" / symbol / f"{symbol}-1m-{ym}.zip")
        df = pd.read_csv(io.BytesIO(raw), header=None, dtype=str)
        if not df.iloc[0, 0].isdigit():
            df = df.iloc[1:]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    t = df[0].astype(np.int64).to_numpy()
    cols = [df[k].astype(float).to_numpy() for k in (1, 2, 3, 4, 5, 9)]
    if t[-1] >= L.PROTECTED_START_MS:
        raise ProtectedAccessError("kline row inside the protected surface")
    bars = L.hourly_bars(t, *cols)
    bars["source_minutes"] = int(t.size)
    return bars


def load_book(symbol: str, grid_ms: np.ndarray) -> tuple[dict, dict]:
    ts_all, bid_all, ask_all = [], [], []
    stats = {"DAYS_PRESENT": 0, "DAYS_MISSING": [], "DUPLICATE_ROWS_DROPPED": 0, "SNAPSHOTS_WITHOUT_BOTH_SIDES": 0}
    for day in book_days():
        path = DATA_ROOT / "raw/BOOKDEPTH" / symbol / f"{symbol}-bookDepth-{day}.zip"
        if not path.exists():
            stats["DAYS_MISSING"].append(day)
            continue
        stats["DAYS_PRESENT"] += 1
        df = pd.read_csv(io.BytesIO(_read_zip_csv(path)), usecols=["timestamp", "percentage", "notional"])
        df["percentage"] = df["percentage"].astype(float)
        df = df[df["percentage"].isin([-float(L.BOOK_BAND_PCT), float(L.BOOK_BAND_PCT)])]
        before = len(df)
        df = df.drop_duplicates(subset=["timestamp", "percentage"], keep="first")
        stats["DUPLICATE_ROWS_DROPPED"] += before - len(df)
        wide = df.pivot(index="timestamp", columns="percentage", values="notional")
        both = wide.dropna()
        stats["SNAPSHOTS_WITHOUT_BOTH_SIDES"] += len(wide) - len(both)
        ts = pd.to_datetime(both.index, format="%Y-%m-%d %H:%M:%S", utc=True).asi8 // 1_000_000
        ts_all.append(ts)
        bid_all.append(both[-float(L.BOOK_BAND_PCT)].to_numpy(dtype=float))
        ask_all.append(both[float(L.BOOK_BAND_PCT)].to_numpy(dtype=float))
    ts = np.concatenate(ts_all)
    order = np.argsort(ts, kind="stable")
    if ts.max() >= L.PROTECTED_START_MS:
        raise ProtectedAccessError("book snapshot inside the protected surface")
    book = L.book_hourly_imbalance(ts[order], np.concatenate(bid_all)[order], np.concatenate(ask_all)[order], grid_ms)
    in_range = grid_ms >= DECISION_START_MS
    stats["HOURS_FROM_2023"] = int(in_range.sum())
    stats["HOURS_WITH_VALUE_FROM_2023"] = int((~np.isnan(book["imbalance"][in_range])).sum())
    stats["MEDIAN_SNAPSHOTS_PER_HOUR"] = float(np.median(book["snapshots"][in_range]))
    return book, stats


# ------------------------------------------------------------------- analysis

def pit_audit(bars: dict, book: dict, episodes: list[dict]) -> dict:
    """Re-run detection on data that end at T for a deterministic sample."""
    if not episodes:
        return {"CHECKED": 0, "IDENTICAL": 0}
    step = max(1, len(episodes) // PIT_AUDIT_PER_SYMBOL)
    sample = episodes[::step][:PIT_AUDIT_PER_SYMBOL]
    same = 0
    for ep in sample:
        keep = bars["open_time_ms"] + L.BAR_MS <= ep["DECISION_TIME_MS"]
        tb = {k: v[keep] for k, v in bars.items() if isinstance(v, np.ndarray)}
        tk = {"open_time_ms": book["open_time_ms"][keep], "imbalance": book["imbalance"][keep]}
        again = L.detect(tb, tk, decision_start_ms=ep["DECISION_TIME_MS"], decision_last_ms=ep["DECISION_TIME_MS"])
        same += again["EPISODES"] == [ep]
    return {"CHECKED": len(sample), "IDENTICAL": same}


def family_structure(episodes: list[dict]) -> dict:
    n = len(episodes)
    if not n:
        return {}
    share = lambda key: sum(bool(e[key]) for e in episodes) / n  # noqa: E731
    return {
        "RSI_FAMILY_SHARE": share("RSI_FAMILY"), "MACD_FAMILY_SHARE": share("MACD_FAMILY"),
        "CVD_FAMILY_SHARE": share("CVD_FAMILY"), "SUPPORT_SHARE": share("SUPPORT"),
        "DIVERGENCE_SHARE": share("DIVERGENCE"),
        "DIV_COUNT": dict(sorted(Counter(e["DIV_COUNT"] for e in episodes).items())),
    }


def symbol_pass(symbol: str) -> dict:
    bars = load_bars(symbol)
    book, book_stats = load_book(symbol, bars["open_time_ms"])
    out = L.detect(bars, book, decision_start_ms=DECISION_START_MS, decision_last_ms=DECISION_LAST_MS)
    episodes = out["EPISODES"]
    audit = pit_audit(bars, book, episodes)
    for ep in episodes:
        ep["SYMBOL"] = symbol
        ep["EPISODE_ID"] = f"{symbol}-{ep['DECISION_TIME_UTC']}"
    L.assert_outcome_blind(episodes)
    chains = L.overlap_chains([e["DECISION_TIME_MS"] for e in episodes])
    for ep, c in zip(episodes, chains):
        ep["CHAIN_48H"] = int(c)
    arms = [e["ARM"] for e in episodes]
    weeks = [e["WEEK_BLOCK"] for e in episodes]
    layout = F.layout_stats(episodes, chains)
    support = F.covariate_support(episodes) if episodes else None
    power = F.power_table(arms, weeks)
    het = F.heterogeneity_assessability(episodes)
    prospective = {}
    for stop in (F.PROSPECTIVE_STOP_A, F.PROSPECTIVE_MIN_A):
        pre = F.prospective_layout(episodes, stop)
        if pre is None:
            prospective[f"A_{stop}"] = {"LAYOUT": None}
            continue
        p_arms, p_weeks = pre
        prospective[f"A_{stop}"] = {"LAYOUT_EPISODES": dict(sorted(Counter(p_arms).items())),
                                    "WEEK_CLUSTERS": len(set(p_weeks)),
                                    "ONE_SIDED_POWER": F.power_table(p_arms, p_weeks, one_sided=True)}
    rows = L.episode_digest_rows(episodes, symbol)
    return {
        "SYMBOL": symbol,
        "BARS": {"HOURS": int(bars["open_time_ms"].size), "INCOMPLETE_HOURS": int((~bars["complete"]).sum()),
                 "SOURCE_MINUTES": bars["source_minutes"], "SEGMENTS": len(L.segments(bars["complete"]))},
        "BOOK": book_stats,
        "FUNNEL": out["FUNNEL"],
        "LAYOUT": layout,
        "FAMILY_STRUCTURE": family_structure(episodes),
        "COVARIATE_SUPPORT": support,
        "POWER_TWO_SIDED_HOLM_CONJUNCTION": power,
        "HETEROGENEITY_ASSESSABILITY": het,
        "PROSPECTIVE_PLANNING": prospective,
        "PIT_TRUNCATION_AUDIT": audit,
        "EPISODE_DIGEST": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
        "_EPISODES": episodes,
    }


def attainable_alpha(layout: dict) -> dict:
    g = layout["WEEK_CLUSTERS"]["COUNT"]
    df = max(g - 1, 1)
    from scipy import stats
    return {
        "HOLM_THRESHOLDS_TWO_SIDED": [F.ALPHA_FAMILY / 2, F.ALPHA_FAMILY],
        "REFERENCE": "t with G - 1 degrees of freedom (continuous; no discrete p floor)",
        "WEEK_CLUSTERS_G": g,
        "T_CRITICAL_STEP_1": float(stats.t.ppf(1 - F.ALPHA_FAMILY / 4, df)),
        "T_CRITICAL_STEP_2": float(stats.t.ppf(1 - F.ALPHA_FAMILY / 2, df)),
        "ARM_WEEK_CLUSTERS": {a: layout["BY_ARM"][a]["WEEK_CLUSTERS"] for a in ("A", "B", "C", "D")},
        "ALPHA_ATTAINABLE": all(layout["BY_ARM"][a]["WEEK_CLUSTERS"] >= 2 for a in ("A", "B", "C")),
    }


def write_episodes(result: dict) -> None:
    eps = result["_EPISODES"]
    if not eps:
        return
    out = REPO / EPISODES_DIR_REL / f"EPISODES_{result['SYMBOL']}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(eps[0].keys())
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for ep in eps:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in ep.items()})


def run() -> dict:
    prereg_bytes = (REPO / PREREG_REL).read_bytes()
    prereg = json.loads(prereg_bytes)
    ident = prereg["CODE_IDENTITY"]
    for key in ("DETECTOR_LIB", "FEASIBILITY_LIB"):
        actual = hashlib.sha256((REPO / ident[f"{key}_PATH"]).read_bytes()).hexdigest()
        if actual != ident[f"{key}_SHA256"]:
            raise RuntimeError(f"CODE_IDENTITY_MISMATCH:{key}")
    manifest = json.loads((REPO / MANIFEST_REL).read_text())
    results = {s: symbol_pass(s) for s in SYMBOLS}
    btc = results[PRIMARY]
    a = btc["LAYOUT"]["BY_ARM"]["A"]
    stress = btc["POWER_TWO_SIDED_HOLM_CONJUNCTION"]["STRESS"]["POWER_BY_EFFECT"][f"{F.MIN_MEANINGFUL_EFFECT:.3f}"]
    max_smd = (btc["COVARIATE_SUPPORT"] or {}).get("MAX_ABS_SMD")
    verdict = F.verdict(a["EPISODES"], a["DISTINCT_DECISION_DATES"], max_smd, stress)
    decl = prereg["COMPILER_V1_DECLARATION"]
    compiler = {
        "COMPILER_SCHEMA_VERSION": compiler_v1.COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": compiler_v1.COMPILER_POLICY_VERSION,
        "DEFINITION_BLOCKERS": compiler_v1._definition_checks(decl),
        "PROTECTED_OVERLAP": compiler_v1._protected_overlap(decl),
        "PASS_D_INFERENCE_CLASS": "NOT_APPLICABLE: no model-based cluster-robust class in the V0 enum; power computed directly",
    }
    for r in results.values():
        r["ATTAINABLE_ALPHA"] = attainable_alpha(r["LAYOUT"])
        write_episodes(r)
    report = {
        "REPORT": "SEED0001_OUTCOME_BLIND_FEASIBILITY_V1",
        "PREREG_PATH": PREREG_REL,
        "PREREG_SHA256": hashlib.sha256(prereg_bytes).hexdigest(),
        "TEST_FAMILY_ID": prereg["TEST_FAMILY_ID"],
        "DATASET_ID": DATASET_ID,
        "DATASET_MANIFEST_DIGEST": manifest["CANONICAL_MANIFEST_DIGEST"],
        "RUNNER_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "DETECTOR_LIB_SHA256": ident["DETECTOR_LIB_SHA256"],
        "FEASIBILITY_LIB_SHA256": ident["FEASIBILITY_LIB_SHA256"],
        "PYTHON": sys.version.split()[0], "NUMPY": np.__version__, "PANDAS": pd.__version__,
        "DECISION_WINDOW_UTC": [L.iso_utc(DECISION_START_MS), L.iso_utc(DECISION_LAST_MS)],
        "SYMBOLS": {s: {k: v for k, v in r.items() if not k.startswith("_")} for s, r in results.items()},
        "COMPILER_V1": compiler,
        "VERDICT_INPUTS": {"BTC_A_EPISODES": a["EPISODES"], "BTC_A_DISTINCT_DATES": a["DISTINCT_DECISION_DATES"],
                           "BTC_MAX_ABS_SMD": max_smd, "BTC_STRESS_POWER_AT_MIN_EFFECT": stress},
        "VERDICT": verdict,
        "ETH_ROLE": "robustness only; reported, never pooled, cannot change the verdict",
        "OUTCOMES_COMPUTED": False,
        "FORBIDDEN_FIELDS_COMPUTED": [],
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "OUTCOME_OPENING_AUTHORIZED": False,
    }
    (REPO / REPORT_REL).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return report


def main(argv: list[str]) -> int:
    if argv[:1] == ["acquire"]:
        m = acquire()
        print(json.dumps({"OBJECT_COUNTS": m["OBJECT_COUNTS"], "MISSING": len(m["MISSING_IN_ARCHIVE"]),
                          "DIGEST": m["CANONICAL_MANIFEST_DIGEST"]}, sort_keys=True))
        return 0
    if argv[:1] == ["run"]:
        r = run()
        print(json.dumps({"VERDICT": r["VERDICT"], **r["VERDICT_INPUTS"]}, sort_keys=True))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
