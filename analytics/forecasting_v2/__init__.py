"""V2 (Multi-model Framework) analytics package — FOUNDATION ONLY.

This package intentionally contains no detector, scoring, context,
multi-timeframe alignment, episode-lifecycle, entry-feasibility, or outcome
logic. It exists only to carry the `model_family` / `rules_version` identity
primitives docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3 freezes, ahead of
the detector/context/episode work later Multi-model Framework PRs add
(docs/FORECASTING_ROADMAP.md §I). V1 (`analytics/forecasting/`) is untouched
and continues running unchanged."""
from .identity import MODEL_FAMILY, V2IdentityError, V2ModelIdentity

__all__ = ["MODEL_FAMILY", "V2IdentityError", "V2ModelIdentity"]
