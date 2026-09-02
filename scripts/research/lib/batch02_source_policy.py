"""Static fail-closed policy for future Signalbot Batch02 runtime modules.

This is defense in depth around the runtime contracts in batch02_contracts.
It is intentionally strict about mechanically auditable integrity boundaries:
future B2-02+ code may transform already-loaded in-memory data, but direct
filesystem/parquet access, evidence mutation, frozen Batch01 runtime reuse,
dynamic imports, and alternate named/library rank APIs are not allowed in the
future-B2 import closure.

Non-repository imports are default-deny except the explicit transform
allowlist. Allowlisted packages may expose in-memory functions/classes, but
they may not re-export a foreign module that is outside that allowlist
(pathlib.posixpath, enum.bltns->builtins, dataclasses.inspect, ...).
Same-package capability submodules remain prefix-denied. AST inspection is
not a sandbox.

Imported module objects are themselves a capability-provenance boundary: a
name bound directly by `import X` (with or without `as`), or a bare copy of
such a name / of an explicitly allowlisted submodule path, must be used
through that canonical binding. It may not be reassigned to a second local
name -- by ordinary assignment, a walrus expression, matching-arity tuple/
list destructuring, or as a function/lambda default parameter value --
because the source-policy checks above are AST-provenance-sensitive: they
recognize a foreign or capability-bearing module by tracing an attribute-
access chain back to the import statement that bound it, and that trace is
lost the moment the reference is copied to any other direct local binding.
See "Static admissibility guarantees" below.

This module deliberately does NOT claim that AST linting can prove arbitrary
numerical Python is semantically equivalent to rolling_midrank_percentile().
The canonical primitive is behaviorally tested; whether a preregistered
hypothesis requires a percentile feature and wires that feature to the
canonical primitive is a hypothesis-freeze/code-review invariant, not a claim
made by this source linter. Keeping that boundary explicit avoids a false
"one semantics" guarantee that neutral-name arithmetic can trivially evade.

## Policy contract

Runtime guarantees (enforced by batch02_contracts, not this module):
    exact code-freeze identity, authorized-dataset/partition binding,
    outcome-window and no-lookahead enforcement, promotion-gate conjunction,
    and immutable result/provenance persistence. This module never executes
    or imports hypothesis code and proves none of these at runtime.

Static admissibility guarantees (enforced here, mechanically, on the AST):
    - non-repository imports are default-deny except the explicit transform
      allowlist (`_ALLOWED_EXTERNAL_MODULES`);
    - a fixed, version-documented set of known aliased foreign-module
      re-exports from allowlisted packages is denied by exact
      (root, attribute) lookup (`_KNOWN_ALIASED_FOREIGN_REEXPORTS`), in
      addition to escaped-stdlib-module names matched by literal attribute
      text regardless of base object (`_FORBIDDEN_ESCAPED_STDLIB_MODULES`);
    - import-system objects (`__loader__`, `__spec__`, `__path__`, loader
      execution surfaces) and code/frame/closure reflection attributes are
      denied by literal attribute/call name, independent of resolvability;
    - unknown `to_*` attributes fail closed; a fixed, explicit allowlist of
      known in-memory conversions is exempted;
    - canonical Batch02 bindings may not be shadowed, reassigned, deleted,
      or rebound via `global`/`nonlocal` across every binding form the AST
      exposes (assignment, destructuring, parameters, comprehensions,
      exception aliases, match captures, type parameters);
    - an imported module reference (a name bound by `import X`, or an exact
      allowlisted submodule path) may not be copied to a second local name --
      including a plain/annotated assignment, a walrus expression, matching-
      arity tuple/list destructuring, or a function/lambda default parameter
      value; it must be used, or further attribute-accessed, through the
      binding import created.
    These checks are a pure, deterministic function of the source AST alone:
    no package is imported or introspected while linting, so results do not
    depend on which package versions happen to be installed wherever the
    checker runs.

Explicit non-guarantees (require arbitrary Python semantic/dataflow
reasoning and are therefore NOT claimed by this static policy):
    - reflection/introspection that bypasses the harness via private module
      globals, `object.__setattr__`, or forged objects;
    - a module reference smuggled through a container, a function return
      value, a class attribute, a closure cell, or any other indirection
      this checker does not walk;
    - completeness of `_KNOWN_ALIASED_FOREIGN_REEXPORTS` against a future
      standard-library or package version that introduces a new aliased
      re-export not yet enumerated here;
    - semantic equivalence of arbitrary numerical Python to any canonical
      primitive (see above);
    - anything requiring the checker to run, or reason about, code that is
      not literally present as this file's own AST.
    This module is a static admissibility gate, not a sandbox.
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
_B2_FILE_NUMBER = re.compile(r"^b2_(\d{2})")
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
# batch02_evidence_retention.py is intentionally NOT trusted for hypothesis
# files. It uses subprocess Git. Hypothesis runners may only reach retention
# through the contracts re-exports; importing the retention module directly
# would fail this policy because subprocess is default-denied.

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

# Names of capability-bearing modules that must remain unavailable even when
# an otherwise transform-allowed package re-exports them as attributes.
_FORBIDDEN_ESCAPED_STDLIB_MODULES = {
    "os",
    "sys",
    "io",
    "pickle",
    "subprocess",
    "socket",
    "urllib",
    "ftplib",
    "ctypes",
    "importlib",
    "operator",
    "mmap",
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
    # Path/OS/eval/import modules commonly re-exported by transform-allowed
    # packages under their original names. Aliased re-exports (enum.bltns,
    # collections._sys) are matched by exact (root, attribute) lookup in
    # _KNOWN_ALIASED_FOREIGN_REEXPORTS instead, since their attribute name
    # does not match the real module name this list is keyed on.
    "posixpath",
    "ntpath",
    "genericpath",
    "inspect",
    "tempfile",
    "builtins",
    "_thread",
    "code",
    "codeop",
    "types",
    "keyword",
    "codecs",
}

_FORBIDDEN_PACKAGE_ATTRIBUTE_PREFIXES = (
    "pandas.io",
    "pandas.core.computation",
    "numpy.lib.npyio",
    "numpy.lib._datasource",
    "numpy.ctypeslib",
    "numpy.testing",
    "pyarrow.parquet",
    "pyarrow.dataset",
    "pyarrow.fs",
    "pyarrow.feather",
    "pyarrow.csv",
    "pyarrow.json",
    "pyarrow.ipc",
    "pyarrow.flight",
    "pyarrow.orc",
    "pyarrow.cuda",
    "pyarrow.jvm",
    "pyarrow.plasma",
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
    "numpy.lib._datasource",
    "numpy.ctypeslib",
    "numpy.testing",
    "pyarrow.parquet",
    "pyarrow.dataset",
    "pyarrow.fs",
    "pyarrow.feather",
    "pyarrow.csv",
    "pyarrow.json",
    "pyarrow.ipc",
    "pyarrow.flight",
    "pyarrow.orc",
    "pyarrow.cuda",
    "pyarrow.jvm",
    "pyarrow.plasma",
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
    # plain .copy is an in-memory transform for copy.copy/DataFrame/ndarray;
    # filesystem copy capability is denied by module origin (shutil) and the
    # specific copyfile/copy2/copytree names below.
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
    "touch",
    "symlink_to",
    "chmod",
    "lchmod",
    "is_file",
    "is_dir",
    "is_symlink",
    "is_mount",
    "is_block_device",
    "is_char_device",
    "is_fifo",
    "is_socket",
    "owner",
    "group",
    "samefile",
    "readlink",
    "resolve",
    "cwd",
    "home",
    "absolute",
    "expanduser",
    "is_junction",
    "link_to",
    # file-backed constructors / writers exposed by transform-allowed packages.
    "FileType",
    "OSFile",
    "PythonFile",
    "LocalFileSystem",
    "ExcelWriter",
    "ExcelFile",
    "StataReader",
    "NativeFile",
    "MemoryMappedFile",
    "ORCFile",
    "DataSource",
    "Repository",
    "fromregex",
    "output_stream",
    "savez",
    "savez_compressed",
    "dump",
    "to_stata",
    "to_html",
    "to_markdown",
    "to_string",
    "to_orc",
    "to_gbq",
    "to_latex",
    "to_xml",
    "to_clipboard",
    "file_digest",
    "load_library",
    "set_data",
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
    "__builtins__",
    "__code__",
    "__defaults__",
    "__kwdefaults__",
    "__closure__",
    "__subclasses__",
    "__mro__",
    "__bases__",
    "__base__",
    "mro",
    "__wrapped__",
    "__traceback__",
    "tb_frame",
    "tb_next",
    "f_builtins",
    "f_globals",
    "f_locals",
    "f_back",
    "gi_frame",
    "cr_frame",
    "ag_frame",
    "gi_code",
    "cr_code",
    "ag_code",
    "f_code",
    "cell_contents",
    "__loader__",
    "__spec__",
    "__path__",
    "exec_module",
    "load_module",
    "create_module",
    "__setattr__",
    "__delattr__",
    "__reduce__",
    "__reduce_ex__",
}
_FORBIDDEN_IO_NAME_PREFIXES = ("read_", "scan_", "open_", "write_")

# pandas/ndarray-style in-memory conversions. Unknown to_* names fail closed
# because they are the historical class of external writers (to_csv, to_sql,
# to_iceberg, ...). Names that can write a file OR return a string (to_json,
# to_string, to_html, ...) remain denied by _FORBIDDEN_IO_ATTRIBUTES.
_IN_MEMORY_TO_METHODS = {
    "to_dict",
    "to_numpy",
    "to_list",
    "to_frame",
    "to_records",
    "to_timestamp",
    "to_period",
    "to_timedelta",
    "to_pydatetime",
    "to_pytimedelta",
    "to_series",
    "to_julian_date",
    "to_flat_index",
    "to_native_types",
    "to_xarray",
    "to_dense",
    "to_sparse",
    "to_view",
}

_FORBIDDEN_RANK_CALLS = {
    "rank",
    "rankdata",
    "percentileofscore",
    "searchsorted",
}
_FORBIDDEN_IMPORTED_SYMBOLS = {
    # I/O symbols whose capability is dangerous independent of local alias.
    # Builtins are handled separately by module+origin, so e.g. re.compile
    # remains a valid in-memory transform.
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
    "ExcelFile",
    "StataReader",
    "NativeFile",
    "MemoryMappedFile",
    "ORCFile",
    "DataSource",
    "Repository",
    "fromregex",
    "output_stream",
    "savez",
    "savez_compressed",
    "dump",
    "to_stata",
    "to_html",
    "to_markdown",
    "to_latex",
    "to_xml",
    "to_clipboard",
    "file_digest",
    "load_library",
    "set_data",
    "touch",
    "symlink_to",
    "chmod",
    "lchmod",
    "is_file",
    "is_dir",
    "is_symlink",
    "is_mount",
    "is_block_device",
    "is_char_device",
    "is_fifo",
    "is_socket",
    "owner",
    "group",
    "samefile",
    "readlink",
    "resolve",
    "cwd",
    "home",
    "absolute",
    "expanduser",
    "is_junction",
    "link_to",
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
_RETENTION_RUNNER_CALLS = {
    "verify_batch02_code",
    "prepare_batch02_evidence_reservation",
    "prepare_batch02_retained_run",
    "persist_batch02_result",
    "archive_batch02_result",
}
_DATASET_OPENING_NAMES = {
    "prepare_batch02_run",
    "prepare_batch02_retained_run",
}
_PROTECTED_BINDINGS = {
    *_REQUIRED_RUNNER_CALLS,
    *_RETENTION_RUNNER_CALLS,
    _CANONICAL_RANK_NAME,
    "load_authorized_parquet_table",
}

# Python 3.12+ stores PEP 695 type-parameter names on dedicated AST nodes
# rather than ast.Name(Store). Keep construction compatible with Python 3.11.
_TYPE_PARAMETER_NODES = tuple(
    node_type
    for node_type in (
        getattr(ast, "TypeVar", None),
        getattr(ast, "ParamSpec", None),
        getattr(ast, "TypeVarTuple", None),
    )
    if node_type is not None
)

_CANONICAL_PUBLIC_API = {
    *_REQUIRED_RUNNER_CALLS,
    *_RETENTION_RUNNER_CALLS,
    _CANONICAL_RANK_NAME,
    "load_authorized_parquet_table",
    "Batch02ContractError",
    "Batch02RunContext",
    "DurableEvidenceReservation",
    "DurableArchiveReceipt",
    "PreOutcomeRetentionError",
    "PostOutcomeRetentionFailure",
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


def _b2_file_number(path: Path) -> int | None:
    match = _B2_FILE_NUMBER.match(path.name)
    if match is None:
        return None
    return int(match.group(1))


def _runner_required_calls(path: Path) -> set[str]:
    number = _b2_file_number(path)
    if number is not None and number >= 3:
        return set(_RETENTION_RUNNER_CALLS)
    return set(_REQUIRED_RUNNER_CALLS)


def _require_repo_relative(repo_root: Path, path: Path) -> Path:
    try:
        return path.relative_to(repo_root)
    except ValueError as exc:
        raise Batch02SourcePolicyError(
            f"Batch02 source resolves outside repository: {path}"
        ) from exc


def _module_name_for_path(repo_root: Path, path: Path) -> str:
    rel = _require_repo_relative(repo_root, path)
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
    bindings, _module_origins = _import_bindings_and_module_origins(
        repo_root=repo_root, path=path, tree=tree
    )
    return bindings


def _import_bindings_and_module_origins(
    *,
    repo_root: Path,
    path: Path,
    tree: ast.AST,
) -> tuple[dict[str, str], set[str]]:
    """Import-alias bindings, plus the subset guaranteed to be modules.

    `module_origins` holds the real dotted path bound by every plain
    `import X` / `import X as Y` statement -- i.e. names Python guarantees
    are bound to an actual module object, independent of the allowlist.
    `from X import Y` bindings are never added here: whether Y itself
    denotes a module cannot be determined without importing/introspecting
    it, which this static checker deliberately does not do.
    """
    bindings: dict[str, str] = {}
    module_origins: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                # Without an alias Python only binds the top-level package.
                origin = alias.name if alias.asname else local
                bindings[local] = origin
                module_origins.add(origin)
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
    return bindings, module_origins


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


def _flatten_destructure_pairs(
    target: ast.AST, value: ast.AST
) -> list[tuple[ast.AST, ast.AST]]:
    """Recursively pair matching-arity Tuple/List target/value elements.

    Descends only through target/value nodes that are BOTH Tuple or List
    with equal element count -- exactly the shapes Python itself unpacks
    positionally -- at any nesting depth. Any other shape (a plain Name, a
    Starred target, an Attribute/Subscript target, a Call value, mismatched
    arity, ...) is returned as a single leaf pair without further descent.
    This mirrors Python's own destructuring semantics; it is not container
    indexing, a call, or any other dataflow indirection.
    """
    if (
        isinstance(target, (ast.Tuple, ast.List))
        and isinstance(value, (ast.Tuple, ast.List))
        and len(target.elts) == len(value.elts)
    ):
        pairs: list[tuple[ast.AST, ast.AST]] = []
        for sub_target, sub_value in zip(target.elts, value.elts):
            pairs.extend(_flatten_destructure_pairs(sub_target, sub_value))
        return pairs
    return [(target, value)]


def _is_forbidden_io_name(name: str | None) -> bool:
    if not name:
        return False
    return (
        name in _FORBIDDEN_IMPORTED_SYMBOLS
        or name in _FORBIDDEN_IO_ATTRIBUTES
        or any(name.startswith(prefix) for prefix in _FORBIDDEN_IO_NAME_PREFIXES)
    )


def _is_unknown_external_to_method(name: str | None) -> bool:
    """Fail-closed unknown to_* writers; keep known in-memory conversions."""
    if not name or not name.startswith("to_"):
        return False
    if name in _IN_MEMORY_TO_METHODS:
        return False
    return True


# Known aliased foreign-module re-exports reachable one attribute-hop off an
# allowlisted root, where the exposed attribute name does NOT match the real
# module's __name__ (so _FORBIDDEN_ESCAPED_STDLIB_MODULES's literal-name
# match cannot catch it). This is a static, explicit, version-documented
# enumeration -- not derived from importing/introspecting the packages at
# lint time -- so policy results are a pure function of the source AST and
# do not vary by which package versions happen to be installed wherever the
# checker runs. Verified against CPython 3.11 stdlib internals; re-verify
# against any newly-supported interpreter version before trusting silently.
# This is deliberately NOT claimed to be exhaustive against every current or
# future third-party/stdlib aliased re-export -- see the module docstring's
# "Explicit non-guarantees".
_KNOWN_ALIASED_FOREIGN_REEXPORTS: dict[str, dict[str, str]] = {
    "enum": {"bltns": "builtins"},
    "collections": {"_sys": "sys", "_collections_abc": "collections.abc"},
}


def _foreign_reexport_real_name(root: str, attr: str) -> str | None:
    """Real module name if (root, attr) is a known aliased foreign re-export."""
    return _KNOWN_ALIASED_FOREIGN_REEXPORTS.get(root, {}).get(attr)


def _transform_allowlist_covers(module_name: str) -> bool:
    if not module_name:
        return False
    if module_name in _ALLOWED_EXTERNAL_MODULES:
        return True
    return any(
        module_name.startswith(allowed + ".")
        for allowed in _ALLOWED_EXTERNAL_MODULES
    )


def _known_foreign_reexport_for_dotted(dotted: str) -> str | None:
    """Real module name if `dotted` is exactly `<allowed_root>.<known_attr>`.

    Only a single attribute hop directly off an allowlisted root is
    recognized, matching _KNOWN_ALIASED_FOREIGN_REEXPORTS. This mirrors the
    bounded, name-based style already used by the other static denylists in
    this module rather than resolving arbitrary nested paths.
    """
    if "." not in dotted:
        return None
    root, attr = dotted.rsplit(".", 1)
    if not _transform_allowlist_covers(root):
        return None
    return _foreign_reexport_real_name(root, attr)


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
    qualified calls, and getattr(..., "prepare_batch02_run") or
    getattr(..., "prepare_batch02_retained_run") all leave at
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
                alias.name in {*_DATASET_OPENING_NAMES, "*"}
                for alias in node.names
            ):
                return True
            if (
                base == "scripts.research.lib"
                and any(alias.name == "batch02_contracts" for alias in node.names)
            ):
                return True
        elif isinstance(node, ast.Name) and node.id in _DATASET_OPENING_NAMES:
            return True
        elif isinstance(node, ast.Attribute):
            resolved = _resolved_dotted_name(node, bindings=bindings)
            if (
                node.attr in {*_DATASET_OPENING_NAMES, "batch02_contracts"}
                or resolved == _CANONICAL_CONTRACTS_MODULE
                or resolved
                in {
                    f"{_CANONICAL_CONTRACTS_MODULE}.{name}"
                    for name in _DATASET_OPENING_NAMES
                }
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
                    and arg.value in _DATASET_OPENING_NAMES
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
    reservation_names: set[str] = set()
    bindings, module_origins = _import_bindings_and_module_origins(
        repo_root=repo_root, path=path, tree=tree
    )
    copy_protected_origins = module_origins | _ALLOWED_EXTERNAL_MODULES

    def _flag_module_copy(binding_name: str, value_node: ast.AST, lineno: int | None) -> None:
        resolved_value = _resolved_dotted_name(value_node, bindings=bindings)
        if resolved_value and resolved_value in copy_protected_origins:
            violations.append(
                SourceViolation(
                    path,
                    "imported module reference may not be copied to "
                    f"a new local binding: {binding_name} = "
                    f"{resolved_value}; use the import binding/alias "
                    "directly",
                    lineno,
                )
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call):
                if any(
                    _is_canonical_call(node.value, bindings=bindings, name=name)
                    for name in _DATASET_OPENING_NAMES
                ):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            context_names.add(target.id)
                if _is_canonical_call(
                    node.value,
                    bindings=bindings,
                    name="prepare_batch02_evidence_reservation",
                ):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            reservation_names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                if any(
                    _is_canonical_call(node.value, bindings=bindings, name=name)
                    for name in _DATASET_OPENING_NAMES
                ):
                    context_names.add(node.target.id)
                if _is_canonical_call(
                    node.value,
                    bindings=bindings,
                    name="prepare_batch02_evidence_reservation",
                ):
                    reservation_names.add(node.target.id)

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
                if (
                    isinstance(node, ast.ImportFrom)
                    and origin_symbol in _FORBIDDEN_ESCAPED_STDLIB_MODULES
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            "transform-allowed package may not re-export "
                            f"capability module {origin_symbol}",
                            getattr(node, "lineno", None),
                        )
                    )
                known_foreign_real_name = _known_foreign_reexport_for_dotted(origin)
                if known_foreign_real_name is not None:
                    violations.append(
                        SourceViolation(
                            path,
                            "transform-allowed package may not re-export "
                            f"foreign module {known_foreign_real_name}",
                            getattr(node, "lineno", None),
                        )
                    )
                if _is_unknown_external_to_method(origin_symbol):
                    violations.append(
                        SourceViolation(
                            path,
                            f"unknown to_* writer is fail-closed: {origin}",
                            getattr(node, "lineno", None),
                        )
                    )
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
                is_canonical_contract_import_from = (
                    isinstance(node, ast.ImportFrom)
                    and import_module == _CANONICAL_CONTRACTS_MODULE
                )
                if (
                    import_module
                    and not is_local
                    and not is_canonical_contract_import_from
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

                # The trusted contracts module object is itself a capability
                # boundary. Hypothesis code gets only explicit public symbols
                # via ImportFrom; importing/re-exporting the module object would
                # expose internal harness primitives as attributes.
                if (
                    origin == _CANONICAL_CONTRACTS_MODULE
                    and not (
                        isinstance(node, ast.ImportFrom)
                        and base == _CANONICAL_CONTRACTS_MODULE
                    )
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            "batch02_contracts module object is forbidden; "
                            "import explicit public API symbols instead",
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
                if (
                    isinstance(node, ast.ImportFrom)
                    and base == "builtins"
                    and origin_symbol in _FORBIDDEN_BARE_CALLS
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            f"forbidden direct I/O symbol import {origin}",
                            getattr(node, "lineno", None),
                        )
                    )
                if _is_forbidden_io_name(origin_symbol):
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
                        *_RETENTION_RUNNER_CALLS,
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

        # Module/capability provenance boundary: a name bound directly by
        # `import X` (with or without `as`), or an exact allowlisted
        # submodule path, must be used through that canonical binding. The
        # foreign-module and escaped-stdlib checks above recognize a
        # forbidden module by tracing an attribute-access chain back to the
        # import statement that bound it; copying the reference to a second
        # ordinary local name severs that trace and would otherwise let
        # provenance-sensitive checks silently stop firing on the copy. This
        # targets bare module-reference copies specifically (a Name or
        # Attribute chain used as the entire right-hand side); it does not
        # restrict calling through the binding or assigning a computed
        # result, so `arr = np.asarray(...)` and `total = pc.sum(arr)`
        # remain unaffected.
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target] if node.value is not None else []
                value = node.value
            else:
                targets = [node.target]
                value = node.value
            value_pairs: list[tuple[ast.AST, ast.AST]] = []
            for target in targets:
                value_pairs.extend(_flatten_destructure_pairs(target, value))
            for target_node, value_node in value_pairs:
                if not isinstance(target_node, ast.Name):
                    continue
                _flag_module_copy(
                    target_node.id, value_node, getattr(node, "lineno", None)
                )

        # Same provenance-copy boundary, for the one other direct-binding
        # form the AST exposes: a function/lambda default parameter value.
        # `def f(mod=collections): ...` binds "mod" to the module reference
        # exactly as `mod = collections` would, and a later `mod._sys` is
        # just as provenance-blind as the assignment case above. This pairs
        # defaults to parameters using Python's own alignment rules (trailing
        # positional/posonly params for `defaults`, index-matched optional
        # entries in `kw_defaults`) and does not otherwise look inside the
        # function body, a call, or any other indirection.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            fn_args = node.args
            positional = [*fn_args.posonlyargs, *fn_args.args]
            defaulted_positional = positional[len(positional) - len(fn_args.defaults):]
            for param, default_node in zip(defaulted_positional, fn_args.defaults):
                _flag_module_copy(
                    param.arg, default_node, getattr(default_node, "lineno", None)
                )
            for param, default_node in zip(fn_args.kwonlyargs, fn_args.kw_defaults):
                if default_node is None:
                    continue
                _flag_module_copy(
                    param.arg, default_node, getattr(default_node, "lineno", None)
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
            if isinstance(node.func, ast.Name) and name in _FORBIDDEN_BARE_CALLS:
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
            canonical_names = _REQUIRED_RUNNER_CALLS | _RETENTION_RUNNER_CALLS | {
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
                            "prepare_batch02_run or prepare_batch02_retained_run",
                            getattr(node, "lineno", None),
                        )
                    )

            if (
                name == "archive_batch02_result"
                and _is_canonical_call(node, bindings=bindings, name=name)
            ):
                reservation_kw = next(
                    (kw.value for kw in node.keywords if kw.arg == "reservation"),
                    None,
                )
                if (
                    not isinstance(reservation_kw, ast.Name)
                    or reservation_kw.id not in reservation_names
                ):
                    violations.append(
                        SourceViolation(
                            path,
                            "archive_batch02_result must receive reservation "
                            "assigned from prepare_batch02_evidence_reservation",
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

        if (
            _TYPE_PARAMETER_NODES
            and isinstance(node, _TYPE_PARAMETER_NODES)
            and getattr(node, "name", None) in _PROTECTED_BINDINGS
        ):
            violations.append(
                SourceViolation(
                    path,
                    "canonical Batch02 binding may not be shadowed by "
                    f"type parameter: {node.name}",
                    getattr(node, "lineno", None),
                )
            )

        # Some Python binding forms store target names as strings rather than
        # ast.Name(Store) nodes. They must still be treated as protected-name
        # rebindings or the direct-call ceremony proof becomes fail-open.
        if (
            isinstance(node, ast.ExceptHandler)
            and node.name in _PROTECTED_BINDINGS
        ):
            violations.append(
                SourceViolation(
                    path,
                    "canonical Batch02 binding may not be shadowed by "
                    f"exception alias: {node.name}",
                    getattr(node, "lineno", None),
                )
            )

        if isinstance(node, (ast.MatchAs, ast.MatchStar)):
            match_name = node.name
            if match_name in _PROTECTED_BINDINGS:
                violations.append(
                    SourceViolation(
                        path,
                        "canonical Batch02 binding may not be shadowed by "
                        f"pattern capture: {match_name}",
                        getattr(node, "lineno", None),
                    )
                )

        if (
            isinstance(node, ast.MatchMapping)
            and node.rest in _PROTECTED_BINDINGS
        ):
            violations.append(
                SourceViolation(
                    path,
                    "canonical Batch02 binding may not be shadowed by "
                    f"mapping-rest capture: {node.rest}",
                    getattr(node, "lineno", None),
                )
            )

        if isinstance(node, (ast.Global, ast.Nonlocal)):
            for binding_name in node.names:
                if binding_name in _PROTECTED_BINDINGS:
                    kind = (
                        "global declaration"
                        if isinstance(node, ast.Global)
                        else "nonlocal declaration"
                    )
                    violations.append(
                        SourceViolation(
                            path,
                            "canonical Batch02 binding may not be shadowed by "
                            f"{kind}: {binding_name}",
                            getattr(node, "lineno", None),
                        )
                    )

        if isinstance(node, ast.Attribute):
            resolved_attribute = _resolved_dotted_name(node, bindings=bindings)
            if node.attr in _FORBIDDEN_ESCAPED_STDLIB_MODULES:
                violations.append(
                    SourceViolation(
                        path,
                        "transform-allowed package may not expose "
                        f"capability module attribute .{node.attr}",
                        getattr(node, "lineno", None),
                    )
                )
            if resolved_attribute:
                known_foreign_real_name = _known_foreign_reexport_for_dotted(
                    resolved_attribute
                )
                if known_foreign_real_name is not None:
                    violations.append(
                        SourceViolation(
                            path,
                            "transform-allowed package may not expose "
                            "foreign module attribute "
                            f"{known_foreign_real_name}",
                            getattr(node, "lineno", None),
                        )
                    )
            if _is_unknown_external_to_method(node.attr):
                violations.append(
                    SourceViolation(
                        path,
                        f"unknown to_* writer is fail-closed: .{node.attr}",
                        getattr(node, "lineno", None),
                    )
                )
            if (
                resolved_attribute
                and (
                    resolved_attribute == _CANONICAL_CONTRACTS_MODULE
                    or resolved_attribute.startswith(
                        _CANONICAL_CONTRACTS_MODULE + "."
                    )
                )
            ):
                violations.append(
                    SourceViolation(
                        path,
                        "batch02_contracts module-object attribute access is "
                        "forbidden; use explicit public API imports",
                        getattr(node, "lineno", None),
                    )
                )
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
            if node.attr in {"query", "eval"}:
                violations.append(
                    SourceViolation(
                        path,
                        "dynamic dataframe/query evaluation surface is forbidden",
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
            if (
                isinstance(node.ctx, (ast.Store, ast.Del))
                and node.id in _PROTECTED_BINDINGS
            ):
                action = (
                    "reassigned"
                    if isinstance(node.ctx, ast.Store)
                    else "unbound"
                )
                violations.append(
                    SourceViolation(
                        path,
                        f"canonical Batch02 binding may not be {action}: {node.id}",
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
        required_calls = _runner_required_calls(path)
        missing_imports = required_calls - canonical_imports
        missing_calls = required_calls - canonical_calls
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
        number = _b2_file_number(path)
        if (
            number is not None
            and number >= 3
            and (
                "prepare_batch02_run" in canonical_imports
                or "prepare_batch02_run" in canonical_calls
            )
        ):
            violations.append(
                SourceViolation(
                    path,
                    "B2-03+ runners may not call prepare_batch02_run; "
                    "durable evidence reservation must precede outcome access",
                )
            )

    return violations


_SKIP_SCAN_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "tests",
    "artifacts",
    "build",
    "dist",
    "site-packages",
    "venv",
    ".venv",
    "virtualenv",
}


def _skip_repo_scan_path(repo_root: Path, path: Path) -> bool:
    rel = _require_repo_relative(repo_root, path)
    current = repo_root
    for part in rel.parts[:-1]:
        current = current / part
        if part in _SKIP_SCAN_DIR_NAMES:
            return True
        if part == "env" and (current / "pyvenv.cfg").is_file():
            return True
    return False


def _discover_future_b2_entrypoints(
    scan_root: Path,
    *,
    repo_root: Path,
) -> list[Path]:
    del scan_root  # source universe is repository-wide, exclusions are explicit.
    out: list[Path] = []
    candidates = {
        path
        for path in repo_root.rglob("*.py")
        if not _skip_repo_scan_path(repo_root, path)
    }
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
