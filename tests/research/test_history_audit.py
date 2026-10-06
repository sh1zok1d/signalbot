"""RESEARCH_HISTORY_AUDIT_V1: the census stays complete and the committed record stays consistent."""
import json

from scripts.research import history_audit as H


def test_census_is_complete_against_every_source():
    res = H.build(write_dates=False)
    assert res["completeness_proof"]["problems"] == []
    assert res["census_total"] == res["atlas_units"] + len(res["post_atlas_units"])
    proof = res["completeness_proof"]
    assert proof["memory_entries"] == 79 and proof["memory_attempts"] == 65


def test_committed_record_matches_a_fresh_build():
    committed = json.loads(H.OUT_JSON.read_text())
    fresh = H.build(write_dates=False)
    assert committed["census_total"] == fresh["census_total"]
    assert committed["counts"]["cat"] == fresh["counts"]["cat"]
    assert committed["counts"]["cons"] == fresh["counts"]["cons"]
    assert committed["lists"] == fresh["lists"]
    assert {u["id"] for u in committed["units"]} == {u["id"] for u in fresh["units"]}


def test_conservatism_claims_require_measured_or_informative_ground():
    res = H.build(write_dates=False)
    for u in res["units"]:
        assert u["cons"] in H.CONS and u["level"] in H.LEVELS
        if u["cat"] in ("REAL_NULL", "STRONG_NEGATIVE"):
            assert u["cons"] == "NO", u["id"]          # a real null is never 'killed by conservatism'
        if u["cat"].startswith("NOT_TESTED") and u["cons"] == "YES":
            raise AssertionError(f"{u['id']}: an untested idea cannot be YES")
        if u["cat"] == "BLOCKED_PRACTICAL_BAR":
            assert u.get("est"), u["id"]                # the bar case needs a recorded estimate


def test_official_verdicts_are_quoted_unchanged_from_the_atlas():
    atlas = {u["id"]: u for u in json.loads(H.ATLAS_JSON.read_text())["UNITS"]}
    for u in H.build(write_dates=False)["units"]:
        if u["id"] in atlas:
            assert u["official_verdict"] == atlas[u["id"]].get("verdict")


def test_units_added_after_the_audit_are_placed_but_outside_the_v1_census():
    post = H.post_audit_atlas_units()
    assert "TOM-BASELINE-V1" in post
    res = H.build(write_dates=False)
    assert not set(post) & {u["id"] for u in res["units"]}
    assert res["census_total"] == json.loads(H.OUT_JSON.read_text())["census_total"] == 188
