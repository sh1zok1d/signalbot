"""
V2 identity configuration loader (SEPARATE from common/stage2_config.py, which
this module never reads, imports, or mutates).

Loads config/v2.yaml: the minimal `model_family` / `rules_version` identity
conventions frozen in docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3. This is
FOUNDATION-ONLY configuration — no detector/scoring/episode parameters live
here; see config/v2.yaml's own header comment for why.

No hot reload / file watching, no environment-variable override: every value
comes from the checked-in YAML file only, so `V2Config.load()` is
deterministic across processes/hosts. Unknown keys in the `v2:` block raise
rather than being silently ignored, so a config typo fails loudly instead of
resolving to whatever default the missing key would have produced.

Layering note: `MODEL_FAMILY` and the `rules_version` naming-convention
validator live here (not in `analytics/forecasting_v2/identity.py`) because
this codebase's existing layering is one-directional — `analytics/` already
imports from `common/` throughout (e.g. `analytics/feature_engine/` reads
`common/stage2_config.py`), and `common/` never imports from `analytics/`.
Putting the single source of truth in the lower layer and having
`analytics/forecasting_v2/identity.py` import it from here keeps exactly one
place that defines the `v2-rules-v<major>.<minor>.<patch>` namespace, without
introducing a new backwards dependency.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
V2_CONFIG_PATH = ROOT_DIR / "config" / "v2.yaml"

# The logical model_family constant V2 rows will carry once a model_family
# column/registry exists at the row level (docs/FORECASTING_ROADMAP.md §A).
# V1's own rows carry model_family="v1" implicitly (see
# storage/stage2_schema.sql's DB-owned DEFAULT 'v1' on forecast_predictions /
# forecast_outcomes) — never "v1" vs. "V2"/"2"/anything else ad hoc.
MODEL_FAMILY = "v2"

# v2-rules-v<major>.<minor>.<patch> — the exact namespace
# docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3 freezes. A V1 rule_version
# (e.g. "forecast-rules-v0.1.0") can never match this pattern, and vice versa
# — the two namespaces are disjoint by construction (differing prefixes).
RULES_VERSION_RE = re.compile(r"^v2-rules-v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

_REQUIRED_KEYS = ("enabled", "model_family", "rules_version")
_ALLOWED_KEYS = frozenset(_REQUIRED_KEYS)


class V2ConfigError(ValueError):
    """Any V2 identity-config validation/resolution failure (explicit, no
    fallback — mirrors common.stage2_config.Stage2ConfigError's posture)."""


def validate_rules_version(value: Any) -> str:
    """Validate a candidate `rules_version` string against the frozen
    `v2-rules-v<major>.<minor>.<patch>` namespace. Returns it unchanged on
    success (never coerces/normalizes); raises V2ConfigError otherwise. Pure:
    no I/O, no side effects."""
    if not isinstance(value, str) or not value:
        raise V2ConfigError(
            f"rules_version must be a non-empty string, got {value!r}")
    if not RULES_VERSION_RE.match(value):
        raise V2ConfigError(
            f"rules_version {value!r} does not match the frozen "
            "'v2-rules-v<major>.<minor>.<patch>' namespace "
            "(V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3) — refusing to accept "
            "a V1-style rule_version or any other unrecognized shape")
    return value


class V2Config:
    """Thin, strictly-validated wrapper around config/v2.yaml's `v2:` block.

    Deliberately tiny: identity/foundation configuration only (see
    config/v2.yaml's header). Does not read, import, or depend on
    common.stage2_config.Stage2Config in any way — the two configs are
    independent by construction, not merely by convention (see
    tests/common/test_v2_stage2_isolation.py, which proves a rules_version
    change here cannot affect Stage2Config's resolved config / config_hash /
    calculation_version)."""

    __slots__ = ("_enabled", "_model_family", "_rules_version")

    def __init__(self, *, enabled: bool, model_family: str, rules_version: str):
        self._enabled = enabled
        self._model_family = model_family
        self._rules_version = rules_version

    @classmethod
    def load(cls, path: Path = V2_CONFIG_PATH) -> "V2Config":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, Mapping):
            raise V2ConfigError(f"{path}: top-level YAML must be a mapping")
        if "v2" not in raw:
            raise V2ConfigError(f"{path}: missing required top-level key: 'v2'")
        block = raw["v2"]
        if not isinstance(block, Mapping):
            raise V2ConfigError(f"{path}: 'v2' must be a mapping")
        return cls.from_mapping(block)

    @classmethod
    def from_mapping(cls, block: Mapping[str, Any]) -> "V2Config":
        """Validate an already-parsed `v2:` mapping and build a V2Config.
        Split out from `load()` so tests can exercise validation without
        touching the filesystem."""
        missing = [k for k in _REQUIRED_KEYS if k not in block]
        if missing:
            raise V2ConfigError(f"v2 config missing required key(s): {missing}")
        unknown = sorted(set(block) - _ALLOWED_KEYS)
        if unknown:
            raise V2ConfigError(
                f"v2 config has unknown key(s): {unknown} — refusing to "
                "silently ignore a possible typo")

        enabled = block["enabled"]
        if not isinstance(enabled, bool):
            raise V2ConfigError(
                f"v2.enabled must be a bool, got {type(enabled).__name__}")

        model_family = block["model_family"]
        if not isinstance(model_family, str) or model_family != MODEL_FAMILY:
            raise V2ConfigError(
                f"v2.model_family must be exactly {MODEL_FAMILY!r}, got {model_family!r}")

        rules_version = validate_rules_version(block["rules_version"])

        return cls(enabled=enabled, model_family=model_family, rules_version=rules_version)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def model_family(self) -> str:
        return self._model_family

    @property
    def rules_version(self) -> str:
        return self._rules_version

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (f"V2Config(enabled={self._enabled!r}, "
                f"model_family={self._model_family!r}, "
                f"rules_version={self._rules_version!r})")
