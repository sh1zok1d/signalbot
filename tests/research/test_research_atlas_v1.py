"""SIGNALBOT_RESEARCH_ATLAS_V1: sources are valid, derived files are current, every closed unit is
on the map, reopening rules are complete and the generator view is outcome-blind."""
import copy
import hashlib
import json
import re
import subprocess

import pytest

from scripts.research.atlas import build_atlas as ba


@pytest.fixture(scope="module")
def sources():
    return (ba._load_yaml(ba.TAXONOMY), ba._load_yaml(ba.SURFACES), ba._load_yaml(ba.UNITS),
            ba._load_json(ba.MEMORY)["ENTRIES"],
            [f["id"] for f in ba._load_yaml(ba.FINDINGS)["findings"]])


@pytest.fixture(scope="module")
def full():
    return ba._load_json(ba.OUT_FULL)


@pytest.fixture(scope="module")
def gen():
    return ba._load_json(ba.OUT_GENERATOR)


def test_sources_are_valid_and_the_derived_files_are_current():
    rep = ba.build(check_only=True)
    assert rep["stale"] == [] and rep["units"] > 100


def test_every_memory_entry_and_every_bot_finding_is_on_the_map(sources):
    tax, surf, units, memory, findings = sources
    ids = {u["id"] for u in units["units"]} | {a for u in units["units"] for a in u.get("aliases") or ()}
    assert set(memory) <= {u["id"] for u in units["units"] if u.get("memory")}
    assert set(findings) <= ids
    for program in ("R03-", "G01-"):
        assert any(i.startswith(program) for i in ids), program


def test_every_unit_says_why_it_closed_and_what_would_reopen_it(full):
    for u in full["UNITS"]:
        if u["state"] in ba.NEEDS_REOPEN:
            assert u.get("reopen"), u["id"]
        if u["state"] in ba.TESTED_STATES:
            assert u.get("why_closed") and u.get("forbidden"), u["id"]
        if u["state"] == "FUTURE_NATURAL_ACCUMULATION":
            assert u.get("revisit"), u["id"]
        assert u.get("records"), u["id"]


def test_cell_state_follows_the_precedence_and_never_hides_a_mix(full):
    prec = full["STATES"]
    order = ba._load_yaml(ba.TAXONOMY)["cell_precedence"]
    for c in full["CELLS"]:
        assert c["state"] in prec
        if c["units"]:
            assert c["state"] == next(s for s in order if c["counts"].get(s))
            assert c["mixed"] is (len(c["counts"]) > 1)
        else:
            assert c["state"] == "OPEN_FRONTIER" and c["counts"] == {}


def test_frontier_value_is_the_documented_sum(full):
    for c in full["CELLS"]:
        v = c["value"]
        assert v["total"] == (v["product_relevance"] + v["data_readiness"] + v["novelty"] + v["confirmation_path"]
                              - v["saturation"] + v["owner_priority"])
        assert 0 <= v["data_readiness"] <= 3 and 0 <= v["novelty"] <= 3 and 0 <= v["saturation"] <= 3
    ranked = [f["value"]["total"] for f in full["FRONTIER"]]
    assert ranked == sorted(ranked, reverse=True)
    assert all(f["value"]["data_readiness"] > 0 for f in full["FRONTIER"])


def test_cells_exist_only_where_the_mechanism_can_be_observed(full):
    rows = {f"{reg['id']}.{r['id']}": r.get("cols") or reg["cols"] for reg in full["REGIONS"] for r in reg["rows"]}
    cells = {(c["row"], c["col"]) for c in full["CELLS"]}
    assert cells == {(r, c) for r, cs in rows.items() for c in cs}
    assert ("MICROSTRUCTURE.book_imbalance", "CANDLES") not in cells
    assert all((u["row"], u["col"]) in cells for u in full["UNITS"])
    assert not [f for f in full["FRONTIER"] + full["FRONTIER_NEEDS_DATA"] if f["row"].startswith("METHOD.")]
    for c in full["CELLS"]:
        if not c["native"]:
            native = next(x for x in full["CELLS"] if x["row"] == c["row"] and x["native"])
            assert c["value"]["data_readiness"] <= native["value"]["data_readiness"] or c["units"] or native["units"]


def test_owner_priority_is_applied_to_the_frontier(full):
    prio = [f for f in full["FRONTIER"] if f["row"].split(".")[0] in ("MICROSTRUCTURE", "SPOT_PERP")]
    assert prio and all(f["value"]["owner_priority"] == 2 for f in prio)
    assert full["FRONTIER"][0]["value"]["owner_priority"] == 2


# ---- the generator view is outcome-blind ------------------------------------------------------------
OUTCOME_WORDS = re.compile(r"NO_STRUCTURE|LIVE_SIGNAL|CLOSED_ON_SURFACE|EXPOSED_ONLY|\bCONFIRMED\b|PROMISING|NO_EVIDENCE|"
                           r"NO_USEFUL|NO_INCREMENTAL|p[-_ ]?value|\bHolm\b|\bSD\b|\d\.\d|surviv|inconclusive|underpowered(?!_NOW)|"
                           r"exploratory outcome|validation once|compatible with zero|economically small|close to useless|"
                           r"\(closed|BLOCKED_GOVERNANCE|CLOSED_BEFORE_START|INFORMATIONALLY_WEAK|verdict", re.IGNORECASE)


def test_generator_view_carries_no_outcomes(gen):
    text = json.dumps({k: v for k, v in gen.items() if k != "RULES"}, ensure_ascii=False)  # RULES is fixed policy text
    hits = OUTCOME_WORDS.findall(text)
    assert not hits, hits[:10]
    assert {c["generator_state"] for c in gen["CELLS"]} <= {"OPEN", "PRIOR_WORK", "DATA_REQUIRED", "UNDERPOWERED_NOW"}
    for c in gen["CELLS"]:
        assert not set(c) & set(ba.GEN_FORBIDDEN_KEYS)


def test_flipping_an_outcome_cannot_change_the_generator_view(monkeypatch):
    """NO_STRUCTURE <-> LIVE_SIGNAL (and a changed verdict text) leave the blind view byte-identical."""
    base = ba._load_yaml(ba.UNITS)
    flipped = copy.deepcopy(base)
    swap = {"NO_STRUCTURE": "LIVE_SIGNAL", "LIVE_SIGNAL": "NO_STRUCTURE", "CONFIRMED": "CLOSED_ON_SURFACE",
            "CLOSED_ON_SURFACE": "CONFIRMED"}
    for u in flipped["units"]:
        u["state"] = swap.get(u["state"], u["state"])
        for k in ("verdict", "why_closed", "note", "practical_bar"):
            if u.get(k):
                u[k] = "SUPPORTED, effect +9.9 SD " + u[k]
    for r in flipped.get("memory_reconciliation") or ():
        r["atlas_state"] = swap.get(r["atlas_state"], r["atlas_state"])
        r["reason"] = "PASSED " + r["reason"]

    def view(units_doc):
        tax, surf = ba._load_yaml(ba.TAXONOMY), ba._load_yaml(ba.SURFACES)
        memory = ba._load_json(ba.MEMORY)["ENTRIES"]
        gov = {r["SIGNATURE_ID"]: r for r in ba._load_json(ba.GOVERNANCE)["ROWS"]}
        units = ba.full_units(units_doc, memory, gov)
        cells = ba.cells(tax, surf, units, list(tax.get("owner_priorities") or ()))
        frontier = sorted((c for c in cells if c["state"] == "OPEN_FRONTIER" and c["value"]["data_readiness"] > 0),
                          key=lambda c: (-c["value"]["total"], c["row"], c["col"]))
        return ba.generator_view(tax, surf, cells, {u["id"]: u for u in units}, ba._load_json(ba.BLIND), frontier, "x")

    assert ba._dump(view(base)) == ba._dump(view(flipped))


# ---- validation fails closed --------------------------------------------------------------------------
def test_validate_reports_broken_sources(sources):
    tax, surf, units, memory, findings = sources
    bad = copy.deepcopy(units)
    bad["units"].append({"id": "X-1", "row": "NOWHERE.row", "col": "CANDLES", "state": "NO_STRUCTURE",
                         "datasets": ["NO_SUCH_DATASET"]})
    bad["units"].append({"id": "X-2", "row": "EVENTS.cpi", "col": "CANDLES", "state": "FUTURE_NATURAL_ACCUMULATION",
                         "datasets": ["CORE_BTC_BINANCE_V0"], "title": "t", "program": "p", "mechanism": "m",
                         "function": "f", "verdict": "v", "records": ["docs/research/NO_SUCH_FILE.md"]})
    bad["units"].append(dict(bad["units"][-1], id="X-3", row="MICROSTRUCTURE.book_imbalance", col="CANDLES"))
    bad["units"] = [u for u in bad["units"] if u["id"] != "D2"]
    problems = "\n".join(ba.validate(tax, surf, bad, memory, findings + ["NO_SUCH_FINDING"]))
    for needle in ("X-1: unknown row", "X-1: unknown dataset", "X-1: missing reopen",
                   "X-2: FUTURE_NATURAL_ACCUMULATION needs revisit", "X-2: record docs/research/NO_SUCH_FILE.md not found",
                   "X-3: column CANDLES is not applicable to row MICROSTRUCTURE.book_imbalance",
                   "memory entry D2 has no atlas unit", "findings registry id NO_SUCH_FINDING"):
        assert needle in problems, needle


# ---- memory reconciliation: memory preserved, atlas authoritative ----------------------------------------
def test_memory_reconciliation_layer(full, sources):
    tax, surf, units, memory, findings = sources
    recs = {r["id"]: r for r in units["memory_reconciliation"]}
    assert recs["D7"]["atlas_state"] == "CONFIRMED" and recs["D7"]["memory_implied_state"] == "LIVE_SIGNAL"
    assert recs["GV0V03L40-C033"]["atlas_state"] == "BLOCKED_METHOD"
    assert recs["GV0V03L40-C033"]["memory_implied_state"] == "CANDIDATE_UNTESTED"
    for uid, r in recs.items():
        assert r["memory_status"] == memory[uid]["STATUS_EVIDENCE_CLASS"], uid  # the memory chain is untouched
    by = {u["id"]: u for u in full["UNITS"]}
    assert by["D7"]["state"] == "CONFIRMED" and by["D7"]["memory_status"].startswith("PROMISING_PROTOTYPE")
    assert all(u["routing_authority"] == ba.VERSION for u in full["UNITS"] if u["source"] == "MECHANISM_MEMORY_V0")


def test_reconciliation_fails_closed(sources):
    tax, surf, units, memory, findings = sources
    missing = copy.deepcopy(units)
    missing["memory_reconciliation"] = [r for r in missing["memory_reconciliation"] if r["id"] != "D7"]
    stale = copy.deepcopy(units)
    stale["memory_reconciliation"].append(dict(stale["memory_reconciliation"][0], id="D2", atlas_state="LIVE_SIGNAL"))
    drift = copy.deepcopy(units)
    next(r for r in drift["memory_reconciliation"] if r["id"] == "GV0V03L40-C033")["memory_status"] = "EDITED"
    assert "D7: atlas state CONFIRMED differs from memory-implied LIVE_SIGNAL" in "\n".join(
        ba.validate(tax, surf, missing, memory, findings))
    assert "reconciliation D2: stale entry" in "\n".join(ba.validate(tax, surf, stale, memory, findings))
    assert "reconciliation GV0V03L40-C033: memory_status no longer matches" in "\n".join(
        ba.validate(tax, surf, drift, memory, findings))


# ---- governance records ---------------------------------------------------------------------------------
def test_price_oi_pilot_is_blocked_by_the_e1_overlap(full):
    u = next(x for x in full["UNITS"] if x["id"] == "PRICE-OI-PILOT-V0")
    assert (u["state"], u["blocker"], u["reservation"]) == ("BLOCKED_GOVERNANCE", "HOLDOUT_OVERLAP", "E1_RUN_001_FINAL_HOLDOUT")
    err = ba._load_json(ba.ROOT / "docs/research/PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.json")
    assert err["RUNNER_EXECUTED"] is False and err["CONCERNED_RECORDS_EDITED"] is False
    assert "E1_RUN_001_TOUCHED" not in err  # no bare "E1 untouched" claim survives the owner decision
    assert (err["E1_EVALUATOR_TOUCHED"], err["E1_SEALED_ARTIFACTS_OPENED"], err["E1_OUTCOME_SURFACE_OPENED_BY_P4"],
            err["E1_PRISTINE_HOLDOUT_STATUS"]) == (False, False, True, "INVALIDATED_FOR_P4_OVERLAP")
    assert err["PROTECTED_INTERVAL"] == {"id": "E1_RUN_001_FINAL_HOLDOUT", "start": "2026-08-16T00:00:00Z",
                                         "end_exclusive": "2026-08-25T17:20:00Z"}
    assert err["FUTURE_EXECUTION"] == "NEW_EXPLICIT_PERMIT_REQUIRED"
    assert err["EARLIEST_ELIGIBLE_GRID_TIMESTAMP"] == "2026-08-25T17:20:00Z"
    g = err["FROZEN_GRID"]
    assert g["buckets_inside_protected_interval"] + g["buckets_after_protected_interval"] == g["authorized_buckets"] == 12434
    frozen = (ba.ROOT / "docs/research/price_oi_incremental_information_pilot_v0.json").read_text()
    assert "E1_OVERLAP" not in frozen  # the frozen twin was not edited


def test_seed0001_prospective_closed_before_start(full):
    u = next(x for x in full["UNITS"] if x["id"] == "SEED-0001-PROSP")
    assert u["state"] == "CLOSED_BEFORE_START"
    rec = ba._load_json(ba.ROOT / "docs/research/SEED0001_PROSPECTIVE_CLOSURE_V1.json")
    assert rec["STATUS"] == "CLOSED_BEFORE_START" and rec["REASON"] == "superseded by divergence program closure"
    assert rec["EXECUTION_STARTED"] is False and rec["PROSPECTIVE_OUTCOMES_OPENED"] is False
    assert rec["CONFIRMATION_SURFACE_CONSUMED"] is False
    prereg = (ba.ROOT / rec["PREREG_PATH"]).read_bytes()
    assert hashlib.sha256(prereg).hexdigest() == rec["PREREG_SHA256"]  # preregistration preserved byte-for-byte
    ledger = ba._load_json(ba.ROOT / "docs/research/SCIENTIFIC_TEST_LEDGER.json")
    entry = next(t for t in ledger["TESTS"] if t["TEST_FAMILY_ID"] == "TF-SEED0001-RD-PROSP1")
    assert entry["STATUS"] == "REGISTERED_NOT_STARTED" and entry["PREREG_SHA256"] == rec["PREREG_SHA256"]


# ---- reserved confirmation surfaces --------------------------------------------------------------------
def test_reserved_surfaces_are_invisible_to_generation(gen, sources):
    tax, surf, units, memory, findings = sources
    res = {r["id"]: r for r in surf["reservations"]}
    assert list(res) == ["E1_RUN_001_FINAL_HOLDOUT"]
    e1 = res["E1_RUN_001_FINAL_HOLDOUT"]
    assert e1["status"] == "RESERVED" and e1["permit_required"] is True and e1["permit"] is None
    period = {"start": "2026-08-16T00:00:00Z", "end_exclusive": "2026-08-25T17:20:00Z"}
    shown = {s["id"]: s for s in gen["SURFACES"]}
    for d in e1["datasets"]:
        assert shown[d]["unavailable_periods"] == [period], d
    # a dataset held whole disappears from the generator view and from data readiness
    held = copy.deepcopy(surf)
    held["reservations"].append({"id": "X", "status": "RESERVED", "datasets": ["D2_BITMEX_PRE2020_XBTUSD"],
                                 "scope": {"regions": ["VOLATILITY_STATE"]}, "intended_use": "test", "period": None,
                                 "holder_units": ["D2"], "permit_required": True, "authority": ["AGENTS.md"]})
    marked = ba._mark_reservations(held)
    assert next(d for d in marked["datasets"] if d["id"] == "D2_BITMEX_PRE2020_XBTUSD")["_fully_reserved"]
    assert ba.readiness("VOLATILITY_STATE.tail_risk", "VOLATILITY_STATE", "CANDLES", marked, {},
                        only=["D2_BITMEX_PRE2020_XBTUSD"]) == 0


def test_reservation_rules_fail_closed(sources):
    tax, surf, units, memory, findings = sources
    bad = copy.deepcopy(surf)
    bad["reservations"].append({"id": "R1", "status": "RESERVED", "datasets": ["CORE_BTC_BINANCE_V0"], "period": None,
                                "scope": {"regions": ["EVENTS"]}, "intended_use": "x", "holder_units": ["D11"],
                                "permit_required": False, "authority": ["AGENTS.md"]})
    bad["reservations"].append({"id": "R2", "status": "CONSUMED", "datasets": ["CORE_BTC_BINANCE_V0"], "period": None,
                                "scope": {"regions": ["EVENTS"]}, "intended_use": "x", "holder_units": ["D11"],
                                "permit_required": True, "authority": ["AGENTS.md"]})
    u = copy.deepcopy(units)
    next(x for x in u["units"] if x["id"] == "PRICE-OI-PILOT-V0")["reservation"] = "NOPE"
    problems = "\n".join(ba.validate(tax, bad, u, memory, findings))
    for needle in ("reservation R1: a RESERVED surface needs permit_required: true",
                   "reservation R2: CONSUMED needs the permit", "PRICE-OI-PILOT-V0: HOLDOUT_OVERLAP must name a reservation"):
        assert needle in problems, needle


# ---- reopen / rescue rules --------------------------------------------------------------------------
def test_reopen_keys_and_forbidden_moves(full):
    keys, moves = set(full["REOPEN_KEYS"]), full["FORBIDDEN_MOVES"]
    assert {"NEW_MECHANISM", "NEW_SURFACE", "NEW_CONFIRMATION_SURFACE", "RECORDED_REOPEN_CONDITION"} <= keys
    for word in ("threshold", "percentile", "lookback", "horizon", "nearby parameter"):
        assert word in moves["PARAMETER_NEIGHBOR"], word
    assert not keys & set(moves)
    for u in full["UNITS"]:
        if u["state"] == "BLOCKED_GOVERNANCE":
            assert u.get("blocker") and u.get("reopen"), u["id"]


# ---- append-only event chain --------------------------------------------------------------------------
def test_event_chain_is_intact_and_current():
    events = ba.load_events()
    assert events[0]["change_type"] == "INITIAL_TRANSFER" and events[0]["prior_atlas_digest"] is None
    assert events[0]["new_atlas_digest"] == "765be4424045e54a02b2fb5cd3e6dd189fe3cc0ac1fb10d46d8179e9345af002"
    assert len(events[0]["affected_units"]["added"]) == 145
    tax, surf, units = ba._load_yaml(ba.TAXONOMY), ba._load_yaml(ba.SURFACES), ba._load_yaml(ba.UNITS)
    memory = ba._load_json(ba.MEMORY)["ENTRIES"]
    findings = [f["id"] for f in ba._load_yaml(ba.FINDINGS)["findings"]]
    digest = ba.sources_digest(tax, surf, units, memory, findings)
    assert ba.verify_events(events, digest, ba.unit_index(units)) == []
    for ev in events:
        assert {"prior_atlas_digest", "new_atlas_digest", "timestamp", "change_type", "affected_units",
                "affected_cells", "source_records", "reason", "event_hash"} <= set(ev)


def test_event_chain_detects_rewrites_and_staleness():
    events = ba.load_events()
    rewritten = copy.deepcopy(events)
    rewritten[0]["reason"] = "rewritten"
    assert any("hash does not match" in p for p in ba.verify_events(rewritten))
    dropped = copy.deepcopy(events[1:])
    assert any("sequence" in p or "first event" in p for p in ba.verify_events(dropped))
    relinked = copy.deepcopy(events)
    relinked[-1]["prior_atlas_digest"] = "0" * 64
    relinked[-1]["event_hash"] = ba.event_hash(relinked[-1])
    assert any("prior_atlas_digest" in p for p in ba.verify_events(relinked))
    assert any("sources changed" in p for p in ba.verify_events(events, "f" * 64))


def test_appending_requires_a_change_and_links_to_the_head(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    path.write_text(ba.EVENTS.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(ba, "EVENTS", path)
    with pytest.raises(ba.AtlasError, match="nothing changed"):
        ba.append_event("GOVERNANCE_RECORD", "no-op", ["AGENTS.md"])
    head = ba.load_events(path)[-1]
    ev = ba.make_event(head, "UNIT_TEXT_CHANGE", "test", ["AGENTS.md"], "a" * 64, head["unit_index"],
                       head["unit_index"], "2099-01-01T00:00:00Z", head["layer_digests"])
    assert ev["seq"] == head["seq"] + 1 and ev["prev_event_hash"] == head["event_hash"]
    assert ba.verify_events(ba.load_events(path) + [ev], "a" * 64) == []


# ---- bot bridge: the atlas never writes bot copy --------------------------------------------------------
def test_atlas_never_writes_the_findings_registry():
    before = ba.FINDINGS.read_bytes()
    ba.build(check_only=True)
    assert ba.FINDINGS.read_bytes() == before
    src = (ba.ROOT / "scripts/research/atlas/build_atlas.py").read_text()
    assert re.findall(r"FINDINGS\b[^\n]*", src) and not re.search(r"FINDINGS[^\n]*(write|open\([^)]*['\"]w)", src)


# ---- owner decision on P4 / E1 (erratum Amendment 1) -------------------------------------------------
def test_p4_exposure_is_derived_from_its_records_and_recorded_everywhere(sources):
    tax, surf, units, memory, findings = sources
    err = ba._load_json(ba.ROOT / "docs/research/PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.json")
    a1 = next(a for a in err["AMENDMENTS"] if a["id"] == "AMENDMENT_1")
    assert a1["E1_RECORDS_REWRITTEN"] is False and a1["P4_ROW_LEVEL_LOG_IN_REPOSITORY"] is False
    # the recorded read window is the one in the P4-era replay code (364db27), not an estimate
    replay = subprocess.check_output(["git", "show", "364db27:scripts/audit/live_archive_replay_preflight/"
                                      "run_price_oi_semantic_replay.py"], cwd=ba.ROOT, text=True)
    assert "ts >= TIMESTAMPTZ '2026-07-17 19:30:00+00'" in replay and "ts < TIMESTAMPTZ '2026-09-29 00:00:00+00'" in replay
    assert a1["P4_RECORDED_READ_WINDOW"] == {"start": "2026-07-17T19:30:00Z", "end_exclusive": "2026-09-29T00:00:00Z"}
    summary = ba._load_json(ba.ROOT / "docs/audit/live_archive_price_oi_p4_followup_v0/p4_followup_summary.json")
    assert summary["authorized_buckets"] == 12434 and "PHASE_A_AUTHORIZED_BUCKETS = 12434" in subprocess.check_output(
        ["git", "show", "364db27:scripts/audit/live_archive_replay_preflight/price_oi_semantic_replay.py"],
        cwd=ba.ROOT, text=True)
    # the replay window contains the whole protected interval, so the E1 exposure is the interval itself
    assert a1["E1_P4_EXPOSED_INTERVAL"] == {"start": "2026-08-16T00:00:00Z", "end_exclusive": "2026-08-25T17:20:00Z",
                                            "share_of_protected_interval": "ALL"}
    rules = a1["FUTURE_PILOT_RULES"]
    assert rules["exclude_outcome_timestamps"] == a1["P4_EXPOSED_TREATED"]
    assert rules["new_explicit_execution_permit_required"] is True and rules["old_frozen_data_gate_reusable"] is False
    assert rules["earliest_input_clean_anchor_under_v0_lookbacks"] == "2026-10-29T04:00:00Z"
    e1 = next(r for r in surf["reservations"] if r["id"] == "E1_RUN_001_FINAL_HOLDOUT")
    assert e1["status"] == "RESERVED" and e1["pristine_status"] == "INVALIDATED_FOR_P4_OVERLAP"
    assert e1["contamination"][0]["period"] == {"start": "2026-08-16T00:00:00Z", "end_exclusive": "2026-08-25T17:20:00Z"}
    live = [d for d in surf["datasets"] if d["id"] in ("STAGE1_LIVE_KLINES_3VENUE", "STAGE1_LIVE_OI_FUNDING")]
    for d in live:
        assert any(e.get("scope") == "ALL" and e["period"] == "2026-07-17T19:30Z..2026-09-29T04:00Z"
                   for e in d["exposure"]), d["id"]
    md = (ba.ROOT / "docs/research/PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.md").read_text()
    assert "E1_PRISTINE_HOLDOUT_STATUS = INVALIDATED_FOR_P4_OVERLAP" in md and not re.search(r"E1[^\n]{0,20}is untouched", md)


def test_non_pristine_reservation_must_record_its_contamination(sources):
    tax, surf, units, memory, findings = sources
    bad = copy.deepcopy(surf)
    next(r for r in bad["reservations"] if r["id"] == "E1_RUN_001_FINAL_HOLDOUT").pop("contamination")
    assert "reservation E1_RUN_001_FINAL_HOLDOUT: a non-pristine reservation must record its contamination" in "\n".join(
        ba.validate(tax, bad, units, memory, findings))
