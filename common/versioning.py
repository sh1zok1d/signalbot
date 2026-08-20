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
from pathlib import Path
from typing import Any, Optional, Sequence


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


# ============================================================================
# Path-scoped feature-computation code identity (V2-H2a;
# docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.3a).
#
# `resolve_code_version()` above resolves its git fallback via a WHOLE-REPO
# `git describe --dirty` -- any uncommitted change ANYWHERE in the working
# tree (a docs edit, a Stage 6 module, a Telegram notifier change) flips the
# `-dirty` suffix and therefore forks Stage 2's `calculation_version`
# namespace, even though none of those changes touch feature-computation
# semantics. §3.3a is explicit that Stage 2 feature-computation identity
# "must represent ONLY feature-computation semantics" and that an unrelated
# repo change "MUST NOT" fork it. `resolve_feature_code_version()` is the
# conforming replacement: it is scoped to an explicit set of
# feature-computation-relevant paths and is provably insensitive to any
# change outside them, committed or not.
# ============================================================================

# The feature-computation code surface that participates in Stage 2's
# `calculation_version` identity. §3.3a's own literal wording is:
# "scoped to `analytics/feature_engine/`+`analytics/percentile_engine/` and
# their direct dependencies" -- this is that scope, resolved by DIRECT
# IMPORT-GRAPH INSPECTION (never introspected/guessed at call time), not
# merely the two paths a first pass happened to touch (Qodo amendment
# round 1, finding 2: `analytics/percentile_engine/` and several direct
# feature-engine dependencies were originally omitted even though they
# demonstrably affect Stage 2 output).
#
# Full transitive closure, confirmed by reading every `from`/`import` line
# in both packages:
#   analytics/feature_engine/*.py    imports common.instrument_metadata,
#                                     common.stage2_config, common.versioning,
#                                     symbols.registry
#   analytics/percentile_engine/*.py imports symbols.registry
#   common/instrument_metadata.py    imports common.symbol_mapper
#   common/stage2_config.py          imports common.versioning (already listed)
#   symbols/registry.py              imports common.capabilities
#   common/symbol_mapper.py          imports nothing further (leaf)
#   common/capabilities.py           imports nothing further (leaf)
# `analytics/data_quality/` remains excluded: it is not imported by either
# package, so it does not participate in COMPUTING a feature vector's or a
# percentile snapshot's identity. An explicit, reviewable list -- same
# "never `vars()`/`dir()` introspection" philosophy
# `analytics/forecasting_v2/rules_manifest.py` already uses for the analogous
# problem on the V2-rules side. `tests/common/test_versioning.py` proves,
# via hermetic throwaway git repos mirroring this exact path set, that
# changing ANY one of these forks the resolved identity while an unrelated
# docs/Stage-6/Telegram-analog change does not.
DEFAULT_FEATURE_CODE_PATHS: "tuple[str, ...]" = (
    "analytics/feature_engine",
    "analytics/percentile_engine",
    "common/stage2_config.py",
    "common/versioning.py",
    "common/instrument_metadata.py",
    "common/symbol_mapper.py",
    "symbols/registry.py",
    "common/capabilities.py",
)


def _repo_root() -> Path:
    """This file's own repository root (`common/versioning.py` -> `common/`
    -> repo root). Computed from `__file__`, never from `os.getcwd()` -- a
    caller invoked from a different working directory must still resolve
    the same paths."""
    return Path(__file__).resolve().parent.parent


def _git_scoped(args: "list[str]", *, cwd: Path, timeout: float = 5) -> str:
    out = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=True,
    )
    return out.stdout


def resolve_feature_code_version(explicit: Optional[str] = None, *,
                                 env_var: str = "STAGE2_CODE_VERSION",
                                 paths: Sequence[str] = DEFAULT_FEATURE_CODE_PATHS,
                                 allow_git: bool = True,
                                 repo_root: Optional[Path] = None) -> str:
    """Resolve the Stage 2 FEATURE-computation code version, scoped to
    `paths` only (§3.3a). Order: explicit argument > environment variable >
    git, PATH-SCOPED to `paths` > raise. Never falls back to a whole-repo
    `git describe`/`--dirty` -- this is the entire point of this function
    existing alongside `resolve_code_version()`.

    Git resolution has two parts, both scoped to `paths`:
      1. The most recent commit that touched any of `paths`
         (`git log -1 --format=%H -- <paths>`) -- unaffected by commits that
         touch only files outside `paths`.
      2. Whether any of `paths` currently has an uncommitted change (working
         tree, staged, or untracked -- `git diff`/`git diff --cached`/
         `git ls-files --others` each scoped to `paths`). If so, a
         deterministic content hash of exactly those changed files (sorted
         path order, path + bytes) is appended as a `-dirty-<hex12>` suffix
         -- reproducible from the working tree alone, never a timestamp or
         anything nondeterministic. A change to a file OUTSIDE `paths`
         (dirty or not) can never affect this value, satisfying §3.3a's
         "MUST NOT fork" requirement directly, not just by convention.

    Raises `VersioningError` if none of explicit/env/git yields a value --
    this must never silently fall back to whole-repo `resolve_code_version()`
    or to `resolve_code_version()`'s own `'unknown'`-refusal posture; a
    caller wanting THAT fallback chain must ask for it explicitly."""
    if explicit is not None and explicit.strip():
        return explicit.strip()
    env_val = os.environ.get(env_var)
    if env_val and env_val.strip():
        return env_val.strip()
    if not allow_git:
        raise VersioningError(
            "cannot determine feature code_version: pass it explicitly, set "
            f"${env_var}, or enable git resolution (allow_git=False)"
        )
    if not paths:
        raise VersioningError("resolve_feature_code_version: paths must be non-empty")

    root = repo_root if repo_root is not None else _repo_root()
    path_args = list(paths)
    try:
        commit = _git_scoped(["log", "-1", "--format=%H", "--", *path_args], cwd=root).strip()
        working = set(_git_scoped(["diff", "--name-only", "--", *path_args], cwd=root).splitlines())
        staged = set(
            _git_scoped(["diff", "--cached", "--name-only", "--", *path_args], cwd=root).splitlines())
        untracked = set(
            _git_scoped(
                ["ls-files", "--others", "--exclude-standard", "--", *path_args], cwd=root
            ).splitlines())
    except Exception as exc:  # noqa: BLE001 - fall through to explicit error
        raise VersioningError(
            "cannot determine feature code_version: git path-scoped resolution failed "
            f"({type(exc).__name__}: {exc}) -- pass it explicitly or set ${env_var}"
        ) from exc

    dirty_files = sorted(working | staged | untracked)
    if not commit and not dirty_files:
        raise VersioningError(
            "cannot determine feature code_version: no commit touches the configured "
            f"feature-computation paths {tuple(path_args)!r} and none are dirty -- pass it "
            f"explicitly or set ${env_var}"
        )
    if not dirty_files:
        return commit

    hasher = hashlib.sha256()
    for rel_path in dirty_files:
        abs_path = root / rel_path
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\x00")
        if abs_path.exists() and abs_path.is_file():
            hasher.update(abs_path.read_bytes())
        else:
            hasher.update(b"<absent>")
        hasher.update(b"\x00")
    dirty_suffix = hasher.hexdigest()[:12]
    base = commit if commit else "none"
    return f"{base}-dirty-{dirty_suffix}"
