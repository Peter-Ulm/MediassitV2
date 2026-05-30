import json

from role3_llm.validation.sanitizer import sanitize_response
from role3_llm.validation.gatekeeper import gatekeeper_check

# The exact shape llama3.2:3b produced: two grounded diagnoses + a trailing
# speculative one with empty evidence, and probabilities summing to 95.
BAD = json.dumps({
    "diagnoses": [
        {"rank": 1, "condition": "Typhoid fever", "probability": 60,
         "reasoning": "Fever for 3 days with chills and headache suggests typhoid.",
         "evidence": "CAUTION: Typhoid fever is characterized by prolonged fever.",
         "source_section": "diagnosis"},
        {"rank": 2, "condition": "Malaria", "probability": 30,
         "reasoning": "Fever with chills could indicate malaria with headache.",
         "evidence": "CAUTION: Malaria is characterized by fever, chills, headache.",
         "source_section": "diagnosis"},
        {"rank": 3, "condition": "Dengue", "probability": 5,
         "reasoning": "Fever with headache could suggest dengue fever.",
         "evidence": "", "source_section": ""},
    ],
    "follow_up_questions": ["Travel history?", "Contact with travellers?"],
    "recommended_tests": ["Malaria RDT"],
    "confidence_overall": "medium",
})


def test_gatekeeper_rejects_the_raw_output():
    # The brittle behaviour we are fixing: one empty-evidence item (and the
    # 95 sum) makes the strict gate reject the whole response.
    assert gatekeeper_check(BAD) is None


def test_sanitizer_drops_empty_evidence_and_passes_gatekeeper():
    cleaned = sanitize_response(BAD)
    assert cleaned is not None
    resp = gatekeeper_check(cleaned)
    assert resp is not None
    conditions = [d.condition for d in resp.diagnoses]
    assert "Dengue" not in conditions
    assert len(resp.diagnoses) == 2
    assert sum(d.probability for d in resp.diagnoses) == 100  # renormalised


def test_sanitizer_returns_none_when_no_usable_diagnoses():
    bad = json.dumps({
        "diagnoses": [
            {"rank": 1, "condition": "X", "probability": 100,
             "reasoning": "short", "evidence": "", "source_section": ""},
        ],
        "follow_up_questions": ["q"], "recommended_tests": ["t"],
        "confidence_overall": "low",
    })
    assert sanitize_response(bad) is None


def test_sanitizer_passes_unparseable_text_through_unchanged():
    assert sanitize_response("not json at all") == "not json at all"
