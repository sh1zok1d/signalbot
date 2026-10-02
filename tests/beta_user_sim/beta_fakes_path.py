"""Re-export the beta test PostgreSQL helpers (tests/beta has no package __init__)."""
import sys
from pathlib import Path

_BETA_TESTS = str(Path(__file__).resolve().parents[1] / "beta")
if _BETA_TESTS not in sys.path:
    sys.path.append(_BETA_TESTS)

from beta_fakes import TEST_DSN, fresh_pool  # noqa: E402,F401
