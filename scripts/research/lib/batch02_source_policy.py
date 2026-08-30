"""Static fail-closed policy for future Signalbot Batch02 runtime modules.

This is defense in depth around the runtime contracts in batch02_contracts.
It is intentionally strict about mechanically auditable integrity boundaries:
future B2-02+ code may transform already-loaded in-memory data, but direct
filesystem/parquet access, evidence mutation, frozen Batch01 runtime reuse,
dynamic imports, and alternate named/library rank APIs are not allowed in the
future-B2 import closure.

This module deliberately does NOT claim that AST linting can prove arbitrary
numerical Python is semantically equivalent to rolling_midrank_percentile().
The canonical primitive is behaviorally tested; whether a preregistered
hypothesis requires a percentile feature and wires that feature to the
canonical primitive is a hypothesis-freeze/code-review invariant, not a claim
made by this source linter. Keeping that boundary explicit avoids a false
"one semantics" guarantee that neutral-name arithmetic can trivially evade.
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

# Non-repository imports are default-deny. Keep this set intentionally narrow:
# future hypotheses may transform already-authorized in-memory data, not grow
# new acquisition/execution capabilities by importing another package.
_ALLOWED_EXTERNAL_MODULES = {
    "numpy",
    "pandas",
    "pyarrow",
    "pyarrow.compute",
    "pathlib",
    "math",
    "statistics",
    "decimal",
    "fractions",
    "collections",
    "collections.abc",
    "itertools",
    "functools",
    "dataclasses",
    "typing",
    "enum",
    "copy",
    "re",
    "json",
    "hashlib",
}

_FORBIDDEN_BUILTIN_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
}

_FORBIDDEN_PACKAGE_ATTRIBUTE_PREFIXES = (
    "pandas.io",
    "pandas.core.computation",
    "numpy.lib.npyio",
    "pyarrow.parquet",
    "pyarrow.dataset",
    "pyarrow.fs",
    "pyarrow.feather",
    "pyarrow.csv",
    "pyarrow.json",
    "pyarrow.ipc",
)

_FORBIDDEN_DIRECT_MODULE_PREFIXES = (
    "scripts.research.lib.research_harness",
    # Dynamic/reflection/native escape hatches are outside the future-B2
    # closure. The runner may transform already-loaded data, not acquire bytes
    # through alternate filesystem/network/process machinery.
    "subprocess",
    "importlib",
    "operator",
    "io",
    "os",
    "urllib",
    "socket",
    "ftplib",
    "ctypes",
    "cffi",
    "requests",
    "httpx",
    "aiohttp",
    "duckdb",
    "fsspec",
    "sqlite3",
    "sqlalchemy",
    "mmap",
    # Stdlib modules that can independently open/copy/execute arbitrary paths.
    "fileinput",
    "runpy",
    "gzip",
    "bz2",
    "lzma",
    "shutil",
    "pty",
    "linecache",
    "zipimport",
    "pkgutil",
    "zipfile",
    "tarfile",
    "shelve",
    "dbm",
    "posix",
    "unittest.mock",
    "mock",
    # I/O/evaluation subpackages inside otherwise transform-allowed packages.
    "pandas.io",
    "pandas.core.computation",
    "numpy.lib.npyio",
    "pyarrow.parquet",
    "pyarrow.dataset",
    "pyarrow.fs",
    "pyarrow.feather",
    "pyarrow.csv",
    "pyarrow.json",
    "pyarrow.ipc",
)
_FORBIDDEN_BARE_CALLS = {
    "open",
    "eval",
    "exec",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "vars",
    "globals",
    "locals",
    "compile",
}
_FORBIDDEN_IO_ATTRIBUTES = {
    # pathlib / os / shutil style mutation or direct filesystem access.
    "open",
    "fdopen",
    "popen",
    "FileIO",
    "urlopen",
    "read",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "to_csv",
    "to_parquet",
    "to_json",
    "to_pickle",
    "to_feather",
    "to_excel",
    "to_sql",
    "to_hdf",
    "save",
    "savetxt",
    "unlink",
    "remove",
    "rename",
    "replace",
    "rmdir",
    "rmtree",
    "move",
    "copy",
    "copyfile",
    "copy2",
    "copytree",
    "GzipFile",
    "BZ2File",
    "LZMAFile",
    "ZipFile",
    "TarFile",
    "get_data",
    "run_path",
    "updatecache",
    "getline",
    "spawn",
    "tofile",
    "hardlink_to",
    "mkdir",
    "exists",
    "stat",
    "lstat",
    # file-backed constructors / writers exposed by transform-allowed packages.
    "FileType",
    "OSFile",
    "PythonFile",
    "LocalFileSystem",
    "ExcelWriter",
    "StataReader",
    "fromregex",
    "output_stream",
    "savez",
    "savez_compressed",
    "dump",
    "to_stata",
    "to_html",
    "to_markdown",
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
    "memmap",
    "memory_map",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_hdf",
    "HDFStore",
    "open_file",
    "open_input_file",
    "open_input_stream",
    "input_stream",
    "glob",
    "rglob",
    "iterdir",
    "listdir",
    "scandir",
    "walk",
    "connect",
    "list_monthly_partitions",
}
_FORBIDDEN_REFLECTION_ATTRIBUTES = {
    "__getattribute__",
    "attrgetter",
    "methodcaller",
    "getattr_static",
    "__globals__",
    "__code__",
    "__defaults__",
    "__kwdefaults__",
    "__closure__",
    "__setattr__",
    "__delattr__",
    "__reduce__",
    "__reduce_ex__",
}
_FORBIDDEN_IO_NAME_PREFIXES = ("read_", "scan_", "open_", "write_")

_FORBIDDEN_RANK_CALLS = {
    "rank",
    "rankdata",
    "percentileofscore",
    "searchsorted",
}
_FORBIDDEN_IMPORTED_SYMBOLS = {
    # Preserve original-symbol identity across "from X import Y as alias".
    # In particular, aliased builtins must not escape the bare-call checks.
    "open",
    "eval",
    "exec",
    "__import__",
    "compile",
    "getattr",
    "setattr",
    "delattr",
    "vars",
    "globals",
    "locals",
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
    "memmap",
    "memory_map",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_hdf",
    "HDFStore",
    "open_file",
    "connect",
    "FileIO",
    "FileType",
    "OSFile",
    "PythonFile",
    "LocalFileSystem",
    "ExcelWriter",
    "StataReader",
    "fromregex",
    "output_stream",
    "savez",
    "savez_compressed",
    "dump",
    "to_stata",
    "to_html",
    "to_markdown",
    "popen",
    "urlopen",
}
_RANK_NAME = re.compile(r"(?:^|_)(?:rank|percentile|pctl)(?:_|$)", re.IGNORECASE)
_CANONICAL_CONTRACTS_MODULE = "scripts.research.lib.batch02_contracts"
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

_CANONICAL_PUBLIC_API = {
    *_REQUIRED_RUNNER_CALLS,
    _CANONICAL_RANK_NAME,
    "load_authorized_parquet_table",
    "Batch02ContractError",
    "Batch02RunContext",
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


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        if prefix:
            return f"{prefix}.{node.attr}"
    return None


def _import_bindings(
    *,
    repo_root: Path,
    path: Path,
    tree: ast.AST,
) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                # Without an alias Python only binds the top-level package.
                bindings[local] = alias.name if alias.asname else local
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(
                repo_root=repo_root,
                current_path=path,
                node=node,
            )
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                bindings[local] = f"{base}.{alias.name}".strip(".")
    return bindings


def _resolved_dotted_name(
    node: ast.AST,
    *,
    bindings: dict[str, str],
) -> str | None:
    dotted = _dotted_name(node)
    if not dotted:
        return None
    head, *tail = dotted.split(".")
    origin = bindings.get(head)
    if origin is None:
        return dotted
    return ".".join([origin, *tail])


def _is_forbidden_io_name(name: str | None) -> bool:
    if not name:
        return False
    return (
        name in _FORBIDDEN_IMPORTED_SYMBOLS
        or name in _FORBIDDEN_IO_ATTRIBUTES
        or any(name.startswith(prefix) for prefix in _FORBIDDEN_IO_NAME_PREFIXES)
    )


def _is_canonical_call(
    node: ast.Call,
    *,
    bindings: dict[str, str],
    name: str,
) -> bool:
    """Return True only for a direct non-aliased canonical contract call."""
    return (
        isinstance(node.func, ast.Name)
        and node.func.id == name
        and bindings.get(name) == f"{_CANONICAL_CONTRACTS_MODULE}.{name}"
    )


def _contains_prepare_reference(
    *,
    repo_root: Path,
    path: Path,
    tree: ast.AST,
) -> bool:
    """Detect direct/aliased/indirected reachability to the canonical preparer.

    Discovery must not depend on the eventual Call identifier.  In particular,
    ImportFrom aliases, assigned references, functools.partial(), module-
    qualified calls, and getattr(..., "prepare_batch02_run") all leave at
    least one of the references below in the importing module.
    """
    bindings = _import_bindings(repo_root=repo_root, path=path, tree=tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name == _CANONICAL_CONTRACTS_MODULE
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(
                repo_root=repo_root,
                current_path=path,
                node=node,
            )
            if base == _CANONICAL_CONTRACTS_MODULE and any(
                alias.name in {"prepare_batch02_run", "*"}
                for alias in node.names
            ):
                return True
            if (
                base == "scripts.research.lib"
                and any(alias.name == "batch02_contracts" for alias in node.names)
            ):
                return True
        elif isinstance(node, ast.Name) and node.id == "prepare_batch02_run":
            return True
        elif isinstance(node, ast.Attribute):
            resolved = _resolved_dotted_name(node, bindings=bindings)
            if (
                node.attr in {"prepare_batch02_run", "batch02_contracts"}
                or resolved == _CANONICAL_CONTRACTS_MODULE
                or resolved
                == f"{_CANONICAL_CONTRACTS_MODULE}.prepare_batch02_run"
            ):
                return True
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if (
                name in {
                    "getattr",
                    "__getattribute__",
                    "attrgetter",
                    "methodcaller",
                    "getattr_static",
                }
                and any(
                    isinstance(arg, ast.Constant)
                    and arg.value == "prepare_batch02_run"
                    for arg in node.args
                )
            ):
                return True
            if name in {"__import__", "import_module"}:
                string_literals = {
                    value.value
                    for value in ast.walk(node)
                    if isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                }
                if (
                    _CANONICAL_CONTRACTS_MODULE in string_literals
                    or "batch02_contracts" in string_literals
                ):
                    return True
    return False


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
    bindings = _import_bindings(repo_root=repo_root, path=path, tree=tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if (
                isinstance(node.value, ast.Call)
                and _is_canonical_call(
                    node.value,
                    bindings=bindings,
                    name="prepare_batch02_run",
                )
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        context_names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Call)
                and _is_canonical_call(
                    node.value,
                    bindings=bindings,
                    name="prepare_batch02_run",
                )
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
                origin_symbol = origin.rsplit(".", 1)[-1]
                if local_name in _PROTECTED_BINDINGS:
                    expected = _CANONICAL_CONTRACTS_MODULE + "." + local_name
                    if origin != expected:
                        violations.append(
                            SourceViolation(
                                path,
                                f"canonical Batch02 binding shadowed by import: "
                                f"{local_name} <- {origin}",
                                getattr(node, "lineno", None),
                            )
                        )
                if (
                    isinstance(node, ast.ImportFrom)
                    and base == _CANONICAL_CONTRACTS_MODULE
                    and origin_symbol in _PROTECTED_BINDINGS
                ):
                    if local_name != origin_symbol:
                        violations.append(
                            SourceViolation(
                                path,
                                "canonical Batch02 entry point may not be aliased: "
                                f"{origin_symbol} as {local_name}",
                                getattr(node, "lineno", None),
                            )
                        )
                # Default-deny every non-local import except the explicit
                # transform-only allowlist and the canonical contract module.
                import_module = (
                    base
                    if isinstance(node, ast.ImportFrom)
                    else origin
                )
                is_local = _resolve_module(repo_root, import_module) is not None
                is_canonical_contract = (
                    import_module == _CANONICAL_CONTRACTS_MODULE
                )
                if (
                    import_module
                    and not is_local
                    and not is_canonical_contract
                    and import_module not in _ALLOWED_EXTERNAL_MODULES
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            f"non-local import is not on the Batch02 transform "
                            f"allowlist: {import_module}",
                            getattr(node, "lineno", None),
                        )
                    )

                if (
                    isinstance(node, ast.ImportFrom)
                    and base == _CANONICAL_CONTRACTS_MODULE
                    and origin_symbol not in _CANONICAL_PUBLIC_API
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            "batch02_contracts internal/re-exported symbol is "
                            f"not part of the hypothesis API: {origin_symbol}",
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
                    and base == _CANONICAL_CONTRACTS_MODULE
                    and origin_symbol in {
                        *_REQUIRED_RUNNER_CALLS,
                        _CANONICAL_RANK_NAME,
                        "load_authorized_parquet_table",
                    }
                    and local_name == origin_symbol
                ):
                    canonical_imports.add(origin_symbol)

            if (
                isinstance(node, ast.ImportFrom)
                and any(alias.name == "*" for alias in node.names)
            ):
                violations.append(
                    SourceViolation(
                        path,
                        "star imports are forbidden in the future Batch02 closure",
                        getattr(node, "lineno", None),
                    )
                )

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
            if _is_forbidden_io_name(name):
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden direct I/O or mutation call {name}",
                        getattr(node, "lineno", None),
                    )
                )
            if name in _FORBIDDEN_REFLECTION_ATTRIBUTES:
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden reflection call {name}",
                        getattr(node, "lineno", None),
                    )
                )
            canonical_names = _REQUIRED_RUNNER_CALLS | {
                _CANONICAL_RANK_NAME,
                "load_authorized_parquet_table",
            }
            if name in canonical_names:
                if _is_canonical_call(node, bindings=bindings, name=name):
                    canonical_calls.add(name)
                else:
                    violations.append(
                        SourceViolation(
                            path,
                            f"{name} must call the direct canonical "
                            f"{_CANONICAL_CONTRACTS_MODULE}.{name} binding",
                            getattr(node, "lineno", None),
                        )
                    )

            if (
                name in {"persist_batch02_result", "load_authorized_parquet_table"}
                and _is_canonical_call(node, bindings=bindings, name=name)
            ):
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
            if node.name in _FORBIDDEN_BUILTIN_NAMES:
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden builtin capability name may not be declared: "
                        f"{node.name}",
                        node.lineno,
                    )
                )
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

        if isinstance(node, ast.Attribute):
            resolved_attribute = _resolved_dotted_name(node, bindings=bindings)
            if (
                resolved_attribute
                and any(
                    resolved_attribute == prefix
                    or resolved_attribute.startswith(prefix + ".")
                    for prefix in _FORBIDDEN_PACKAGE_ATTRIBUTE_PREFIXES
                )
            ):
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden I/O-capable package surface "
                        f"{resolved_attribute}",
                        getattr(node, "lineno", None),
                    )
                )
            if node.attr == "query":
                violations.append(
                    SourceViolation(
                        path,
                        "dynamic dataframe query/evaluation surface is forbidden",
                        getattr(node, "lineno", None),
                    )
                )
            if _is_forbidden_io_name(node.attr):
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden direct I/O or mutation attribute .{node.attr}",
                        getattr(node, "lineno", None),
                    )
                )
            if node.attr in _FORBIDDEN_REFLECTION_ATTRIBUTES:
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden reflection attribute .{node.attr}",
                        getattr(node, "lineno", None),
                    )
                )
            if node.attr == "__dict__":
                violations.append(
                    SourceViolation(
                        path,
                        "dynamic module/object __dict__ access is forbidden",
                        getattr(node, "lineno", None),
                    )
                )
            if (
                isinstance(node.ctx, (ast.Store, ast.Del))
                and node.attr in _PROTECTED_BINDINGS
            ):
                violations.append(
                    SourceViolation(
                        path,
                        "canonical Batch02 module attribute may not be reassigned: "
                        f".{node.attr}",
                        getattr(node, "lineno", None),
                    )
                )

        if isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_BUILTIN_NAMES:
                violations.append(
                    SourceViolation(
                        path,
                        f"forbidden builtin capability reference {node.id}",
                        getattr(node, "lineno", None),
                    )
                )
            if node.id == "__builtins__":
                violations.append(
                    SourceViolation(
                        path,
                        "direct __builtins__ access is forbidden",
                        getattr(node, "lineno", None),
                    )
                )
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


def _discover_future_b2_entrypoints(
    scan_root: Path,
    *,
    repo_root: Path,
) -> list[Path]:
    out: list[Path] = []
    # Inspect the normal runtime tree plus any future-B2-named Python module
    # anywhere in the repository. This catches a repo-root b2_02_*.py without
    # treating tests/docs that merely mention the contracts as runtime runners.
    candidates = set(scan_root.rglob("*.py"))
    candidates.update(
        path
        for path in repo_root.rglob("*.py")
        if _FUTURE_B2_FILE.match(path.name)
    )
    for path in sorted(candidates):
        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            raise Batch02SourcePolicyError(
                f"unable to inspect potential Batch02 source {path}: {exc}"
            ) from exc
        if _FUTURE_B2_FILE.match(path.name) or _contains_prepare_reference(
            repo_root=repo_root,
            path=path,
            tree=tree,
        ):
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
    scripts_root = root / "scripts"
    scan_root = scripts_root if scripts_root.is_dir() else research
    entrypoints = _discover_future_b2_entrypoints(
        scan_root,
        repo_root=root,
    )
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

        has_prepare_reference = _contains_prepare_reference(
            repo_root=root,
            path=path,
            tree=tree,
        )
        is_runner = bool(
            has_prepare_reference
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
