"""
Deterministic canonical JSON + hashing for Stage 2 computation identity.

Everything here is pure and reproducible: no timestamps, no cwd, no hostname,
no random values, and NO subprocess at module import. `calculation_version`
follows the spec §10 formula exactly.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from collections.abc import Mapping
from typing import Any, Optional


class VersioningError(RuntimeError):
    """Raised when a version input cannot be determined and no explicit value
    was provided (never falls back to a silent 'unknown')."""


def _to_plain(obj: Any) -> Any:
    """Recursively convert to plain JSON-safe types.

    Accepts any Mapping (including MappingProxyType) and any list/tuple — so an
    immutable resolved config (nested MappingProxyType + tuples) hashes exactly
    like its plain-dict/list equivalent. Rejects non-finite floats and any
    unsupported type explicitly (never silently coerces).
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"non-finite float not allowed in canonical JSON: {obj!r}")
        return obj
    if isinstance(obj, Mapping):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    raise TypeError(f"unsupported type for canonical JSON: {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, stable compact separators, UTF-8.

    The same semantic mapping always serializes identically regardless of the
    original key insertion order (and regardless of dict-vs-MappingProxyType or
    list-vs-tuple), so hashes are stable across machines/runs.
    """
    return json.dumps(
        _to_plain(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def config_hash(resolved_config: dict) -> str:
    """sha256 (full 64-char lowercase hex) of the resolved config's canonical
    JSON. Two semantically-equal configs hash identically."""
    payload = canonical_json(resolved_config).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_calculation_version(feature_schema_version: int,
                                cfg_hash: str,
                                code_version: str) -> str:
    """calculation_version = sha256(canonical_json({feature_schema_version,
    config_hash, code_version}))[:16] — 16 lowercase hex chars (spec §10).

    Pure: takes code_version explicitly, never resolves it here. Changing any
    of the three inputs changes the result.
    """
    if not isinstance(feature_schema_version, int) or isinstance(feature_schema_version, bool):
        raise VersioningError(
            f"feature_schema_version must be an int, got {type(feature_schema_version).__name__}")
    if not isinstance(cfg_hash, str) or not cfg_hash:
        raise VersioningError("config_hash must be a non-empty string")
    if not isinstance(code_version, str) or not code_version.strip():
        raise VersioningError("code_version must be a non-empty string (refusing silent 'unknown')")
    payload = {
        "feature_schema_version": feature_schema_version,
        "config_hash": cfg_hash,
        "code_version": code_version,
    }
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return digest[:16]


def resolve_code_version(explicit: Optional[str] = None, *,
                         env_var: str = "STAGE2_CODE_VERSION",
                         allow_git: bool = True) -> str:
    """Resolve the analytics code version.

    Order: explicit argument > environment variable > `git describe`. If none
    yields a value, raise VersioningError — an active Stage 2 calculation must
    never proceed with a silent 'unknown'. This may run `git describe`, but ONLY
    when called (never at import time).
    """
    if explicit is not None and explicit.strip():
        return explicit.strip()
    env_val = os.environ.get(env_var)
    if env_val and env_val.strip():
        return env_val.strip()
    if allow_git:
        try:
            out = subprocess.run(
                ["git", "describe", "--always", "--dirty", "--tags"],
                capture_output=True, text=True, timeout=5, check=True,
            )
            desc = out.stdout.strip()
            if desc:
                return desc
        except Exception:  # noqa: BLE001 - fall through to explicit error
            pass
    raise VersioningError(
        "cannot determine code_version: pass it explicitly or set "
        f"${env_var} (git describe unavailable)"
    )
