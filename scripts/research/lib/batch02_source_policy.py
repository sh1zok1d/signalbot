"""Static fail-closed policy for future Signalbot Batch02 runtime modules.

This is defense in depth around the runtime contracts in batch02_contracts.
It is intentionally strict: future B2-02+ code may transform already-loaded
in-memory data, but filesystem/parquet access, evidence mutation, frozen
Batch01 runtime reuse, dynamic imports, and alternate rolling-rank helpers are
not allowed in the future-B2 import closure.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class Batch02SourcePolicyError(RuntimeError):
    """Future Batch02 source violates an experiment-integrity policy."""


_FUTURE_B2_FILE = re.compile(r"^b2_(?!01)\d{2}.*\.py$")
_FROZEN_RUNTIME_PREFIXES = (
    "scripts.research.h01_",
    "scripts.research.h02_",
    "scripts.research.h03_",
    "scripts.research.h04_",
    "scripts.research.h05_",
    "scripts.research.b2_01_",
)
_TRUSTED_MODULES = {
    "scripts.research.lib.batch02_contracts",
}
_FORBIDDEN_DIRECT_MODULE_PREFIXES = (
    "scripts.research.lib.research_harness",
    "subprocess",
    "importlib",
    "duckdb",
    "fsspec",
)
_FORBIDDEN_BARE_CALLS = {
    "open",
    "eval",
    "exec",
    "__import__",
    "getattr",
}
_FORBIDDEN_IO_ATTRIBUTES = {
    # pathlib / os / shutil style mutation or direct filesystem access.
    "open",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "unlink",
    "remove",
    "rename",
    "replace",
    "rmdir",
    "rmtree",
    "move",
    # parquet / dataframe / array file readers.
    "read_table",
    "read_parquet",
    "ParquetFile",
    "dataset",
    "scan_parquet",
    "read_csv",
    "scan_csv",
    "read_json",
    "read_pickle",
    "read_feather",
    "read_ipc",
    "load",
    "loadtxt",
    "genfromtxt",
    "fromfile",
}
_FORBIDDEN_RANK_CALLS = {
    "rank",
    "rankdata",
    "percentileofscore",
    "searchsorted",
}
_FORBIDDEN_IMPORTED_SYMBOLS = {
    "read_table",
    "read_parquet",
    "ParquetFile",
    "dataset",
    "scan_parquet",
    "read_csv",
    "scan_csv",
    "read_json",
    "read_pickle",
    "read_feather",
    "read_ipc",
    "loadtxt",
    "genfromtxt",
    "fromfile",
}
_RANK_NAME = re.compile(r"(?:^|_)(?:rank|percentile|pctl)(?:_|$)", re.IGNORECASE)
_CANONICAL_RANK_NAME = "rolling_midrank_percentile"
_REQUIRED_RUNNER_CALLS = {
    "verify_batch02_code",
    "prepare_batch02_run",
    "persist_batch02_result",
}
_PROTECTED_BINDINGS = {
    *_REQUIRED_RUNNER_CALLS,
    _CANONICAL_RANK_NAME,
    "load_authorized_parquet_table",
}


@dataclass(frozen=True)
class SourceViolation:
    path: Path
    message: str
    lineno: int | None = None

    def render(self) -> str:
        where = str(self.path)
        if self.lineno is not None:
            where += f":{self.lineno}"
        return f"{where}: {self.message}"


def _module_name_for_path(repo_root: Path, path: Path) -> str:
    rel = path.relative_to(repo_root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_module(repo_root: Path, module: str) -> Path | None:
    if not module:
        return None
    rel = Path(*module.split("."))
    py = repo_root / rel.with_suffix(".py")
    if py.is_file():
        return py.resolve()
    init = repo_root / rel / "__init__.py"
    if init.is_file():
        return init.resolve()
    return None


def _resolve_import_from(
    *,
    repo_root: Path,
    current_path: Path,
    node: ast.ImportFrom,
) -> str:
    if node.level == 0:
        return node.module or ""

    current_module = _module_name_for_path(repo_root, current_path)
    package = current_module.split(".")
    if current_path.name != "__init__.py":
        package = package[:-1]
    if node.level > len(package):
        return ""
    prefix = package[: len(package) - node.level + 1]
    suffix = (node.module or "").split(".") if node.module else []
    return ".".join([*prefix, *suffix])


def _local_import_paths(
    *,
    repo_root: Path,
    current_path: Path,
    tree: ast.AST,
) -> set[Path]:
    out: set[Path] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                path = _resolve_module(repo_root, alias.name)
                if path is not None:
                    out.add(path)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(
                repo_root=repo_root,
                current_path=current_path,
                node=node,
            )
            base_path = _resolve_module(repo_root, base)
            if base_path is not None:
                out.add(base_path)
            for alias in node.names:
                candidate = f"{base}.{alias.name}" if base else alias.name
                path = _resolve_module(repo_root, candidate)
                if path is not None:
                    out.add(path)
    return out


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _import_origin(
    node: ast.Import | ast.ImportFrom,
    *,
    resolved_base: str = "",
) -> Iterable[tuple[str, str]]:
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.asname or alias.name.split(".")[0], alias.name
        return

    module = resolved_base or node.module or ""
    for alias in node.names:
        yield alias.asname or alias.name, f"{module}.{alias.name}".strip(".")


def _lint_module(
    *,
    repo_root: Path,
    path: Path,
    tree: ast.AST,
    is_runner: bool,
) -> list[SourceViolation]:
    violations: list[SourceViolation] = []
    canonical_imports: set[str] = set()
    canonical_calls: set[str] = set()
    context_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if (
                isinstance(node.value, ast.Call)
                and _call_name(node.value) == "prepare_batch02_run"
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        context_names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Call)
                and _call_name(node.value) == "prepare_batch02_run"
            ):
                context_names.add(node.target.id)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom):
                base = _resolve_import_from(
                    repo_root=repo_root,
                    current_path=path,
                    node=node,
                )
            else:
                base = ""

            for local_name, origin in _import_origin(node, resolved_base=base):
                origin_module = origin.rsplit(".", 1)[0] if "." in origin else origin
                if local_name in _PROTECTED_BINDINGS:
                    expected = (
                        "scripts.research.lib.batch02_contracts."
                        + local_name
                    )
                    if origin != expected:
                        violations.append(
                            SourceViolation(
                                path,
                                f"canonical Batch02 binding shadowed by import: "
                                f"{local_name} <- {origin}",
                                getattr(node, "lineno", None),
                            )
                        )
                if any(
                    origin.startswith(prefix)
                    for prefix in _FROZEN_RUNTIME_PREFIXES
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            f"future Batch02 may not import frozen runtime {origin}",
                            getattr(node, "lineno", None),
                        )
                    )
                if any(
                    origin.startswith(prefix)
                    for prefix in _FORBIDDEN_DIRECT_MODULE_PREFIXES
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            f"forbidden direct/dynamic I/O module import {origin}",
                            getattr(node, "lineno", None),
                        )
                    )
                if origin.split(".")[-1] in _FORBIDDEN_RANK_CALLS:
                    violations.append(
                        SourceViolation(
                            path,
                            f"alternate rank/percentile primitive import is forbidden: {origin}",
                            getattr(node, "lineno", None),
                        )
                    )
                if origin.split(".")[-1] in _FORBIDDEN_IMPORTED_SYMBOLS:
                    violations.append(
                        SourceViolation(
                            path,
                            f"forbidden direct I/O symbol import {origin}",
                            getattr(node, "lineno", None),
                        )
                    )
                if (
                    isinstance(node, ast.ImportFrom)
                    and base == "scripts.research.lib.batch02_contracts"
                    and local_name in {
                        *_REQUIRED_RUNNER_CALLS,
                        _CANONICAL_RANK_NAME,
                        "load_authorized_parquet_table",
                    }
                ):
                    # Aliasing canonical security-sensitive entry points is
                    # intentionally rejected so call-site policy is auditable.
                    original = next(
                        (
                            alias.name
                            for alias in node.names
                            if (alias.asname or alias.name) == local_name
                        ),
                        local_name,
                    )
                    if original != local_name:
                        violations.append(
                            SourceViolation(
                                path,
                                f"canonical Batch02 entry point may not be aliased: {origin}",
                                getattr(node, "lineno", None),
                            )
                        )
                    canonical_imports.add(local_name)

        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in _FORBIDDEN_RANK_CALLS:
                violations.append(
                    SourceViolation(
                        path,
                        f"alternate rank/percentile primitive call is forbidden: {name}",
                        getattr(node, "lineno", None),
                    )
                )
            if name in _FORBIDDEN_BARE_CALLS:
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden dynamic/filesystem call {name}",
                        getattr(node, "lineno", None),
                    )
                )
            if isinstance(node.func, ast.Attribute) and node.func.attr in _FORBIDDEN_IO_ATTRIBUTES:
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden direct I/O or mutation call .{node.func.attr}",
                        getattr(node, "lineno", None),
                    )
                )
            if name in _REQUIRED_RUNNER_CALLS | {
                _CANONICAL_RANK_NAME,
                "load_authorized_parquet_table",
            }:
                canonical_calls.add(name)

            if name in {"persist_batch02_result", "load_authorized_parquet_table"}:
                context_kw = next(
                    (kw.value for kw in node.keywords if kw.arg == "run_context"),
                    None,
                )
                if (
                    not isinstance(context_kw, ast.Name)
                    or context_kw.id not in context_names
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            f"{name} must receive run_context assigned from "
                            "prepare_batch02_run",
                            getattr(node, "lineno", None),
                        )
                    )

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in _PROTECTED_BINDINGS:
                violations.append(
                    SourceViolation(
                        path,
                        f"canonical Batch02 binding may not be shadowed: {node.name}",
                        node.lineno,
                    )
                )
            if node.name == "_git_sha":
                violations.append(
                    SourceViolation(
                        path,
                        "fallback _git_sha helper is forbidden",
                        node.lineno,
                    )
                )
            if (
                _RANK_NAME.search(node.name)
                and node.name != _CANONICAL_RANK_NAME
            ):
                violations.append(
                    SourceViolation(
                        path,
                        f"alternate rank/percentile helper is forbidden: {node.name}",
                        node.lineno,
                    )
                )

        if isinstance(node, ast.arg) and node.arg in _PROTECTED_BINDINGS:
            violations.append(
                SourceViolation(
                    path,
                    f"canonical Batch02 binding may not be shadowed by argument: "
                    f"{node.arg}",
                    getattr(node, "lineno", None),
                )
            )

        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store) and node.id in _PROTECTED_BINDINGS:
                violations.append(
                    SourceViolation(
                        path,
                        f"canonical Batch02 binding may not be reassigned: {node.id}",
                        getattr(node, "lineno", None),
                    )
                )
            if (
                _RANK_NAME.search(node.id)
                and node.id != _CANONICAL_RANK_NAME
                and not node.id.startswith("bootstrap_")
            ):
                # Names in prose/docstrings are irrelevant; executable symbol
                # names that advertise a second rank/percentile path are not.
                violations.append(
                    SourceViolation(
                        path,
                        f"alternate rank/percentile symbol is forbidden: {node.id}",
                        getattr(node, "lineno", None),
                    )
                )

    if is_runner:
        missing_imports = _REQUIRED_RUNNER_CALLS - canonical_imports
        missing_calls = _REQUIRED_RUNNER_CALLS - canonical_calls
        if missing_imports:
            violations.append(
                SourceViolation(
                    path,
                    f"runner missing canonical imports: {sorted(missing_imports)}",
                )
            )
        if missing_calls:
            violations.append(
                SourceViolation(
                    path,
                    f"runner missing canonical calls: {sorted(missing_calls)}",
                )
            )

    return violations


def _contains_prepare_call(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise Batch02SourcePolicyError(
            f"unable to inspect potential Batch02 source {path}: {exc}"
        ) from exc
    return any(
        isinstance(node, ast.Call)
        and _call_name(node) == "prepare_batch02_run"
        for node in ast.walk(tree)
    )


def _discover_future_b2_entrypoints(research: Path) -> list[Path]:
    out: list[Path] = []
    for path in research.rglob("*.py"):
        if _FUTURE_B2_FILE.match(path.name) or _contains_prepare_call(path):
            # Trusted contract implementation contains no prepare call; source
            # policy itself is likewise not an experiment entrypoint.
            out.append(path.resolve())
    return sorted(set(out))


def validate_batch02_source_tree(
    research_dir: Path,
    *,
    repo_root: Path | None = None,
) -> tuple[Path, ...]:
    """Validate every future B2 entrypoint and its local import closure.

    Trusted contract modules are not recursively linted here; they have direct
    behavioral tests. All other repository-local helpers imported by B2-02+
    are recursively scanned, including helpers under lib/, experiments/, or
    other repository packages.
    """
    research = research_dir.resolve()
    root = (repo_root or research.parents[1]).resolve()
    entrypoints = _discover_future_b2_entrypoints(research)
    if not entrypoints:
        return ()

    pending = list(entrypoints)
    visited: set[Path] = set()
    violations: list[SourceViolation] = []

    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)

        module = _module_name_for_path(root, path)
        if module in _TRUSTED_MODULES:
            continue

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            raise Batch02SourcePolicyError(
                f"unable to inspect future Batch02 source {path}: {exc}"
            ) from exc

        has_prepare_call = any(
            isinstance(node, ast.Call)
            and _call_name(node) == "prepare_batch02_run"
            for node in ast.walk(tree)
        )
        is_runner = bool(
            has_prepare_call
            or (
                _FUTURE_B2_FILE.match(path.name)
                and not path.name.endswith("_lib.py")
            )
        )
        violations.extend(
            _lint_module(
                repo_root=root,
                path=path,
                tree=tree,
                is_runner=is_runner,
            )
        )

        for imported_path in _local_import_paths(
            repo_root=root,
            current_path=path,
            tree=tree,
        ):
            imported_module = _module_name_for_path(root, imported_path)
            if imported_module in _TRUSTED_MODULES:
                continue
            if imported_path not in visited:
                pending.append(imported_path)

    if violations:
        rendered = "\n".join(v.render() for v in violations)
        raise Batch02SourcePolicyError(
            "future Batch02 source policy violations:\n" + rendered
        )
    return tuple(sorted(visited))
