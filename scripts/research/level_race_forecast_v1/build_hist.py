"""Run once after the design freeze: python -m scripts.research.level_race_forecast_v1.build_hist

Writes docs/research/LEVEL_RACE_HIST_TABLE_V1.json. Reads CORE_BTC_BINANCE_V0 2020-01..2024-12 only.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.owner_cards_r03 import data as RD

from . import constants as K
from .events import attach_outcomes, early_census, first_touches, landmark_rows
from .hist import build_table

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/LEVEL_RACE_HIST_TABLE_V1.json"


def main() -> None:
    bars = load_discovery_bars()
    touches = first_touches(bars)
    rows = landmark_rows(bars, touches)
    census = early_census(bars, touches)
    rows = attach_outcomes(bars, rows, touches)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    prov = {
        "design_sha": K.DESIGN_SHA,
        "code_commit": commit,
        "surface": "CORE_BTC_BINANCE_V0",
        "dataset_digest": RD.btc_dataset_digest(),
        "bars": {"first_open_ms": int(bars.times[0]), "end_ms": int(bars.end_ms), "n": int(bars.close.shape[0])},
        "first_touches": len(touches),
        "rows": {lm: sum(1 for r in rows if r["landmark"] == lm) for lm in K.LANDMARKS},
        "early_j1_j2_census": census,
        "out_of_corridor_t0": sum(1 for r in rows if r["landmark"] == "T0"
                                  and not (r["p_dn"] < r["position"] < r["p_up"])),
        "years": sorted({r["year"] for r in rows}),
    }
    table = build_table(rows, provenance=prov)
    OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1, sort_keys=False) + "\n")
    print(json.dumps(prov, indent=1))
    print("table_sha256", table["table_sha256"])


if __name__ == "__main__":
    main()
