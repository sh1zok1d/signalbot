"""One-shot held-out read (design §5). Planning is outcome-free; loading refuses without a go.

Dry run (no download):  python -m scripts.research.level_race_forecast_v1.heldout --plan 2026-10-16
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from typing import Optional

from beta import history_data as HD

from scripts.research.level_touch_degradation_v1 import constants as K352

from . import constants as K

HELDOUT_START = date(2025, 1, 1)
WARMUP_START = date(2024, 12, 1)          # previous month for the Jan-2025 monthly levels; 24h sigma
OBJECT_GAP = (datetime(2026, 8, 16, tzinfo=timezone.utc), datetime(2026, 8, 26, tzinfo=timezone.utc))
E1 = (datetime(2026, 8, 16, tzinfo=timezone.utc), datetime(2026, 8, 25, 17, 20, tzinfo=timezone.utc))


def _ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


GAP_MS = (_ms(OBJECT_GAP[0]), _ms(OBJECT_GAP[1]))


def plan(freeze_date: date) -> tuple[list, list]:
    """5m kline objects from the product planner (E1-overlapping objects replaced or rejected),
    from the warm-up month to the day before the freeze date. Metrics objects are dropped."""
    planned, rejected = HD.plan_objects(freeze_date, klines_start=WARMUP_START, metrics_start=freeze_date)
    planned = [o for o in planned if o.kind.startswith("klines")]
    rejected = [o for o in rejected if o.kind.startswith("klines")]
    return planned, rejected


def plan_digest(freeze_date: date) -> str:
    """sha256 of the newline-joined planned object URLs (sorted), then 'REFUSED' and the refused ones."""
    import hashlib
    planned, rejected = plan(freeze_date)
    text = "\n".join(sorted(o.url for o in planned)) + "\nREFUSED\n" + "\n".join(sorted(o.url for o in rejected))
    return hashlib.sha256(text.encode()).hexdigest()


def assert_plan_legal(planned: list) -> None:
    for o in planned:
        a, z = o.period_ms
        if a < GAP_MS[1] and GAP_MS[0] < z:
            raise RuntimeError(f"object {o.key} intersects the E1 object gap")
        if HD.url_refusal(o.url) is not None:
            raise RuntimeError(f"object {o.key} refused by the product guard")


def event_span_ok(touch_open_ms: int) -> bool:
    """σ window (j-289 .. j-1), the touch bar and the 4h window (j+1 .. j+48) clear of the gap."""
    a = int(touch_open_ms) - (K352.SCALE_BARS + 1) * K352.BAR_MS
    z = int(touch_open_ms) + (K.WINDOW_BARS + 1) * K352.BAR_MS
    return not (a < GAP_MS[1] and GAP_MS[0] < z)


def event_in_window(touch_open_ms: int, freeze_date: date) -> bool:
    start = _ms(datetime(HELDOUT_START.year, HELDOUT_START.month, HELDOUT_START.day, tzinfo=timezone.utc))
    end = _ms(datetime(freeze_date.year, freeze_date.month, freeze_date.day, tzinfo=timezone.utc))
    close_48 = int(touch_open_ms) + (K.WINDOW_BARS + 1) * K352.BAR_MS
    return start <= int(touch_open_ms) and close_48 <= end


def require_go(go_token: Optional[str]) -> None:
    """The one-shot read runs only with the explicit go of the mini-head / architect, given as
    GO:<first 12 hex of the frozen model file sha256> (beta.level_race.MODEL_FILE_SHA256), and only if
    the model file on disk still has that digest."""
    from beta import level_race as L
    L.load_model()                                   # refuses a model file with another digest
    if go_token != f"GO:{L.MODEL_FILE_SHA256[:12]}":
        raise RuntimeError("held-out read refused: no explicit go for this frozen model")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="freeze date YYYY-MM-DD (exclusive end)")
    a = ap.parse_args()
    fd = date.fromisoformat(a.plan)
    planned, rejected = plan(fd)
    assert_plan_legal(planned)
    for o in planned:
        print("GET", o.url)
    for o in rejected:
        print("REFUSED", o.url, HD.object_protected(o))
    print(f"planned {len(planned)} objects, refused {len(rejected)}; none intersects [2026-08-16, 2026-08-26)")
    print("plan sha256", plan_digest(fd))


if __name__ == "__main__":
    main()


# ---- held-out decision and prequential publication on the live calibrator (F3, #408) ---------------
# One calibrator: beta.level_race_calibration is imported, never re-implemented here. Records use the
# calibrator's outcome names (BREAK / REJECT / NEITHER; generic UP_FIRST in the BREAK slot) and carry
# week, issued_ms, resolved_ms and the raw three-outcome vectors p_m1 (champion), p_g1 (G1@event) and
# p_b0 (raw B0) for level rows, or p_g1 for generic rows.
LANDMARK_CLASS = {"T0": "LEVEL_T0", "T15": "LEVEL_T15"}


def decide_cases(level_records: list) -> dict:
    """§11b / Q6 per landmark, on raw outputs: case A only if the champion beats raw B0 AND raw
    G1@event (week-clustered 95 % interval of the log-loss gain above 0); otherwise case B."""
    from beta import level_race_calibration as LRC
    out = {}
    for lm, cls in LANDMARK_CLASS.items():
        recs = [r for r in level_records if r["cal_class"] == cls]
        a = bool(recs) and LRC.beats(recs, "p_m1", "p_b0") and LRC.beats(recs, "p_m1", "p_g1")
        out[lm] = "A" if a else "B"
    return out


def prequential(level_records: list, generic_records: list, start_ms: int, end_ms: int, cases: dict) -> dict:
    """Adds p_pub (published by the case) and p_fb (fallback model) to every level record. The level
    rows feed the case's raw (A: p_m1, B: p_g1); generic rows feed p_g1. Each calibrator version is
    fitted from prior_for_cases on outcomes resolved before its cutoff; calibrator_at picks the version
    in force at each issue time (the same call live uses)."""
    from beta import level_race_calibration as LRC
    raw_of = {LANDMARK_CLASS[lm]: ("p_m1" if c == "A" else "p_g1") for lm, c in cases.items()}
    case_of = {LANDMARK_CLASS[lm]: c for lm, c in cases.items()}
    feed = [{**r, "p_raw": r[raw_of[r["cal_class"]]]} for r in level_records]
    feed += [{**r, "cal_class": "GENERIC", "p_raw": r["p_g1"]} for r in generic_records]
    priors = LRC.prior_for_cases(cases["T0"], cases["T15"])
    prior_cal = LRC.prior_calibrator(priors, int(start_ms))
    versions = [LRC.fit_calibrator(feed, priors, cutoff_ms=c) for c in LRC.batch_cutoffs(int(start_ms), int(end_ms))]
    out = []
    for r in feed:
        if r["cal_class"] == "GENERIC":
            continue
        cal = LRC.calibrator_at(int(r["issued_ms"]), versions, prior_cal)
        cls_pub = r["cal_class"] if case_of[r["cal_class"]] == "A" else "GENERIC"
        out.append({**r, "p_pub": LRC.apply_calibrator(cal, r["p_raw"], cls_pub).tolist(),
                    "p_fb": LRC.apply_calibrator(cal, r["p_g1"], "GENERIC").tolist(),
                    "calibrator_version": None if cal is None else cal.version})
    return {"records": out, "versions": [v.version for v in versions], "cases": cases}


def gate_report(published: list, cases: dict) -> dict:
    """Per landmark: G0–G3 on the published probabilities, and whether the fallback passes G2 (the
    FALLBACK entry condition). Case B never enters an L3 state (F3 §7.3)."""
    from beta import level_race_calibration as LRC
    out = {}
    for lm, cls in LANDMARK_CLASS.items():
        recs = [r for r in published if r["cal_class"] == cls]
        g = LRC.gates(recs, "p_pub", b0_key="p_b0")
        fb_g2 = LRC.g2_only(recs, "p_fb")
        if cases[lm] == "A":
            state = "L3_HISTORY_BACKED" if g["passed"] else ("FALLBACK" if fb_g2 else "HIST")
        else:
            state = "FALLBACK" if fb_g2 else "HIST"
        out[lm] = {"case": cases[lm], "gates": g, "fallback_g2": fb_g2, "state_at_switch": state}
    return out


# ---- the one-shot evaluator (runs only with the go; design §5, §11b, §11c) -------------------------
def _fetch_verified(url: str) -> bytes:
    import hashlib
    import urllib.request
    if HD.url_refusal(url) is not None:
        raise RuntimeError(f"refused before request: {url}")
    def get(u):
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "signalbot-research/f1"}),
                                    timeout=300) as resp:
            return resp.read()
    body = get(url)
    if HD.checksum_of(get(url + ".CHECKSUM").decode("utf-8", "replace")) != hashlib.sha256(body).hexdigest():
        raise RuntimeError(f"checksum mismatch: {url}")
    return body


def _window_ms(freeze_date: date) -> tuple[int, int, int]:
    w = _ms(datetime(WARMUP_START.year, WARMUP_START.month, WARMUP_START.day, tzinfo=timezone.utc))
    a = _ms(datetime(HELDOUT_START.year, HELDOUT_START.month, HELDOUT_START.day, tzinfo=timezone.utc))
    z = _ms(datetime(freeze_date.year, freeze_date.month, freeze_date.day, tzinfo=timezone.utc))
    return w, a, z


def evaluate_bars(bars, freeze_date: date, model: dict) -> dict:
    """Everything after the bars: events, raws, outcomes, case decision, prequential publication and
    gates. Pure given the bars (tested on synthetic bars)."""
    import numpy as np
    from beta import level_race as L
    from .events import attach_outcomes, first_touches, landmark_rows
    from .generic import generic_rows
    _, a, z = _window_ms(freeze_date)
    in_gap = (bars.times >= GAP_MS[0]) & (bars.times < GAP_MS[1])
    if np.any(np.isfinite(bars.close[in_gap])):
        raise RuntimeError("a bar inside the E1 object gap is present")
    touches = [t for t in first_touches(bars, end_ms=z)
               if event_in_window(int(t["open_ms"]), freeze_date) and event_span_ok(int(t["open_ms"]))]
    rows = attach_outcomes(bars, landmark_rows(bars, touches), touches)
    by_id = {f"{t['episode_id']}:{int(t['j'])}": t for t in touches}
    out_map = {"BEYOND": "BREAK", "BACK": "REJECT", "NEITHER": "NEITHER"}
    level = []
    counts = {"rows": {"T0": 0, "T15": 0}, "ambiguous": {"T0": 0, "T15": 0}, "unusable": 0}
    for r in rows:
        counts["rows"][r["landmark"]] += 1
        if r["outcome"] == "AMBIGUOUS":
            counts["ambiguous"][r["landmark"]] += 1
            continue
        if r["outcome"] is None:
            counts["unusable"] += 1
            continue
        t = by_id[r["event_id"]]
        b0 = (r["b0_beyond"], r["b0_back"], r["b0_neither"])
        kind = t["kind"]
        open_ms = int(t["open_ms"])
        lag = 1 if r["landmark"] == "T0" else 3
        level.append({"cal_class": LANDMARK_CLASS[r["landmark"]], "landmark": r["landmark"], "event_id": r["event_id"],
                      "outcome": out_map[r["outcome"]], "week": int(r["week"]),
                      "issued_ms": open_ms + lag * 300_000, "resolved_ms": open_ms + 49 * 300_000,
                      "p_b0": list(L._floor3(b0)),
                      "p_m1": list(L.two_head(model["M1"], b0, landmark=r["landmark"], kind=kind, sigma=r["sigma"])),
                      "p_g1": list(L.two_head(model["G1"], b0, landmark=r["landmark"], kind=None, sigma=r["sigma"]))})
    generic = []
    for g in generic_rows(bars, with_outcome=True, start_ms=a, end_ms=z):
        oms = int(bars.times[g["i"]])
        if not event_span_ok(oms) or g["outcome"] not in out_map:
            continue
        b0 = (g["b0_beyond"], g["b0_back"], g["b0_neither"])
        generic.append({"outcome": out_map[g["outcome"]], "week": int(g["week"]), "issued_ms": oms + 300_000,
                        "resolved_ms": oms + 49 * 300_000,
                        "p_g1": list(L.two_head(model["G1"], b0, landmark="T0", kind=None, sigma=g["sigma"]))})
    from beta import level_race_calibration as LRC
    raw = {}
    for lm, cls in LANDMARK_CLASS.items():
        recs = [r for r in level if r["cal_class"] == cls]
        raw[lm] = {"n": len(recs),
                   "m1_vs_b0": LRC.paired_log_loss(recs, "p_m1", "p_b0") if recs else None,
                   "m1_vs_g1": LRC.paired_log_loss(recs, "p_m1", "p_g1") if recs else None,
                   "g1_vs_b0": LRC.paired_log_loss(recs, "p_g1", "p_b0") if recs else None}
    cases = decide_cases(level)
    pub = prequential(level, generic, a, z, cases)
    return {"counts": counts, "n_level": len(level), "n_generic": len(generic), "raw": raw, "cases": cases,
            "gates": gate_report(pub["records"], cases), "calibrator_versions": pub["versions"]}


def run(freeze_date: date, go_token: Optional[str]) -> dict:
    """The one-shot held-out read. Refuses without the go; requests only planned, legal objects."""
    import json
    from pathlib import Path
    from beta import level_race as L
    from beta.hist_series import bars_from_rows
    require_go(go_token)
    out = Path(__file__).resolve().parents[3] / "docs/research/LEVEL_RACE_FORECAST_V1_HELDOUT.json"
    if out.exists():
        raise RuntimeError("held-out result already exists: the read is one-shot")
    model = L.load_model()
    planned, rejected = plan(freeze_date)
    assert_plan_legal(planned)
    rows, objects = [], []
    for o in planned:
        body = _fetch_verified(o.url)
        objects.append({"key": o.key, "sha256": __import__("hashlib").sha256(body).hexdigest()})
        rows += HD.drop_protected(HD.parse_klines(body), "open_time_ms")
    w, a, z = _window_ms(freeze_date)
    bars = bars_from_rows(rows, start_ms=w, end_ms=z)
    result = evaluate_bars(bars, freeze_date, model)
    result.update({"freeze_date": freeze_date.isoformat(), "model_file_sha256": L.MODEL_FILE_SHA256,
                   "objects": objects, "refused": [o.key for o in rejected]})
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float) + "\n")
    return result
