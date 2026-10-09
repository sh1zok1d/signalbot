"""Load settled funding and the already aggregated 5-minute price path.

Outcome statistics are not computed here. Open interest files are not opened.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import zipfile
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .model import absolute_excursion, adverse_long, funding_state

ROOT = Path(__file__).resolve().parents[3]
FUNDING_DIR = (
    ROOT
    / "artifacts"
    / "research_data"
    / "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
    / "raw"
    / "funding"
)
UTC = dt.timezone.utc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _verify_zip(path: Path) -> None:
    sidecar = Path(str(path) + ".CHECKSUM")
    recorded = sidecar.read_text(encoding="utf-8").split()[0]
    if _sha256(path) != recorded:
        raise SystemExit(f"CHECKSUM_MISMATCH {path.name}")


def load_funding() -> tuple[np.ndarray, np.ndarray]:
    zips = sorted(FUNDING_DIR.glob("BTCUSDT-fundingRate-*.zip"))
    if len(zips) != 52:
        raise SystemExit(f"FUNDING_ZIP_COUNT {len(zips)}")
    times: list[int] = []
    rates: list[float] = []
    for path in zips:
        _verify_zip(path)
        with zipfile.ZipFile(path) as archive:
            name = archive.namelist()[0]
            text = archive.read(name).decode().splitlines()
        for row in csv.DictReader(text):
            if int(row["funding_interval_hours"]) != 8:
                raise SystemExit("FUNDING_INTERVAL_NOT_8H")
            calc = int(row["calc_time"])
            if calc >= K.SURFACE_END_MS:
                raise SystemExit("FUNDING_TOUCHES_2025")
            times.append(calc)
            rates.append(float(row["last_funding_rate"]))
    calc_ms = np.asarray(times, dtype=np.int64)
    rate = np.asarray(rates, dtype=np.float64)
    if calc_ms.size != K.FUNDING_N:
        raise SystemExit(f"SAMPLE_DOES_NOT_MATCH_AUDIT n={calc_ms.size}")
    if int(calc_ms[0]) != K.FIRST_CALC_MS or int(calc_ms[-1]) != K.LAST_CALC_MS:
        raise SystemExit("SAMPLE_DOES_NOT_MATCH_AUDIT bounds")
    if not np.all(calc_ms[1:] > calc_ms[:-1]):
        raise SystemExit("FUNDING_TIMES_NOT_STRICTLY_INCREASING")
    residual = calc_ms % K.HOUR_MS
    if int(residual.min()) < 0 or int(residual.max()) > K.HOUR_RESIDUAL_MAX_MS:
        raise SystemExit("FUNDING_HOUR_RESIDUAL_OUTSIDE_AUDIT")
    hour = calc_ms - residual
    if np.unique(hour).size != hour.size:
        raise SystemExit("FUNDING_HOUR_COLLISION")
    expected = np.arange(hour[0], hour[-1] + 1, 8 * K.HOUR_MS, dtype=np.int64)
    if expected.size != hour.size or not np.array_equal(expected, hour):
        raise SystemExit("FUNDING_8H_GRID_GAP")
    return hour, rate


def math_sqrt_sumsq(rets: np.ndarray) -> float:
    return float(np.sqrt(np.dot(rets, rets)))


def _window(bars, start_open: int, n_bars: int):
    i0 = bars.index_at_open(start_open)
    i1 = i0 + n_bars
    if i0 < 0 or i1 > bars.n:
        return None
    if int(bars.times[i0]) != start_open:
        return None
    if int(bars.times[i1 - 1]) >= K.SURFACE_END_MS:
        return None
    return i0, i1


def build_frame() -> dict:
    hour, rate = load_funding()
    bars = load_discovery_bars()
    if int(bars.times[0]) < 0 or int(bars.times[-1]) >= K.SURFACE_END_MS:
        raise SystemExit("PRICE_PANEL_LEAVES_LEGAL_SURFACE")
    state = funding_state(rate)
    kept = {
        "t": [],
        "rate": [],
        "state": [],
        "rv": [],
        "adverse_8h": [],
        "adverse_1h": [],
        "adverse_4h": [],
        "abs_excursion_8h": [],
        "year": [],
        "week": [],
    }
    dropped = {"state_undefined": 0, "path": 0, "rv": 0}
    for i, t in enumerate(hour.tolist()):
        if not np.isfinite(state[i]):
            dropped["state_undefined"] += 1
            continue
        p0_open = int(t) - K.BAR_MS
        p0_slice = _window(bars, p0_open, 1)
        future = _window(bars, int(t), K.PRIMARY_BARS)
        rv_open = int(t) - K.RV_RETURNS * K.BAR_MS - K.BAR_MS
        rv_slice = _window(bars, rv_open, K.RV_RETURNS + 1)
        if p0_slice is None or future is None or rv_slice is None:
            dropped["path"] += 1
            continue
        p0 = float(bars.close[p0_slice[0]])
        closes = bars.close[rv_slice[0]:rv_slice[1]]
        lows = bars.low[future[0]:future[1]]
        highs = bars.high[future[0]:future[1]]
        if not np.all(np.isfinite(closes)) or np.any(closes <= 0.0):
            dropped["rv"] += 1
            continue
        rets = np.log(closes[1:] / closes[:-1])
        if rets.size != K.RV_RETURNS or not np.all(np.isfinite(rets)):
            dropped["rv"] += 1
            continue
        try:
            adverse = adverse_long(p0, lows)
            short = adverse_long(p0, lows[:K.SECONDARY_BARS[0]])
            mid = adverse_long(p0, lows[:K.SECONDARY_BARS[1]])
            excursion = absolute_excursion(p0, lows, highs)
        except RuntimeError:
            dropped["path"] += 1
            continue
        stamp = dt.datetime.fromtimestamp(int(t) / 1000.0, tz=UTC)
        iso = stamp.isocalendar()
        kept["t"].append(int(t))
        kept["rate"].append(float(rate[i]))
        kept["state"].append(float(state[i]))
        kept["rv"].append(float(math_sqrt_sumsq(rets)))
        kept["adverse_8h"].append(adverse)
        kept["adverse_1h"].append(short)
        kept["adverse_4h"].append(mid)
        kept["abs_excursion_8h"].append(excursion)
        kept["year"].append(stamp.year)
        kept["week"].append((int(iso[0]), int(iso[1])))
    frame = {key: np.asarray(value) if key != "week" else value for key, value in kept.items()}
    frame["dropped"] = dropped
    frame["funding_n"] = int(hour.size)
    return frame
