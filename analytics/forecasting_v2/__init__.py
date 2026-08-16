"""V2 (Multi-model Framework + Multi-timeframe Alignment) analytics package.

This package contains identity primitives, the immutable episode-event
PERSISTENCE model, the provenance/construction/dependency boundaries the
Multi-model Framework stage built (now complete), and — starting with
Stage 3, Multi-timeframe Alignment — deterministic decision-clock /
bucket-alignment primitives. It does **not** contain a state machine,
detector, scoring, or context engine, and does **not** yet read any
feature/percentile/health data. `V2EpisodeEvent` (events.py) validates and
freezes an already-decided event a future Episode State Machine PR will
construct; `V2EventProvenance` (provenance.py) is a frozen snapshot of one
event-construction operation's identity; `build_v2_episode_event()`
(event_factory.py) is the one canonical way to combine the two;
`V2EpisodeEventWriter` (ports.py) is the narrow structural-typing
dependency port future orchestration code depends on instead of importing
`storage.db.Database` directly; `decision_boundary()`/`selected_bucket()`
(alignment.py) are the two pure timestamp-selection layers
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §1 freezes — which closed 5m/
15m/1h/4h bucket timestamps are legal to decide from, nothing about what to
do with them. None of this decides what state an episode should be in,
when an event should be emitted, or reads any actual market/feature data.
See docs/FORECASTING_ROADMAP.md §I for where each of those still-missing
pieces lands. V1 (`analytics/forecasting/`) is untouched and continues
running unchanged."""
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
from .ports import V2EpisodeEventWriter
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
    "V2EpisodeEventWriter",
    "V2AlignmentError", "TIMEFRAME_MINUTES", "decision_boundary", "selected_bucket",
]
