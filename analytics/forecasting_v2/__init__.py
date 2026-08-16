"""V2 (Multi-model Framework + Multi-timeframe Alignment + Context Engines)
analytics package.

This package contains identity primitives, the immutable episode-event
PERSISTENCE model, the provenance/construction/dependency boundaries the
Multi-model Framework stage built (complete), the full deterministic
read/alignment boundary Stage 3 — Multi-timeframe Alignment built
(complete): the decision clock (`decision_boundary()`/`selected_bucket()`,
alignment.py), deterministic Stage 2 reads (via
`storage/v2_alignment_readers.py`, reached only through the
`V2AlignedInputReader` port, never imported directly here), canonical
Binance reference-input preparation, and the final immutable
`V2AlignedInputs` snapshot (`load_v2_aligned_inputs()`, aligned_inputs.py)
— and now, Stage 4 — Context Engines, PR 1/~3 and PR 2/~3: the shared
evidence mathematics (`context_evidence.py`) both the 4h regime engine
and the future 1h bias engine consume — exact consensus-percentile
lookup (`find_consensus_percentile()`), the corrected signed evidence
primitive (`normalized_evidence()`), its unsigned compression companion
(`compression_score()`), and the corrected OI confirmation/opposition
primitive (`oi_confirmation()`) — and the 4h regime engine itself
(`regime_4h.py`): `classify_4h_regime()` deterministically classifies one
already-aligned 4h `V2TimeframeInputs` into exactly one of
`BULLISH_TRENDING`/`BEARISH_TRENDING`/`NON_DIRECTIONAL` (with an attached
`is_compressed` flag) /`INSUFFICIENT_DATA`, per the frozen §4.2 decision
tree — direction always decided by price alone, cross-exchange agreement
as a gate only, OI as an optional symmetric veto only (never a
directional vote), and a careful distinction between genuinely MISSING
mandatory evidence (forces `INSUFFICIENT_DATA`) and evidence that is
merely below the percentile confidence-tier floor (does not). It does
**not** yet contain a state machine, setup detector, 1h bias
classification, or a combined context snapshot — no `BIAS_*` threshold,
`NEUTRAL_NOT_ESTABLISHED`, `directional_context_gate`, `structural_anchor`,
episode identity, or lifecycle logic exists anywhere in this package.
`V2EpisodeEvent` (events.py) validates and freezes an already-decided
event a future Episode State Machine PR will construct;
`V2EventProvenance` (provenance.py) is a frozen snapshot of one
event-construction operation's identity; `build_v2_episode_event()`
(event_factory.py) is the one canonical way to combine the two;
`V2EpisodeEventWriter`/`V2AlignedInputReader` (ports.py) are the narrow
structural-typing dependency ports future orchestration code depends on
instead of importing `storage.db.Database` directly. None of this decides
what state an episode should be in, when an event should be emitted, or
what a setup/bias IS — only which data is legal to decide from, how to
read it deterministically, the shared mathematical vocabulary, and now
the established 4h regime. See docs/FORECASTING_ROADMAP.md §I for where
each of the still-missing pieces lands (Stage 4 PR 3/~3 onward). V1
(`analytics/forecasting/`) is untouched and continues running unchanged."""
from .aligned_inputs import (
    ALIGNED_TIMEFRAMES, STRUCTURAL_OHLC_TIMEFRAMES, V2_REFERENCE_EXCHANGE,
    V2AlignedInputError, V2AlignedInputRequest, V2AlignedInputs,
    V2ReferenceExtrema, V2TimeframeInputs, load_v2_aligned_inputs,
)
from .alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, decision_boundary, selected_bucket,
)
from .context_evidence import (
    MIN_PCTL_TIER, V2ContextEvidenceError, compression_score,
    find_consensus_percentile, normalized_evidence, oi_confirmation,
)
from .event_factory import build_v2_episode_event
from .events import (
    COMPRESSION_BREAKOUT, CONFIRMED, CONFIRMED_BREAKOUT, DIRECTIONS,
    EARLY_SIGNAL, EPISODE_STATES, EXPIRED, COMPLETED, INVALIDATED, LIVE,
    LONG, REPLAY, RUN_KINDS, SETUP_FAMILIES, SHORT, SUPPORTED_MARKET_TYPE,
    SUPPORTED_SYMBOL, TREND_PULLBACK, V2EpisodeEvent, V2EventInputError,
    WEAKENING,
)
from .identity import MODEL_FAMILY, V2IdentityError, V2ModelIdentity
from .ports import V2AlignedInputReader, V2EpisodeEventWriter
from .provenance import V2EventProvenance, V2ProvenanceError
from .regime_4h import (
    BEARISH_TRENDING, BULLISH_TRENDING, INSUFFICIENT_DATA, NON_DIRECTIONAL,
    REGIME_COMPRESSION, REGIME_MIN_AGREEMENT, REGIME_MIN_COVERAGE,
    REGIME_MIN_CONFIDENCE, REGIME_OI_VETO, REGIME_TREND_THRESHOLD, REGIMES,
    V2RegimeError, V2RegimeResult, classify_4h_regime,
)

__all__ = [
    "MODEL_FAMILY", "V2IdentityError", "V2ModelIdentity",
    "V2EpisodeEvent", "V2EventInputError",
    "RUN_KINDS", "LIVE", "REPLAY",
    "DIRECTIONS", "LONG", "SHORT",
    "SETUP_FAMILIES", "TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT",
    "EPISODE_STATES", "EARLY_SIGNAL", "CONFIRMED", "WEAKENING", "INVALIDATED",
    "EXPIRED", "COMPLETED",
    "SUPPORTED_SYMBOL", "SUPPORTED_MARKET_TYPE",
    "V2EventProvenance", "V2ProvenanceError",
    "build_v2_episode_event",
    "V2EpisodeEventWriter", "V2AlignedInputReader",
    "V2AlignmentError", "TIMEFRAME_MINUTES", "decision_boundary", "selected_bucket",
    "V2AlignedInputError", "V2_REFERENCE_EXCHANGE",
    "ALIGNED_TIMEFRAMES", "STRUCTURAL_OHLC_TIMEFRAMES",
    "V2AlignedInputRequest", "V2ReferenceExtrema", "V2TimeframeInputs",
    "V2AlignedInputs", "load_v2_aligned_inputs",
    "V2ContextEvidenceError", "MIN_PCTL_TIER",
    "find_consensus_percentile", "normalized_evidence", "compression_score",
    "oi_confirmation",
    "V2RegimeError", "V2RegimeResult", "classify_4h_regime",
    "BULLISH_TRENDING", "BEARISH_TRENDING", "NON_DIRECTIONAL", "INSUFFICIENT_DATA",
    "REGIMES",
    "REGIME_MIN_CONFIDENCE", "REGIME_MIN_COVERAGE", "REGIME_TREND_THRESHOLD",
    "REGIME_MIN_AGREEMENT", "REGIME_OI_VETO", "REGIME_COMPRESSION",
]
