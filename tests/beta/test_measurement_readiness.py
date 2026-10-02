"""Synthetic PRODUCT_FIRST measurement gate. No database and no live provider."""
import inspect
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from beta.measurement_eval import (
    DECISION_THRESHOLDS, FAIL, FREEZE, INC, MF, NOT_PASS, PASS, evaluate, load_contract,
    volatility_bottom_quartile)

UTC = timezone.utc
CUTOFF = datetime(2026, 7, 1, tzinfo=UTC)
ORIGIN = datetime(2026, 6, 1, 6, tzinfo=UTC)
CONTRACT = load_contract()


def _at(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


def _pseudo(n):
    return f"{n:064x}"


def _prices(month_return):
    origin = date(2026, 6, 1)
    day8 = origin + timedelta(days=7)
    day30 = origin + timedelta(days=29)
    first = day8 - timedelta(days=91)
    prior = [0.001] * 20 + [0.05] * 70
    returns = {}
    cursor = first + timedelta(days=1)
    for value in prior:
        returns[cursor] = value
        cursor += timedelta(days=1)
    assert cursor == day8 and len(prior) == 90
    cursor = day8
    while cursor <= day30:
        returns[cursor] = month_return
        cursor += timedelta(days=1)
    price = 100.0
    rows = [{"date": first.isoformat(), "close": price}]
    cursor = first + timedelta(days=1)
    while cursor <= day30:
        price *= math.exp(returns[cursor])
        rows.append({"date": cursor.isoformat(), "close": price})
        cursor += timedelta(days=1)
    return rows


def _overlay():
    return {
        "briefing_withdrawal_dates": ["2026-06-16", "2026-06-17", "2026-06-18"],
        "u1a_aggregation": "PER_USER_AT_LEAST_2_OF_3_DAYS",
        "u1a_verbal_question_id": "u1a_where_is_the_brief",
        "u1a_conflict_precedence": "FAIL_WINS",
        "brief_off_reading": "OFF_EVENT_IN_MEASUREMENT_WINDOW",
        "u1b_pull_actions": ["cmd_btc", "cmd_catchup", "cmd_history"],
        "u1b_week_definition": "TWO_BLOCKS_18_24_AND_25_30",
        "push_click_attribution": "LATEST_SENT_WITHIN_WINDOW",
        "u2_push_floor_scope": "MEASUREMENT_WINDOW",
        "u2_volatility_series": "TEST_DAILY_CLOSE",
        "u2_volatility_formula": "MEAN_SQUARED_LOG_RETURN_VS_P25_PRIOR_90",
        "u2_disable_reading": "OFF_EVENT_IN_MEASUREMENT_WINDOW",
        "u2_conflict_precedence": "INCONCLUSIVE_WINS",
        "blocked_classifier": ["blocked"],
        "delivery_failure_day": {
            "denominator": "ENROLLED_UNKNOWN_AS_OF_DAY",
            "brief_failure_states": ["FAILED"],
            "episodic_failure_states": ["FAILED", "DELIVERY_UNKNOWN"],
            "applies_to": ["U1a", "U1b", "U2", "U5"],
        },
        "refund_anchor": "PAYMENT_PLUS_30D",
        "u3_denominator": "ENROLLED_BY_CUTOFF",
        "u4_window_start": "2026-06-01",
        "u4_work_within_cap": True,
        "u5_verbal_question_id": "u5_other_markets",
    }


def _person(pk, *, joined, known, owner, label):
    return {
        "enrollment_pk": pk, "pseudonym": _pseudo(pk), "joined_at": joined,
        "invite_code": None if label is None else f"code-{label}", "invite_label": label,
        "known_contact_initial": known, "owner_excluded": owner,
    }


def _pass_snapshot():
    early = ORIGIN
    late = _at(6, 20, 6)
    people = [
        _person(1, joined=early, known=False, owner=True, label=None),
        _person(2, joined=early, known=True, owner=False, label="acq"),
    ]
    for pk in range(3, 7):
        people.append(_person(pk, joined=early, known=False, owner=False, label="ch-a"))
    for pk in range(7, 11):
        people.append(_person(pk, joined=early, known=False, owner=False, label="ch-b"))
    people.append(_person(11, joined=late, known=False, owner=False, label="ch-b"))
    classifications = [
        {"enrollment_pk": p["enrollment_pk"], "known_contact": p["known_contact_initial"],
         "recorded_at": p["joined_at"]} for p in people]
    classifications.append({
        "enrollment_pk": 3, "known_contact": True, "recorded_at": _at(7, 5, 12)})
    activity = []
    for pk in (3, 4, 5, 6):
        for day in (16, 17):
            activity.append({"enrollment_pk": pk, "action": "cmd_catchup", "detail": None,
                             "at": _at(6, day, 5, 30)})
        for day in (18, 19, 20, 25, 26, 27):
            activity.append({"enrollment_pk": pk, "action": "cmd_btc", "detail": None,
                             "at": _at(6, day, 12)})
    activity.append({"enrollment_pk": 7, "action": "cmd_brief", "detail": "off", "at": _at(6, 10, 10)})
    activity.append({"enrollment_pk": 10, "action": "cmd_push", "detail": "off", "at": _at(6, 12, 10)})
    activity.append({"enrollment_pk": 1, "action": "cmd_catchup", "detail": None, "at": _at(6, 16, 5, 30)})
    for pk in (3, 4, 5, 6, 7):
        for day in (10, 11):
            activity.append({"enrollment_pk": pk, "action": "btn_fake_door", "detail": None,
                             "at": _at(6, day, 15)})
    for pk in (3, 4, 5, 6):
        for day in range(8, 14):
            activity.append({"enrollment_pk": pk, "action": "tab_event", "detail": None,
                             "at": _at(6, day, 6, 1)})
    deliveries = []
    for pk in range(3, 11):
        for day in range(8, 23):
            deliveries.append({"enrollment_pk": pk, "state": "SENT", "finished_at": _at(6, day, 6),
                               "error_summary": None, "decision_ts": _at(6, day, 6)})
    for day in range(21, 26):
        for hour in (6, 10, 14):
            deliveries.append({"enrollment_pk": 11, "state": "SENT", "finished_at": _at(6, day, hour),
                               "error_summary": None, "decision_ts": _at(6, day, hour)})
    deliveries.append({"enrollment_pk": 9, "state": "FAILED", "finished_at": _at(6, 11, 6),
                       "error_summary": "Forbidden: bot was blocked by the user",
                       "decision_ts": _at(6, 11, 6)})
    deliveries.append({"enrollment_pk": 8, "state": "DELIVERY_UNKNOWN", "finished_at": _at(6, 13, 7),
                       "error_summary": "TimeoutError", "decision_ts": _at(6, 13, 7)})
    briefs = []
    for pk in range(3, 11):
        for day in (16, 17, 18):
            briefs.append({"enrollment_pk": pk, "brief_date": date(2026, 6, day), "state": "WITHHELD",
                           "recorded_at": _at(6, day, 5), "error_summary": None, "error_class": None})
    briefs.append({"enrollment_pk": 10, "brief_date": date(2026, 6, 9), "state": "FAILED",
                   "recorded_at": _at(6, 9, 5), "error_summary": "timed out", "error_class": "NOT_BLOCKED"})
    briefs.append({"enrollment_pk": 3, "brief_date": date(2026, 6, 10), "state": "SENT",
                   "recorded_at": _at(6, 10, 5), "error_summary": None, "error_class": None})
    commercial = []
    for pk in range(3, 12):
        commercial.append({"enrollment_pk": pk, "event_type": "OFFER", "recorded_at": _at(6, 22, 10),
                           "amount": "25", "currency": "USD"})
    for pk in (3, 4, 5, 6):
        commercial.append({"enrollment_pk": pk, "event_type": "PAYMENT", "recorded_at": _at(6, 23, 10),
                           "amount": "25", "currency": "USD"})
    commercial.append({"enrollment_pk": 6, "event_type": "REFUND", "recorded_at": _at(6, 24, 10),
                       "amount": "25", "currency": "USD"})
    commercial.append({"enrollment_pk": 2, "event_type": "PAYMENT", "recorded_at": _at(6, 23, 11),
                       "amount": "25", "currency": "USD"})
    interviews = [
        {"enrollment_pk": 8, "question_id": "u5_other_markets", "answered_at": _at(6, 12, 12),
         "verbatim": "I keep wanting other markets", "spontaneous": True},
        {"enrollment_pk": 9, "question_id": "u5_other_markets", "answered_at": _at(6, 12, 13),
         "verbatim": "other markets, because you asked", "spontaneous": False},
    ]
    votes = [
        {"enrollment_pk": 3, "episode_pk": 1, "vote": "USEFUL", "recorded_at": _at(6, 15, 12)},
        {"enrollment_pk": 3, "episode_pk": 1, "vote": "NOISE", "recorded_at": _at(7, 5, 12)},
    ]
    return {
        "enrollments": people,
        "classifications": classifications,
        "activity": activity,
        "votes": votes,
        "briefs": briefs,
        "deliveries": deliveries,
        "commercial": commercial,
        "interviews": interviews,
        "telemetry": {"activity_write_failures": 0, "last_failure_at": None},
        "prices": _prices(0.08),
        "prices_status": "TEST_SERIES",
    }


def _score(snapshot=None, overlay=None, cutoff=CUTOFF):
    return evaluate(snapshot if snapshot is not None else _pass_snapshot(), CONTRACT,
                    cutoff=cutoff, overlay=_overlay() if overlay is None else overlay)


def test_contract_leaves_product_choices_unfrozen_and_keeps_decision_thresholds():
    assert CONTRACT["day0_declared"] is False
    assert CONTRACT["source_decision_commit"] == "d7f931d070d65815c4f1c39284af20a6d5b21f90"
    assert CONTRACT["frozen"]["thresholds"] == DECISION_THRESHOLDS
    assert CONTRACT["frozen"]["failure_fraction_is_strictly_greater_than"] == 0.30
    for value in CONTRACT["requires_freeze_before_day0"].values():
        assert value == FREEZE
    for value in CONTRACT["cells_not_in_the_decision_table"].values():
        assert value == FREEZE


def test_synthetic_fixture_scores_each_available_branch():
    assert volatility_bottom_quartile(_prices(0.08), date(2026, 6, 1),
                                      "MEAN_SQUARED_LOG_RETURN_VS_P25_PRIOR_90") is False
    first = _score()
    second = _score()
    assert first == second
    assert first["metrics"]["U1a"]["status"] == PASS
    assert first["metrics"]["U1a"]["detail"]["react"] == 4
    assert first["metrics"]["U1a"]["detail"]["brief_off"] == 1
    assert first["metrics"]["U1b"]["status"] == PASS
    assert first["metrics"]["U1b"]["detail"]["qualifiers"] == 4
    assert first["metrics"]["U2"]["status"] == PASS
    assert first["metrics"]["U2"]["detail"]["positive"] == 4
    assert first["metrics"]["U2"]["detail"]["disabled_or_blocked"] == 2
    assert first["metrics"]["U3"]["status"] == PASS
    assert first["metrics"]["U3"]["detail"]["paid"] == 3
    assert first["metrics"]["U3"]["detail"]["enrolled_unknown"] == 9
    assert first["metrics"]["U4"]["status"] == PASS
    assert first["metrics"]["U4"]["detail"]["joins"] == 8
    assert first["metrics"]["U5"]["status"] == PASS
    assert first["metrics"]["U5"]["detail"]["qualifying"] >= 5
    assert first["decision"]["status"] == "CONTINUE"
    assert first["origin"].startswith("2026-06-01")
    blocks = _overlay()
    blocks["u1b_week_definition"] = "ORIGIN_BLOCKS_OF_7_MIN3"
    assert _score(overlay=blocks)["metrics"]["U1b"]["status"] == PASS


def test_a_command_inside_ten_minutes_after_a_push_is_not_a_pull():
    snap = _pass_snapshot()
    for row in snap["activity"]:
        if row["enrollment_pk"] == 3 and row["action"] == "cmd_btc" and row["at"] == _at(6, 18, 12):
            row["at"] = _at(6, 18, 6, 5)
    scored = _score(snap)
    assert scored["metrics"]["U1b"]["status"] == INC
    assert scored["metrics"]["U1b"]["detail"]["qualifiers"] == 3


def test_reclassification_after_cutoff_does_not_rewrite_the_cohort():
    base = _score()
    changed = _pass_snapshot()
    changed["classifications"].append(
        {"enrollment_pk": 3, "known_contact": True, "recorded_at": _at(6, 20, 8)})
    moved = _score(changed)
    assert moved["metrics"]["U1a"]["status"] != PASS
    assert base["metrics"]["U4"]["detail"]["joins"] == 8
    initial = _pass_snapshot()
    initial["enrollments"][2]["known_contact_initial"] = True
    assert _score(initial)["metrics"]["U4"]["detail"]["joins"] == 8


def test_missing_evidence_is_measurement_failure_not_a_product_cell():
    missing_offer = _pass_snapshot()
    missing_offer["commercial"] = [r for r in missing_offer["commercial"]
                                   if not (r["enrollment_pk"] == 11 and r["event_type"] == "OFFER")]
    offer = _score(missing_offer)
    assert offer["metrics"]["U3"]["status"] == MF
    assert offer["metrics"]["U3"]["reason"] == "U3_OFFER_MISSING"
    short = _pass_snapshot()
    short["activity"] = [r for r in short["activity"] if r["action"] != "btn_fake_door"]
    overlay = _overlay()
    overlay.pop("u5_verbal_question_id")
    verbal = _score(short, overlay)
    assert verbal["metrics"]["U5"]["status"] == MF
    assert verbal["metrics"]["U5"]["reason"] == "U5_VERBAL_QUESTION_UNFROZEN"
    bare = evaluate(_pass_snapshot(), CONTRACT, cutoff=CUTOFF, overlay=None)
    for code in ("U1a", "U1b", "U2", "U3", "U4", "U5"):
        assert bare["metrics"][code]["status"] == MF
        assert bare["metrics"][code]["status"] not in (PASS, FAIL, INC)


def test_activity_failure_blanks_behaviour_metrics_and_a_later_failure_does_not():
    tainted = _pass_snapshot()
    tainted["telemetry"] = {"activity_write_failures": 1, "last_failure_at": _at(6, 18, 12)}
    scored = _score(tainted)
    for code in ("U1a", "U1b", "U2", "U5"):
        assert scored["metrics"][code]["status"] == MF
        assert scored["metrics"][code]["reason"] == "ACTIVITY_WRITE_FAILURE"
    assert scored["metrics"]["U3"]["status"] == PASS
    assert scored["metrics"]["U4"]["status"] == PASS
    later = _pass_snapshot()
    later["telemetry"] = {"activity_write_failures": 1, "last_failure_at": _at(7, 2, 0)}
    assert _score(later)["metrics"]["U1a"]["status"] == PASS


def test_cutoff_ignores_later_payments_revotes_and_identity():
    early = _score(cutoff=_at(6, 22, 12))
    assert early["metrics"]["U3"]["status"] == FAIL
    assert early["metrics"]["U3"]["detail"]["paid"] == 0
    dirty = _pass_snapshot()
    dirty["enrollments"][0]["telegram_user_id"] = 1
    assert _score(dirty)["metrics"]["U4"]["status"] == MF
    assert _score(dirty)["metrics"]["U4"]["reason"] == "IDENTITY_IN_SNAPSHOT"


def test_revote_uses_only_the_revision_at_or_before_cutoff():
    people = [_person(n, joined=ORIGIN, known=False, owner=False, label=label)
              for n, label in ((3, "ch-a"), (4, "ch-a"), (5, "ch-b"), (6, "ch-b"))]
    snapshot = _pass_snapshot()
    snapshot["enrollments"] = people
    snapshot["classifications"] = [
        {"enrollment_pk": p["enrollment_pk"], "known_contact": False, "recorded_at": ORIGIN} for p in people]
    snapshot["activity"] = []
    snapshot["briefs"] = []
    snapshot["interviews"] = []
    snapshot["commercial"] = []
    for pk in (3, 4, 5, 6):
        snapshot["commercial"].append({"enrollment_pk": pk, "event_type": "OFFER",
                                       "recorded_at": _at(6, 22, 10), "amount": "25", "currency": "USD"})
    snapshot["deliveries"] = [
        {"enrollment_pk": pk, "state": "SENT", "finished_at": _at(6, day, 6),
         "error_summary": None, "decision_ts": _at(6, day, 6)}
        for pk in (3, 4, 5, 6) for day in range(8, 23)]
    snapshot["votes"] = []
    for pk in (3, 4, 5, 6):
        for episode in range(1, 6):
            snapshot["votes"].append({"enrollment_pk": pk, "episode_pk": episode, "vote": "USEFUL",
                                     "recorded_at": _at(6, 15, 12)})
    before = _score(snapshot, cutoff=_at(6, 28, 12))
    assert before["metrics"]["U2"]["status"] == PASS
    snapshot["votes"].append({"enrollment_pk": 3, "episode_pk": 1, "vote": "NOISE",
                              "recorded_at": _at(6, 29, 12)})
    for episode in range(2, 6):
        snapshot["votes"].append({"enrollment_pk": 3, "episode_pk": episode, "vote": "NOISE",
                                  "recorded_at": _at(6, 29, 12)})
    assert _score(snapshot, cutoff=_at(6, 28, 12))["metrics"]["U2"]["status"] == PASS
    after = _score(snapshot, cutoff=_at(6, 30, 12))
    assert after["metrics"]["U2"]["status"] == MF
    assert after["metrics"]["U2"]["reason"] == "U2_CELL_NOT_IN_CONTRACT"
    assert after["metrics"]["U2"]["detail"]["positive"] == 3


def test_unlisted_cells_and_conflicts_are_not_guessed():
    snap = _pass_snapshot()
    snap["activity"] = [r for r in snap["activity"]
                        if not (r["enrollment_pk"] == 6 and r["action"] == "tab_event")]
    cell = _score(snap)
    assert cell["metrics"]["U2"]["status"] == MF
    assert cell["metrics"]["U2"]["reason"] == "U2_CELL_NOT_IN_CONTRACT"
    two = _pass_snapshot()
    two["commercial"] = [r for r in two["commercial"]
                         if not (r["enrollment_pk"] == 5 and r["event_type"] == "PAYMENT")]
    assert _score(two)["metrics"]["U3"]["status"] == INC
    low = _prices(0.0001)
    assert volatility_bottom_quartile(low, date(2026, 6, 1),
                                      "MEAN_SQUARED_LOG_RETURN_VS_P25_PRIOR_90") is True
    quiet = _pass_snapshot()
    quiet["prices"] = low
    assert _score(quiet)["metrics"]["U2"]["status"] == INC
    conflict = _overlay()
    conflict["u1a_aggregation"] = "AT_LEAST_2_DAYS_WITH_AT_LEAST_4_USERS"
    conflict["u1a_conflict_precedence"] = FREEZE
    assert _score(overlay=conflict)["metrics"]["U1a"]["status"] == MF


def test_delivery_unknown_is_not_a_block_and_exact_thirty_percent_is_kept():
    scored = _score()
    assert scored["metrics"]["U2"]["detail"]["disabled_or_blocked"] == 2
    people = [_person(pk, joined=ORIGIN, known=False, owner=False, label="ch-a" if pk < 8 else "ch-b")
              for pk in range(3, 13)]
    briefs = [{"enrollment_pk": pk, "brief_date": date(2026, 6, 12), "state": "FAILED",
               "recorded_at": _at(6, 12, 5), "error_summary": "down", "error_class": "NOT_BLOCKED"}
              for pk in (3, 4, 5)]
    snap = {"enrollments": people, "classifications": [
                {"enrollment_pk": p["enrollment_pk"], "known_contact": False, "recorded_at": ORIGIN}
                for p in people],
            "activity": [], "votes": [], "deliveries": [], "commercial": [], "interviews": [],
            "briefs": briefs, "prices": [],
            "telemetry": {"activity_write_failures": 0, "last_failure_at": None}}
    overlay = {"delivery_failure_day": _overlay()["delivery_failure_day"]}
    kept = evaluate(snap, CONTRACT, cutoff=CUTOFF, overlay=overlay)
    assert "2026-06-12" not in kept["excluded_dates"]
    briefs.append({"enrollment_pk": 6, "brief_date": date(2026, 6, 12), "state": "FAILED",
                   "recorded_at": _at(6, 12, 5), "error_summary": "down", "error_class": "NOT_BLOCKED"})
    dropped = evaluate(snap, CONTRACT, cutoff=CUTOFF, overlay=overlay)
    assert "2026-06-12" in dropped["excluded_dates"]


def test_evaluator_does_not_read_admin_stats():
    source = Path(inspect.getfile(evaluate)).read_text(encoding="utf-8")
    assert "admin_stats" not in source
    assert "build_usage_report" not in source
    assert "beta.usage" not in source


def test_late_join_splits_the_u3_denominator_until_it_is_frozen():
    person_a = _person(3, joined=ORIGIN, known=False, owner=False, label="ch-a")
    person_b = _person(4, joined=_at(6, 26, 8), known=False, owner=False, label="ch-b")
    snap = {
        "enrollments": [person_a, person_b],
        "classifications": [
            {"enrollment_pk": 3, "known_contact": False, "recorded_at": ORIGIN},
            {"enrollment_pk": 4, "known_contact": False, "recorded_at": person_b["joined_at"]},
        ],
        "activity": [], "votes": [], "briefs": [], "deliveries": [], "interviews": [],
        "commercial": [
            {"enrollment_pk": 3, "event_type": "OFFER", "recorded_at": _at(6, 22, 10),
             "amount": "25", "currency": "USD"},
            {"enrollment_pk": 3, "event_type": "PAYMENT", "recorded_at": _at(6, 23, 10),
             "amount": "25", "currency": "USD"},
        ],
        "telemetry": {"activity_write_failures": 0, "last_failure_at": None},
        "prices": [],
    }
    overlay = {"u4_window_start": "2026-06-01", "u4_work_within_cap": True,
               "refund_anchor": "PAYMENT_PLUS_30D"}
    assert _score(snap, overlay)["metrics"]["U3"]["reason"] == "U3_DENOMINATOR_UNFROZEN"
    by_end = dict(overlay, u3_denominator="ENROLLED_BY_OFFER_END")
    assert _score(snap, by_end)["metrics"]["U3"]["status"] == FAIL
    by_cutoff = dict(overlay, u3_denominator="ENROLLED_BY_CUTOFF")
    assert _score(snap, by_cutoff)["metrics"]["U3"]["reason"] == "U3_OFFER_MISSING"
