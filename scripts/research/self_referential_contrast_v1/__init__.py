"""SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1 implementation.

Validation-protocol amendment V1. Official screens are not executed on import.
"""

from scripts.research.self_referential_contrast_v1 import env_limits as _env_limits  # noqa: F401

from scripts.research.self_referential_contrast_v1.contrast import run_primary
from scripts.research.self_referential_contrast_v1.runner import run_worlds

__all__ = ["run_primary", "run_worlds"]
