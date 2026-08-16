"""V2 (Multi-model Framework + Multi-timeframe Alignment + Context Engines
+ Setup Detectors) analytics package.

This package contains identity primitives, the immutable episode-event
PERSISTENCE model, the provenance/construction/dependency boundaries the
Multi-model Framework stage built (COMPLETE), the full deterministic
read/alignment boundary Stage 3 — Multi-timeframe Alignment built
(COMPLETE): the decision clock (`decision_boundary()`/`selected_bucket()`,
alignment.py), deterministic Stage 2 reads (via
`storage/v2_alignment_readers.py`, reached only through the
`V2AlignedInputReader` port, never imported directly here), canonical
Binance reference-input preparation, and the final immutable
`V2AlignedInputs` snapshot (`load_v2_aligned_inputs()`, aligned_inputs.py)
— and Stage 4 — Context Engines (COMPLETE, PR #36/#37/#38, all merged):
the shared evidence mathematics (`context_evidence.py`) the 4h regime and
1h bias engines both consume — exact consensus-percentile lookup
(`find_consensus_percentile()`), the corrected signed evidence primitive
(`normalized_evidence()`), its unsigned compression companion
(`compression_score()`), and the corrected OI confirmation/opposition
primitive (`oi_confirmation()`) — the 4h regime engine (`regime_4h.py`):
`classify_4h_regime()` deterministically classifies one already-aligned
4h `V2TimeframeInputs` into exactly one of `BULLISH_TRENDING`/
`BEARISH_TRENDING`/`NON_DIRECTIONAL` (with an attached `is_compressed`
flag)/`INSUFFICIENT_DATA`, per the frozen §4.2 decision tree — the 1h
bias engine (`bias_1h.py`): `classify_1h_bias()` deterministically
classifies one already-aligned 1h `V2TimeframeInputs` into exactly one of
`BULLISH`/`BEARISH`/`NEUTRAL_NOT_ESTABLISHED`/`"UNAVAILABLE"`, per the
frozen §4.3 decision tree, deliberately lighter/faster-adapting than the
4h regime and reading no OI/compression at all (§4.4) — and the final
combined context snapshot (`context_snapshot.py`): `build_v2_context_
snapshot()` combines the 4h regime and 1h bias already computed for ONE
`V2AlignedInputs` into a single immutable `V2ContextSnapshot`, preserving
both facts SEPARATELY (no overall/combined direction, §4.4) and failing
closed against pairing results from two different decision boundaries or
a source-identity mismatch.

**Stage 5 — Setup Detectors: IN PROGRESS**, started by this PR (#39, PR 1
of ~4 — shared detector FOUNDATION only, no detector itself). Adds
`setup_common.py`: the canonical §7.0b breakout directional-context
compatibility gate (`directional_context_gate()` ->
`V2DirectionalContextDecision`, consumed by `COMPRESSION_BREAKOUT`/
`CONFIRMED_BREAKOUT` only — never `TREND_PULLBACK`, whose own stricter
"4h trending AND 1h same direction" precondition makes this gate
redundant there); §7's `RANGE_PROXY_pct(timeframe, N=14, B)` rolling-mean
volatility proxy (`range_proxy_pct()`, `15m`/`1h` only); §7's
`protection_buffer()` structural-invalidation buffer (`max(3*tick_size,
reference_price*RANGE_PROXY_pct/100*0.5)`); and §7.0c's deterministic
most-recent-tie extreme selection (`select_extreme_anchor()` ->
`V2ExtremeAnchor`, for `TREND_PULLBACK`'s `trend_leg_extreme`/
`CONFIRMED_BREAKOUT`'s `resistance_level`/`support_level` — never
`COMPRESSION_BREAKOUT`'s plain-numeric `range_high`/`range_low`). Also
adds `storage/v2_setup_readers.py` (deterministic historical-window
reads: `consensus_feature_vectors`, consensus-scope `percentile_
snapshots`, `exchange_feature_vectors`, and a single-row `exchange_
instruments` tick-size lookup — reached only through the NEW, separate
`V2SetupHistoryReader` port, `ports.py`; `V2AlignedInputReader` is
UNCHANGED). **Still ZERO setup detection anywhere in this package** — no
`TREND_PULLBACK`/`COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT` candidate
can be produced by anything here: no `EARLY_SIGNAL`/`CONFIRMED`
transition, no entry zone, no per-episode invalidation price, no
`structural_anchor`/episode-identity construction, no episode
lifecycle/state machine, no confidence scoring, no entry feasibility, no
runtime wiring. Those are PR 2/~4 (`TREND_PULLBACK`), PR 3/~4
(`COMPRESSION_BREAKOUT`), and PR 4/~4 (`CONFIRMED_BREAKOUT` + Stage 5
completion) — do not read this docstring as claiming any of them exist
while Stage 5 remains IN PROGRESS.

`V2EpisodeEvent` (events.py) validates and freezes an already-decided
event a future Episode State Machine PR will construct;
`V2EventProvenance` (provenance.py) is a frozen snapshot of one
event-construction operation's identity; `build_v2_episode_event()`
(event_factory.py) is the one canonical way to combine the two;
`V2EpisodeEventWriter`/`V2AlignedInputReader`/`V2SetupHistoryReader`
(ports.py) are the narrow structural-typing dependency ports future
orchestration code depends on instead of importing `storage.db.Database`
directly. None of this decides what state an episode should be in, when
an event should be emitted, or what a setup IS — only which data is
legal to decide from, how to read it deterministically, the shared
mathematical vocabulary, the complete Stage 4 context, and now Stage 5's
shared detector math/context-gate/historical-read foundation. See
docs/FORECASTING_ROADMAP.md §I for the full stage breakdown and §J for
the authoritative current merge-state truth. V1 (`analytics/forecasting/`)
is untouched and continues running unchanged."""
from .aligned_inputs import (
    ALIGNED_TIMEFRAMES, STRUCTURAL_OHLC_TIMEFRAMES, V2_REFERENCE_EXCHANGE,
    V2AlignedInputError, V2AlignedInputRequest, V2AlignedInputs,
    V2ReferenceExtrema, V2TimeframeInputs, load_v2_aligned_inputs,
)
from .alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, decision_boundary, selected_bucket,
)
from .bias_1h import (
    BEARISH, BIAS_MIN_AGREEMENT, BIAS_MIN_COVERAGE, BIAS_THRESHOLD,
    BIAS_MIN_CONFIDENCE, BIAS_UNAVAILABLE, BIASES, BULLISH,
    NEUTRAL_NOT_ESTABLISHED, V2BiasError, V2BiasResult, classify_1h_bias,
)
from .context_evidence import (
    MIN_PCTL_TIER, V2ContextEvidenceError, compression_score,
    find_consensus_percentile, normalized_evidence, oi_confirmation,
)
from .context_snapshot import (
    V2ContextSnapshot, V2ContextSnapshotError, build_v2_context_snapshot,
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
from .ports import V2AlignedInputReader, V2EpisodeEventWriter, V2SetupHistoryReader
from .provenance import V2EventProvenance, V2ProvenanceError
from .regime_4h import (
    BEARISH_TRENDING, BULLISH_TRENDING, INSUFFICIENT_DATA, NON_DIRECTIONAL,
    REGIME_COMPRESSION, REGIME_MIN_AGREEMENT, REGIME_MIN_COVERAGE,
    REGIME_MIN_CONFIDENCE, REGIME_OI_VETO, REGIME_TREND_THRESHOLD, REGIMES,
    V2RegimeError, V2RegimeResult, classify_4h_regime,
)
from .setup_common import (
    BUFFER_MULTIPLIER, CONTEXT_ACCEPT, MIN_TICK_BUFFER_TICKS, RANGE_PROXY_N,
    REJECT_BIAS_OPPOSES, REJECT_BIAS_UNAVAILABLE, REJECT_REGIME_OPPOSES,
    REJECT_REGIME_UNAVAILABLE, SETUP_RANGE_TIMEFRAMES, V2DirectionalContextDecision,
    V2ExtremeAnchor, V2SetupFoundationError, directional_context_gate,
    protection_buffer, range_proxy_pct, select_extreme_anchor,
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
    "V2EpisodeEventWriter", "V2AlignedInputReader", "V2SetupHistoryReader",
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
    "V2BiasError", "V2BiasResult", "classify_1h_bias",
    "BULLISH", "BEARISH", "NEUTRAL_NOT_ESTABLISHED", "BIAS_UNAVAILABLE", "BIASES",
    "BIAS_MIN_CONFIDENCE", "BIAS_MIN_COVERAGE", "BIAS_THRESHOLD", "BIAS_MIN_AGREEMENT",
    "V2ContextSnapshotError", "V2ContextSnapshot", "build_v2_context_snapshot",
    "V2SetupFoundationError",
    "CONTEXT_ACCEPT", "REJECT_REGIME_UNAVAILABLE", "REJECT_REGIME_OPPOSES",
    "REJECT_BIAS_UNAVAILABLE", "REJECT_BIAS_OPPOSES",
    "V2DirectionalContextDecision", "directional_context_gate",
    "RANGE_PROXY_N", "SETUP_RANGE_TIMEFRAMES", "range_proxy_pct",
    "MIN_TICK_BUFFER_TICKS", "BUFFER_MULTIPLIER", "protection_buffer",
    "V2ExtremeAnchor", "select_extreme_anchor",
]
