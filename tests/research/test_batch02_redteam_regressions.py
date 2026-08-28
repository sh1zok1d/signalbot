from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from scripts.research.lib.batch02_contracts import (
    Batch02ContractError,
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
        seeds={{}},
    )
    {extra}
    persist_batch02_result(OUT, {{"status": "closed"}})
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
    pctl(X, window=10)
    persist_batch02_result(OUT, {"status": "closed"})
"""
    repo, research = _synthetic_tree(tmp_path, runner=source)
    with pytest.raises(Batch02SourcePolicyError):
        validate_batch02_source_tree(research, repo_root=repo)


def test_durable_result_reservation_blocks_unlink_then_repersist(tmp_path: Path):
    path = tmp_path / "B2_02_DEV_RESULTS.json"
    first = persist_batch02_result(path, {"version": 1})
    assert len(first) == 64
    assert path.exists()

    # Simulate the red-team cleanup/retry bypass outside future-B2 source.
    path.unlink()
    assert not path.exists()

    with pytest.raises(ArtifactExistsError, match="previously reserved"):
        persist_batch02_result(path, {"version": 2})
    assert not path.exists()


def test_durable_result_reservation_blocks_existing_logical_path(tmp_path: Path):
    path = tmp_path / "B2_02_DEV_RESULTS.json"
    path.write_text('{"legacy": true}\n', encoding="utf-8")

    with pytest.raises(ArtifactExistsError):
        persist_batch02_result(path, {"version": 2})

    # Fail closed: the reservation remains even after the failed attempt.
    path.unlink()
    with pytest.raises(ArtifactExistsError, match="previously reserved"):
        persist_batch02_result(path, {"version": 3})


def test_canonical_loader_rejects_hollow_authorized_dataset_before_pyarrow_io():
    forged = object.__new__(AuthorizedDataset)

    with pytest.raises(DatasetIdentityError, match="created by authorize_dataset_access"):
        load_authorized_parquet_table(
            forged,
            columns=("open_time_ms", "close"),
        )


def test_canonical_loader_rejects_bad_column_contract_before_io():
    forged = object.__new__(AuthorizedDataset)
    # Mint validation occurs before columns by design; a non-proof can never
    # reach the parquet layer regardless of caller-controlled columns.
    with pytest.raises(DatasetIdentityError):
        load_authorized_parquet_table(forged, columns=())


def test_contract_loader_does_not_accept_plain_paths_or_fake_objects(tmp_path: Path):
    for value in (tmp_path, object()):
        with pytest.raises(Batch02ContractError, match="AuthorizedDataset"):
            load_authorized_parquet_table(
                value,  # type: ignore[arg-type]
                columns=("close",),
            )
