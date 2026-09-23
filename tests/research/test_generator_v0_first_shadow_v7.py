"""Operational closeout of sealed first-shadow-v7. No real LLM calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.generator_v0.context import ContractError, canonical
from scripts.research.generator_v0.__main__ import ARCHIVED_PAID_RUNS, main

REPO = Path(__file__).resolve().parents[2]
CAMPAIGN = REPO / "docs/research/GENERATOR_V0_FIRST_SHADOW_V7.json"
JOURNAL = REPO / "docs/research/generator_v0_first_shadow_v7/run.sqlite"
DIAGNOSTIC = REPO / "docs/research/generator_v0_first_shadow_v7/GEN3_VALIDATION_DIAGNOSTIC.json"
V6_SHA = "ed318020ff5d6c765394c15ba4ff5bd7dc0f89ffe83f7692f678e3f7e124b22d"
V7_SHA = "e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457"


def test_first_shadow_v7_is_archived_and_refused(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    assert ("generator_v0", "first-shadow-v7") in ARCHIVED_PAID_RUNS
    with pytest.raises(ContractError, match="archived paid run"):
        main(["resume", "--provider", "openai", "--allow-real-llm", "--budget-usd", "17.100000", "--run-dir", "artifacts/generator_v0/first-shadow-v7"])


def test_first_shadow_v7_campaign_record():
    payload = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    digest = payload["RESULT_PAYLOAD_SHA256"]
    body = dict(payload)
    body.pop("RESULT_PAYLOAD_SHA256")
    assert hashlib.sha256(canonical(body).encode("utf-8")).hexdigest() == digest
    assert payload["STATUS"] == "STOPPED_PROTECTED_RANGE_VALIDATION"
    assert payload["STOP_REASON"] == "ambiguous protected range"
    assert payload["NEW_SPEND_MICRO_USD"] == 1167200
    assert payload["CUMULATIVE_SPENT_MICRO_USD"] == 4946750
    assert payload["CAP_MICRO_USD"] == 17_100_000
    assert payload["REAL_LLM_CALLS_THIS_UNIT"] == 1
    assert payload["LIVE_GENERATION_3_RESPONSE_ID"] == "resp_071edfe3d5c0aaa9006ab3de92a5ac87d28b9f8efaec6c7db7"
    assert payload["IMPORTED_RESPONSE_IDS"] == [
        "resp_08273b80118314ac006ab39d9b92dc87d2ba9539e343da810e",
        "resp_0a0404f934baedd9006ab3a068c70887d2af71eda734b5aa3c",
        "resp_0804f042cef56925006ab3cdfb548887d2b43773b1e57a8094",
    ]
    assert payload["GENERATION_3_CARDS_VALID"] == 1
    assert payload["GENERATION_3_CARDS_INVALID"] == 9
    assert payload["CANDIDATE_COUNT_REGISTERED"] == 0
    assert payload["CARDS_TABLE_COUNT"] == 0
    assert payload["CRITICS_RUN"] is False
    assert payload["SELECTOR_RUN"] is False
    assert payload["SELECTOR_RESULT"] is None
    assert payload["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert payload["PROTECTED_2025_2026_OPENED"] is False
    assert payload["VALIDATOR_REPAIRED_AFTER_OUTCOME"] is False
    assert payload["LEGAL_RANGE_VALIDATOR_EXTENDED_AFTER_GEN3"] is False
    assert payload["SOURCE_CARDS_EDITED"] is False
    assert payload["FIRST_SHADOW_V6_SQLITE_SHA256"] == V6_SHA
    assert payload["AUTHORITY_JOURNAL_SHA256"] == V7_SHA
    assert hashlib.sha256(JOURNAL.read_bytes()).hexdigest() == V7_SHA
    diagnostic = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    assert diagnostic["VALID_COUNT"] == 1
    assert diagnostic["INVALID_COUNT"] == 9
    assert diagnostic["VALIDATOR_REPAIRED_AFTER_OUTCOME"] is False
    md = (REPO / "docs/research/GENERATOR_V0_FIRST_SHADOW_V7.md").read_text(encoding="utf-8")
    assert digest in md
    assert V7_SHA in md
