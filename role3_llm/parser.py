"""
LLM output parser and safety net for MediAssist.

LLMs do not always produce valid JSON. Stage 5.3 of the reference document
lists five common failure modes; this module handles all of them:

    1. Markdown code fences:        ```json ... ```
    2. Explanatory prose before:    "Here is the diagnosis: { ... }"
    3. Explanatory prose after:     "{ ... } I hope this helps."
    4. Trailing commas:             {"a": 1, "b": 2,}
    5. Missing or invalid fields:   no `evidence`, bad `confidence_overall`, etc.

The processing pipeline is three stages:

    raw text → clean_llm_output() → json.loads() → DiagnosticResponse(**data)
                (regex cleanup)     (parse JSON)   (Pydantic validation)

If anything fails at any stage we (a) write a forensic log to ./logs/ for
later review and Phase 7 metrics, and (b) return None so the caller knows
parsing failed.

The orchestrator-facing function is parse_llm_response_safe(): it never
returns None, never raises. On any failure it returns the constant
FALLBACK_RESPONSE — a structured DiagnosticResponse the doctor's UI can
render, telling the user the system encountered a technical error and to
perform a manual clinical assessment. This is a patient safety property:
the system is allowed to be wrong, but it is not allowed to be silent.

Module exports:
    clean_llm_output(raw)             — strip artefacts, return cleaner text.
    parse_llm_response(raw)           — Optional[DiagnosticResponse].
    parse_llm_response_safe(raw)      — DiagnosticResponse, never None.
    log_parser_failure(raw, cleaned, error)
                                       — writes a forensic log entry.
    FALLBACK_RESPONSE                 — the never-None default.
"""

import json
import os
import re
from datetime import datetime
from typing import Optional

from pydantic import ValidationError

from shared.schemas import DiagnosisItem, DiagnosticResponse


# All forensic logs land here. Listed in .gitignore — never committed,
# because they may contain patient symptoms in raw form.
LOG_DIRECTORY = "./logs"


def clean_llm_output(raw_text: str) -> str:
    """
    Strip common LLM artefacts to leave (hopefully) parseable JSON.

    Args:
        raw_text: The exact string returned by provider.generate().

    Returns:
        Cleaned text. Not guaranteed to be valid JSON — parse_llm_response()
        still wraps json.loads() in a try/except.

    Handles, in order:
        - leading/trailing whitespace,
        - markdown code fences (opening ```json or ``` and closing ```),
        - explanatory prose before/after the JSON object,
        - trailing commas before } or ].
    """
    text = raw_text.strip()

    # Stage 1: strip markdown code fences. We match both the opening
    # variants (```json or just ```) and any closing ``` line.
    #     ```json
    #     {...}
    #     ```
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)

    # Stage 2: extract the JSON object even if surrounded by prose. The
    # regex {.*} with re.DOTALL spans newlines and is greedy, so it
    # captures from the first { to the LAST }. This handles:
    #   "Here is the diagnosis: { ... } I hope this helps!"
    #   →  "{ ... }"
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group()

    # Stage 3: remove trailing commas before } or ]. JavaScript allows them;
    # strict JSON does not. Common LLM mistake when the model has seen lots
    # of JS examples in training.
    #     {"a": 1, "b": 2,}  →  {"a": 1, "b": 2}
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text.strip()


def log_parser_failure(raw_text: str, cleaned_text: str, error: str) -> None:
    """
    Write a forensic record of a parser failure to ./logs/.

    Each call creates a timestamped file containing the error message,
    the original raw output, and the cleaned text we attempted to parse.
    These logs are later analysed to:
        - identify new failure modes the parser does not yet handle,
        - feed Phase 7 metrics on schema compliance per provider.

    Args:
        raw_text:     The original LLM output passed to the parser.
        cleaned_text: The output of clean_llm_output() applied to it.
        error:        A human-readable error description (e.g. the
                      JSONDecodeError or ValidationError stringified).

    Logs are LOCAL ONLY. ./logs/ is in .gitignore because the raw output
    may contain identifiable patient symptoms.
    """
    # Create the directory on demand. The first parser failure of a fresh
    # checkout will create ./logs/; subsequent failures append more files.
    os.makedirs(LOG_DIRECTORY, exist_ok=True)

    # Microsecond precision in the filename so two failures in the same
    # second do not overwrite each other (which would lose data).
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = os.path.join(LOG_DIRECTORY, f"parse_failure_{timestamp}.txt")

    with open(filepath, "w", encoding="utf-8") as log_file:
        log_file.write(f"ERROR: {error}\n\n")
        log_file.write("RAW OUTPUT:\n")
        log_file.write(raw_text)
        log_file.write("\n\nCLEANED OUTPUT:\n")
        log_file.write(cleaned_text)
        log_file.write("\n")


def parse_llm_response(raw_text: str) -> Optional[DiagnosticResponse]:
    """
    Parse and validate raw LLM output into a DiagnosticResponse.

    Args:
        raw_text: The exact string returned by provider.generate().

    Returns:
        A validated DiagnosticResponse on success.
        None on any failure — the failure is also written to ./logs/.

    The two failure stages are:
        - json.JSONDecodeError: cleaned text is still not valid JSON.
        - ValidationError:      JSON parsed, but does not match our schema.
    """
    cleaned = clean_llm_output(raw_text)

    # Stage A — JSON parsing. If the cleaned text is still malformed
    # (mismatched braces, broken strings, exotic characters), this raises
    # JSONDecodeError. We log the raw and cleaned versions for review.
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log_parser_failure(raw_text, cleaned, f"JSONDecodeError: {exc}")
        return None

    # Stage B — schema validation via Pydantic. Catches every constraint
    # violation: missing fields, wrong types, out-of-range values, the
    # probabilities-sum-to-100 rule, the Literal restriction on
    # confidence_overall, etc.
    try:
        return DiagnosticResponse(**data)
    except ValidationError as exc:
        log_parser_failure(raw_text, cleaned, f"ValidationError: {exc}")
        return None


# A frozen DiagnosticResponse used when the parser cannot produce a real
# answer. Built once at module load so we do not re-construct it on every
# failure. Defined AFTER parse_llm_response() so the file reads top-to-
# bottom in pipeline order.
#
# Patient safety: the doctor's UI must always receive a structured response
# it knows how to render. The fallback says explicitly, in clinical terms,
# that the system encountered a technical error and recommends manual
# assessment. Never None, never an exception, never a blank screen.
FALLBACK_RESPONSE = DiagnosticResponse(
    diagnoses=[
        DiagnosisItem(
            rank=1,
            condition="Unable to generate diagnosis",
            probability=100,
            reasoning="The system encountered a technical error.",
            evidence="System fallback — not derived from clinical evidence.",
            source_section="System",
        )
    ],
    follow_up_questions=["Please retry the query, or escalate if urgent."],
    recommended_tests=["Manual clinical assessment required."],
    confidence_overall="low",
    pipeline_confidence="low",
)


def parse_llm_response_safe(raw_text: str) -> DiagnosticResponse:
    """
    Parse with a guaranteed return — never None, never raises.

    Wraps parse_llm_response() and substitutes FALLBACK_RESPONSE on any
    failure. This is the function the orchestrator calls; the rest of
    the pipeline can rely on always receiving a DiagnosticResponse.

    Args:
        raw_text: The exact string returned by provider.generate().

    Returns:
        Either a parsed DiagnosticResponse (success) or FALLBACK_RESPONSE
        (any failure mode).
    """
    result = parse_llm_response(raw_text)
    return result if result is not None else FALLBACK_RESPONSE
