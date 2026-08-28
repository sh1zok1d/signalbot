from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

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


def _hollow_test_context() -> Batch02RunContext:
    ctx = object.__new__(Batch02RunContext)
    object.__setattr__(ctx, "run_identity", {"proof": "canonical"})
    object.__setattr__(ctx, "_run_identity_sha256", "e" * 64)
    return ctx


def test_durable_result_reservation_blocks_unlink_then_repersist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = _hollow_test_context()
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    path = tmp_path / "B2_02_DEV_RESULTS.json"
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
    ctx = _hollow_test_context()
    monkeypatch.setattr(batch02_contracts, "_reverify_run_code", lambda value: None)

    path = tmp_path / "B2_02_DEV_RESULTS.json"
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
):
    ctx = _hollow_test_context()
    object.__setattr__(ctx, "authorized_dataset", object())
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
