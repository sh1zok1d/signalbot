"""Operational tombstones for CLOSED research lines (entry-layer guard).

A closed line's frozen code and records stay byte-identical; this module sits in front of
them. Each guarded package calls `install(__name__)` from its `__init__.py` (not hash-bound):

- **CLI.** `python -m <package>.<module> <official args>` (or the file path) is refused before
  the module runs.
- **Programmatic.** When a guarded module is imported, its official entry points are wrapped:
  a call refuses before any of the original code runs. The wrapper reaches the original
  through `wrapper.__wrapped__`.

Registry: `docs/research/CLOSED_RESEARCH_LINES_V1.json`. A refusal is lifted only by the line's
reopen-authorization artifact, a new explicit owner decision; none exists.
"""
from __future__ import annotations

import functools
import importlib.abc
import importlib.machinery
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "docs/research/CLOSED_RESEARCH_LINES_V1.json"


class ClosedResearchLineError(RuntimeError):
    """The research line is CLOSED; its official entry points are refused."""


def registry() -> dict:
    return json.loads(REGISTRY.read_text())


def _line_for_package(package: str) -> Optional[dict]:
    for line in registry()["LINES"]:
        if package in line["PACKAGES"]:
            return line
    return None


def reopen_authorized(line: Mapping[str, Any], entrypoint: str) -> bool:
    """True only for a valid owner reopen-authorization artifact naming this line and entry point."""
    path = REPO / line["REOPEN_AUTHORIZATION_PATH"]
    if not path.exists():
        return False
    try:
        auth = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    record = auth.get("OWNER_DECISION_RECORD")
    return (auth.get("LINE_ID") == line["LINE_ID"] and auth.get("OWNER_AUTHORIZED") is True
            and entrypoint in (auth.get("ENTRYPOINTS") or []) and bool(record) and (REPO / record).exists())


def _message(line: Mapping[str, Any], entrypoint: str) -> str:
    return (f"{entrypoint}: research line {line['LINE_ID']} is CLOSED ({line['CLOSURE_RECORD']}); "
            f"official execution is refused. Reopening needs a new explicit owner authorization at "
            f"{line['REOPEN_AUTHORIZATION_PATH']} (none exists).")


# ----------------------------------------------------------------------------- CLI
def _invoked_module(argv: Sequence[str]) -> tuple[Optional[str], list[str], Optional[str]]:
    """(module name if `-m`, the remaining args, script path if run by file)."""
    argv = list(argv)
    for i, a in enumerate(argv[1:], start=1):
        if a == "-m" and i + 1 < len(argv):
            return argv[i + 1], argv[i + 2:], None
        if a == "-c":
            return None, [], None
        if not a.startswith("-"):
            return None, argv[i + 1:], a
    return None, [], None


def cli_violation(argv: Sequence[str], line: Mapping[str, Any]) -> Optional[str]:
    """Entry point refused for this command line, or None. Pure; used by the tests."""
    module, args, script = _invoked_module(argv)
    for rule in line["CLI"]:
        target = rule["MODULE"]
        hit = module == target or (script is not None and
                                   Path(script).resolve() == (REPO / (target.replace(".", "/") + ".py")).resolve())
        if not hit:
            continue
        refused = set(rule.get("REFUSED_ARGS", []))
        if any(a in refused for a in args):
            return f"{target} {' '.join(args)}".strip()
        if rule.get("REFUSE_UNLESS_ALLOWED") and not any(a in set(rule.get("ALLOWED_ARGS", [])) for a in args):
            return f"{target} {' '.join(args)}".strip()
    return None


# ----------------------------------------------------------------------------- programmatic
def _refusal_class(module, base_name: Optional[str]):
    base = getattr(module, base_name) if base_name else RuntimeError
    if base is RuntimeError:
        return ClosedResearchLineError
    return type(f"ClosedLineRefused_{base.__name__}", (ClosedResearchLineError, base), {})


def _wrap(module, line: Mapping[str, Any], spec: Mapping[str, Any]) -> None:
    original = getattr(module, spec["FUNCTION"])
    if getattr(original, "_closed_line_guard", False):
        return
    entrypoint = f"{module.__name__}.{spec['FUNCTION']}"
    refuse = _refusal_class(module, spec.get("REFUSAL_BASE"))
    only_if = spec.get("ONLY_IF_ARG_TRUE")
    signature = inspect.signature(original)

    @functools.wraps(original)
    def guarded(*args, **kwargs):
        active = True
        if only_if:
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            active = bool(bound.arguments.get(only_if))
        if active and not reopen_authorized(line, entrypoint):
            raise refuse(_message(line, entrypoint))
        return guarded.__wrapped__(*args, **kwargs)

    guarded._closed_line_guard = True
    setattr(module, spec["FUNCTION"], guarded)


class _GuardedLoader(importlib.abc.Loader):
    def __init__(self, inner, line, specs):
        self._inner, self._line, self._specs = inner, line, specs

    def create_module(self, spec):
        return self._inner.create_module(spec)

    def exec_module(self, module):
        self._inner.exec_module(module)
        for s in self._specs:
            _wrap(module, self._line, s)

    def get_code(self, fullname):          # runpy / tracebacks
        return self._inner.get_code(fullname)

    def get_source(self, fullname):
        return self._inner.get_source(fullname)


class _GuardFinder(importlib.abc.MetaPathFinder):
    def __init__(self, line, by_module):
        self._line, self._by_module = line, by_module

    def find_spec(self, fullname, path, target=None):
        specs = self._by_module.get(fullname)
        if not specs:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        spec.loader = _GuardedLoader(spec.loader, self._line, specs)
        return spec


def install(package: str) -> None:
    """Called from a guarded package's __init__.py."""
    line = _line_for_package(package)
    if line is None:
        return
    violation = cli_violation(getattr(sys, "orig_argv", sys.argv), line)
    if violation and not reopen_authorized(line, violation.split()[0]):
        raise SystemExit(_message(line, violation))
    by_module: dict = {}
    for spec in line["ENTRYPOINTS"]:
        if spec["MODULE"].startswith(package + "."):
            by_module.setdefault(spec["MODULE"], []).append(spec)
    for name, specs in by_module.items():
        loaded = sys.modules.get(name)
        if loaded is not None:
            for s in specs:
                _wrap(loaded, line, s)
    if not any(isinstance(f, _GuardFinder) and f._by_module == by_module for f in sys.meta_path):
        sys.meta_path.insert(0, _GuardFinder(line, by_module))
