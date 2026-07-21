"""
Stage 2 configuration loader (SEPARATE from Stage 1's common/config.py, which is
not touched). Familiar shape: `@classmethod load`, `get`, `__getitem__`.

Resolution order (spec §3): global `defaults` -> `asset_tiers[tier]` override ->
`symbols[symbol]` override, with the SYMBOL winning. Nested mappings are deep
merged. The parsed YAML is never mutated; a resolved config is a separate,
deep-copied, read-only object. There is no fallback to BTCUSDT and no silent
typo normalization — unknown symbol/tier, missing keys, bad types/ranges and
unsupported market types all raise explicitly.

No hot reload / file watching.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from common.versioning import config_hash as _config_hash

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE2_CONFIG_PATH = ROOT_DIR / "config" / "stage2.yaml"

SUPPORTED_MARKET_TYPES = ("perp",)
_REQUIRED_DEFAULT_KEYS = ("percentile_windows", "timeframes", "data_confidence",
                          "warmup", "outliers", "percentiles")

# Percentile Contract Revision 0.2.4 (frozen). Confidence-tier span thresholds
# (calendar days): three ints > 0, strictly increasing. See STAGE2_SPEC.md §12.
_CONFIDENCE_TIER_KEYS = ("none_below_days", "low_below_days", "building_below_days")

# Consensus Contract Revision 0.2.3 (frozen). Data Confidence weights: each
# component weight is finite and >= 0, coverage must be > 0, and the three MUST
# sum to exactly 1.0 (within float tolerance). See docs/STAGE2_SPEC.md §11.
_CONFIDENCE_WEIGHT_KEYS = ("coverage", "agreement", "dispersion")
_WEIGHT_SUM_TOL = 1e-9


class Stage2ConfigError(ValueError):
    """Any Stage 2 config validation / resolution failure (explicit, no fallback)."""


def _deep_merge(base: Mapping, override: Mapping) -> dict:
    """Return a NEW dict: base deep-merged with override (override wins). Nested
    mappings merge recursively; lists/scalars are replaced. Inputs untouched."""
    out = copy.deepcopy(dict(base))
    for k, v in override.items():
        if k in out and isinstance(out[k], Mapping) and isinstance(v, Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _freeze(obj: Any) -> Any:
    """Recursively make a structure DEEPLY immutable: every nested mapping
    becomes a MappingProxyType and every nested list becomes a tuple."""
    if isinstance(obj, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(v) for v in obj)
    return obj


def _thaw(obj: Any) -> Any:
    """Inverse of _freeze: produce an independent, fully-mutable plain copy
    (MappingProxyType -> dict, tuple -> list)."""
    if isinstance(obj, Mapping):
        return {k: _thaw(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_thaw(v) for v in obj]
    return obj


class ResolvedSymbolConfig:
    """DEEPLY immutable resolved config for one symbol.

    `.data` is a deeply-frozen view (nested MappingProxyType / tuple) that a
    caller cannot mutate at any depth. `as_dict()` returns a fresh, independent,
    fully-mutable deep copy each call (mutating it never affects this object or
    the loader). config_hash is computed over the frozen data and equals the
    hash of the equivalent plain dict (canonical_json normalizes both)."""

    __slots__ = ("symbol", "tier", "enabled", "market_types", "_frozen")

    def __init__(self, symbol: str, data: dict):
        self.symbol = symbol
        self.tier = data["tier"]
        self.enabled = bool(data["enabled"])
        self.market_types = tuple(data["market_types"])
        self._frozen = _freeze(copy.deepcopy(data))

    @property
    def data(self):
        """Deeply-immutable view of the full resolved config."""
        return self._frozen

    def __getitem__(self, key: str) -> Any:
        return self._frozen[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._frozen.get(key, default)

    def as_dict(self) -> dict:
        """Independent, fully-mutable deep copy (safe to mutate freely)."""
        return _thaw(self._frozen)

    def config_hash(self) -> str:
        """sha256 of the resolved config — order-independent by construction and
        identical whether computed from the frozen or plain form."""
        return _config_hash(self._frozen)


class Stage2Config:
    def __init__(self, raw: dict):
        # Store a private deep copy so the caller's dict can never be mutated
        # through us, and vice versa.
        self._raw = copy.deepcopy(raw)

    @classmethod
    def load(cls, path: Path = STAGE2_CONFIG_PATH) -> "Stage2Config":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, Mapping):
            raise Stage2ConfigError(f"{path}: top-level YAML must be a mapping")
        obj = cls(dict(raw))
        obj._validate()
        return obj

    # -- dict-like access to the raw parsed config -------------------------
    def __getitem__(self, key: str) -> Any:
        return self._raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    # -- explicit reads ----------------------------------------------------
    @property
    def enabled(self) -> bool:
        """stage2.enabled, read explicitly (defaults to False if absent)."""
        stage2 = self._raw.get("stage2", {})
        val = stage2.get("enabled", False)
        if not isinstance(val, bool):
            raise Stage2ConfigError("stage2.enabled must be a boolean")
        return val

    @property
    def config_version(self) -> str:
        v = self._raw.get("stage2", {}).get("config_version")
        if not isinstance(v, str) or not v:
            raise Stage2ConfigError("stage2.config_version must be a non-empty string")
        return v

    @property
    def feature_schema_version(self) -> int:
        v = self._raw.get("stage2", {}).get("feature_schema_version")
        if not isinstance(v, int) or isinstance(v, bool):
            raise Stage2ConfigError("stage2.feature_schema_version must be an int")
        return v

    # -- validation --------------------------------------------------------
    def _validate(self) -> None:
        for key in ("stage2", "defaults", "asset_tiers", "symbols"):
            if key not in self._raw:
                raise Stage2ConfigError(f"missing required top-level key: {key!r}")
        # trigger the typed checks
        _ = self.enabled
        _ = self.config_version
        _ = self.feature_schema_version

        defaults = self._raw["defaults"]
        if not isinstance(defaults, Mapping):
            raise Stage2ConfigError("defaults must be a mapping")
        for key in _REQUIRED_DEFAULT_KEYS:
            if key not in defaults:
                raise Stage2ConfigError(f"defaults missing required key: {key!r}")
        if not isinstance(defaults["percentile_windows"], list) or not defaults["percentile_windows"]:
            raise Stage2ConfigError("defaults.percentile_windows must be a non-empty list")
        if not isinstance(defaults["timeframes"], list) or not defaults["timeframes"]:
            raise Stage2ConfigError("defaults.timeframes must be a non-empty list")
        dc = defaults["data_confidence"]
        if not isinstance(dc, Mapping) or "minimum_exchange_coverage" not in dc:
            raise Stage2ConfigError("defaults.data_confidence.minimum_exchange_coverage required")
        mec = dc["minimum_exchange_coverage"]
        if not isinstance(mec, int) or isinstance(mec, bool) or mec < 1:
            raise Stage2ConfigError("minimum_exchange_coverage must be an int >= 1")
        self._validate_confidence_weights(dc)
        self._validate_outliers(defaults["outliers"])
        self._validate_percentiles(defaults["percentiles"])

        if not isinstance(self._raw["asset_tiers"], Mapping):
            raise Stage2ConfigError("asset_tiers must be a mapping")
        if not isinstance(self._raw["symbols"], Mapping) or not self._raw["symbols"]:
            raise Stage2ConfigError("symbols must be a non-empty mapping")
        # validate each declared symbol resolves cleanly (fail fast at load)
        for sym in self._raw["symbols"]:
            self.resolve(sym)

    @staticmethod
    def _finite_number(value: Any, name: str) -> float:
        """A real, finite number (bool rejected, NaN/Inf rejected)."""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise Stage2ConfigError(f"{name} must be a number, got {type(value).__name__}")
        v = float(value)
        if not math.isfinite(v):
            raise Stage2ConfigError(f"{name} must be finite, got {value!r}")
        return v

    def _validate_confidence_weights(self, dc: Mapping) -> None:
        """Data Confidence weights (Revision 0.2.3): the three components are
        present, finite, >= 0; coverage > 0; and they sum to exactly 1.0 within
        a small float tolerance. Weights land in the resolved config and thus in
        config_hash / calculation_version."""
        if "weights" not in dc or not isinstance(dc["weights"], Mapping):
            raise Stage2ConfigError("data_confidence.weights must be a mapping")
        weights = dc["weights"]
        for key in _CONFIDENCE_WEIGHT_KEYS:
            if key not in weights:
                raise Stage2ConfigError(f"data_confidence.weights missing {key!r}")
        extra = set(weights) - set(_CONFIDENCE_WEIGHT_KEYS)
        if extra:
            raise Stage2ConfigError(
                f"data_confidence.weights has unknown keys: {sorted(extra)}")
        values = {}
        for key in _CONFIDENCE_WEIGHT_KEYS:
            w = self._finite_number(weights[key], f"data_confidence.weights.{key}")
            if w < 0:
                raise Stage2ConfigError(
                    f"data_confidence.weights.{key} must be >= 0, got {w!r}")
            values[key] = w
        if values["coverage"] <= 0:
            raise Stage2ConfigError("data_confidence.weights.coverage must be > 0")
        total = sum(values.values())
        if abs(total - 1.0) > _WEIGHT_SUM_TOL:
            raise Stage2ConfigError(
                f"data_confidence.weights must sum to 1.0, got {total!r}")

    def _validate_outliers(self, outliers: Any) -> None:
        """Outlier config (Revision 0.2.3): a finite, strictly-positive robust-z
        threshold. The robust-z scale constant is fixed in code, never config."""
        if not isinstance(outliers, Mapping):
            raise Stage2ConfigError("defaults.outliers must be a mapping")
        if "robust_z_threshold" not in outliers:
            raise Stage2ConfigError("outliers.robust_z_threshold is required")
        extra = set(outliers) - {"robust_z_threshold"}
        if extra:
            raise Stage2ConfigError(f"outliers has unknown keys: {sorted(extra)}")
        thr = self._finite_number(outliers["robust_z_threshold"],
                                   "outliers.robust_z_threshold")
        if thr <= 0:
            raise Stage2ConfigError(
                f"outliers.robust_z_threshold must be > 0, got {thr!r}")

    def _validate_percentiles(self, percentiles: Any) -> None:
        """Percentile confidence-tier thresholds (Revision 0.2.4): a
        'confidence_tiers' mapping of exactly three int day-spans, each > 0 and
        strictly increasing. Sourced here so the pure percentile core never reads
        the Stage 1 Config. Enters config_hash / calculation_version."""
        if not isinstance(percentiles, Mapping):
            raise Stage2ConfigError("defaults.percentiles must be a mapping")
        if "confidence_tiers" not in percentiles or not isinstance(
                percentiles["confidence_tiers"], Mapping):
            raise Stage2ConfigError("defaults.percentiles.confidence_tiers must be a mapping")
        tiers = percentiles["confidence_tiers"]
        if set(tiers) != set(_CONFIDENCE_TIER_KEYS):
            raise Stage2ConfigError(
                f"percentiles.confidence_tiers must have exactly "
                f"{list(_CONFIDENCE_TIER_KEYS)}, got {sorted(tiers)}")
        values = []
        for key in _CONFIDENCE_TIER_KEYS:
            v = tiers[key]
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                raise Stage2ConfigError(
                    f"percentiles.confidence_tiers.{key} must be an int > 0, got {v!r}")
            values.append(v)
        if not (values[0] < values[1] < values[2]):
            raise Stage2ConfigError(
                f"percentiles.confidence_tiers must be strictly increasing "
                f"(none_below < low_below < building_below), got {values}")

    # -- resolution --------------------------------------------------------
    def resolve(self, symbol: str) -> ResolvedSymbolConfig:
        """Resolve defaults -> tier -> symbol for `symbol`. Explicit errors; no
        BTCUSDT fallback; returns a separate immutable object."""
        symbols = self._raw["symbols"]
        if symbol not in symbols:
            raise Stage2ConfigError(
                f"unknown symbol {symbol!r}; declared: {sorted(symbols)}")
        sym_over = symbols[symbol]
        if not isinstance(sym_over, Mapping):
            raise Stage2ConfigError(f"symbols.{symbol} must be a mapping")

        tier = sym_over.get("tier")
        if tier is None:
            raise Stage2ConfigError(f"symbols.{symbol}.tier is required")
        tiers = self._raw["asset_tiers"]
        if tier not in tiers:
            raise Stage2ConfigError(
                f"unknown asset tier {tier!r} for {symbol}; declared: {sorted(tiers)}")
        tier_over = tiers.get(tier) or {}
        if not isinstance(tier_over, Mapping):
            raise Stage2ConfigError(f"asset_tiers.{tier} must be a mapping (or empty)")

        resolved = _deep_merge(self._raw["defaults"], tier_over)
        resolved = _deep_merge(resolved, sym_over)

        # required resolved keys + market_type validation
        if "enabled" not in resolved:
            raise Stage2ConfigError(f"{symbol}: resolved config missing 'enabled'")
        mts = resolved.get("market_types")
        if not isinstance(mts, list) or not mts:
            raise Stage2ConfigError(f"{symbol}: market_types must be a non-empty list")
        for mt in mts:
            if mt not in SUPPORTED_MARKET_TYPES:
                raise Stage2ConfigError(
                    f"{symbol}: unsupported market_type {mt!r} "
                    f"(supported: {list(SUPPORTED_MARKET_TYPES)}; spot not implemented)")
        return ResolvedSymbolConfig(symbol, resolved)

    def config_hash(self, symbol: str) -> str:
        return self.resolve(symbol).config_hash()
