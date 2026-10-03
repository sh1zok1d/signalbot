"""SIGNALBOT_RESEARCH_ATLAS_V1: sources are valid, derived files are current, every closed unit is
on the map, reopening rules are complete and the generator view is outcome-blind."""
import copy
import json
import re

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
                           r"NO_USEFUL|NO_INCREMENTAL|p[-_ ]?value|\bHolm\b|\bSD\b|\d\.\d", re.IGNORECASE)


def test_generator_view_carries_no_outcomes(gen):
    text = json.dumps(gen, ensure_ascii=False)
    hits = OUTCOME_WORDS.findall(text)
    assert not hits, hits[:10]
    assert {c["generator_state"] for c in gen["CELLS"]} <= {"OPEN", "PRIOR_WORK", "DATA_REQUIRED", "UNDERPOWERED_NOW"}
    for c in gen["CELLS"]:
        assert not set(c) & set(ba.GEN_FORBIDDEN_KEYS)


def test_flipping_an_outcome_cannot_change_the_generator_view(monkeypatch):
    """NO_STRUCTURE <-> LIVE_SIGNAL (and a changed verdict text) leave the blind view byte-identical."""
    base = ba._load_yaml(ba.UNITS)
    flipped = copy.deepcopy(base)
    for u in flipped["units"]:
        if u["state"] == "NO_STRUCTURE":
            u["state"] = "LIVE_SIGNAL"
        elif u["state"] == "LIVE_SIGNAL":
            u["state"] = "NO_STRUCTURE"
        if u.get("verdict"):
            u["verdict"] = "SUPPORTED " + u["verdict"]

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
