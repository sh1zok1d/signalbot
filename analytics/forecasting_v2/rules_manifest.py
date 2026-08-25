"""
V2 rules/version integrity guard (roadmap's lightweight-integrity-check
requirement; `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3/§23).

A canonical, deterministic manifest of every behavior-affecting frozen
V2-v0 constant across the currently-implemented Stage 3/4/5 surface
(`aligned_inputs.py`, `context_evidence.py`, `family_quality.py`,
`regime_4h.py`, `bias_1h.py`, `setup_common.py`, `trend_pullback.py`,
`compression_breakout.py`, `confirmed_breakout.py`), PLUS Stage 6 Unit 3's
own frozen §18.1 planned-risk floor (`episode_lifecycle.py`), plus a
deterministic fingerprint of that manifest keyed by `rules_version`
(`config/v2.yaml`).
A version-participating constant changing WITHOUT a corresponding
`rules_version` bump is exactly the silent-behavior-change class of bug
this module exists to catch -- `assert_rules_manifest_matches_version()`
fails closed against it.

**Scope, deliberately narrow (no large configuration framework).** Covers
scalar/lookback/multiplier/timedelta thresholds AND fixed behavior
selectors (timeframe/percentile-window/metric-name/reference-exchange
constants) this package's detectors and context engines actually gate
decisions on or key their data reads by. The inclusion test (tech-lead
amendment round 1, item 3): "would changing this constant while keeping
all inputs the same materially change the V2 decision semantics?" -- if
yes AND it is an explicit fixed rules selector/parameter, it belongs
here; if no / implementation-only (a private helper's local variable
name, an unrelated exception class, a docstring), it is excluded.
Deliberately EXCLUDES: wall clock, git commit SHA, hostname, process
identity, any V1 (`analytics/forecasting/`) constant, and any repo file
unrelated to V2 executable rules -- a docs-only or Telegram-only change
therefore cannot change the fingerprint this module computes. Also
excludes `model_confidence`'s future weighted-sum weight table (§8) and
per-family `setup_strength`/`data_confidence` FORMULA SHAPE (not yet a
separate tunable numeric constant beyond what is already covered below)
-- neither is independently executable yet beyond the per-candidate
values this PR already freezes via the constants listed here.

**`aligned_inputs.V2_REFERENCE_EXCHANGE` is included** (tech-lead
amendment round 1, item 3's explicit callout): every Stage 5 detector's
structural range/close-price reads are keyed by this single,
non-overridable reference-exchange selector (`aligned_inputs.py`'s own
docstring) -- changing it would silently redirect every detector's price
source to a different exchange while every other input stays the same,
which is exactly this module's inclusion test. No separate frozen
identity guard already covers it (V2's own identity model, `identity.py`
§3, freezes only `model_family`/`rules_version` -- an unrelated
dimension), so it is represented here instead.

**Explicit `(module, constant_name)` list, never `vars()`/`dir()`
introspection.** Blind module introspection would silently pick up
unrelated names (helper functions, imported symbols, exception classes)
any time a module's surface changes for reasons that have nothing to do
with V2 rules behavior -- this manifest is deliberately an explicit,
reviewable allow-list instead.

Pure module: no DB, no network, no filesystem beyond importing already-
loaded Python constants, no clock, no randomness. `build_rules_manifest()`
is a pure function of the already-imported module constants; the same
code always yields the same manifest/fingerprint.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from typing import Any, Mapping

from importlib import import_module

# `importlib.import_module()` (never `import pkg.mod as alias` / `from pkg
# import mod as alias`) -- `analytics/forecasting_v2/__init__.py`
# re-exports several of these modules' own PUBLIC FUNCTIONS under the same
# bare name as their module (e.g. `family_quality` the function vs.
# `family_quality.py` the module); both `import`-statement forms resolve
# the submodule via attribute access on the already-initialized parent
# package, which that re-export shadows. `import_module()` instead returns
# `sys.modules[name]` directly, immune to that shadowing.
_aligned_inputs = import_module("analytics.forecasting_v2.aligned_inputs")
_bias_1h = import_module("analytics.forecasting_v2.bias_1h")
_compression_breakout = import_module("analytics.forecasting_v2.compression_breakout")
_confirmed_breakout = import_module("analytics.forecasting_v2.confirmed_breakout")
_context_evidence = import_module("analytics.forecasting_v2.context_evidence")
_episode_lifecycle = import_module("analytics.forecasting_v2.episode_lifecycle")
_family_quality = import_module("analytics.forecasting_v2.family_quality")
_regime_4h = import_module("analytics.forecasting_v2.regime_4h")
_setup_common = import_module("analytics.forecasting_v2.setup_common")
_trend_pullback = import_module("analytics.forecasting_v2.trend_pullback")

__all__ = [
    "V2RulesManifestError",
    "EXPECTED_FINGERPRINTS_BY_RULES_VERSION",
    "build_rules_manifest",
    "compute_rules_fingerprint",
    "assert_rules_manifest_matches_version",
]


class V2RulesManifestError(ValueError):
    """The live rules manifest's fingerprint does not match the expected
    fingerprint recorded for the given `rules_version` -- a
    version-participating V2 rule constant changed without a
    corresponding `rules_version` bump -- or `rules_version` itself has
    no recorded expected fingerprint at all (unrecognized version)."""


def _seconds(value: Any, name: str) -> float:
    if not isinstance(value, timedelta):
        raise V2RulesManifestError(
            f"{name} must be a timedelta, got {type(value).__name__}: {value!r}")
    return value.total_seconds()


def _string_tuple(value: Any, name: str) -> "list[str]":
    """Deterministically serialize a fixed `tuple[str, ...]` selector
    (e.g. `setup_common.SETUP_RANGE_TIMEFRAMES`) to a stable JSON-native
    `list[str]`, preserving the constant's own defined order (never
    sorted/deduped here -- a real order change in the source constant
    IS a behavior change this manifest must catch). Rejects anything
    that is not literally a `tuple`/`list` of `str` (a `set`/generator
    would silently introduce nondeterministic iteration order)."""
    if not isinstance(value, (tuple, list)):
        raise V2RulesManifestError(
            f"{name} must be a tuple/list of str, got {type(value).__name__}: {value!r}")
    for item in value:
        if not isinstance(item, str):
            raise V2RulesManifestError(
                f"{name} must contain only str elements, got {type(item).__name__}: {item!r}")
    return list(value)


def _decimal_text(value: Any, name: str) -> str:
    """Deterministically serialize a frozen `Decimal` rule constant to its
    plain-text form -- `Decimal` is not itself JSON-serializable. The
    constant this backs is a fixed source-code literal, never reconstructed
    from external input here, so plain `str()` is already deterministic run
    to run without needing `canonical_decimal_text()`'s
    normalize-then-de-scientific-notation handling (which exists for
    values that arrive as persisted/parsed decimal strings, not literals)."""
    if not isinstance(value, Decimal):
        raise V2RulesManifestError(
            f"{name} must be a Decimal, got {type(value).__name__}: {value!r}")
    return str(value)


def build_rules_manifest() -> "dict[str, Any]":
    """The canonical, deterministic manifest of every behavior-affecting
    frozen V2-v0 constant across the currently-implemented Stage 3/4/5
    surface. Pure function of the already-imported module constants --
    no I/O, no clock. Returns a plain, JSON-serializable dict grouped by
    owning module; every leaf is a `bool`/`int`/`float`/`str`/`list[str]`
    (a raw `timedelta` is converted to `total_seconds()`, a raw
    `tuple[str, ...]` selector to a `list[str]` via `_string_tuple()` --
    neither is JSON-serializable/order-guaranteed on its own)."""
    return {
        "aligned_inputs": {
            "V2_REFERENCE_EXCHANGE": _aligned_inputs.V2_REFERENCE_EXCHANGE,
        },
        "context_evidence": {
            "MIN_PCTL_TIER": _context_evidence.MIN_PCTL_TIER,
            "_COMPRESSION_METRIC": _context_evidence._COMPRESSION_METRIC,
            "_OI_METRIC": _context_evidence._OI_METRIC,
        },
        "episode_lifecycle": {
            # §18.1's frozen V2-v0 planned-risk floor, MIN_VALID_PLANNED_RISK
            # = 3 * tick_size -- changing the multiplier while holding every
            # other input fixed moves the confirmation hard gate, exactly
            # this module's inclusion test.
            "_MIN_PLANNED_RISK_TICKS": _decimal_text(
                _episode_lifecycle._MIN_PLANNED_RISK_TICKS,
                "episode_lifecycle._MIN_PLANNED_RISK_TICKS"),
            # §7.1's frozen TREND_PULLBACK resumption-trigger threshold
            # (">= 2/3") -- a primary literal defined in THIS module (never
            # sourced from another already-covered constant), so nothing
            # else protects it. Lowering it would silently confirm episodes
            # §7.1 says must stay HOLD.
            "RESUMPTION_MIN_AGREEMENT": _episode_lifecycle.RESUMPTION_MIN_AGREEMENT,
            # §14's fixed decision/re-evaluation cadence selectors -- the
            # same class of fixed-timeframe selector already covered for
            # regime_4h/bias_1h (_REGIME_TIMEFRAME/_BIAS_TIMEFRAME). Changing
            # either would silently misalign confirmation or the TP
            # mechanism-(1) re-measurement cadence against a different grid.
            "DECISION_TIMEFRAME": _episode_lifecycle.DECISION_TIMEFRAME,
            "REEVALUATION_TIMEFRAME": _episode_lifecycle.REEVALUATION_TIMEFRAME,
            # §6.3a's per-family required-metric selector -- the same class
            # of per-family selector map already covered for
            # family_quality.FAMILY_MIN_COVERAGE/CONFIDENCE. Adding a metric
            # to (or removing one from) a family's required set would
            # silently change which quality gate that family's confirmation
            # is scoped to. Flattened to one leaf per family (never a nested
            # dict) so every manifest leaf stays a plain scalar/string-list,
            # matching every other module's own shape.
            **{
                f"REQUIRED_METRIC_FAMILY__{family}": _string_tuple(
                    metrics, f"episode_lifecycle.REQUIRED_METRIC_FAMILY[{family!r}]")
                for family, metrics in sorted(_episode_lifecycle.REQUIRED_METRIC_FAMILY.items())
            },
            # NOT included, by design: CANDIDATE_MAX_AGE is not a primary
            # literal -- it is computed entirely from already-manifest
            # -covered source constants (trend_pullback.
            # PULLBACK_MAX_AGE_15M_BUCKETS, compression_breakout.
            # COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS, confirmed_breakout.
            # CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS) multiplied
            # by DECISION_TIMEFRAME/REEVALUATION_TIMEFRAME, both covered
            # directly above. A change to any ingredient already moves the
            # fingerprint; manifesting the derived dict too would be exactly
            # the indiscriminate double-coverage this module's docstring
            # warns against.
        },
        "family_quality": {
            "FAMILY_MIN_COVERAGE": _family_quality.FAMILY_MIN_COVERAGE,
            "FAMILY_MIN_CONFIDENCE": _family_quality.FAMILY_MIN_CONFIDENCE,
        },
        "regime_4h": {
            "REGIME_MIN_CONFIDENCE": _regime_4h.REGIME_MIN_CONFIDENCE,
            "REGIME_MIN_COVERAGE": _regime_4h.REGIME_MIN_COVERAGE,
            "REGIME_TREND_THRESHOLD": _regime_4h.REGIME_TREND_THRESHOLD,
            "REGIME_MIN_AGREEMENT": _regime_4h.REGIME_MIN_AGREEMENT,
            "REGIME_OI_VETO": _regime_4h.REGIME_OI_VETO,
            "REGIME_COMPRESSION": _regime_4h.REGIME_COMPRESSION,
            "_REGIME_TIMEFRAME": _regime_4h._REGIME_TIMEFRAME,
            "_REGIME_PERCENTILE_WINDOW": _regime_4h._REGIME_PERCENTILE_WINDOW,
            "_PRICE_METRIC": _regime_4h._PRICE_METRIC,
            "_COMPRESSION_METRIC": _regime_4h._COMPRESSION_METRIC,
            "_BOUNDARY_ULP_TOLERANCE": _regime_4h._BOUNDARY_ULP_TOLERANCE,
        },
        "bias_1h": {
            "BIAS_MIN_CONFIDENCE": _bias_1h.BIAS_MIN_CONFIDENCE,
            "BIAS_MIN_COVERAGE": _bias_1h.BIAS_MIN_COVERAGE,
            "BIAS_THRESHOLD": _bias_1h.BIAS_THRESHOLD,
            "BIAS_MIN_AGREEMENT": _bias_1h.BIAS_MIN_AGREEMENT,
            "_BIAS_TIMEFRAME": _bias_1h._BIAS_TIMEFRAME,
            "_BIAS_PERCENTILE_WINDOW": _bias_1h._BIAS_PERCENTILE_WINDOW,
            "_PRICE_METRIC": _bias_1h._PRICE_METRIC,
        },
        "setup_common": {
            "SETUP_MIN_COVERAGE": _setup_common.SETUP_MIN_COVERAGE,
            "SETUP_MIN_CONFIDENCE": _setup_common.SETUP_MIN_CONFIDENCE,
            "RANGE_PROXY_N": _setup_common.RANGE_PROXY_N,
            "MIN_TICK_BUFFER_TICKS": _setup_common.MIN_TICK_BUFFER_TICKS,
            "BUFFER_MULTIPLIER": _setup_common.BUFFER_MULTIPLIER,
            "SETUP_RANGE_TIMEFRAMES": _string_tuple(
                _setup_common.SETUP_RANGE_TIMEFRAMES, "setup_common.SETUP_RANGE_TIMEFRAMES"),
            "_RANGE_METRIC": _setup_common._RANGE_METRIC,
        },
        "trend_pullback": {
            "LOOKBACK_15M": _trend_pullback.LOOKBACK_15M,
            "PULLBACK_MIN_MULT": _trend_pullback.PULLBACK_MIN_MULT,
            "PULLBACK_MAX_MULT": _trend_pullback.PULLBACK_MAX_MULT,
            "PULLBACK_MAX_AGE_15M_BUCKETS": _trend_pullback.PULLBACK_MAX_AGE_15M_BUCKETS,
            "RESUMPTION_MIN_BUCKETS": _trend_pullback.RESUMPTION_MIN_BUCKETS,
            "EXPECTED_HORIZON_SECONDS": _seconds(
                _trend_pullback.EXPECTED_HORIZON, "trend_pullback.EXPECTED_HORIZON"),
        },
        "compression_breakout": {
            "COMPRESSION_LOOKBACK": _compression_breakout.COMPRESSION_LOOKBACK,
            "COMPRESSION_MIN_DURATION": _compression_breakout.COMPRESSION_MIN_DURATION,
            "COMPRESSION_THRESHOLD": _compression_breakout.COMPRESSION_THRESHOLD,
            "COMPRESSION_PERCENTILE_WINDOW": _compression_breakout.COMPRESSION_PERCENTILE_WINDOW,
            "BREAKOUT_MIN_AGREEMENT": _compression_breakout.BREAKOUT_MIN_AGREEMENT,
            "COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS":
                _compression_breakout.COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS,
            "EXPECTED_HORIZON_SECONDS": _seconds(
                _compression_breakout.EXPECTED_HORIZON, "compression_breakout.EXPECTED_HORIZON"),
            "_COMPRESSION_METRIC": _compression_breakout._COMPRESSION_METRIC,
        },
        "confirmed_breakout": {
            "LEVEL_LOOKBACK": _confirmed_breakout.LEVEL_LOOKBACK,
            "CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS":
                _confirmed_breakout.CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS,
            "EXPECTED_HORIZON_SECONDS": _seconds(
                _confirmed_breakout.EXPECTED_HORIZON, "confirmed_breakout.EXPECTED_HORIZON"),
        },
    }


def compute_rules_fingerprint(manifest: Mapping[str, Any]) -> str:
    """A deterministic, order-stable SHA-256 hex digest of `manifest`:
    `json.dumps(..., sort_keys=True, separators=(",", ":"))` canonicalizes
    key order and whitespace, so semantically-identical manifests always
    hash identically regardless of `build_rules_manifest()`'s own dict
    literal order."""
    canonical = json.dumps(dict(manifest), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Frozen expected fingerprint for each shipped `rules_version` -- the
# ANCHOR this guard checks the live manifest against. Recorded here as a
# literal (not recomputed at import time from "whatever the code currently
# does") so a future accidental constant edit under an unchanged
# `rules_version` string is exactly what trips `V2RulesManifestError`,
# rather than the anchor silently following the drift.
EXPECTED_FINGERPRINTS_BY_RULES_VERSION: "dict[str, str]" = {
    # Recomputed twice, both times as INTEGRITY-GUARD coverage corrections
    # under the SAME rules_version -- neither changed any executable V2
    # rule behavior:
    #   1. Tech-lead amendment round 1, item 3: the manifest surface grew
    #      (aligned_inputs.V2_REFERENCE_EXCHANGE, context_evidence, and the
    #      fixed timeframe/percentile-window/metric selectors on
    #      regime_4h/bias_1h/setup_common/compression_breakout) to actually
    #      cover every behavior-affecting constant this module claims to.
    #   2. regime_4h._BOUNDARY_ULP_TOLERANCE (the IEEE-754 representation-
    #      hardening width `_ge_inclusive`/`_le_inclusive` walk by, at the
    #      `REGIME_TREND_THRESHOLD`/`REGIME_OI_VETO` boundaries) was itself
    #      already behavior-affecting -- changing it while holding every
    #      other input fixed can move a decision across those inclusive
    #      boundaries -- but was missing from the manifest. Now included;
    #      the constant's own value (4) is unchanged.
    #   3. Post-merge Stage 6 Unit 3 planned-risk-gate repair red-team
    #      finding: episode_lifecycle._MIN_PLANNED_RISK_TICKS (§18.1's
    #      MIN_VALID_PLANNED_RISK = 3 * tick_size multiplier) is exactly
    #      this module's inclusion test -- changing it while holding every
    #      other input fixed moves the confirmation hard gate -- but this
    #      manifest's scope had never been extended past Stage 3/4/5 to
    #      cover it. Now included; the constant's own value (3) is
    #      unchanged.
    #   4. Independent red-team finding on the same PR:
    #      episode_lifecycle.RESUMPTION_MIN_AGREEMENT (§7.1's ">= 2/3"
    #      confirmation threshold) is a primary literal defined in that
    #      module and was not covered by anything. Auditing the rest of
    #      episode_lifecycle.py's frozen constants against the same
    #      inclusion test surfaced two more primary, uncovered selectors of
    #      an already-established class -- DECISION_TIMEFRAME/
    #      REEVALUATION_TIMEFRAME (fixed timeframe selectors, the same class
    #      as regime_4h._REGIME_TIMEFRAME/bias_1h._BIAS_TIMEFRAME) and
    #      REQUIRED_METRIC_FAMILY (a per-family required-metric selector
    #      map, the same class as family_quality.FAMILY_MIN_COVERAGE/
    #      CONFIDENCE) -- now all included. CANDIDATE_MAX_AGE was reviewed
    #      and deliberately EXCLUDED: it is computed entirely from
    #      already-covered source constants (trend_pullback.
    #      PULLBACK_MAX_AGE_15M_BUCKETS, compression_breakout.
    #      COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS, confirmed_breakout.
    #      CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS) and the two
    #      timeframe selectors above, so manifesting it too would be
    #      double coverage of the same drift. None of these four
    #      constants' own values changed. REQUIRED_METRIC_FAMILY is
    #      flattened to one leaf per family (`REQUIRED_METRIC_FAMILY__
    #      <family>`) rather than a nested dict, so every manifest leaf
    #      stays a plain scalar/string-list like every other module's own.
    "v2-rules-v0.2.0": "2da3d34adc3e217bbffe9aa22aa8de59664ecfa2457e7b29acda911a9653fb31",
}


def assert_rules_manifest_matches_version(rules_version: str) -> None:
    """Raise `V2RulesManifestError` unless the LIVE rules manifest's
    fingerprint exactly matches the expected fingerprint recorded for
    `rules_version`. Also raises if `rules_version` itself has no
    recorded expected fingerprint (an unrecognized/un-shipped version) --
    never silently treated as passing."""
    manifest = build_rules_manifest()
    actual = compute_rules_fingerprint(manifest)
    expected = EXPECTED_FINGERPRINTS_BY_RULES_VERSION.get(rules_version)
    if expected is None:
        raise V2RulesManifestError(
            f"no expected V2 rules fingerprint recorded for rules_version={rules_version!r}")
    if actual != expected:
        raise V2RulesManifestError(
            f"live V2 rules manifest fingerprint ({actual!r}) does not match the expected "
            f"fingerprint recorded for rules_version={rules_version!r} ({expected!r}) -- a "
            "version-participating V2 rule constant changed without a corresponding "
            "rules_version bump")
