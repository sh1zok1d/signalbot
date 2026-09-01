from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.research.lib import batch02_contracts
from scripts.research.lib.batch02_contracts import (
    Batch02ContractError,
    Batch02RunContext,
    load_authorized_parquet_table,
    persist_batch02_result,
)
from scripts.research.lib.batch02_source_policy import (
    Batch02SourcePolicyError,
    validate_batch02_source_tree,
)
from scripts.research.lib.research_harness import (
    ArtifactExistsError,
    AuthorizedDataset,
    DatasetIdentityError,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = REPO_ROOT / "scripts" / "research"


def _synthetic_tree(
    tmp_path: Path,
    *,
    runner: str,
    helpers: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    research.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (research / "b2_02_attack.py").write_text(runner, encoding="utf-8")

    for rel, source in (helpers or {}).items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure local packages are import-resolvable by the policy.
        parent = path.parent
        while parent != repo:
            init = parent / "__init__.py"
            init.touch(exist_ok=True)
            parent = parent.parent
        path.write_text(source, encoding="utf-8")
    return repo, research


def _canonical_runner(extra: str = "") -> str:
    return f"""
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={{}},
    )
    {extra}
    persist_batch02_result(
        OUT,
        {{"status": "closed"}},
        run_context=ctx,
    )
"""


def test_actual_tree_policy_executes_even_before_b202_exists():
    # The real repository currently has no B2-02+ runtime. This is allowed,
    # but the policy itself is exercised below against committed synthetic
    # attack shapes so the regression suite is not a vacuous for-loop.
    assert validate_batch02_source_tree(
        RESEARCH_DIR, repo_root=REPO_ROOT
    ) == ()


def test_source_policy_accepts_canonical_ceremony_without_hidden_io(tmp_path: Path):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(),
    )
    visited = validate_batch02_source_tree(research, repo_root=repo)
    assert any(path.name == "b2_02_attack.py" for path in visited)


@pytest.mark.parametrize(
    "extra_import,extra_call",
    [
        (
            "from scripts.research.h04_trend_pullback_continuation_lib "
            "import load_development_1m",
            'load_development_1m("/evil/dataset")',
        ),
        (
            "from pyarrow.parquet import read_table as load_bars",
            'load_bars("/evil/data.parquet")',
        ),
        (
            "import pyarrow.parquet as pq",
            'pq.ParquetFile("/evil/data.parquet").read()',
        ),
        (
            "import pandas as pd",
            'pd.read_parquet("/evil/data.parquet")',
        ),
        (
            "import pyarrow.parquet as pq",
            'getattr(pq, "read_table")("/evil/data.parquet")',
        ),
    ],
)
def test_source_policy_rejects_ceremony_plus_direct_or_aliased_hidden_read(
    tmp_path: Path,
    extra_import: str,
    extra_call: str,
):
    source = _canonical_runner(extra=extra_call)
    source = extra_import + "\n" + source
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_hidden_read_in_recursive_lib_helper(tmp_path: Path):
    source = (
        "from scripts.research.lib.core_loader import load_any\n"
        + _canonical_runner(extra='load_any("/evil/data.parquet")')
    )
    helper = """
import pandas as pd

def load_any(path):
    return pd.read_parquet(path)
"""
    repo, research = _synthetic_tree(
        tmp_path,
        runner=source,
        helpers={"scripts/research/lib/core_loader.py": helper},
    )

    with pytest.raises(Batch02SourcePolicyError, match="read_parquet"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_result_unlink_replace_and_rename(tmp_path: Path):
    for expression in (
        "OUT.unlink()",
        "OUT.replace(OTHER)",
        "OUT.rename(OTHER)",
    ):
        repo, research = _synthetic_tree(
            tmp_path / expression.split(".")[1],
            runner=_canonical_runner(extra=expression),
        )
        with pytest.raises(Batch02SourcePolicyError):
            validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_alternate_percentile_helper(tmp_path: Path):
    helper = """
import numpy as np

def trailing_rank(values, window):
    out = np.empty(len(values))
    for i, x in enumerate(values):
        ref = values[max(0, i-window):i]
        out[i] = (ref < x).mean() if len(ref) else np.nan
    return out
"""
    source = (
        "from scripts.research.lib.rank_helper import trailing_rank\n"
        + _canonical_runner(extra="trailing_rank(X, 10)")
    )
    repo, research = _synthetic_tree(
        tmp_path,
        runner=source,
        helpers={"scripts/research/lib/rank_helper.py": helper},
    )

    with pytest.raises(Batch02SourcePolicyError, match="rank/percentile"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_unused_canonical_import_plus_h03_midrank(tmp_path: Path):
    source = """
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
    rolling_midrank_percentile,
)
from scripts.research.h03_extreme_impulse_lib import (
    rolling_midrank_percentile as pctl,
)

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={},
    )
    pctl(X, window=10)
    persist_batch02_result(
        OUT,
        {"status": "closed"},
        run_context=ctx,
    )
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def _hollow_test_context(repo_root: Path) -> Batch02RunContext:
    ctx = object.__new__(Batch02RunContext)
    object.__setattr__(
        ctx,
        "run_identity",
        {
            "hypothesis_id": "B2-02",
            "stage": "development",
            "proof": "canonical",
        },
    )
    object.__setattr__(ctx, "_run_identity_sha256", "e" * 64)
    object.__setattr__(ctx, "code_freeze", SimpleNamespace(repo_root=repo_root))
    return ctx


def test_durable_result_reservation_blocks_unlink_then_repersist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = _hollow_test_context(tmp_path)
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    path = (
        tmp_path / "artifacts" / "b2_02" / "B2_02_DEV_RESULTS.json"
    )
    first = persist_batch02_result(path, {"version": 1}, run_context=ctx)
    assert len(first) == 64
    assert path.exists()

    # Simulate the red-team cleanup/retry bypass outside future-B2 source.
    path.unlink()
    assert not path.exists()

    with pytest.raises(ArtifactExistsError, match="previously reserved"):
        persist_batch02_result(path, {"version": 2}, run_context=ctx)
    assert not path.exists()


def test_durable_result_reservation_blocks_existing_logical_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = _hollow_test_context(tmp_path)
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    path = (
        tmp_path / "artifacts" / "b2_02" / "B2_02_DEV_RESULTS.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"legacy": true}\n', encoding="utf-8")

    with pytest.raises(ArtifactExistsError):
        persist_batch02_result(path, {"version": 2}, run_context=ctx)

    # Fail closed: the reservation remains even after the failed attempt.
    path.unlink()
    with pytest.raises(ArtifactExistsError, match="previously reserved"):
        persist_batch02_result(path, {"version": 3}, run_context=ctx)


def test_canonical_loader_rejects_hollow_run_context_before_pyarrow_io():
    forged = object.__new__(Batch02RunContext)

    with pytest.raises(
        Batch02ContractError,
        match="created by prepare_batch02_run",
    ):
        load_authorized_parquet_table(
            run_context=forged,
            columns=("open_time_ms", "close"),
        )


def test_canonical_loader_rejects_bad_column_contract_before_io(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    ctx = _hollow_test_context(tmp_path)
    object.__setattr__(ctx, "_authorized_dataset", object())
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    with pytest.raises(Batch02ContractError, match="columns"):
        load_authorized_parquet_table(
            run_context=ctx,
            columns=(),
        )


def test_contract_loader_does_not_accept_plain_paths_or_fake_objects(tmp_path: Path):
    for value in (tmp_path, object()):
        with pytest.raises(Batch02ContractError, match="Batch02RunContext"):
            load_authorized_parquet_table(
                run_context=value,  # type: ignore[arg-type]
                columns=("close",),
            )


@pytest.mark.parametrize(
    "extra_import,extra_call",
    [
        ("import pandas as pd", "pd.Series(X).rank()"),
        (
            "from scipy.stats import percentileofscore",
            "percentileofscore(X, 1.0)",
        ),
        ("import numpy as np", "np.searchsorted(X, 1.0)"),
    ],
)
def test_source_policy_rejects_common_alternate_rank_primitives(
    tmp_path: Path,
    extra_import: str,
    extra_call: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=extra_call)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="rank/percentile"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_shadowed_canonical_persist(tmp_path: Path):
    source = """
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)

def persist_batch02_result(*args, **kwargs):
    return "forged"

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={},
    )
    persist_batch02_result(OUT, {"status": "fake"}, run_context=ctx)
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="shadowed"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_requires_persist_context_from_prepare(tmp_path: Path):
    source = """
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={},
    )
    persist_batch02_result(OUT, {"status": "fake"}, run_context=OTHER)
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="assigned from prepare"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_canonical_name_shadowed_by_import(tmp_path: Path):
    source = """
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)
from other.module import persist as persist_batch02_result

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={},
    )
    persist_batch02_result(OUT, {"status": "fake"}, run_context=ctx)
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="shadowed by import"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_discovers_generic_named_runner_by_prepare_call(tmp_path: Path):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    experiments = research / "experiments"
    experiments.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")

    source = (
        "from scripts.research.h04_trend_pullback_continuation_lib "
        "import load_development_1m\n"
        + _canonical_runner(extra='load_development_1m("/evil")')
    )
    (experiments / "generic_experiment.py").write_text(source, encoding="utf-8")

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_treats_lib_suffix_with_prepare_as_runner(tmp_path: Path):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    research.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (research / "b2_02_fake_lib.py").write_text(
        """
from scripts.research.lib.batch02_contracts import prepare_batch02_run

def helper():
    return prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={},
    )
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError, match="missing canonical"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_direct_partition_path_extraction(tmp_path: Path):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(
            extra="ctx._authorized_dataset.list_monthly_partitions()"
        ),
    )
    with pytest.raises(Batch02SourcePolicyError, match="list_monthly_partitions"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "prepare_import,prepare_setup,prepare_call",
    [
        (
            "from scripts.research.lib.batch02_contracts import "
            "prepare_batch02_run as start",
            "",
            "start",
        ),
        (
            "from scripts.research.lib.batch02_contracts import "
            "prepare_batch02_run",
            "start = prepare_batch02_run",
            "start",
        ),
        (
            "from functools import partial\n"
            "from scripts.research.lib.batch02_contracts import "
            "prepare_batch02_run",
            "start = partial(prepare_batch02_run)",
            "start",
        ),
    ],
)
def test_source_policy_discovers_generic_prepare_indirection(
    tmp_path: Path,
    prepare_import: str,
    prepare_setup: str,
    prepare_call: str,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    experiments = research / "experiments"
    experiments.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")

    source = f"""
{prepare_import}
import pandas as pd

{prepare_setup}

def main():
    {prepare_call}(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "generic"),
        seeds={{}},
    )
    pd.read_parquet("/evil/data.parquet")
"""
    (experiments / "generic_runner.py").write_text(source, encoding="utf-8")

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_discovers_helper_with_aliased_prepare_even_if_importer_is_generic(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    experiments = research / "experiments"
    lib = research / "lib"
    experiments.mkdir(parents=True)
    lib.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")
    (lib / "__init__.py").write_text("", encoding="utf-8")

    (lib / "prepare_wrapper.py").write_text(
        """
from scripts.research.lib.batch02_contracts import prepare_batch02_run as _prepare

def start(**kwargs):
    return _prepare(**kwargs)
""",
        encoding="utf-8",
    )
    (experiments / "generic_runner.py").write_text(
        """
from scripts.research.lib.prepare_wrapper import start
import pandas as pd

def main():
    start()
    pd.read_parquet("/evil/data.parquet")
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,extra_call",
    [
        ("import numpy as np", 'np.memmap("/evil/raw", mode="r")'),
        ("import pyarrow as pa", 'pa.memory_map("/evil/raw").read()'),
        ("import pandas as pd", 'pd.read_sql("select * from bars", CONN)'),
        ("import pandas as pd", 'pd.read_hdf("/evil/bars.h5")'),
        ("from pathlib import Path", 'Path("/evil").glob("*.parquet")'),
        ("from pathlib import Path", 'Path("/evil").iterdir()'),
        ("import sqlite3", 'sqlite3.connect("/evil/bars.db")'),
    ],
)
def test_source_policy_rejects_additional_filesystem_and_db_entrypoints(
    tmp_path: Path,
    extra_import: str,
    extra_call: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=extra_call)
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_canonical_module_attribute_replacement(tmp_path: Path):
    source = """
import scripts.research.lib.batch02_contracts as bc
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)

def fake_strength(values, width):
    return values

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={},
    )
    bc.rolling_midrank_percentile = fake_strength
    bc.rolling_midrank_percentile(X, window=10)
    persist_batch02_result(OUT, {"status": "closed"}, run_context=ctx)
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(
        Batch02SourcePolicyError,
        match="module attribute may not be reassigned",
    ):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_explicitly_does_not_claim_arbitrary_math_semantic_proof(
    tmp_path: Path,
):
    # Static AST policy cannot prove that arbitrary numerical Python is or is
    # not a percentile implementation.  This neutral-name arithmetic remains
    # outside the linter's guarantee by design; hypothesis freeze/review must
    # own the semantic wiring to rolling_midrank_percentile when required.
    source = _canonical_runner(
        extra="""
values = np.asarray([1.0, 2.0, 3.0])
width = 2
out = np.full(len(values), np.nan)
for i in range(width, len(values)):
    ref = values[:i]
    x = values[i]
    count_less = float(np.sum(ref < x))
    out[i] = count_less / float(len(ref))
"""
    )
    source = "import numpy as np\n" + source
    repo, research = _synthetic_tree(tmp_path, runner=source)

    visited = validate_batch02_source_tree(research, repo_root=repo)
    assert any(path.name == "b2_02_attack.py" for path in visited)


def test_source_policy_discovers_generic_module_qualified_prepare_indirection(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    experiments = research / "experiments"
    experiments.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")

    (experiments / "generic_runner.py").write_text(
        """
import scripts.research.lib.batch02_contracts as bc
import pandas as pd

start = bc.prepare_batch02_run

def main():
    start(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "generic"),
        seeds={},
    )
    pd.read_parquet("/evil/data.parquet")
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_setattr_monkeypatch_of_canonical_contract(
    tmp_path: Path,
):
    source = """
import scripts.research.lib.batch02_contracts as bc
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)

def fake_strength(values, width):
    return values

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-02",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={},
    )
    setattr(bc, "rolling_midrank_percentile", fake_strength)
    persist_batch02_result(OUT, {"status": "closed"}, run_context=ctx)
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError, match="setattr"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,extra",
    [
        (
            "import pandas as pd",
            'reader = pd.read_parquet\nreader("/evil/data.parquet")',
        ),
        (
            "from pathlib import Path",
            'reader = Path("/evil/data").read_text\nreader()',
        ),
    ],
)
def test_source_policy_rejects_extracted_forbidden_io_attribute(
    tmp_path: Path,
    extra_import: str,
    extra: str,
):
    indented_extra = extra.replace("\n", "\n    ")
    source = extra_import + "\n" + _canonical_runner(extra=indented_extra)
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError, match="forbidden direct I/O"):
        validate_batch02_source_tree(research, repo_root=repo)



def test_source_policy_discovers_parent_package_attrgetter_prepare_bypass(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    experiments = research / "experiments"
    experiments.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")

    (experiments / "generic_runner.py").write_text(
        """
import operator
import scripts.research.lib as lib
import pandas as pd

start = operator.attrgetter("prepare_batch02_run")(lib.batch02_contracts)

def main():
    start()
    pd.read_parquet("/evil/data.parquet")
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_discovers_top_package_qualified_prepare_bypass(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    experiments = research / "experiments"
    experiments.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")

    (experiments / "generic_runner.py").write_text(
        """
import scripts
import pandas as pd

start = scripts.research.lib.batch02_contracts.prepare_batch02_run

def main():
    start()
    pd.read_parquet("/evil/data.parquet")
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_discovers_computed_dynamic_prepare_bypass(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    experiments = research / "experiments"
    experiments.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")

    (experiments / "generic_runner.py").write_text(
        """
import pandas as pd

mod = __import__(".".join(["scripts", "research", "lib", "batch02_contracts"]))
start = object.__getattribute__(mod, "prepare_batch02_run")

def main():
    start()
    pd.read_parquet("/evil/data.parquet")
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_star_import_bare_reader(tmp_path: Path):
    source = "from pandas import *\n" + _canonical_runner(
        extra='read_parquet("/evil/data.parquet")'
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,extra_call",
    [
        ("", '__builtins__["open"]("/evil/data.parquet", "rb").read()'),
        ("import io", 'io.FileIO("/evil/data.parquet").read()'),
        ("import os", 'os.popen("cat /evil/data.parquet").read()'),
        (
            "import urllib.request",
            'urllib.request.urlopen("file:///evil/data.parquet").read()',
        ),
        (
            "import operator\nimport pandas as pd",
            'operator.attrgetter("read_parquet")(pd)("/evil/data.parquet")',
        ),
        (
            "import operator\nimport pandas as pd",
            'operator.methodcaller("read_parquet", "/evil/data.parquet")(pd)',
        ),
        (
            "import pandas as pd",
            'object.__getattribute__(pd, "read_parquet")("/evil/data.parquet")',
        ),
    ],
)
def test_source_policy_rejects_reflection_and_low_level_io_escape_hatches(
    tmp_path: Path,
    extra_import: str,
    extra_call: str,
):
    source = (extra_import + "\n" if extra_import else "") + _canonical_runner(
        extra=extra_call
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_discovers_future_b2_runner_outside_research_tree(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    research = scripts / "research"
    experiments = scripts / "experiments"
    research.mkdir(parents=True)
    experiments.mkdir(parents=True)
    (scripts / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "__init__.py").write_text("", encoding="utf-8")
    (experiments / "b2_02_outside.py").write_text(
        """
import pandas as pd

def main():
    return pd.read_parquet("/evil/data.parquet")
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "import_line",
    [
        "from builtins import open as load_file",
        "from builtins import exec as run_code",
        "from builtins import eval as compute",
        "from builtins import compile as build_code",
    ],
)
def test_source_policy_rejects_aliased_forbidden_builtins_by_origin(
    tmp_path: Path,
    import_line: str,
):
    source = import_line + "\n" + _canonical_runner()
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(
        Batch02SourcePolicyError,
        match="forbidden direct I/O symbol import",
    ):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "module_name",
    [
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
    ],
)
def test_source_policy_rejects_stdlib_file_process_escape_modules(
    tmp_path: Path,
    module_name: str,
):
    source = f"import {module_name}\n" + _canonical_runner()
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(
        Batch02SourcePolicyError,
        match="forbidden direct/dynamic I/O module import",
    ):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_discovers_repo_root_future_b2_runner(tmp_path: Path):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    research.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (repo / "b2_02_root.py").write_text(
        """
import pandas as pd

def main():
    return pd.read_parquet("/fixture/outcome.parquet")
""",
        encoding="utf-8",
    )

    with pytest.raises(Batch02SourcePolicyError, match="forbidden direct I/O"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_contract_function_globals_access(tmp_path: Path):
    source = _canonical_runner(
        extra='marker = persist_batch02_result.__globals__'
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError, match="__globals__"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_source_policy_rejects_fake_attribute_ceremony_even_with_real_imports(
    tmp_path: Path,
):
    source = """
from types import SimpleNamespace
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)

h = SimpleNamespace(
    verify_batch02_code=lambda **kwargs: object(),
    prepare_batch02_run=lambda **kwargs: object(),
    persist_batch02_result=lambda *args, **kwargs: "forged",
)

def main():
    h.verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = h.prepare_batch02_run()
    h.persist_batch02_result(OUT, {"status": "closed"}, run_context=ctx)
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)

    with pytest.raises(Batch02SourcePolicyError, match="direct canonical"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra",
    [
        'ARRAY.tofile("/fixture/output.bin")',
        'PATH.hardlink_to("/fixture/output.bin")',
    ],
)
def test_source_policy_rejects_unsanctioned_write_link_attributes(
    tmp_path: Path,
    extra: str,
):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=extra),
    )

    with pytest.raises(Batch02SourcePolicyError, match="forbidden direct I/O"):
        validate_batch02_source_tree(research, repo_root=repo)

# RT-20260830 capability/TCB regression closure

@pytest.mark.parametrize(
    "expression",
    [
        "captured = open",
        "captured = exec",
        "captured = eval",
        "captured = compile",
        "(captured := open)",
    ],
)
def test_rt_builtin_capability_name_capture_is_rejected(
    tmp_path: Path,
    expression: str,
):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=expression),
    )
    with pytest.raises(Batch02SourcePolicyError, match="forbidden builtin capability"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize("module_name", ["argparse", "logging"])
def test_rt_non_transform_stdlib_is_default_denied(
    tmp_path: Path,
    module_name: str,
):
    source = f"import {module_name}\n" + _canonical_runner()
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="transform allowlist"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        ("import pyarrow as pa", 'fh = pa.OSFile("/evil/data.parquet", "r")'),
        ("import pyarrow as pa", 'fh = pa.PythonFile(OBJ)'),
        ("import pyarrow as pa", 'fh = pa.output_stream("/evil/out.bin")'),
        ("import numpy as np", 'arr = np.fromregex("/evil/data.txt", ".*", dtype=str)'),
        ("import pandas as pd", 'writer = pd.ExcelWriter("/evil/out.xlsx")'),
        ("from pathlib import Path", 'Path("/evil/out").mkdir()'),
        ("import numpy as np", 'np.savez("/evil/out.npz", x=[1, 2])'),
        ("import pandas as pd", 'pd.DataFrame({"x": [1]}).to_stata("/evil/out.dta")'),
        ("import pandas as pd", 'pd.DataFrame({"x": [1]}).to_html("/evil/out.html")'),
    ],
)
def test_rt_allowlisted_packages_cannot_reacquire_file_capabilities(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        ("import pandas as pd", 'reader = pd.io.stata.StataReader("/evil/data.dta")'),
        ("import pyarrow as pa", "fs = pa.fs.LocalFileSystem()"),
    ],
)
def test_rt_forbidden_submodule_attribute_hops_are_rejected(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="package surface"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "symbol",
    ["write_json_new", "authorize_dataset_access"],
)
def test_rt_contract_internal_reexports_are_not_hypothesis_api(
    tmp_path: Path,
    symbol: str,
):
    source = (
        f"from scripts.research.lib.batch02_contracts import {symbol}\n"
        + _canonical_runner()
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="not part of the hypothesis API"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_safe_in_memory_copy_and_regex_compile_remain_allowed(tmp_path: Path):
    source = (
        "import copy\nimport re\n"
        + _canonical_runner(
            extra='x = copy.copy([1, 2, 3]); pattern = re.compile("x+")'
        )
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    visited = validate_batch02_source_tree(research, repo_root=repo)
    assert any(path.name == "b2_02_attack.py" for path in visited)


def test_rt_reflection_reduce_paths_are_rejected(tmp_path: Path):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(
            extra="state = persist_batch02_result.__reduce_ex__(4)"
        ),
    )
    with pytest.raises(Batch02SourcePolicyError, match="reflection"):
        validate_batch02_source_tree(research, repo_root=repo)

# RT-20260831 successor repair regressions

@pytest.mark.parametrize(
    "import_line,expression",
    [
        ("from numpy import load as npload", 'data = npload("/evil/data.npy")'),
        ("from pandas import read_fwf as load_bars", 'data = load_bars("/evil/data.txt")'),
    ],
)
def test_rt_import_alias_uses_shared_io_origin_predicate(
    tmp_path: Path,
    import_line: str,
    expression: str,
):
    source = import_line + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="forbidden direct I/O symbol import"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        ("import pandas as pd", 'x = pd.ExcelFile("/evil/data.xlsx")'),
        ("import pyarrow as pa", 'x = pa.NativeFile()'),
        ("import pyarrow as pa", 'x = pa.MemoryMappedFile()'),
        ("import pandas as pd", 'pd.DataFrame({"x": [1]}).to_latex("/evil/out.tex")'),
        ("import pandas as pd", 'pd.DataFrame({"x": [1]}).to_xml("/evil/out.xml")'),
        ("from pathlib import Path", 'Path("/evil/out").touch()'),
        ("from pathlib import Path", 'Path("/evil/out").symlink_to("/evil/source")'),
        ("from pathlib import Path", 'Path("/evil/out").chmod(0o600)'),
    ],
)
def test_rt_additional_allowlisted_file_surfaces_are_rejected(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize("location", ["generic_runner.py", "docs/experiment.py"])
def test_rt_prepare_reference_is_discovered_repo_wide(
    tmp_path: Path,
    location: str,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    research.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    target = repo / location
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "import pandas as pd\n"
        + _canonical_runner(extra='pd.read_parquet("/evil/data.parquet")'),
        encoding="utf-8",
    )
    with pytest.raises(Batch02SourcePolicyError, match="read_parquet"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "module_import,expression",
    [
        (
            "import scripts.research.lib.batch02_contracts as contracts",
            "x = contracts.authorize_dataset_access",
        ),
        (
            "from scripts.research.lib import batch02_contracts as contracts",
            "x = contracts.AuthorizedDataset",
        ),
    ],
)
def test_rt_contracts_module_object_is_not_hypothesis_capability(
    tmp_path: Path,
    module_import: str,
    expression: str,
):
    source = module_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="module object"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        (
            "from numpy import ctypeslib",
            'x = ctypeslib.load_library("c", "/lib")',
        ),
        (
            "import numpy as np",
            'x = np.ctypeslib.load_library("c", "/lib")',
        ),
        (
            "from pyarrow import flight",
            'x = flight.FlightClient("grpc://localhost:1")',
        ),
        (
            "import pyarrow as pa",
            "x = pa.flight",
        ),
        (
            "from pyarrow import orc",
            'x = orc.ORCFile("/evil/data.orc")',
        ),
    ],
)
def test_rt_capability_subpackages_cannot_hide_under_allowed_parent(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "probe",
    [
        "is_file",
        "is_dir",
        "is_symlink",
        "owner",
        "group",
        "samefile",
    ],
)
def test_rt_pathlib_filesystem_probes_are_rejected(
    tmp_path: Path,
    probe: str,
):
    if probe == "samefile":
        expression = 'x = Path("/a").samefile("/b")'
    else:
        expression = f'x = Path("/evil").{probe}()'
    source = "from pathlib import Path\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_hashlib_file_digest_surface_is_rejected(tmp_path: Path):
    source = (
        "import hashlib\n"
        + _canonical_runner(extra="digest = hashlib.file_digest(HANDLE, 'sha256')")
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="file_digest"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_symlink_escape_fails_with_policy_error(tmp_path: Path):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    research.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")

    outside = tmp_path / "outside.py"
    outside.write_text(
        "from scripts.research.lib.batch02_contracts import prepare_batch02_run\n",
        encoding="utf-8",
    )
    link = repo / "linked_runner.py"
    link.symlink_to(outside)

    with pytest.raises(Batch02SourcePolicyError, match="outside repository"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_safe_import_aliases_and_compute_remain_allowed(tmp_path: Path):
    source = (
        "from re import compile as cre\n"
        "import numpy as np\n"
        "import pyarrow.compute as pc\n"
        + _canonical_runner(
            extra=(
                'pattern = cre("x+"); '
                "arr = np.asarray([1, 2, 3]).copy(); "
                "result = pc.sum(arr)"
            )
        )
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    visited = validate_batch02_source_tree(research, repo_root=repo)
    assert any(path.name == "b2_02_attack.py" for path in visited)


# RT-20260831 protected-binding string-target regressions

@pytest.mark.parametrize(
    "extra",
    [
        """
class CallableError(Exception):
    def __call__(self, **kwargs):
        return object()

try:
    raise CallableError()
except CallableError as verify_batch02_code:
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
""",
        """
candidate = (lambda **kwargs: object())
match candidate:
    case verify_batch02_code:
        verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
""",
        """
candidate = [lambda **kwargs: object()]
match candidate:
    case [*verify_batch02_code]:
        pass
""",
        """
candidate = {"x": 1}
match candidate:
    case {**verify_batch02_code}:
        pass
""",
    ],
)
def test_rt_protected_canonical_bindings_cannot_hide_in_string_target_nodes(
    tmp_path: Path,
    extra: str,
):
    indented_extra = extra.strip().replace("\n", "\n    ")
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=indented_extra),
    )
    with pytest.raises(Batch02SourcePolicyError, match="shadowed"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "expression",
    [
        'pd.DataFrame({"x": [1]}).to_string("/evil/out.txt")',
        'pd.Series([1]).to_string("/evil/out.txt")',
        'pd.DataFrame({"x": [1]}).to_orc("/evil/out.orc")',
        'pd.DataFrame({"x": [1]}).to_gbq("project.dataset.table")',
    ],
)
def test_rt_pandas_output_methods_with_external_side_effects_are_rejected(
    tmp_path: Path,
    expression: str,
):
    source = "import pandas as pd\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="forbidden direct I/O"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_local_function_builtins_cannot_reacquire_open(tmp_path: Path):
    source = _canonical_runner(
        extra=(
            "def helper():\n"
            "        return None\n"
            "    opener = helper.__builtins__[\"open\"]\n"
            "    data = b\"\".join(opener(\"/evil/data.parquet\", \"rb\"))"
        )
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="reflection"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "expression",
    [
        "classes = object.__subclasses__()",
        "lineage = int.__mro__",
        "bases = int.__bases__",
        "base = int.__base__",
        "lineage = int.mro()",
    ],
)
def test_rt_class_graph_reflection_is_rejected(tmp_path: Path, expression: str):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=expression),
    )
    with pytest.raises(Batch02SourcePolicyError, match="reflection"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_traceback_frame_cannot_reacquire_builtins(tmp_path: Path):
    extra = """
try:
    1 / 0
except Exception as err:
    opener = err.__traceback__.tb_frame.f_builtins["open"]
    data = b"".join(opener("/evil/data.parquet", "rb"))
"""
    indented_extra = extra.strip().replace("\n", "\n    ")
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=indented_extra),
    )
    with pytest.raises(Batch02SourcePolicyError, match="reflection"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "expression",
    [
        "frame = GEN.gi_frame",
        "frame = CORO.cr_frame",
        "frame = ASYNCGEN.ag_frame",
        "frame = TRACE.tb_frame",
        "builtins_map = FRAME.f_builtins",
        "globals_map = FRAME.f_globals",
        "locals_map = FRAME.f_locals",
        "parent = FRAME.f_back",
    ],
)
def test_rt_frame_family_reflection_attributes_are_rejected(
    tmp_path: Path,
    expression: str,
):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=expression),
    )
    with pytest.raises(Batch02SourcePolicyError, match="reflection"):
        validate_batch02_source_tree(research, repo_root=repo)


# RT-20260901 final class-level repair regressions

@pytest.mark.parametrize(
    "extra_import,expression",
    [
        ("import pathlib", "marker = pathlib.os"),
        ("from pathlib import os", "marker = os"),
        ("import pathlib", "marker = pathlib.sys.modules"),
        ("import numpy as np", "marker = np.lib.format.os"),
    ],
)
def test_rt_allowed_packages_cannot_reexport_denied_capability_modules(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        ("import numpy as np", 'x = np.lib._datasource.DataSource("")'),
        ("from numpy.lib import _datasource", 'x = _datasource.DataSource("")'),
    ],
)
def test_rt_numpy_datasource_file_constructors_are_rejected(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "expression",
    [
        'x = Path.cwd()',
        'x = Path.home()',
        'x = Path("/x").resolve()',
        'x = Path("/x").absolute()',
        'x = Path("~/x").expanduser()',
        'x = Path("/x").is_junction()',
        'x = Path("/x").link_to("/y")',
    ],
)
def test_rt_remaining_pathlib_filesystem_identity_probes_are_rejected(
    tmp_path: Path,
    expression: str,
):
    source = "from pathlib import Path\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.skipif(
    not hasattr(ast, "TypeVar"),
    reason="PEP 695 type-parameter AST nodes require Python 3.12+",
)
@pytest.mark.parametrize(
    "declaration",
    [
        "def helper[persist_batch02_result]():\n        return None",
        "def helper[**prepare_batch02_run]():\n        return None",
        "def helper[*verify_batch02_code]():\n        return None",
    ],
)
def test_rt_pep695_type_parameters_cannot_shadow_canonical_bindings(
    tmp_path: Path,
    declaration: str,
):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=declaration),
    )
    with pytest.raises(Batch02SourcePolicyError, match="shadowed"):
        validate_batch02_source_tree(research, repo_root=repo)


# RT-20260901 follow-up: foreign-module re-exports, import-system objects,
# remaining object-model surfaces, fail-closed unknown to_* writers, and
# protected-binding string targets (global/nonlocal/del).


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        ("import pathlib", "x = pathlib.posixpath.isfile('/evil')"),
        ("from pathlib import posixpath", "x = posixpath.isfile('/evil')"),
        ("from pathlib import ntpath", "x = ntpath.isdir('/evil')"),
        ("import enum", "opener = enum.bltns.open"),
        ("import collections", "mods = collections._sys.modules"),
        ("import dataclasses", "frame = dataclasses.inspect.currentframe()"),
        ("import typing", "fn = typing.operator.attrgetter('x')"),
    ],
)
def test_rt_allowlisted_packages_cannot_reexport_foreign_modules(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "expression",
    [
        "loader = json.__loader__",
        "spec = json.__spec__",
        "json.__loader__.set_data('/evil/out', b'x')",
        "json.__spec__.loader.exec_module(json)",
        "paths = json.__path__",
    ],
)
def test_rt_import_system_objects_are_not_hypothesis_capabilities(
    tmp_path: Path,
    expression: str,
):
    source = "import json\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="reflection|set_data|__path__"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "expression",
    [
        "code = FRAME.f_code",
        "value = CELL.cell_contents",
    ],
)
def test_rt_code_object_and_closure_cell_surfaces_are_rejected(
    tmp_path: Path,
    expression: str,
):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=expression),
    )
    with pytest.raises(Batch02SourcePolicyError, match="reflection"):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        ("import pandas as pd", "x = pd.DataFrame({'a': [1]}).to_iceberg('t')"),
        ("import pandas as pd", "writer = pd.DataFrame.to_iceberg"),
        (
            "from numpy import testing",
            "testing.runstring('print(1)', {})",
        ),
        ("import numpy as np", "np.testing.temppath"),
    ],
)
def test_rt_unknown_external_writers_and_testing_subpackage_are_rejected(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


@pytest.mark.parametrize(
    "extra",
    [
        "global persist_batch02_result",
        "del persist_batch02_result",
        "def inner():\n        nonlocal persist_batch02_result\n        return None",
    ],
)
def test_rt_protected_bindings_cannot_use_global_nonlocal_or_del(
    tmp_path: Path,
    extra: str,
):
    repo, research = _synthetic_tree(
        tmp_path,
        runner=_canonical_runner(extra=extra),
    )
    with pytest.raises(Batch02SourcePolicyError, match="shadowed|unbound"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_in_memory_scientific_transforms_remain_allowed(tmp_path: Path):
    source = (
        "import json\n"
        "import math\n"
        "import numpy as np\n"
        "from pathlib import Path\n"
        "import pandas as pd\n"
        + _canonical_runner(
            extra=(
                "payload = json.dumps({'a': 1}); "
                "value = json.loads(payload); "
                "norm = np.linalg.norm(np.asarray([3.0, 4.0])); "
                "frame = pd.DataFrame({'a': [1]}).to_dict(); "
                "arr = pd.Series([1, 2]).to_numpy(); "
                "items = pd.Series([1]).to_list(); "
                "joined = Path('a').joinpath('b'); "
                "pure = Path('a').as_posix(); "
                "root = math.sqrt(norm)"
            )
        )
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    visited = validate_batch02_source_tree(research, repo_root=repo)
    assert any(path.name == "b2_02_attack.py" for path in visited)


# RT-20260901b follow-up: the foreign-module-reexport invariant was
# provenance-sensitive (it traces an attribute-access chain back to the
# import statement that bound it) and that trace was lost the moment an
# imported module reference was copied to an ordinary second local name.
# These regressions protect the general "module/capability provenance"
# class, not one particular module's spelling: they cover a root-import
# copy, a copy of an already-allowlisted submodule, multiple simultaneous
# aliases of the same module, and tuple-destructuring copies, alongside
# confirmation that direct (uncopied) use and ordinary scientific value
# assignment are unaffected.


@pytest.mark.parametrize(
    "extra_import,expression",
    [
        # The exact literal pattern from the architecture task.
        ("import collections", "alias = collections; x = alias._sys.modules"),
        # Same provenance loss for the other originally-cited example.
        ("import enum", "alias = enum; x = alias.bltns"),
        # Copying an aliased root import, not just an unaliased one.
        ("import numpy as np", "np2 = np; x = np2"),
        # Copying an *allowed* submodule reached via attribute access still
        # has to go through its own canonical import, not a second name.
        ("import pyarrow", "pc2 = pyarrow.compute"),
        # Annotated assignment is a distinct AST node from plain Assign.
        ("import collections", "alias: object = collections"),
        # Walrus is a third distinct binding form.
        ("import collections", "x = (alias := collections)"),
    ],
)
def test_rt_module_reference_cannot_be_copied_to_new_local_binding(
    tmp_path: Path,
    extra_import: str,
    expression: str,
):
    source = extra_import + "\n" + _canonical_runner(extra=expression)
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="copied"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_multiple_aliases_of_same_module_are_consistently_protected(
    tmp_path: Path,
):
    source = (
        "import collections as c1\nimport collections as c2\n"
        + _canonical_runner(extra="x = c1; y = c2")
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="copied") as excinfo:
        validate_batch02_source_tree(research, repo_root=repo)
    # Both aliases are caught, not just whichever happens to be visited first.
    messages = str(excinfo.value)
    assert "x = collections" in messages
    assert "y = collections" in messages


def test_rt_tuple_destructuring_copy_of_module_references_is_rejected(
    tmp_path: Path,
):
    source = "import numpy as np\nimport pandas as pd\n" + _canonical_runner(
        extra="a, b = np, pd"
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="copied"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_direct_foreign_module_reexport_still_denied_without_any_copy(
    tmp_path: Path,
):
    # Control: the underlying foreign-module-reexport class must still fire
    # on its own, independent of the new copy-prohibition.
    source = "import collections\n" + _canonical_runner(
        extra="mods = collections._sys.modules"
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError, match="foreign module"):
        validate_batch02_source_tree(research, repo_root=repo)


def test_rt_ordinary_scientific_values_remain_freely_assignable(
    tmp_path: Path,
):
    # Calling through an import binding, and assigning/reusing the computed
    # result, must remain unaffected by the copy-prohibition -- only a bare
    # module-reference copy is restricted, not generic assignment.
    source = (
        "import numpy as np\n"
        "import pandas as pd\n"
        "import pyarrow.compute as pc\n"
        + _canonical_runner(
            extra=(
                "arr = np.asarray([1, 2, 3]); "
                "frame = pd.DataFrame({'x': arr}); "
                "total = pc.sum(arr); "
                "doubled = total.as_py() * 2; "
                "norm = np.linalg.norm(arr)"
            )
        )
    )
    repo, research = _synthetic_tree(tmp_path, runner=source)
    visited = validate_batch02_source_tree(research, repo_root=repo)
    assert any(path.name == "b2_02_attack.py" for path in visited)


def test_rt_h01_h05_and_b2_01_frozen_trees_are_unaffected_by_the_repair():
    # The real repository's frozen historical hypothesis code is not part of
    # the future-B2 policy closure at all (only b2_(?!01)NN files are). This
    # asserts that claim continues to hold after the copy-prohibition and
    # static foreign-module rewrite: running the real linter against the
    # actual on-disk research tree still returns no violations, exactly as
    # before this repair, and does not require importing/evaluating any
    # H01-H05 or B2-01 module to do so.
    assert validate_batch02_source_tree(
        RESEARCH_DIR, repo_root=REPO_ROOT
    ) == ()
