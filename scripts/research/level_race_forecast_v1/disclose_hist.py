"""Disclosure beside HIST table V1 (no share is recomputed; the table file is not touched).

Per T0 cell: how many scored events had the touch-bar close already outside (P_DN, P_UP).
python -m scripts.research.level_race_forecast_v1.disclose_hist
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from .events import attach_outcomes, first_touches, landmark_rows
from .hist import cell_key, SCORED

REPO = Path(__file__).resolve().parents[3]
TABLE = REPO / "docs/research/LEVEL_RACE_HIST_TABLE_V1.json"
OUT = REPO / "docs/research/LEVEL_RACE_HIST_TABLE_V1_DISCLOSURE.json"


def main() -> None:
    table_bytes = TABLE.read_bytes()
    table = json.loads(table_bytes)
    bars = load_discovery_bars()
    touches = first_touches(bars)
    rows = attach_outcomes(bars, [r for r in landmark_rows(bars, touches) if r["landmark"] == "T0"], touches)
    cells: dict = {}
    for r in rows:
        if r["outcome"] not in SCORED:
            continue
        k = cell_key(r)
        c = cells.setdefault(k, {"n": 0, "outside": 0, "outside_above_p_up": 0, "outside_below_p_dn": 0})
        c["n"] += 1
        if r["position"] >= r["p_up"]:
            c["outside"] += 1
            c["outside_above_p_up"] += 1
        elif r["position"] <= r["p_dn"]:
            c["outside"] += 1
            c["outside_below_p_dn"] += 1
    for k, c in cells.items():
        assert c["n"] == table["cells"][k]["n"], k
        c["outside_share"] = c["outside"] / c["n"] if c["n"] else None
    out = {"table": TABLE.name, "table_file_sha256": hashlib.sha256(table_bytes).hexdigest(),
           "table_sha256": table["table_sha256"],
           "what": "T0 scored events whose touch-bar close is outside (P_DN, P_UP); shares unchanged",
           "t0_cells": dict(sorted(cells.items())),
           "total_outside_scored": sum(c["outside"] for c in cells.values())}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
