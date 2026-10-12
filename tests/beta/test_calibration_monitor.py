"""Calibration monitor V2. The live V1 wording and sticky health key are not invoked."""
import json
from datetime import datetime, timedelta, timezone

from beta import claims as claims
from beta.calibration_monitor import (
    ACTION_NO_OVERRIDE, ACTION_WITHHOLD_FIGURE, ACTION_WITHHOLD_PROBABILITY,
    COVERAGE_MIN, CONFIRM_ALPHA_UNION, E_CONFIRM, E_SUSPECT, MIN_DAYS_SUSPECT,
    MONITOR_VERSION, N_PREDECLARED_BOOKS, PRACTICAL_ABS, PROCEDURE_TOUCH_CHANCE,
    STATE_CONFIRMED, STATE_FAULT, STATE_INCOMPLETE, STATE_INSUFFICIENT, STATE_NOISE,
    STATE_RECOVERED, STATE_SUSPECTED, digest_due, evaluate, observation_from_journal_row,
    observations_from_claim_rows, shadow_notifications, user_action,
)

UTC = timezone.utc
START = datetime(2024, 1, 1, tzinfo=UTC)


def _rows(days, *, family="touch", horizon="4h", probabilities=(0.40,), outcome=0.0,
          every_hours=1, snapshot="snap-a", rule="TOUCH_V1", procedure=PROCEDURE_TOUCH_CHANCE,
          status="COMPLETE", probability_override=None):
    out = []
    step = timedelta(hours=every_hours)
    moment = START
    end = START + timedelta(days=days)
    index = 0
    while moment < end:
        for probability in probabilities:
            out.append({
                "procedure_id": procedure,
                "family": family,
                "horizon": horizon,
                "as_of": moment,
                "probability": probability if probability_override is None else probability_override(index, probability),
                "outcome": outcome if not callable(outcome) else outcome(index, probability),
                "status": status,
                "eval_rule_id": rule,
                "snapshot_id": snapshot,
            })
            index += 1
        moment += step
    return out


def _book(report, family="touch", horizon="4h"):
    found = [item for item in report["books"]
             if item["family"] == family and item["horizon"] == horizon]
    assert len(found) == 1
    return found[0]


def test_seven_dense_days_stay_insufficient_even_when_the_gap_is_large():
    """V1's slot count is already past 30; V2 still has fewer than the day floor."""
    report = evaluate(_rows(7, outcome=0.0, probabilities=(0.40,)))
    book = _book(report)
    assert book["state"] == STATE_INSUFFICIENT
    assert book["n_days"] == 7
    assert book["n_slots"] >= 30
    assert book["user_action"]["action"] == ACTION_NO_OVERRIDE
    assert book["monitor_version"] == MONITOR_VERSION


def test_v1_diverges_on_the_same_seven_days_the_v2_refuses():
    rows = _rows(7, outcome=0.0, probabilities=(0.40,))
    cells = {}
    for row in rows:
        day = int(row["as_of"].timestamp()) // 86400
        slot = int(row["as_of"].timestamp()) // 14400
        bin_index = 3  # [0.30, 0.50)
        key = (day, slot, bin_index)
        cell = cells.setdefault(key, {"n": 0, "hits": 0, "psum": 0.0, "day": day, "slot": slot,
                                      "bin": bin_index, "claim_class": "L3_DISTANCE_TOUCH_4H"})
        cell["n"] += 1
        cell["hits"] += int(row["outcome"])
        cell["psum"] += row["probability"]
    bins = claims.live_touch_bins(list(cells.values()), "4h")
    assert claims.diverged_bins(bins) == [[0.3, 0.5]]
    assert _book(evaluate(rows))["state"] == STATE_INSUFFICIENT


def test_a_sustained_level_shift_confirms_and_keeps_both_snapshots():
    rows = _rows(40, outcome=0.0, probabilities=(0.40,), snapshot="snap-a")
    rows += _rows(40, outcome=0.0, probabilities=(0.40,), snapshot="snap-b")
    # second half continues the clock instead of repeating January
    for index, row in enumerate(rows):
        row["as_of"] = START + timedelta(hours=index)
    book = _book(evaluate(rows))
    assert book["state"] == STATE_CONFIRMED
    assert book["snapshot_ids"] == ["snap-a", "snap-b"]
    assert book["snapshot_policy"] == "RECORDED_NOT_RESET"
    level = book["channels"]["LEVEL"]
    assert level["estimate"] < -PRACTICAL_ABS
    assert level["e_value"] >= E_CONFIRM
    assert book["user_action"]["show_model_probability"] is False
    assert book["user_action"]["blend_model_toward_outcome"] is False
    assert book["user_action"]["action"] == ACTION_WITHHOLD_PROBABILITY


def test_tails_confirm_when_the_horizon_average_residual_is_zero():
    def outcome(_index, probability):
        if probability >= 0.70:
            return 0.0
        if probability < 0.30:
            return 1.0
        return 1.0 if probability == 0.50 else 0.0

    rows = _rows(25, probabilities=(0.10, 0.50, 0.90), outcome=outcome)
    # two claims at 0.50 so their residuals cancel: rewrite half of the 0.50 outcomes
    for row in rows:
        if row["probability"] != 0.50:
            continue
        # Anchor hours are 0, 4, 8, ... so alternating by hour would make every anchor a hit.
        slot = int(row["as_of"].timestamp()) // 14400
        row["outcome"] = 1.0 if slot % 2 == 0 else 0.0
    book = _book(evaluate(rows))
    assert abs(book["channels"]["LEVEL"]["estimate"]) < 0.02
    assert book["channels"]["TAIL_HIGH"]["state"] == STATE_CONFIRMED
    assert book["channels"]["TAIL_LOW"]["state"] == STATE_CONFIRMED
    assert book["state"] == STATE_CONFIRMED


def test_neither_can_confirm_while_touch_stays_inside_noise():
    touch = _rows(30, family="touch", probabilities=(0.50,),
                  outcome=lambda index, _p: 1.0 if (index // 4) % 2 == 0 else 0.0,
                  rule="TOUCH_V1")
    neither = _rows(30, family="neither", probabilities=(0.80,), outcome=1.0, rule="NEITHER_V1")
    report = evaluate(touch + neither)
    assert _book(report, "touch")["state"] in (STATE_NOISE, STATE_INSUFFICIENT, STATE_SUSPECTED)
    assert _book(report, "neither")["state"] == STATE_CONFIRMED
    assert _book(report, "touch")["state"] != STATE_CONFIRMED


def test_clean_days_after_a_confirmed_gap_recover_without_erasing_the_episode():
    biased = _rows(30, probabilities=(0.55,), outcome=0.0)
    clean = []
    # Exactly 11 hits per 20 anchor slots, so the anchor mean equals 0.55. Non-anchors
    # are outside the decision chain.
    for day in range(30, 70):
        for slot in range(6):
            moment = START + timedelta(days=day, hours=slot * 4)
            anchor_index = (day - 30) * 6 + slot
            clean.append({
                "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "4h",
                "as_of": moment, "probability": 0.55,
                "outcome": 1.0 if anchor_index % 20 < 11 else 0.0,
                "status": "COMPLETE", "eval_rule_id": "TOUCH_V1", "snapshot_id": "snap-refit",
            })
    full = evaluate(biased + clean)
    book = _book(full)
    level = book["channels"]["LEVEL"]
    assert level["episodes"], "the biased stretch has to leave an episode"
    assert level["episodes"][0]["recovered_on"] is not None
    assert level["episodes"][0]["confirmed_by"] == "BOOK_E_PROCESS"
    assert level["episodes"][0]["archived_e"] >= E_CONFIRM
    assert book["state"] == STATE_RECOVERED
    prefix = _book(evaluate(biased))
    assert prefix["state"] == STATE_CONFIRMED
    assert prefix["channels"]["LEVEL"]["episodes"][0]["recovered_on"] is None


def test_illegal_probability_and_mixed_rules_are_faults_not_divergences():
    broken = _rows(12, probabilities=(0.40,))
    broken[0]["probability"] = 1.4
    fault = _book(evaluate(broken))
    assert fault["state"] == STATE_FAULT
    assert fault["user_action"]["action"] == ACTION_WITHHOLD_FIGURE
    mixed = _rows(4, probabilities=(0.40,))
    mixed[0]["eval_rule_id"] = "OTHER_RULE"
    assert _book(evaluate(mixed))["state"] == STATE_FAULT


def test_too_many_unscored_outcomes_are_incomplete_rather_than_a_model_verdict():
    rows = _rows(15, probabilities=(0.40,), outcome=0.0)
    for row in rows[: len(rows) // 3]:
        row["status"] = "NO_DATA"
        row["outcome"] = None
    book = _book(evaluate(rows))
    assert book["state"] == STATE_INCOMPLETE
    assert book["user_action"]["show_model_probability"] is False
    assert book["user_action"]["allow_separate_baseline"] is False


def test_naive_timestamps_are_a_fault():
    rows = _rows(2, probabilities=(0.40,))
    rows[0]["as_of"] = datetime(2024, 1, 1, 0, 0)
    assert _book(evaluate(rows))["state"] == STATE_FAULT


def test_owner_digest_is_once_per_utc_day_and_silence_is_not_paged():
    assert digest_due(STATE_NOISE, utc_day="2026-10-12", last_digest_day=None) is False
    assert digest_due(STATE_CONFIRMED, utc_day="2026-10-12", last_digest_day=None) is True
    assert digest_due(STATE_CONFIRMED, utc_day="2026-10-12", last_digest_day="2026-10-12") is False
    assert digest_due(STATE_CONFIRMED, utc_day="2026-10-13", last_digest_day="2026-10-12") is True
    assert digest_due(STATE_RECOVERED, utc_day="2026-10-14", last_digest_day=None,
                      previous_state=STATE_CONFIRMED) is True
    assert digest_due(STATE_RECOVERED, utc_day="2026-10-14", last_digest_day=None,
                      previous_state=STATE_NOISE) is False
    assert user_action(STATE_SUSPECTED)["action"] == ACTION_NO_OVERRIDE
    assert user_action(STATE_INSUFFICIENT)["show_model_probability"] is True


def test_replay_is_deterministic_and_does_not_mutate_inputs():
    rows = _rows(12, probabilities=(0.22, 0.78), outcome=lambda index, probability: 1.0 if index % 3 == 0 else 0.0)
    first = evaluate(rows)
    second = evaluate(rows)
    assert first == second
    assert rows[0]["probability"] == 0.22


def test_e_process_null_bound_is_not_exceeded_on_daily_noise():
    import random
    rng = random.Random(20261005)
    crossings = 0
    paths = 80
    for _ in range(paths):
        rows = []
        for day in range(120):
            bit = 1.0 if rng.random() < 0.5 else 0.0
            rows.append({
                "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "1h",
                "as_of": START + timedelta(days=int(day), hours=1),
                "probability": 0.50, "outcome": bit,
                "status": "COMPLETE", "eval_rule_id": "TOUCH_V1", "snapshot_id": "noise",
            })
        book = _book(evaluate(rows), horizon="1h")
        if book["episodes"]:
            crossings += 1
    # One book, E >= 60, Ville bound 1/60. 80 paths: expected about 1.3 if the bound is tight.
    assert crossings <= 6


def test_day_floor_is_the_predeclared_constant_not_a_slot_count():
    assert MIN_DAYS_SUSPECT > 5
    short = _rows(MIN_DAYS_SUSPECT - 1, probabilities=(0.90,), outcome=0.0)
    assert _book(evaluate(short))["state"] == STATE_INSUFFICIENT


def test_family_wise_confirm_bound_is_the_predeclared_ville_union():
    assert N_PREDECLARED_BOOKS == 6
    assert E_CONFIRM == 60
    assert E_SUSPECT == 20
    assert N_PREDECLARED_BOOKS / E_CONFIRM == CONFIRM_ALPHA_UNION
    assert COVERAGE_MIN == claims.COVERAGE_MIN


def test_overlapping_hours_contribute_one_anchor_step_per_slot():
    rows = _rows(9, probabilities=(0.40,), outcome=0.0)
    book = _book(evaluate(rows))
    assert book["n_claims"] == 9 * 24
    assert book["n_included_slots"] == 9 * 6
    assert book["filtration"] == "NON_OVERLAPPING_ANCHOR"
    assert book["state"] == STATE_INSUFFICIENT


def test_a_claim_issued_before_the_previous_anchor_resolves_is_not_a_second_step():
    rows = []
    for day in range(3):
        base = START + timedelta(days=day)
        for hour, minute in ((0, 30), (4, 0), (8, 0)):
            moment = base + timedelta(hours=hour, minutes=minute)
            rows.append({
                "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "4h",
                "as_of": moment, "probability": 0.40, "outcome": 0.0, "status": "COMPLETE",
                "eval_rule_id": "TOUCH_V1", "snapshot_id": "snap-a",
            })
    book = _book(evaluate(rows))
    # 00:30 resolves at 04:30, so the 04:00 claim is still entangled with it. 08:00 is free.
    assert book["n_included_slots"] == 3 * 2
    assert book["n_skipped_overlapping"] == 3


def test_claims_outside_the_anchor_hour_do_not_move_the_decision_clock():
    rows = []
    for day in range(12):
        rows.append({
            "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "4h",
            "as_of": START + timedelta(days=day, hours=2),
            "probability": 0.90, "outcome": 0.0, "status": "COMPLETE",
            "eval_rule_id": "TOUCH_V1", "snapshot_id": "snap-a",
        })
    book = _book(evaluate(rows))
    assert book["n_claims"] == 12
    assert book["n_included_slots"] == 0
    assert book["state"] == STATE_INSUFFICIENT


def test_low_coverage_hits_are_unfinished_for_both_outcomes():
    rows = _rows(12, probabilities=(0.40,), outcome=1.0)
    for row in rows:
        row["coverage"] = 0.4
        row["status"] = "COMPLETE"
    book = _book(evaluate(rows))
    assert book["state"] == STATE_INCOMPLETE
    assert book["user_action"]["action"] == ACTION_WITHHOLD_FIGURE
    assert book["n_low_coverage"] == len(rows)


def test_full_window_subset_stays_calibrated_when_partial_hits_would_not():
    """Production keeps a low-coverage touch and drops a low-coverage miss.

    The scored subset is the full-coverage windows only. Gaps here are one claim in six,
    independent of the five-claim hit cycle, so that subset stays at 40%.
    """
    rows = []
    for index in range(240):
        moment = START + timedelta(days=index // 6, hours=(index % 6) * 4)
        hit = 1.0 if index % 5 < 2 else 0.0
        gappy = index % 6 == 0
        if gappy and hit == 0.0:
            status, outcome, coverage = "NO_DATA", None, 0.4
        elif gappy:
            status, outcome, coverage = "COMPLETE", hit, 0.4
        else:
            status, outcome, coverage = "COMPLETE", hit, 0.97
        rows.append({
            "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "4h",
            "as_of": moment, "probability": 0.40, "outcome": outcome, "status": status,
            "coverage": coverage, "eval_rule_id": "TOUCH_V1", "snapshot_id": "snap-a",
        })
    complete = [row for row in rows if row["status"] == "COMPLETE"]
    naive = sum(row["outcome"] for row in complete) / len(complete)
    assert naive > 0.43
    book = _book(evaluate(rows))
    assert book["state"] == STATE_NOISE
    assert abs(book["channels"]["LEVEL"]["estimate"]) < 1e-9


def _journal_row(**overrides):
    row = {
        "claim_class": "L3_DISTANCE_TOUCH_4H",
        "as_of": "2024-01-01T00:01:00+00:00",
        "horizon_end": "2024-01-01T04:01:00+00:00",
        "numbers": {"probability": 0.42, "printed": "42%"},
        "stats_digest": "digest-snap",
        "stats_pk": 9,
        "eval_rule_digest": "rule-digest-1",
        "eval_rule_id": "TOUCH_V1",
        "rule_version": "BETA_RANGE_MODEL_V1",
        "status": "COMPLETE",
        "realized": {"touched": False, "coverage": 0.97, "high": 1.0},
        "subject": {"price": 100.0, "level": 101.0},
    }
    row.update(overrides)
    return row


def test_journal_adapter_uses_digest_snapshot_and_drops_the_subject():
    observation = observation_from_journal_row(_journal_row())
    assert observation["family"] == "touch"
    assert observation["horizon"] == "4h"
    assert observation["probability"] == 0.42
    assert observation["outcome"] == 0.0
    assert observation["snapshot_id"] == "digest-snap"
    assert observation["eval_rule_id"] == "rule-digest-1"
    assert observation["coverage"] == 0.97
    assert observation["procedure_id"] == PROCEDURE_TOUCH_CHANCE
    assert observation["spec_id"] == "JOURNAL_UNSPECIFIED"
    assert "subject" not in observation
    assert "price" not in observation
    level = _journal_row(claim_class="L3_LEVEL_TOUCH_4H",
                         realized={"touched": True, "coverage": 0.95})
    pooled = observations_from_claim_rows([
        _journal_row(), level, {"claim_class": "L2_SOMETHING", "as_of": "2024-01-01T00:01:00+00:00"},
    ])
    assert len(pooled) == 2
    book = _book(evaluate(pooled))
    assert book["state"] == STATE_INSUFFICIENT
    assert book["n_claims"] == 2
    assert book["snapshot_ids"] == ["digest-snap"]
    mixed = observations_from_claim_rows([
        _journal_row(),
        _journal_row(eval_rule_digest="rule-digest-2"),
    ])
    assert _book(evaluate(mixed))["state"] == STATE_FAULT
    mismatch = observations_from_claim_rows([
        _journal_row(horizon_end="2024-01-01T09:01:00+00:00"),
    ])
    assert "HORIZON_WINDOW" in _book(evaluate(mismatch))["reason"]
    wrong_rule = observations_from_claim_rows([
        _journal_row(claim_class="L3_NEITHER_4H", eval_rule_id="TOUCH_V1",
                     realized={"neither": True, "coverage": 0.99}),
    ])
    assert _book(evaluate(wrong_rule), family="neither")["state"] == STATE_FAULT
    fallback = observation_from_journal_row(_journal_row(stats_digest=None))
    assert fallback["snapshot_id"] == "9"


def _sql_executable(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return " ".join(" ".join(lines).lower().split())


def test_replay_export_rejects_prices_and_stays_read_only():
    from scripts.beta.replay_calibration_monitor_v2 import (
        READ_ONLY_EXPORT_SQL, forbidden_keys, load_jsonl, summary,
    )

    folded = _sql_executable(READ_ONLY_EXPORT_SQL)
    assert folded.startswith("select ")
    for verb in ("insert ", "update ", "delete ", "truncate ", "alter ", "drop "):
        assert verb not in folded
    for banned in ("subject", "subject_key", "'high'", "'low'", "'close'", "price"):
        assert banned not in folded
    assert "realized -" not in folded
    assert "coverage" in folded
    assert "eval_rule_digest" in folded
    assert "eval_rule_id" in folded
    assert "outcome_revision" in folded
    assert "order by x.revision desc" in folded
    assert "beta_claims" in folded
    clean = json_line = (
        '{"claim_class":"L3_DISTANCE_TOUCH_4H","as_of":"2024-01-01T00:01:00+00:00",'
        '"horizon_end":"2024-01-01T04:01:00+00:00","probability":0.4,'
        '"stats_digest":"snap","eval_rule_digest":"rule","eval_rule_id":"TOUCH_V1",'
        '"status":"COMPLETE","realized":{"touched":false,"coverage":0.95}}'
    )
    assert forbidden_keys(json.loads(clean)) == set()
    loaded = load_jsonl(json_line + "\n")
    assert loaded[0]["claim_class"] == "L3_DISTANCE_TOUCH_4H"
    try:
        load_jsonl('{"claim_class":"L3_DISTANCE_TOUCH_4H","subject":{"price":1}}\n')
    except ValueError as exc:
        assert "subject" in str(exc)
    else:
        raise AssertionError("a subject field must be refused")
    report = evaluate(observations_from_claim_rows(loaded))
    assert summary(report)["shadow_component"] == "touch_cal_monitor_v2"


def test_two_procedures_stay_in_separate_books():
    v1 = _rows(12, probabilities=(0.40,), outcome=0.0)
    v2 = _rows(12, probabilities=(0.90,), outcome=1.0)
    for row in v2:
        row["procedure_id"] = "RANGECAST_V2"
        row["spec_id"] = "W_L1"
    report = evaluate(v1 + v2)
    books = [item for item in report["books"] if item["family"] == "touch" and item["horizon"] == "4h"]
    assert {(item["procedure_id"], item["spec_id"]) for item in books} == {
        (PROCEDURE_TOUCH_CHANCE, "JOURNAL_UNSPECIFIED"),
        ("RANGECAST_V2", "W_L1"),
    }
    assert len({item["e_value"] for item in books}) == 2
    named = observation_from_journal_row(_journal_row(procedure_id="RANGECAST_V2", spec_id="W_L1"))
    assert named["procedure_id"] == "RANGECAST_V2"
    assert named["spec_id"] == "W_L1"


def test_shadow_notices_fire_on_a_change_and_once_per_day():
    confirmed = {"books": [{
        "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "4h",
        "state": STATE_CONFIRMED,
    }]}
    first = shadow_notifications(None, confirmed, utc_day="2026-10-12", last_summary_day=None)
    assert first["changes"][0]["kind"] == "STATE_CHANGED"
    assert first["changes"][0]["to_state"] == STATE_CONFIRMED
    assert first["daily_summary"]["utc_day"] == "2026-10-12"
    assert first["v1_repeat_untouched"] is True
    assert first["v1_component_untouched"] == "touch_live_cal"
    standing = shadow_notifications(confirmed, confirmed, utc_day="2026-10-12",
                                    last_summary_day=first["last_summary_day"])
    assert standing["changes"] == []
    assert standing["daily_summary"] is None
    next_day = shadow_notifications(confirmed, confirmed, utc_day="2026-10-13",
                                    last_summary_day="2026-10-12")
    assert next_day["changes"] == []
    assert next_day["daily_summary"]["books"][0]["state"] == STATE_CONFIRMED
    quiet = shadow_notifications(
        {"books": [{"procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch",
                    "horizon": "4h", "state": STATE_INSUFFICIENT}]},
        {"books": [{"procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch",
                    "horizon": "4h", "state": STATE_NOISE}]},
        utc_day="2026-10-12",
    )
    assert quiet["changes"] == []
    assert quiet["daily_summary"] is None
    recovered = shadow_notifications(
        confirmed,
        {"books": [{"procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch",
                    "horizon": "4h", "state": STATE_RECOVERED}]},
        utc_day="2026-10-14", last_summary_day="2026-10-13",
    )
    assert recovered["changes"][0]["from_state"] == STATE_CONFIRMED
    assert recovered["changes"][0]["to_state"] == STATE_RECOVERED
