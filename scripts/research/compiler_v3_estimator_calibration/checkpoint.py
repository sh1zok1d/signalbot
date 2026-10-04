"""Append-only, idempotent replicate checkpoint keyed by (P, C, S) = (PHASE, CELL_ID, SEED).

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
    """Slim schema (V4 D6): the first line is a HEADER record carrying the executor digest and
    input digests; every other line is a row with keys P (phase), C (CELL_ID), S (seed),
    VA, [VB], T (authoritative truth), E (error or null). A header mismatch on resume is an
    integrity error."""

    def __init__(self, path: Path, header: dict | None = None):
        self.path = path
        self.index: dict[tuple[str, str, int], str] = {}
        self.header = None
        if path.exists() and path.stat().st_size > 0:
            with path.open() as fh:
                for i, line in enumerate(fh):
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if i == 0 and "HEADER" in row:
                        self.header = row["HEADER"]
                        if header is not None and canonical(header) != canonical(self.header):
                            raise ExecutionIntegrityError("EXECUTION_INTEGRITY_ERROR: checkpoint header (executor/binding identity) mismatch")
                        continue
                    key = (row["P"], row["C"], int(row["S"]))
                    text = canonical(row)
                    if key in self.index and self.index[key] != text:
                        raise ExecutionIntegrityError(f"conflicting duplicate on resume: {key}")
                    self.index[key] = text
        self._fh = path.open("a")
        if self.header is None and header is not None:
            self.header = header
            self._fh.write(canonical({"HEADER": header}) + "\n")
            self._fh.flush()

    def has(self, phase: str, cell_id: str, seed: int) -> bool:
        return (phase, cell_id, int(seed)) in self.index

    def record(self, row: dict) -> None:
        key = (row["P"], row["C"], int(row["S"]))
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
        return sorted(out, key=lambda r: (r["P"], r["C"], int(r["S"])))

    def close(self) -> None:
        self._fh.close()
