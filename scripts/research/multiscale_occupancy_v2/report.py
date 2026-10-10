"""Assemble the V2 synthetic adequacy record from the study outputs (stage1, stage2, validate, calibrate, v1repro).

    python -m scripts.research.multiscale_occupancy_v2.report DIR OUT.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import constants as K


def assemble(d: Path) -> dict:
    load = lambda n: json.loads((d / n).read_text())
    s1, s2 = load("stage1.json"), load("stage2.json")
    return {"unit": K.UNIT, "stage": K.STAGE, "protocol_commit": "6e1bc6a4",
            "market_outcomes_read": "none (synthetic outcomes on real features only)",
            "calibration": load("calibrate.json"), "v1_reproduction": load("v1repro.json"),
            "stage1": {"results": s1["results"], "selection": s1["selection"], "seconds": s1["seconds"]},
            "stage2": {k: s2[k] for k in ("selected", "results", "adequacy", "adequacy_cw_option", "mde80", "per_rep",
                                         "seconds")},
            "validation": load("validate.json")}


def main() -> None:
    out = assemble(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
