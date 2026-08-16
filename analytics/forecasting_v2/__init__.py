"""V2 (Multi-model Framework + Multi-timeframe Alignment) analytics package.

This package contains identity primitives, the immutable episode-event
PERSISTENCE model, the provenance/construction/dependency boundaries the
Multi-model Framework stage built (complete), and — Stage 3, Multi-
timeframe Alignment (complete as of this package version) — the full
deterministic read/alignment boundary: the decision clock
(`decision_boundary()`/`selected_bucket()`, alignment.py), deterministic
Stage 2 reads (via `storage/v2_alignment_readers.py`, reached only through
the `V2AlignedInputReader` port, never imported directly here), canonical
Binance reference-input preparation, and the final immutable
`V2AlignedInputs` snapshot (`load_v2_aligned_inputs()`, aligned_inputs.py)
Stage 4 Context Engines will consume. It does **not** contain a state
machine, detector, scoring, or context engine of any kind — no
`normalized_evidence`, 4h regime, 1h bias, OI confirmation, setup
detector, `structural_anchor`, episode identity, or lifecycle logic exists
anywhere in this package. `V2EpisodeEvent` (events.py) validates and
freezes an already-decided event a future Episode State Machine PR will
construct; `V2EventProvenance` (provenance.py) is a frozen snapshot of one
event-construction operation's identity; `build_v2_episode_event()`
(event_factory.py) is the one canonical way to combine the two;
`V2EpisodeEventWriter`/`V2AlignedInputReader` (ports.py) are the narrow
structural-typing dependency ports future orchestration code depends on
instead of importing `storage.db.Database` directly. None of this decides
what state an episode should be in, when an event should be emitted, or
what a setup/regime/bias IS — only which data is legal to decide from and
how to read it deterministically. See docs/FORECASTING_ROADMAP.md §I for
where each of those still-missing pieces lands (Stage 4 onward). V1
(`analytics/forecasting/`) is untouched and continues running unchanged."""
from .aligned_inputs import (
    ALIGNED_TIMEFRAMES, STRUCTURAL_OHLC_TIMEFRAMES, V2_REFERENCE_EXCHANGE,
    V2AlignedInputError, V2AlignedInputRequest, V2AlignedInputs,
    V2ReferenceExtrema, V2TimeframeInputs, load_v2_aligned_inputs,
)
from .alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, decision_boundary, selected_bucket,
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
]
