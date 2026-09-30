"""Pin worker numerical libraries to one thread.

Imported before NumPy so a spawned worker process does not multiply
OpenMP/BLAS threads by the process count. The statistical contract does
not depend on this limit.
"""

from __future__ import annotations

import os

_THREAD_VARS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)

for _name in _THREAD_VARS:
    os.environ[_name] = "1"

THREAD_LIMIT_VARS = _THREAD_VARS
