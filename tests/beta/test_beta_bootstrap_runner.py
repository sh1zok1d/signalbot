"""Bounded bootstrap wrapper: loops the unchanged bootstrap, fails fast, verifies idempotency."""
import io
from datetime import datetime, timedelta, timezone

import pytest

from runtime import beta_bootstrap_runner as r

T = datetime(2026, 3, 1, tzinfo=timezone.utc)


def rep(status="PARTIAL", written=288, skipped=0, complete=False, target=T):
    return {"status": status, "written": written, "skipped_existing": skipped, "unmaterialized": 0,
            "last_bucket": target.isoformat(), "target": target.isoformat(), "complete": complete}


def seq(*reports):
    it = iter(reports)
    calls = []

    def invoke():
        calls.append(1)
        x = next(it)
        if isinstance(x, Exception):
            raise x
        return x
    return invoke, calls


def go(invoke, **kw):
    out = io.StringIO()
    return r.run_until_complete(invoke, out=out, **kw), out.getvalue()


def test_runs_until_complete_then_verifies_once():
    invoke, calls = seq(rep(), rep(), rep("OK", 1, complete=True), rep("OK", 0, complete=True))
    code, out = go(invoke)
    assert code == r.EXIT_OK and len(calls) == 4
    assert "iteration 1/40" in out and "iteration 3/40" in out and "idempotency verification" in out
    assert "COMPLETE and verified" in out


def test_verification_may_write_only_newly_closed_buckets():
    later = T + timedelta(minutes=10)
    invoke, _ = seq(rep("OK", 5, complete=True), rep("OK", 2, complete=True, target=later))
    assert go(invoke)[0] == r.EXIT_OK
    invoke, _ = seq(rep("OK", 5, complete=True), rep("OK", 3, complete=True, target=later))
    code, out = go(invoke)
    assert code == r.EXIT_VERIFY and "only 2" in out
    invoke, _ = seq(rep("OK", 5, complete=True), rep("OK", 1, complete=True))
    assert go(invoke)[0] == r.EXIT_VERIFY


def test_verification_must_itself_complete():
    invoke, _ = seq(rep("OK", 5, complete=True), rep("PARTIAL", 0, complete=False))
    assert go(invoke)[0] == r.EXIT_VERIFY


@pytest.mark.parametrize("bad", [rep("DISABLED"), rep("LOCKED"), rep("DB_UNAVAILABLE"),
                                 r.BootstrapRunError("bootstrap exited 1 without a JSON report")])
def test_fails_immediately_on_bootstrap_error(bad):
    invoke, calls = seq(rep(), bad, rep())
    code, out = go(invoke)
    assert code == r.EXIT_ERROR and len(calls) == 2 and "FAILED" in out


def test_fails_when_a_partial_batch_makes_no_progress():
    invoke, calls = seq(rep(), rep(written=0, skipped=0))
    assert go(invoke)[0] == r.EXIT_ERROR and len(calls) == 2


def test_iteration_bound_is_enforced():
    invoke, calls = seq(*[rep() for _ in range(5)])
    code, out = go(invoke, max_iterations=3)
    assert code == r.EXIT_LIMIT and len(calls) == 3 and "after 3 iterations" in out
    with pytest.raises(ValueError):
        go(invoke, max_iterations=0)
    with pytest.raises(ValueError):
        go(invoke, max_iterations=r.MAX_ITERATIONS_CAP + 1)


def test_default_bound_covers_a_full_30_day_bootstrap():
    from beta.config import BetaConfig
    b = BetaConfig.load()["bootstrap"]
    needed = -(-(b["lookback_days"] * 288 + 1) // b["max_buckets_per_run"])
    assert needed == 31 and needed < r.DEFAULT_MAX_ITERATIONS <= r.MAX_ITERATIONS_CAP


def test_cli_rejects_out_of_range_bound():
    with pytest.raises(SystemExit):
        r.main(["--max-iterations", "0"])
    with pytest.raises(SystemExit):
        r.main(["--max-iterations", "101"])


def test_subprocess_invoker_runs_the_existing_command(monkeypatch):
    seen = {}

    class P:
        returncode = 0
        stdout = '{"status": "OK", "complete": true}\n'

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return P()
    monkeypatch.setattr(r.subprocess, "run", fake_run)
    assert r.invoke_bootstrap_subprocess()["status"] == "OK"
    assert seen["cmd"][1].endswith("main.py") and seen["cmd"][2:4] == ["--beta-bootstrap", "--beta-json"]
    P.returncode, P.stdout = 2, '{"status": "DB_UNAVAILABLE"}\n'
    with pytest.raises(r.BootstrapRunError):
        r.invoke_bootstrap_subprocess()
    P.returncode, P.stdout = 1, ""
    with pytest.raises(r.BootstrapRunError):
        r.invoke_bootstrap_subprocess()
