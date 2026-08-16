"""V2 (Multi-model Framework) analytics package.

This package contains identity primitives, the immutable episode-event
PERSISTENCE model, and the provenance/construction/dependency boundaries
future V2 modules build on — it does **not** contain a state machine,
detector, scoring, context, multi-timeframe alignment, or
entry-feasibility logic. `V2EpisodeEvent` (events.py) validates and
freezes an already-decided event a future Episode State Machine PR will
construct; `V2EventProvenance` (provenance.py) is a frozen snapshot of one
event-construction operation's identity; `build_v2_episode_event()`
(event_factory.py) is the one canonical way to combine the two;
`V2EpisodeEventWriter` (ports.py) is the narrow structural-typing
dependency port future orchestration code depends on instead of importing
`storage.db.Database` directly. None of this decides what state an episode
should be in or when an event should be emitted. See
docs/FORECASTING_ROADMAP.md §I for where each of those still-missing
pieces lands. V1 (`analytics/forecasting/`) is untouched and continues
running unchanged."""
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
]
