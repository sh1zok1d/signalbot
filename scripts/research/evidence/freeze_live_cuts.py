"""Materialize the frozen DH3 state cut points for live matching (research evidence integration).

The DH3 states are quantile states: their cut points were computed on the research surface by the
frozen feature code (`scripts/research/dh3/features.py`, bound by `DH3_PREREG.json`). A live
matcher must use those same numbers, never quantiles recomputed on live data. This script runs the
frozen feature builders unchanged, records every cut the builders compute (the frozen `_q` calls,
in call order), and writes them with their provenance to `config/beta_research_cuts.json`.

No outcome is read: the feature builders never compute one (`features.py` docstring), and this
script does not import `outcomes.py` or the evaluator. As a consistency check it recounts each
cell's rows with the frozen `cell_rows` and compares them with the N recorded in
`DH3_RESULT_DISCOVERY.json` (N + rows dropped for a missing outcome; BTC rows for pooled cards).

python -m scripts.research.evidence.freeze_live_cuts            # writes config/beta_research_cuts.json
python -m scripts.research.evidence.freeze_live_cuts --check    # recompute and compare, write nothing
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.research.dh3 import constants as K
from scripts.research.dh3 import features as FT

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "config/beta_research_cuts.json"
PREREG = REPO / "docs/research/DH3_PREREG.json"
RESULT = REPO / "docs/research/DH3_RESULT_DISCOVERY.json"
VERSION = "BETA_RESEARCH_CUTS_V1"

# The order of the frozen `_q` calls inside each builder (features.py), per symbol where a card loops.
CUT_NAMES = {
    "DH3-P": ["P1_QUIET_RANGE_MAX", "P1_DOI4_MIN", "P2_DOI1_MAX", "P3_CROWD_Z_SHORT_MAX", "P3_CROWD_Z_LONG_MIN"],
    "DH3-L": ["L1_DEPTH_RATIO_MAX", "L2_ASYM_ASK_HEAVY_MAX", "L2_ASYM_BID_HEAVY_MIN", "L3_RECOVERY_MAX"],
    "DH3-O": ["O1_IMPLIED_REALIZED_MIN", "O2_DVOL_JUMP_MIN"],
    "DH3-S": ["S3_LARGE_PRINTS_Q67"],
}
DEFINITIONS = {
    "P1_QUIET_RANGE_MAX": "log((max high - min low) / close) over the 48 bars ending at T: <= cut is a quiet hour",
    "P1_DOI4_MIN": "log(OI_T / OI_T-4h) (metrics snapshot labelled bar j's open, used at bar j's close): >= cut",
    "P2_DOI1_MAX": "log(OI_T / OI_T-1h): <= cut is the deleveraging state",
    "P3_CROWD_Z_SHORT_MAX": "z of count_long_short_ratio vs the previous 720 hourly values (>= 600 finite): <= cut",
    "P3_CROWD_Z_LONG_MIN": "same z: >= cut is the crowd-long state",
    "L1_DEPTH_RATIO_MAX": "(bid1 + ask1 notional at T) / median of the previous 168 hourly values (>= 120): <= cut",
    "L2_ASYM_ASK_HEAVY_MAX": "log(bid1 / ask1) at T: <= cut (comparator arm)",
    "L2_ASYM_BID_HEAVY_MIN": "log(bid1 / ask1) at T: >= cut (state arm)",
    "L3_RECOVERY_MAX": "depth at move end + 30 min / depth 15 min before the move end (DH1 sharp move): <= cut",
    "O1_IMPLIED_REALIZED_MIN": "log((DVOL_T-1h / 100 * sqrt(4/8760)) / (sigma5m_24h * sqrt(48))): >= cut",
    "O2_DVOL_JUMP_MIN": "log(DVOL candle T-1h close / DVOL candle T-2h close): >= cut",
    "S3_LARGE_PRINTS_Q67": "number of perp aggTrades >= 1M USD in a stress hour: > max(cut, 0) is the state",
}


class _Recorder:
    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def __call__(self, values, p):
        v = self.inner(values, p)
        self.calls.append(float(v))
        return v


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(rows: list, hid: str, symbol: str | None = None) -> dict:
    h = K.HYPOTHESIS_BY_ID[hid]
    kept = FT.cell_rows(rows, h)
    if symbol is not None:
        kept = [r for r in kept if r["SYMBOL"] == symbol]
    return {"N": len(kept), "N_STATE": sum(1 for r in kept if r["S"] == 1)}


def build() -> dict:
    result = json.loads(RESULT.read_text())["CELLS"]
    cuts: dict = {}
    checks: dict = {}
    real_q = FT._q
    try:
        # card P (BTC only)
        rec = _Recorder(real_q)
        FT._q = rec
        built = FT.card_p()
        cuts.update(dict(zip(CUT_NAMES["DH3-P"], rec.calls)))
        for hid in ("DH3-P1", "DH3-P2", "DH3-P3"):
            c = _counts(built["ROWS"][hid], hid)
            want = result[hid]["N"] + result[hid]["MISSING_OUTCOME_DROPPED"]
            checks[hid] = {"RECOUNT_N": c["N"], "RECORDED_N_PLUS_DROPPED": want, "MATCH": c["N"] == want,
                           "RECOUNT_N_STATE": c["N_STATE"]}
        # card L and O: BTC only (their quantiles are computed per symbol inside the loop)
        saved = {c: dict(K.SURFACES[c]) for c in ("DH3-L", "DH3-O")}
        try:
            for card in ("DH3-L", "DH3-O"):
                K.SURFACES[card]["SYMBOLS"] = ("BTC",)
                rec = _Recorder(real_q)
                FT._q = rec
                built = FT.card_l() if card == "DH3-L" else FT.card_o()
                cuts.update(dict(zip(CUT_NAMES[card], rec.calls)))
                for hid in [h["ID"] for h in K.HYPOTHESES if h["CARD"] == card]:
                    c = _counts(built["ROWS"][hid], hid, "BTC")
                    want = (result[hid].get("BTC_ONLY") or {}).get("N")
                    dropped = result[hid]["MISSING_OUTCOME_DROPPED"]
                    checks[hid] = {"RECOUNT_N_BTC": c["N"], "RECORDED_BTC_ONLY_N": want,
                                   "MATCH": want is not None and want <= c["N"] <= want + dropped,
                                   "RECOUNT_N_STATE_BTC": c["N_STATE"]}
        finally:
            for card, spec in saved.items():
                K.SURFACES[card].clear()
                K.SURFACES[card].update(spec)
        # card S (BTC only); the stress cut itself is recorded in the aggTrades inventory
        rec = _Recorder(real_q)
        FT._q = rec
        built = FT.card_s()
        cuts.update(dict(zip(CUT_NAMES["DH3-S"], rec.calls)))
        for hid in ("DH3-S1", "DH3-S3"):
            c = _counts(built["ROWS"][hid], hid)
            want = result[hid]["N"] + result[hid]["MISSING_OUTCOME_DROPPED"]
            checks[hid] = {"RECOUNT_N": c["N"], "RECORDED_N_PLUS_DROPPED": want, "MATCH": c["N"] == want,
                           "RECOUNT_N_STATE": c["N_STATE"]}
    finally:
        FT._q = real_q
    inv_s = json.loads((REPO / "docs/research_data/DH3_BINANCE_AGGTRADES_STRESS_V0/SOURCE_INVENTORY.json").read_text())
    stress_cut = float(inv_s["STRESS_RULE"].split(">=")[1].split("(")[0].strip())
    cuts["S_STRESS_HOUR_LOG_RANGE_MIN"] = stress_cut
    DEFINITIONS["S_STRESS_HOUR_LOG_RANGE_MIN"] = "UTC hour perp log range (max high / min low of its 12 5m bars): >= cut"
    datasets = {}
    for name in ("DH3_BINANCE_UM_BTC_METRICS_5M_V0", "DH3_BINANCE_UM_BOOKDEPTH_V0", "DH3_DERIBIT_DVOL_1H_V0",
                 "DH3_BINANCE_AGGTRADES_STRESS_V0"):
        inv = json.loads((REPO / "docs/research_data" / name / "SOURCE_INVENTORY.json").read_text())
        datasets[name] = inv.get("OBJECT_LIST_SHA256") or inv.get("CSV_SHA256") or inv.get("FEATURES_SHA256")
    return {
        "version": VERSION,
        "purpose": "frozen DH3 state cut points for live research-evidence matching; never recomputed on live data",
        "source_code": "scripts/research/dh3/features.py (frozen; bound by DH3_PREREG.json CODE_DIGESTS)",
        "dh3_prereg_sha256": _sha(PREREG),
        "dh3_result_discovery_sha256": _sha(RESULT),
        "datasets": datasets,
        "symbol": "BTC (Binance USD-M BTCUSDT; card L and O cuts are the BTC-specific ones)",
        "cuts": {k: cuts[k] for k in sorted(cuts)},
        "definitions": {k: DEFINITIONS[k] for k in sorted(cuts)},
        "recount_checks": checks,
        "outcomes_read": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    body = build()
    bad = [h for h, c in body["recount_checks"].items() if not c["MATCH"]]
    text = json.dumps(body, indent=2, sort_keys=True) + "\n"
    if args.check:
        same = OUT.exists() and json.loads(OUT.read_text())["cuts"] == body["cuts"]
        print(json.dumps({"cuts_match_committed": same, "recount_mismatch": bad}, indent=2))
        raise SystemExit(0 if same and not bad else 1)
    if bad:
        raise SystemExit(f"recount mismatch for {bad}; cuts not written")
    OUT.write_text(text)
    print(json.dumps({"written": str(OUT.relative_to(REPO)), "cuts": body["cuts"]}, indent=2))


if __name__ == "__main__":
    main()
