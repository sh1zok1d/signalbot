"""Paired shadow: V1 and V2 share anchors, keep the first probability, and score one outcome."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from beta.calibration_monitor import (
    JOURNAL_SPEC_ID, PROCEDURE_TOUCH_CHANCE, STATE_FAULT, STATE_INSUFFICIENT, evaluate,
)
from beta.claims import claim_row
from beta.hist_series import Bars, to_ms
from beta.paired_shadow import (
    SHADOW_RECORDING_ENABLED, V1_PROCEDURE_ID, V1_SPEC_DIGEST, V1_SPEC_ID, V2_PROCEDURE_ID,
    V2_SPEC_DIGEST, V2_SPEC_ID, BoundShadowModel, ShadowConflict, ShadowLedger,
    ShadowRecordingDisabled, bind_rangecast_v1, execute_hour, export_row, monitor_observations,
    log_loss, paired_report, plan_issues, plan_shadow_record, score_anchor,
)
from beta.rangecast import P_GRID
from beta.state_tape import sha256_json
from beta_fakes import TEST_DSN

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc
AS_OF = datetime(2024, 1, 1, tzinfo=UTC)
SLOT = AS_OF
PRICE = 65432.1


def _stub(procedure, spec, digest, snapshot, touch_p, neither_p):
    return BoundShadowModel(
        procedure_id=procedure, spec_id=spec, spec_digest=digest, snapshot_id=snapshot,
        touch=lambda horizon, distance, side: touch_p,
        neither=lambda horizon, up, down: neither_p,
    )


def _models(touch_v2=0.80, neither_v2=0.30, snapshot_v2="snap-v2"):
    v1 = _stub(V1_PROCEDURE_ID, V1_SPEC_ID, V1_SPEC_DIGEST, "snap-v1", 0.20, 0.70)
    v2 = _stub(V2_PROCEDURE_ID, V2_SPEC_ID, V2_SPEC_DIGEST, snapshot_v2, touch_v2, neither_v2)
    return v1, v2


def _plan(**overrides):
    v1, v2 = _models()
    args = dict(
        price=PRICE, as_of=AS_OF, issue_slot=SLOT, horizons=("4h",),
        distances=(1.25,), neither_pairs=((0.5, 1.0),),
    )
    args.update(overrides)
    return plan_issues([v1, v2], **args)


def _bars(*, high, low, n=48):
    return Bars(
        t0=to_ms(AS_OF),
        open=np.full(n, PRICE),
        high=np.full(n, high),
        low=np.full(n, low),
        close=np.full(n, PRICE),
        volume=np.ones(n),
        quote=np.ones(n),
        taker_buy_quote=np.ones(n),
        oi=np.ones(n),
    )


def test_recording_stays_off_and_is_not_wired_into_the_product():
    assert SHADOW_RECORDING_ENABLED is False
    with pytest.raises(ShadowRecordingDisabled):
        ShadowLedger().record_issues([], allow_write=False)
    for relative in ("beta/health.py", "beta/delivery.py", "beta/decision_format.py", "beta/claims.py",
                     "beta/rangecast.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "paired_shadow" not in text
        assert "beta_shadow_" not in text
    schema = (ROOT / "storage/beta_v0_schema.sql").read_text(encoding="utf-8")
    applicator = (ROOT / "storage/beta_v0_store.py").read_text(encoding="utf-8")
    assert "beta_shadow_" not in schema
    assert "beta_paired_shadow" not in applicator
    shadow_sql = (ROOT / "storage/beta_paired_shadow_schema.sql").read_text(encoding="utf-8")
    assert "GRANT" not in shadow_sql
    assert "beta_claims" not in shadow_sql
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/beta/apply_paired_shadow_schema.py")],
        capture_output=True, text=True, check=False,
        env={key: value for key, value in os.environ.items() if key != "PAIRED_SHADOW_SCHEMA_APPROVED"},
    )
    assert completed.returncode == 2
    refused = execute_hour(_shadow_record(), ShadowLedger(), issue_slot=SLOT)
    assert refused["written"] is False
    dry = subprocess.run(
        [sys.executable, str(ROOT / "scripts/beta/run_paired_shadow_hour.py"), "--write", "record.json"],
        capture_output=True, text=True, check=False,
        env={key: value for key, value in os.environ.items() if key != "PAIRED_SHADOW_HOUR_APPROVED"},
    )
    assert dry.returncode == 2


def test_v1_binder_uses_the_existing_touch_function_and_ignores_side():
    quantiles = [0.5 + 0.02 * index for index in range(len(P_GRID))]
    model = {"horizons": {"4h": {
        "q_one": quantiles,
        "q_joint": {"u": [0.5, 2.0], "v": [0.5, 2.0], "F": [[0.2, 0.3], [0.4, 0.6]]},
    }}}
    bound = bind_rangecast_v1(model, {"4h": 1.0}, snapshot_id="fit-v1")
    up = bound.touch_probability(horizon="4h", distance_pct=1.0, side=1)
    down = bound.touch_probability(horizon="4h", distance_pct=1.0, side=-1)
    assert up == down
    assert 0.0 < up < 1.0
    neither = bound.neither_probability(horizon="4h", distance_up_pct=1.0, distance_down_pct=1.0)
    assert 0.0 < neither < 1.0
    assert bound.procedure_id == V1_PROCEDURE_ID
    assert bound.spec_digest == V1_SPEC_DIGEST


def test_both_models_share_anchors_and_the_first_probability_is_kept():
    rows = _plan()
    keys = {row["anchor_key"] for row in rows}
    assert len(keys) * 2 == len(rows)
    assert {row["horizon"] for row in rows} == {"4h"}
    assert {row["distance_pct"] for row in rows if row["family"] == "touch"} == {1.25}
    touch_keys = {row["anchor_key"] for row in rows if row["family"] == "touch" and row["procedure_id"] == V1_PROCEDURE_ID}
    same_for_v2 = {row["anchor_key"] for row in rows if row["family"] == "touch" and row["procedure_id"] == V2_PROCEDURE_ID}
    assert touch_keys == same_for_v2
    ledger = ShadowLedger()
    first = ledger.record_issues(rows, allow_write=True)
    assert first["inserted"] == len(rows)
    replacement = _stub(V2_PROCEDURE_ID, V2_SPEC_ID, V2_SPEC_DIGEST, "snap-refit", 0.11, 0.11)
    v1 = _stub(V1_PROCEDURE_ID, V1_SPEC_ID, V1_SPEC_DIGEST, "snap-v1", 0.20, 0.70)
    again = plan_issues(
        [v1, replacement], price=PRICE, as_of=AS_OF, issue_slot=SLOT, horizons=("4h",),
        distances=(1.25,), neither_pairs=((0.5, 1.0),),
    )
    second = ledger.record_issues(again, allow_write=True)
    assert second == {"inserted": 0, "kept": len(again)}
    stored_v2 = [row for row in ledger.joined_rows() if row["procedure_id"] == V2_PROCEDURE_ID]
    assert stored_v2
    assert {row["snapshot_id"] for row in stored_v2} == {"snap-v2"}
    assert {row["probability"] for row in stored_v2 if row["family"] == "touch"} == {0.80}
    other = sha256_json({"spec_id": "W_L2"})
    new_spec = _stub(V2_PROCEDURE_ID, "W_L2", other, "snap-v2", 0.33, 0.33)
    added = ledger.record_issues(plan_issues(
        [new_spec], price=PRICE, as_of=AS_OF, issue_slot=SLOT, horizons=("1h",),
        distances=(1.25,), neither_pairs=(),
    ), allow_write=True)
    assert added["inserted"] == 2
    assert {row["horizon"] for row in ledger.joined_rows() if row["spec_id"] == "W_L2"} == {"1h"}
    with pytest.raises(ValueError):
        plan_issues([v1, v1], price=PRICE, as_of=AS_OF, issue_slot=SLOT)


def test_one_outcome_scores_both_procedures_and_hides_the_barrier():
    ledger = ShadowLedger()
    ledger.record_issues(_plan(), allow_write=True)
    anchor = next(row for row in ledger.anchors.values()
                  if row["family"] == "touch" and row["side"] == 1)
    quiet = score_anchor(anchor, _bars(high=PRICE * 1.005, low=PRICE * 0.995), now=AS_OF + timedelta(hours=5))
    assert quiet == {"status": "COMPLETE", "outcome": 0, "coverage": 1.0}
    assert "high" not in quiet
    hit = score_anchor(anchor, _bars(high=PRICE * 1.02, low=PRICE * 0.995), now=AS_OF + timedelta(hours=5))
    assert hit["outcome"] == 1
    ledger.record_outcome(
        anchor["anchor_key"], status="COMPLETE", outcome=1, coverage=0.97,
        eval_rule_digest=anchor["eval_rule_digest"], computed_at=AS_OF + timedelta(hours=5),
        allow_write=True,
    )
    with pytest.raises(ShadowConflict):
        ledger.record_outcome(
            anchor["anchor_key"], status="COMPLETE", outcome=0, coverage=0.97,
            eval_rule_digest="ab" * 32, computed_at=AS_OF + timedelta(hours=6),
            allow_write=True,
        )
    with pytest.raises(ValueError):
        ledger.record_outcome(
            anchor["anchor_key"], status="COMPLETE", outcome=0, coverage=0.2,
            eval_rule_digest=anchor["eval_rule_digest"], computed_at=AS_OF + timedelta(hours=6),
            revision=2, allow_write=True,
        )
    ledger.record_outcome(
        anchor["anchor_key"], status="COMPLETE", outcome=0, coverage=0.97,
        eval_rule_digest=anchor["eval_rule_digest"], computed_at=AS_OF + timedelta(hours=6),
        revision=2, correction_note="full window", allow_write=True,
    )
    assert ledger.latest_outcome(anchor["anchor_key"])["revision"] == 2
    assert ledger.latest_outcome(anchor["anchor_key"])["outcome"] == 0
    other = sha256_json({"spec_id": "W_L2"})
    later_spec = _stub(V2_PROCEDURE_ID, "W_L2", other, "snap-l2", 0.99, 0.99)
    ledger.record_issues(plan_issues(
        [later_spec], price=PRICE, as_of=AS_OF, issue_slot=SLOT, horizons=("4h",),
        distances=(1.25,), neither_pairs=((0.5, 1.0),),
    ), allow_write=True)
    report = paired_report(ledger.joined_rows())
    assert report["spec_v1"] == V1_SPEC_ID
    assert report["spec_v2"] == V2_SPEC_ID
    touch = report["horizons"]["4h"]["touch"]
    assert touch["n"] == 1
    assert touch["log_loss_v2"] == pytest.approx(log_loss(0.80, 0.0))
    assert touch["log_loss_v2_minus_v1"] > 0
    assert touch["brier_v2_minus_v1"] > 0
    exported = [export_row(row) for row in ledger.joined_rows()]
    blob = json.dumps(exported)
    assert "65432" not in blob
    assert "level_up" not in blob
    assert "subject" not in blob
    observations = monitor_observations(ledger.joined_rows())
    books = evaluate(observations)["books"]
    touch_books = [book for book in books if book["family"] == "touch" and book["horizon"] == "4h"]
    assert {(book["procedure_id"], book["spec_id"]) for book in touch_books} == {
        (V1_PROCEDURE_ID, V1_SPEC_ID),
        (V2_PROCEDURE_ID, V2_SPEC_ID),
        (V2_PROCEDURE_ID, "W_L2"),
    }
    assert PROCEDURE_TOUCH_CHANCE not in {book["procedure_id"] for book in books}
    assert JOURNAL_SPEC_ID not in {book["spec_id"] for book in books}
    assert all(book["state"] == STATE_INSUFFICIENT for book in touch_books)
    assert all(book["state"] != STATE_FAULT for book in touch_books)
    assert {book["spec_id"] for book in books} == {V1_SPEC_ID, V2_SPEC_ID, "W_L2"}


def _shadow_record(*, status="OK", spec_digest=V2_SPEC_DIGEST, p_v2=0.80):
    return {
        "schema": "RANGECAST_SHADOW_RECORD_V1",
        "status": status,
        "reason": None if status == "OK" else "PRICE_OLDER_THAN_10_MIN",
        "as_of": AS_OF.isoformat(),
        "price": PRICE,
        "horizons": {"4h": {
            "status": status,
            "reason": None if status == "OK" else "PRICE_OLDER_THAN_10_MIN",
            "v1": {"procedure_id": "TOUCH_CHANCE_PROCEDURE_V1", "stats_digest": "a" * 64,
                   "status": "OK",
                   "touch": [{"side": 1, "distance_pct": 1.25, "status": "OK", "probability": 0.20},
                             {"side": -1, "distance_pct": 1.25, "status": "OK", "probability": 0.20}],
                   "neither": [{"up_pct": 0.5, "down_pct": 1.0, "status": "OK", "probability": 0.70}]},
            "v2": {"procedure_id": "TOUCH_CHANCE_PROCEDURE_RCV2_W_L1", "spec_id": "RANGECAST_V2_W_L1",
                   "spec_digest": spec_digest, "params_digest": "b" * 64, "status": "OK",
                   "touch": [{"side": 1, "distance_pct": 1.25, "status": "OK", "probability": p_v2},
                             {"side": -1, "distance_pct": 1.25, "status": "OK", "probability": p_v2}],
                   "neither": [{"up_pct": 0.5, "down_pct": 1.0, "status": "OK", "probability": 0.30}]},
        }},
    }


def test_w_l1_digest_is_the_mathematical_procedure_pin():
    assert V2_SPEC_ID == "W_L1"
    assert V2_SPEC_DIGEST == "00539f2d2a1660c861d4ee7cbd411a010b2f296f3af3826b8ab527cc98727246"
    assert len(V2_SPEC_DIGEST) == 64


def test_one_spec_digest_covers_every_anchor():
    ledger = ShadowLedger()
    ledger.record_issues(_plan(), allow_write=True)
    later = SLOT + timedelta(hours=4)
    bad = _stub(V2_PROCEDURE_ID, V2_SPEC_ID, "ab" * 32, "snap-other", 0.11, 0.11)
    v1 = _stub(V1_PROCEDURE_ID, V1_SPEC_ID, V1_SPEC_DIGEST, "snap-v1", 0.20, 0.70)
    with pytest.raises(ShadowConflict, match="spec_digest"):
        ledger.record_issues(plan_issues(
            [v1, bad], price=PRICE, as_of=later, issue_slot=later, horizons=("4h",),
            distances=(1.25,), neither_pairs=(),
        ), allow_write=True)
    assert {row["issue_slot"] for row in ledger.joined_rows()} == {SLOT}


def test_hour_path_keeps_probabilities_and_records_a_data_gap():
    ledger = ShadowLedger()
    first = execute_hour(_shadow_record(), ledger, issue_slot=SLOT, allow_write=True, score=True,
                         bars=_bars(high=PRICE * 1.005, low=PRICE * 0.995), now=AS_OF + timedelta(hours=5))
    assert first["written"] is True
    assert first["inserted"] > 0
    assert {book["procedure_id"] for book in first["books"]} == {V1_PROCEDURE_ID, V2_PROCEDURE_ID}
    assert PROCEDURE_TOUCH_CHANCE not in {book["procedure_id"] for book in first["books"]}
    touch = [item for item in first["scoring"] if item["family"] == "touch"]
    assert touch and {item["status"] for item in touch} == {"COMPLETE"}
    assert touch[0]["outcome"] == 0
    second = execute_hour(_shadow_record(p_v2=0.11), ledger, issue_slot=SLOT, allow_write=True)
    assert second["inserted"] == 0
    assert second["kept"] == first["inserted"]
    stored = [row["probability"] for row in ledger.joined_rows()
              if row["procedure_id"] == V2_PROCEDURE_ID and row["family"] == "touch"]
    assert stored == [0.80, 0.80]
    stale = execute_hour(_shadow_record(status="STALE_DATA"), ledger, issue_slot=SLOT + timedelta(hours=4),
                         allow_write=True)
    assert stale["inserted"] == 0
    assert stale["horizons"]["4h"]["status"] == "STALE_DATA"
    assert all(row["issue_slot"] == SLOT for row in ledger.joined_rows())
    refused = plan_shadow_record(_shadow_record(spec_digest="cd" * 32), issue_slot=SLOT + timedelta(hours=8))
    assert refused["rows"] == []
    assert refused["horizons"]["4h"]["status"] == "MODEL_INVALID"


def test_coverage_below_the_monitor_floor_is_not_paired():
    ledger = ShadowLedger()
    ledger.record_issues(_plan(), allow_write=True)
    for anchor in ledger.anchors.values():
        ledger.record_outcome(
            anchor["anchor_key"], status="COMPLETE", outcome=1, coverage=0.2,
            eval_rule_digest=anchor["eval_rule_digest"], computed_at=AS_OF + timedelta(hours=5),
            allow_write=True,
        )
    report = paired_report(ledger.joined_rows())
    assert report["horizons"] == {}
    assert report["n_unscored_anchors"] == len(ledger.anchors)


def _psql(*args, stdin=None, check=True):
    completed = subprocess.run(
        ["psql", TEST_DSN, "-X", "-v", "ON_ERROR_STOP=1", *args],
        input=stdin, capture_output=True, text=True, check=False,
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed


def _dollar(text: str) -> str:
    tag = "shadow"
    while f"${tag}$" in text:
        tag += "x"
    return f"${tag}${text}${tag}$"


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
@pytest.mark.skipif(shutil.which("psql") is None, reason="psql not installed")
def test_shadow_schema_is_additive_and_the_export_view_hides_barriers():
    _psql("-c", "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
    _psql("-1", "-f", str(ROOT / "storage/beta_v0_schema.sql"))
    row = claim_row(
        "L3_DISTANCE_TOUCH_4H", issued_at=AS_OF, issue_slot=SLOT, as_of=AS_OF + timedelta(minutes=1),
        subject={"side": 1, "level": PRICE, "price": PRICE}, subject_key="user-claim",
        numbers={"probability": 0.4}, rule_version="v1", eligible_reason="GRID",
        horizon_ms=14_400_000,
    )
    columns = (
        "claim_class", "level", "issued_at", "issue_slot", "as_of", "stats_digest", "subject",
        "subject_key", "numbers", "rule_version", "template_id", "template_digest", "eval_rule_id",
        "eval_rule", "eval_rule_digest", "horizon_end", "eligible_reason", "claim_digest",
    )
    values = []
    for column in columns:
        value = row[column]
        if value is None:
            values.append("NULL")
        elif isinstance(value, datetime):
            values.append("timestamptz " + _dollar(value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00")))
        elif isinstance(value, dict):
            values.append(_dollar(json.dumps(value)) + "::jsonb")
        else:
            values.append(_dollar(str(value)))
    _psql("-c", f"INSERT INTO beta_claims ({', '.join(columns)}) VALUES ({', '.join(values)})")
    assert _psql("-At", "-c", "SELECT count(*) FROM beta_claims").stdout.strip() == "1"
    approved = os.environ.copy()
    approved["PAIRED_SHADOW_SCHEMA_APPROVED"] = "1"
    applied = subprocess.run(
        [sys.executable, str(ROOT / "scripts/beta/apply_paired_shadow_schema.py"), TEST_DSN],
        capture_output=True, text=True, check=False, env=approved,
    )
    assert applied.returncode == 0, applied.stderr
    assert _psql("-At", "-c", "SELECT count(*) FROM beta_claims").stdout.strip() == "1"
    applied_again = subprocess.run(
        [sys.executable, str(ROOT / "scripts/beta/apply_paired_shadow_schema.py"), TEST_DSN],
        capture_output=True, text=True, check=False, env=approved,
    )
    assert applied_again.returncode == 0, applied_again.stderr
    view = _psql("-At", "-c", "SELECT pg_get_viewdef('beta_shadow_export_v1'::regclass)").stdout
    assert "level_up" not in view
    assert "level_down" not in view
    digest = "a" * 64
    _psql("-c", f"""
        INSERT INTO beta_shadow_anchors (
            anchor_key, symbol, family, horizon, issue_slot, as_of, horizon_end, side,
            distance_pct, level_up, eval_rule_id, eval_rule_digest)
        VALUES (
            'anchor-1', 'BTCUSDT', 'touch', '4h',
            timestamptz '2024-01-01 00:00:00+00', timestamptz '2024-01-01 00:01:00+00',
            timestamptz '2024-01-01 04:01:00+00', 1, 1.25, 65432.1, 'TOUCH_V1', {_dollar(digest)})
    """)
    _psql("-c", f"""
        INSERT INTO beta_shadow_issues (
            anchor_pk, procedure_id, spec_id, spec_digest, snapshot_id, probability, issued_at)
        SELECT anchor_pk, 'RANGECAST_V1', 'RANGECAST_V1', {_dollar(digest)}, 'snap-v1', 0.20,
               timestamptz '2024-01-01 00:01:00+00'
        FROM beta_shadow_anchors WHERE anchor_key = 'anchor-1'
    """)
    _psql("-c", f"""
        INSERT INTO beta_shadow_issues (
            anchor_pk, procedure_id, spec_id, spec_digest, snapshot_id, probability, issued_at)
        SELECT anchor_pk, 'RANGECAST_V2', 'W_L1', {_dollar(digest)}, 'snap-v2', 0.80,
               timestamptz '2024-01-01 00:01:00+00'
        FROM beta_shadow_anchors WHERE anchor_key = 'anchor-1'
        ON CONFLICT (anchor_pk, procedure_id, spec_id) DO NOTHING
    """)
    _psql("-c", f"""
        INSERT INTO beta_shadow_issues (
            anchor_pk, procedure_id, spec_id, spec_digest, snapshot_id, probability, issued_at)
        SELECT anchor_pk, 'RANGECAST_V2', 'W_L1', {_dollar(digest)}, 'snap-refit', 0.10,
               timestamptz '2024-01-01 00:02:00+00'
        FROM beta_shadow_anchors WHERE anchor_key = 'anchor-1'
        ON CONFLICT (anchor_pk, procedure_id, spec_id) DO NOTHING
    """)
    assert _psql("-At", "-c", """
        SELECT probability::text FROM beta_shadow_issues i
        JOIN beta_shadow_anchors a USING (anchor_pk)
        WHERE a.anchor_key = 'anchor-1' AND i.procedure_id = 'RANGECAST_V2'
    """).stdout.strip() == "0.8"
    changed_digest = _psql("-c", f"""
        INSERT INTO beta_shadow_issues (
            anchor_pk, procedure_id, spec_id, spec_digest, snapshot_id, probability, issued_at)
        SELECT anchor_pk, 'RANGECAST_V2', 'W_L1', {_dollar('b' * 64)}, 'snap-other', 0.10,
               timestamptz '2024-01-01 00:03:00+00'
        FROM beta_shadow_anchors WHERE anchor_key = 'anchor-1'
        ON CONFLICT (anchor_pk, procedure_id, spec_id) DO NOTHING
    """, check=False)
    assert changed_digest.returncode != 0
    assert "digest" in changed_digest.stderr
    _psql("-c", f"""
        INSERT INTO beta_shadow_anchors (
            anchor_key, symbol, family, horizon, issue_slot, as_of, horizon_end, side,
            distance_pct, level_up, eval_rule_id, eval_rule_digest)
        VALUES (
            'anchor-2', 'BTCUSDT', 'touch', '4h',
            timestamptz '2024-01-01 04:00:00+00', timestamptz '2024-01-01 04:01:00+00',
            timestamptz '2024-01-01 08:01:00+00', 1, 1.25, 66000, 'TOUCH_V1', {_dollar(digest)})
    """)
    other_anchor = _psql("-c", f"""
        INSERT INTO beta_shadow_issues (
            anchor_pk, procedure_id, spec_id, spec_digest, snapshot_id, probability, issued_at)
        SELECT anchor_pk, 'RANGECAST_V2', 'W_L1', {_dollar('b' * 64)}, 'snap-other', 0.10,
               timestamptz '2024-01-01 04:01:00+00'
        FROM beta_shadow_anchors WHERE anchor_key = 'anchor-2'
    """, check=False)
    assert other_anchor.returncode != 0
    assert "spec_digest" in other_anchor.stderr
    assert _psql("-At", "-c", "SELECT count(*) FROM beta_shadow_issues WHERE snapshot_id = 'snap-other'").stdout.strip() == "0"
    identity_update = _psql("-c", "UPDATE beta_shadow_spec_identity SET spec_digest = repeat('c', 64)", check=False)
    assert identity_update.returncode != 0
    _psql("-c", """
        INSERT INTO beta_shadow_hour_status (issue_slot, horizon, status, reason)
        VALUES (timestamptz '2024-01-01 00:00:00+00', '4h', 'STALE_DATA', 'PRICE_OLDER_THAN_10_MIN')
    """)
    replayed = _psql("-c", """
        INSERT INTO beta_shadow_hour_status (issue_slot, horizon, status, reason)
        VALUES (timestamptz '2024-01-01 00:00:00+00', '4h', 'STALE_DATA', 'PRICE_OLDER_THAN_10_MIN')
        ON CONFLICT (issue_slot, horizon) DO NOTHING
    """)
    assert replayed.returncode == 0
    changed_status = _psql("-c", """
        INSERT INTO beta_shadow_hour_status (issue_slot, horizon, status, reason)
        VALUES (timestamptz '2024-01-01 00:00:00+00', '4h', 'OK', NULL)
        ON CONFLICT (issue_slot, horizon) DO NOTHING
    """, check=False)
    assert changed_status.returncode != 0
    denied = _psql("-c", "UPDATE beta_shadow_issues SET probability = 0.1", check=False)
    assert denied.returncode != 0
    assert "append-only" in denied.stderr
    _psql("-c", f"""
        INSERT INTO beta_shadow_outcomes (
            anchor_pk, revision, status, outcome, coverage, eval_rule_digest, computed_at)
        SELECT anchor_pk, 1, 'COMPLETE', 1, 0.2, {_dollar(digest)}, timestamptz '2024-01-01 05:00:00+00'
        FROM beta_shadow_anchors WHERE anchor_key = 'anchor-1'
    """)
    revised = _psql("-c", f"""
        INSERT INTO beta_shadow_outcomes (
            anchor_pk, revision, supersedes_outcome_pk, status, outcome, coverage,
            eval_rule_digest, computed_at, correction_note)
        SELECT a.anchor_pk, 2, o.outcome_pk, 'COMPLETE', 0, 0.97, {_dollar(digest)},
               timestamptz '2024-01-01 06:00:00+00', 'full window'
        FROM beta_shadow_anchors a
        JOIN beta_shadow_outcomes o ON o.anchor_pk = a.anchor_pk AND o.revision = 1
        WHERE a.anchor_key = 'anchor-1'
    """)
    assert revised.returncode == 0
    bare = _psql("-c", f"""
        INSERT INTO beta_shadow_outcomes (
            anchor_pk, revision, status, outcome, coverage, eval_rule_digest, computed_at)
        SELECT anchor_pk, 3, 'COMPLETE', 0, 0.97, {_dollar(digest)}, timestamptz '2024-01-01 07:00:00+00'
        FROM beta_shadow_anchors WHERE anchor_key = 'anchor-1'
    """, check=False)
    assert bare.returncode != 0
    wrong_rule = _psql("-c", """
        INSERT INTO beta_shadow_outcomes (
            anchor_pk, revision, supersedes_outcome_pk, status, outcome, coverage,
            eval_rule_digest, computed_at, correction_note)
        SELECT a.anchor_pk, 3, o.outcome_pk, 'COMPLETE', 0, 0.97,
               'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
               timestamptz '2024-01-01 07:00:00+00', 'wrong rule'
        FROM beta_shadow_anchors a
        JOIN beta_shadow_outcomes o ON o.anchor_pk = a.anchor_pk AND o.revision = 2
        WHERE a.anchor_key = 'anchor-1'
    """, check=False)
    assert wrong_rule.returncode != 0
    assert "evaluation rule" in wrong_rule.stderr
    exported = _psql("-At", "-c", "SELECT row_to_json(beta_shadow_export_v1)::text FROM beta_shadow_export_v1").stdout
    assert "65432" not in exported
    assert "0.97" in exported
    assert exported.count('"outcome_revision": 2') == 2 or exported.count('"outcome_revision":2') == 2
    assert _psql("-At", "-c", "SELECT count(*) FROM beta_claims").stdout.strip() == "1"
