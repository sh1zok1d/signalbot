"""Append-only, idempotent replicate checkpoint keyed by (PHASE, CELL_ID, SEED).

A replicate already recorded is never executed again. A duplicate record that is not
bit-identical raises EXECUTION_INTEGRITY_ERROR. Rows are canonical JSON so that
bit-identity is well defined and independent of execution order. Final artifacts are
sorted canonically: phase -> class -> CELL_ID -> SEED.
"""

from __future__ import annotations

import json
from pathlib import Path


class ExecutionIntegrityError(RuntimeError):
    pass


def canonical(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Checkpoint:
    def __init__(self, path: Path):
        self.path = path
        self.index: dict[tuple[str, str, int], str] = {}
        if path.exists():
            with path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    key = (row["PHASE"], row["CELL_ID"], int(row["SEED"]))
                    text = canonical(row)
                    if key in self.index and self.index[key] != text:
                        raise ExecutionIntegrityError(f"conflicting duplicate on resume: {key}")
                    self.index[key] = text
        self._fh = path.open("a")

    def has(self, phase: str, cell_id: str, seed: int) -> bool:
        return (phase, cell_id, int(seed)) in self.index

    def record(self, row: dict) -> None:
        key = (row["PHASE"], row["CELL_ID"], int(row["SEED"]))
        text = canonical(row)
        if key in self.index:
            if self.index[key] != text:
                raise ExecutionIntegrityError(f"EXECUTION_INTEGRITY_ERROR: duplicate not bit-identical: {key}")
            return
        self.index[key] = text
        self._fh.write(text + "\n")
        self._fh.flush()

    def rows(self, phase: str | None = None) -> list[dict]:
        out = [json.loads(t) for (p, _, _), t in self.index.items() if phase is None or p == phase]
        return sorted(out, key=lambda r: (r["PHASE"], r.get("CLASS", ""), r["CELL_ID"], int(r["SEED"])))

    def close(self) -> None:
        self._fh.close()
