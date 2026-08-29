from __future__ import annotations

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
