"""Candidate C table: built from CAL rows only, sealed once, never modified (Protocol V2 A6, V3 C4).

seal_c_table is the ONLY writer of the C-table artifact and is called only by the CAL phase.
The EVAL phase imports load_sealed and factor only (tested by AST in the test suite).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from scripts.research.compiler_v3_estimator_calibration import cells as C

C_TABLE_NAME = "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_C_TABLE_V1.json"
QUANTILE = 0.99


def build_c_table(cal_rows: list[dict], cal_cells: list[dict]) -> dict:
    """cal_rows: slim CAL rows (C, S, VA, T, E). Pool per (class, n) over MUST cells."""
    by_cell = {c["CELL_ID"]: c for c in cal_cells}
    pools: dict[tuple[str, int], list[float]] = {}
    ids: dict[tuple[str, int], set] = {}
    for r in cal_rows:
        cell = by_cell[r["C"]]
        if r.get("E"):
            raise RuntimeError(f"CAL row with error cannot enter the pool: {r['C']} {r['S']}")
        key = (cell["CLASS"], int(cell["N"]))
        pools.setdefault(key, []).append(r["T"] / r["VA"])
        ids.setdefault(key, set()).add(cell["CELL_ID"])
    table = {}
    classes = sorted({c["CLASS"] for c in cal_cells})
    for klass in classes:
        sizes = sorted({int(c["N"]) for c in cal_cells if c["CLASS"] == klass})   # frozen run: equals cells.CAL_SIZES (checked by the engine)
        raw = {}
        for n in sizes:
            vals = sorted(pools[(klass, n)])
            m = len(vals)
            rank = math.ceil(QUANTILE * m)
            raw[n] = {"M": m, "RANK": rank, "C_RAW": vals[rank - 1],
                      "CAL_CELL_IDS": sorted(ids[(klass, n)]),
                      "CAL_SEED_RANGES": sorted(C.cal_seed_range(by_cell[i]) for i in ids[(klass, n)])}
        running = -math.inf
        for n in reversed(sizes):
            running = max(running, raw[n]["C_RAW"])
            raw[n]["C_ENV"] = running
        table[klass] = {str(n): raw[n] for n in sizes}
    return table


def seal_c_table(out_dir: Path, table: dict, executor_digest: str, input_digests: dict) -> Path:
    """Write the immutable C-table artifact. Refuses to overwrite."""
    path = out_dir / C_TABLE_NAME
    if path.exists():
        raise RuntimeError("C-table already sealed; it may not be rewritten")
    body = {"ARTIFACT": C_TABLE_NAME, "QUANTILE": QUANTILE, "RANK_RULE": "ceil(0.99 * M)", "ENVELOPE": "suffix max over calibrated sizes",
            "TABLE": table, "INPUT_DIGESTS": input_digests, "EXECUTOR_DIGEST": executor_digest}
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return path


def load_sealed(out_dir: Path, expected_sha256: str | None = None) -> dict:
    path = out_dir / C_TABLE_NAME
    if not path.exists():
        raise RuntimeError("EVAL requires a sealed C-table; none exists")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise RuntimeError("sealed C-table digest does not match the execution binding")
    body = json.loads(path.read_text())
    body["_SHA256"] = digest
    return body


def factor(table_body: dict, klass: str, n: int) -> float | None:
    """c_env(class, n_i) with n_i the largest calibrated size <= n; None below the smallest calibrated size."""
    sizes = sorted(int(k) for k in table_body["TABLE"][klass])
    if n < sizes[0]:
        return None
    lower = max(s for s in sizes if s <= n)
    return float(table_body["TABLE"][klass][str(lower)]["C_ENV"])
