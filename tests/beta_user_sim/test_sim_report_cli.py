"""Reports, manifest, CLI and the read-only exporter guards (no network, no database)."""
import json
import re
import socket
from datetime import datetime, timezone

import pytest

from tools.beta_user_sim import STATUS, STATUS_LABELS
from tools.beta_user_sim.__main__ import main
from tools.beta_user_sim.export import EXPORT_QUERIES, ExportRefused, check_query, connect_kwargs, export_scope
from tools.beta_user_sim.report import (ReportWordingError, build_report, render_markdown,
                                        render_transcript)

from sim_helpers import run

FIXED = datetime(2024, 4, 1, tzinfo=timezone.utc)
COMMIT = {"commit": "TEST", "worktree_dirty": False}


@pytest.fixture(scope="module")
def result():
    return run()[1]


@pytest.fixture(scope="module")
def report(result):
    return build_report(result, run_at=FIXED, commit=COMMIT)


def test_manifest_records_models_prompts_seeds_inputs_and_commit(report, result):
    m = report["manifest"]
    assert m["status"] == STATUS and m["status_labels"] == list(STATUS_LABELS)
    assert m["code"] == COMMIT and m["run_at"] == FIXED.isoformat()
    assert set(m["models"]) == {"ROLE_A_USER", "ROLE_B_AUDITOR", "ROLE_B_JUDGE"}
    assert all("model_id" in x and "settings" in x for x in m["models"].values())
    assert set(m["prompt_versions"]) and all(v.endswith("_V0") for v in m["prompt_versions"].values())
    rc = m["replay_config"]
    assert {"replay_seed", "judge_seed"} <= set(rc) and "seed" in rc["attention"]
    assert m["replay_input_ids"] == result["replay_input_ids"] and m["replay_input_ids"]
    assert m["outcome_version"] == "BETA_OUTCOME_V1"
    assert "not bit-identical" in m["reproducibility"]


def test_report_has_no_composite_score_or_forbidden_wording(report):
    def keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield str(k)
                yield from keys(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from keys(v)
    assert not [k for k in keys(report) if "score" in k.lower() or "p_value" in k.lower()]
    md = render_markdown(report)
    assert "SYNTHETIC" in md and "DESCRIPTIVE_MONITORING" in md
    assert not re.search(r"\bedge\b|predictive|\bPMF\b|p-value", md, re.IGNORECASE)


def test_report_wording_guard_raises(report):
    bad = json.loads(json.dumps(report))
    bad["role_a"]["commands"] = {"predictive edge": 1}
    with pytest.raises(ReportWordingError):
        render_markdown(bad)


def test_daily_and_weekly_grouping(report, result):
    g = report["grouped"]
    assert g["daily"] and g["weekly"]
    for store in (g["daily"], g["weekly"]):
        assert sum(sum(r["messages"].values()) for r in store.values()) == len(result["shown"])
        turns = sum(1 for e in result["transcript"] if e["event"] == "ROLE_A_TURN")
        assert sum(r["turns"] for r in store.values()) == turns
    assert all(len(k) == 10 for k in g["daily"]) and all("-W" in k for k in g["weekly"])


def test_report_sections_present(report):
    assert {"manifest", "role_a", "deterministic_audit", "role_b", "grouped"} == set(report)
    bc = report["role_b"]["blind_comparison"]
    assert {"SIGNALBOT_VS_BASELINE", "CONTROL_BASELINE_VS_BASELINE", "CONTROL_SIGNALBOT_VS_SIGNALBOT",
            "side_bias_all_pairs"} <= set(bc)


def test_full_run_is_deterministic_with_fake_models():
    a = build_report(run()[1], run_at=FIXED, commit=COMMIT)
    b = build_report(run()[1], run_at=FIXED, commit=COMMIT)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_transcript_renders_all_phases(result):
    text = render_transcript(result)
    for event in ("PUSH_ARRIVED", "ROLE_A_TURN", "OUTCOME_UNLOCK", "ROLE_B_AUDIT", "AB_JUDGE"):
        assert event in text


def test_cli_offline_end_to_end_without_network(tmp_path, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket.socket, "connect", no_net)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    bundle = tmp_path / "bundle.json"
    assert main(["make-synthetic-bundle", "--out", str(bundle)]) == 0
    out = tmp_path / "run"
    assert main(["replay", "--bundle", str(bundle), "--out", str(out), "--model", "fake"]) == 0
    for name in ("run.json", "report.json", "report.md", "transcript.md"):
        assert (out / name).stat().st_size > 0
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["manifest"]["status"] == STATUS


def test_cli_openai_model_refuses_without_authorization(tmp_path, monkeypatch):
    monkeypatch.delenv("SIGNALBOT_SIM_ALLOW_NETWORK", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    bundle = tmp_path / "bundle.json"
    main(["make-synthetic-bundle", "--out", str(bundle)])
    with pytest.raises(Exception) as exc:
        main(["replay", "--bundle", str(bundle), "--out", str(tmp_path / "r"), "--model", "openai",
              "--model-id", "x"])
    assert "NetworkNotAuthorized" in type(exc.value).__name__ or "network" in str(exc.value).lower()
    assert not (tmp_path / "r").exists()


def test_export_queries_are_select_only_and_skip_participant_tables():
    for sql in EXPORT_QUERIES.values():
        check_query(sql)
        assert "user_pk" not in sql and "telegram_message_id" not in sql and "error_summary" not in sql
    for bad in ("DELETE FROM beta_episodes", "SELECT 1; DROP TABLE x", "SELECT * FROM beta_users",
                "SELECT x FROM beta_feedback", "SELECT 1 FROM t WHERE a = 1 UPDATE "):
        with pytest.raises(ExportRefused):
            check_query(bad)


def test_export_window_and_dsn_guards():
    with pytest.raises(ExportRefused):
        export_scope(datetime(2024, 12, 31, 12, tzinfo=timezone.utc), datetime(2024, 12, 31, 13, tzinfo=timezone.utc))
    with pytest.raises(ExportRefused):
        export_scope(datetime(2024, 3, 2, tzinfo=timezone.utc), datetime(2024, 3, 1, tzinfo=timezone.utc))
    assert export_scope(datetime(2024, 3, 1, tzinfo=timezone.utc),
                        datetime(2024, 3, 2, tzinfo=timezone.utc)) == "PRE_2025_UNSEALED"
    with pytest.raises(ExportRefused):
        connect_kwargs(None)
    kw = connect_kwargs("postgresql://x")
    assert kw["server_settings"]["default_transaction_read_only"] == "on"
