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
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from common.versioning import config_hash as _config_hash

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE2_CONFIG_PATH = ROOT_DIR / "config" / "stage2.yaml"

SUPPORTED_MARKET_TYPES = ("perp",)
_REQUIRED_DEFAULT_KEYS = ("percentile_windows", "timeframes", "data_confidence", "warmup")


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


class ResolvedSymbolConfig:
    """Immutable, deep-copied resolved config for one symbol."""

    __slots__ = ("_data", "symbol", "tier", "enabled", "market_types")

    def __init__(self, symbol: str, data: dict):
        self.symbol = symbol
        self.tier = data["tier"]
        self.enabled = bool(data["enabled"])
        self.market_types = tuple(data["market_types"])
        self._data = data  # already deep-copied by caller

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def as_dict(self) -> Mapping:
        """Read-only view of the full resolved dict (used for config_hash)."""
        return MappingProxyType(self._data)

    def config_hash(self) -> str:
        """sha256 of the resolved config — order-independent by construction."""
        return _config_hash(self._data)


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

        if not isinstance(self._raw["asset_tiers"], Mapping):
            raise Stage2ConfigError("asset_tiers must be a mapping")
        if not isinstance(self._raw["symbols"], Mapping) or not self._raw["symbols"]:
            raise Stage2ConfigError("symbols must be a non-empty mapping")
        # validate each declared symbol resolves cleanly (fail fast at load)
        for sym in self._raw["symbols"]:
            self.resolve(sym)

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
