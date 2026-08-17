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

**Stage 5 — Setup Detectors: completes the implementation required for
Stage 5's three frozen detector families when #42 merges.**

  - **PR 1 of ~4 — shared detector foundation: MERGED** (#39, "feat: add
    V2 setup detector foundation"). Added `setup_common.py`: the
    canonical §7.0b breakout directional-context compatibility gate
    (`directional_context_gate()` -> `V2DirectionalContextDecision`,
    consumed by `COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT` only — never
    `TREND_PULLBACK`, whose own stricter "4h trending AND 1h same
    direction" precondition makes this gate redundant there); §7's
    `RANGE_PROXY_pct(timeframe, N=14, B)` rolling-mean volatility proxy
    (`range_proxy_pct()`, `15m`/`1h` only); §7's `protection_buffer()`
    structural-invalidation buffer (`max(3*tick_size, reference_price*
    RANGE_PROXY_pct/100*0.5)`); and §7.0c's deterministic most-recent-tie
    extreme selection (`select_extreme_anchor()` -> `V2ExtremeAnchor`).
    Also added `storage/v2_setup_readers.py` (deterministic historical-
    window reads: `consensus_feature_vectors`, consensus-scope
    `percentile_snapshots`, `exchange_feature_vectors`, and a single-row
    `exchange_instruments` tick-size lookup — reached only through the
    separate `V2SetupHistoryReader` port, `ports.py`; `V2AlignedInputReader`
    is UNCHANGED). Implemented ZERO setup detection itself.
  - **PR 2 of ~4 — `TREND_PULLBACK`: MERGED** (#40, "feat: add V2 trend
    pullback detector"), the FIRST actual V2 setup detector. Adds
    `trend_pullback.py`: `detect_trend_pullback(inputs:
    V2TrendPullbackInputs) -> Optional[V2TrendPullbackCandidate]` —
    §7.1's frozen strict precondition (4h regime AND 1h bias must both
    firmly agree with the candidate direction; `directional_context_gate`
    is deliberately never used here), evaluated only on 15m formation
    boundaries (`selected_bucket("15m", T) + 15m == T`, never floored);
    the exact `LOOKBACK_15M=48`-bucket reference-close retracement
    structure with §7.0c's tie-broken `trend_leg_extreme` (reusing PR 1's
    `select_extreme_anchor()` unchanged); the exact retracement formulas
    and inclusive `[PULLBACK_MIN_MULT=0.5, PULLBACK_MAX_MULT=3.0] *
    RANGE_PROXY_pct(15m,14,B15)` valid band; the `pullback_extreme`
    structural span (`trend_leg_extreme`'s own anchor bucket THROUGH
    `B15` inclusive — never the full 48-bucket extreme, never buckets
    strictly older than the anchor); `protection_buffer()`/entry-zone/
    `invalidation_price` structural facts (reusing PR 1's
    `protection_buffer()` unchanged, no future `confirmation_close_price`).
    Also adds `trend_pullback_inputs.py`: `load_trend_pullback_inputs()`,
    a narrow async assembler over `V2SetupHistoryReader` fetching exactly
    the 48-bucket reference window, the 14-bucket consensus window, and
    the single instrument row this detector needs (zero percentile/kline/
    5m/1h/4h/health/OI/funding/liquidation reads) — mirroring Stage 3's
    own pure-detector/async-assembler module split.
    **Deliberately implements ONLY the qualification question** ("does
    the current structure qualify as `TREND_PULLBACK` at this exact `T`,
    and what are its deterministic structural facts") — a stateless
    detector cannot know whether a qualification is a brand-new episode's
    `T_detect` or a pre-confirmation re-evaluation of an already-active
    `EARLY_SIGNAL`, so this PR never constructs `episode_id`/`event_id`,
    never transitions `EARLY_SIGNAL`/`CONFIRMED`/`WEAKENING`/
    `INVALIDATED`/`EXPIRED`/`COMPLETED`, never evaluates the §7.1 5m
    resumption/confirmation trigger (which is only meaningful relative to
    an ALREADY-EXISTING episode's own `T_detect`), never counts candidate
    age against `PULLBACK_MAX_AGE_15M_BUCKETS` (exposed only as frozen
    family metadata), and never computes `model_confidence` (§8). All of
    that is Stage 6 (Episode State Machine).
  - **PR 3 of ~4 — `COMPRESSION_BREAKOUT`: MERGED** (#41, "feat: add V2
    compression breakout detector"). Adds `compression_breakout.py`:
    `detect_compression_breakout(inputs: V2CompressionBreakoutInputs) ->
    Optional[V2CompressionBreakoutCandidate]` -- evaluated at EVERY legal
    5m V2 decision boundary (not restricted to 15m formation boundaries,
    unlike `TREND_PULLBACK`); the exact `COMPRESSION_LOOKBACK=16`-bucket
    15m compression-evidence grid, gated per-bucket by the SAME §6.2/§6.3
    quality gate PLUS `context_evidence.compression_score()` (reused
    unchanged) `>= COMPRESSION_THRESHOLD=0.75`; the new deterministic
    maximal-consecutive-run partition + most-recent-end selection
    (`COMPRESSION_MIN_DURATION=6`, full run length used, never truncated);
    the selected run's structural `range_high`/`range_low` via
    `aligned_inputs.derive_reference_extrema()` (reused unchanged, §7.0a)
    over ONLY that run's own buckets; the fresh 5m-crossing check (current
    vs. immediately-previous closed Binance 5m reference closes,
    distinguishing a NEW cross from merely remaining outside an
    already-broken level); the 5m trigger's quality/
    `BREAKOUT_MIN_AGREEMENT=2/3` directional-agreement/taker-flow-sign
    gates; the shared §7.0b `directional_context_gate()` (reused
    unchanged, deliberately NOT `TREND_PULLBACK`'s own stricter
    precondition); and `protection_buffer()`/entry-zone/
    `invalidation_price` structural facts (the 15m reference close AT
    `B15`, never the 5m breakout close itself). Also adds
    `compression_breakout_inputs.py`: `load_compression_breakout_inputs()`,
    a narrow async assembler over `V2SetupHistoryReader` issuing exactly 7
    reads (16-bucket 15m consensus + matching percentile + matching
    reference-feature windows, one raw-1m-kline window, the two closed 5m
    reference buckets, the current 5m consensus trigger row, and the
    instrument row) -- no formation-boundary skip, since every 5m boundary
    is a possible breakout instant. **Deliberately implements ONLY the
    qualification question**, exactly like `TREND_PULLBACK`: never
    constructs `episode_id`/`event_id`, never transitions
    `EARLY_SIGNAL`/`CONFIRMED`/`WEAKENING`/`INVALIDATED`/`EXPIRED`/
    `COMPLETED`, never evaluates the direction-aware false-break rule or
    the boundary-equality HOLD convention, never counts candidate age
    against `COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS` (exposed only as
    frozen family metadata), and never applies §7.4 family precedence
    against `CONFIRMED_BREAKOUT`/`TREND_PULLBACK`. All of that is Stage 6.
  - **PR 4 of ~4 — `CONFIRMED_BREAKOUT` + Stage 5 completion: THIS PR**
    (#42, "feat: add V2 confirmed breakout detector"), the FINAL planned
    Stage 5 detector PR. Adds `confirmed_breakout.py`:
    `detect_confirmed_breakout(inputs: V2ConfirmedBreakoutInputs) ->
    Optional[V2ConfirmedBreakoutCandidate]` -- evaluated at EVERY legal
    5m V2 decision boundary like `COMPRESSION_BREAKOUT` (no 1h-boundary
    restriction); the exact `LEVEL_LOOKBACK=48`-bucket 1h structural
    lookback (`resistance_level = max(HTF_high)`,
    `support_level = min(HTF_low)`, via `aligned_inputs.derive_reference_
    extrema()` reused unchanged, §7.0a) -- ANY one of the 48 buckets
    unavailable makes the whole level unavailable (intentionally
    stricter than #41's selected-run subset, since there is no
    "selected run" concept here); the deterministic latest-tie
    resistance/support anchor selection via the real `select_extreme_
    anchor()` (§7.0c, reused unchanged); the fresh 5m-crossing check
    (current vs. immediately-previous closed Binance 5m reference
    closes); the shared §7.0b `directional_context_gate()` (reused
    unchanged); and `protection_buffer()`/entry-zone/`invalidation_price`
    structural facts (the 1h reference close AT `B1h`, never the 5m
    breakout close itself; a SEPARATE, smaller 14-bucket 1h consensus
    window for `RANGE_PROXY_pct(1h,14,B1h)` and the current-B1h quality
    gate, distinct from the 48-bucket structural window which carries no
    consensus rows at all). **`CONFIRMED_BREAKOUT` is deliberately NOT
    `COMPRESSION_BREAKOUT` without compression (load-bearing, §7.3): no
    preceding-compression precondition, no taker-flow confirmation
    requirement, and no invented `price_direction_agreement >= 2/3`
    EARLY_SIGNAL gate** -- §7.3 freezes exactly two EARLY_SIGNAL
    requirements (the fresh structural-level crossing and
    `directional_context_gate` acceptance), so `V2ConfirmedBreakoutCandidate`
    carries no `price_direction_agreement`/`taker_delta_notional_usd_sum`
    fields at all. Also adds `confirmed_breakout_inputs.py`:
    `load_confirmed_breakout_inputs()`, a narrow async assembler over
    `V2SetupHistoryReader` issuing exactly 5 reads (14-bucket 1h consensus
    window, 48-bucket 1h reference-feature window, one raw-1m-kline
    window, the two closed 5m reference buckets, the instrument row) --
    deliberately NO current-B5 5m consensus read (load-bearing difference
    from #41's loader, since this family has no taker-flow/agreement gate
    to feed). **Deliberately implements ONLY the qualification question**,
    exactly like `TREND_PULLBACK`/`COMPRESSION_BREAKOUT`: never constructs
    `episode_id`/`event_id`/`episode_logical_key`, never transitions
    `EARLY_SIGNAL`/`CONFIRMED`/`WEAKENING`/`INVALIDATED`/`EXPIRED`/
    `COMPLETED`, never evaluates the direction-aware false-break rule or
    the boundary-equality HOLD convention, never counts candidate age
    against `CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS` (exposed
    only as frozen family metadata), and never applies §7.4 family
    precedence against `COMPRESSION_BREAKOUT`/`TREND_PULLBACK`. All of
    that is Stage 6.

Stage 5's detector-implementation portion becomes COMPLETE when #42
merges -- all three frozen setup families (`TREND_PULLBACK`,
`COMPRESSION_BREAKOUT`, `CONFIRMED_BREAKOUT`) then have a deterministic
Stage 5 qualification implementation. This does NOT mean the V2 trading
product is complete: Stage 6 (Episode State Machine) -- episode identity/
dedup, family precedence, confirmation, false-break transitions, expiry,
weakening, persistence orchestration -- has not started.

`V2EpisodeEvent` (events.py) validates and freezes an already-decided
event a future Episode State Machine PR will construct;
`V2EventProvenance` (provenance.py) is a frozen snapshot of one
event-construction operation's identity; `build_v2_episode_event()`
(event_factory.py) is the one canonical way to combine the two;
`V2EpisodeEventWriter`/`V2AlignedInputReader`/`V2SetupHistoryReader`
(ports.py) are the narrow structural-typing dependency ports future
orchestration code depends on instead of importing `storage.db.Database`
directly. None of this decides what state an episode should be in, when
an event should be emitted — only which data is legal to decide from, how
to read it deterministically, the shared mathematical vocabulary, the
complete Stage 4 context, Stage 5's shared detector math/context-gate/
historical-read foundation, and now (#40) the first concrete setup
qualification, `TREND_PULLBACK`. See docs/FORECASTING_ROADMAP.md §I for
the full stage breakdown and §J for the authoritative current merge-state
truth. V1 (`analytics/forecasting/`) is untouched and continues running
unchanged."""
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
from .compression_breakout import (
    BREAKOUT_MIN_AGREEMENT, COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS,
    COMPRESSION_LOOKBACK, COMPRESSION_MIN_DURATION, COMPRESSION_PERCENTILE_WINDOW,
    COMPRESSION_THRESHOLD, V2CompressionBreakoutCandidate, V2CompressionBreakoutError,
    V2CompressionBreakoutInputs, detect_compression_breakout,
)
from .compression_breakout import EXPECTED_HORIZON as COMPRESSION_BREAKOUT_EXPECTED_HORIZON
from .compression_breakout_inputs import load_compression_breakout_inputs
from .confirmed_breakout import (
    CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS, LEVEL_LOOKBACK,
    V2ConfirmedBreakoutCandidate, V2ConfirmedBreakoutError, V2ConfirmedBreakoutInputs,
    detect_confirmed_breakout,
)
from .confirmed_breakout import EXPECTED_HORIZON as CONFIRMED_BREAKOUT_EXPECTED_HORIZON
from .confirmed_breakout_inputs import load_confirmed_breakout_inputs
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
    REJECT_REGIME_UNAVAILABLE, SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE,
    SETUP_RANGE_TIMEFRAMES, V2DirectionalContextDecision,
    V2ExtremeAnchor, V2SetupFoundationError, directional_context_gate,
    protection_buffer, range_proxy_pct, select_extreme_anchor,
)
from .trend_pullback import (
    EXPECTED_HORIZON, LOOKBACK_15M, PULLBACK_MAX_AGE_15M_BUCKETS, PULLBACK_MAX_MULT,
    PULLBACK_MIN_MULT, RESUMPTION_MIN_BUCKETS, V2TrendPullbackCandidate,
    V2TrendPullbackError, V2TrendPullbackInputs, detect_trend_pullback,
)
from .trend_pullback_inputs import load_trend_pullback_inputs

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
    "SETUP_MIN_COVERAGE", "SETUP_MIN_CONFIDENCE",
    "V2TrendPullbackError",
    "LOOKBACK_15M", "PULLBACK_MIN_MULT", "PULLBACK_MAX_MULT",
    "PULLBACK_MAX_AGE_15M_BUCKETS", "RESUMPTION_MIN_BUCKETS", "EXPECTED_HORIZON",
    "V2TrendPullbackInputs", "V2TrendPullbackCandidate", "detect_trend_pullback",
    "load_trend_pullback_inputs",
    "V2CompressionBreakoutError",
    "COMPRESSION_LOOKBACK", "COMPRESSION_MIN_DURATION", "COMPRESSION_THRESHOLD",
    "COMPRESSION_PERCENTILE_WINDOW", "BREAKOUT_MIN_AGREEMENT",
    "COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS", "COMPRESSION_BREAKOUT_EXPECTED_HORIZON",
    "V2CompressionBreakoutInputs", "V2CompressionBreakoutCandidate",
    "detect_compression_breakout", "load_compression_breakout_inputs",
    "V2ConfirmedBreakoutError",
    "LEVEL_LOOKBACK", "CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS",
    "CONFIRMED_BREAKOUT_EXPECTED_HORIZON",
    "V2ConfirmedBreakoutInputs", "V2ConfirmedBreakoutCandidate",
    "detect_confirmed_breakout", "load_confirmed_breakout_inputs",
]
