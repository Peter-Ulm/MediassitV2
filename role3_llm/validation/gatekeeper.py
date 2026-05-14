"""
Gatekeeper validation node.

The first of three validation nodes in the MediAssist validation pipeline.
The Gatekeeper answers a single question:

    Is the LLM's output structurally acceptable?

That decomposes into two checks, both of which parse_llm_response()
already performs:

    1. After cleaning, is the text valid JSON?
    2. Does the JSON match the DiagnosticResponse Pydantic schema?

If both checks pass, the Gatekeeper returns the validated response to the
next node (Auditor). If either check fails, it returns None — the
orchestrator then substitutes parser.FALLBACK_RESPONSE.

Why this is a separate file from parser.py:
    The parser converts messy text into a structured object. The Gatekeeper
    decides whether that object is fit to enter the rest of the pipeline.
    Different concerns, different audiences (the parser's forensic logs
    are written to disk for later analysis; the Gatekeeper's messages go
    to the console for live observation). Keeping them in separate files
    makes the three-node validation architecture visible at a glance.

Position in the validation pipeline:

    Gatekeeper  ──→ JSON valid? Schema correct?      ← THIS FILE
    Auditor     ──→ Every diagnosis grounded in STG?
    Strategist  ──→ Probabilities sensible? Coherent?
"""

from typing import Optional

from role3_llm.parser import parse_llm_response
from shared.schemas import DiagnosticResponse


def gatekeeper_check(raw_text: str) -> Optional[DiagnosticResponse]:
    """
    Run raw LLM output through the Gatekeeper validation node.

    Args:
        raw_text: The exact string returned by provider.generate().

    Returns:
        A validated DiagnosticResponse if the input passes both JSON and
        schema validation. None otherwise.

    Side effects:
        - On failure, parse_llm_response() has already written a forensic
          log file under ./logs/ describing the technical cause.
        - On both pass and fail, this function prints a single-line
          pipeline message so the orchestrator's console output shows
          the Gatekeeper's verdict in real time.
    """
    response = parse_llm_response(raw_text)

    if response is None:
        # The parser logged the technical detail (which field, which error)
        # to disk. Here we surface a high-level pipeline message — the
        # orchestrator and Phase 7 benchmark scripts can grep for this
        # prefix to count rejections per provider.
        print("[Gatekeeper] REJECTED — input failed JSON or schema validation.")
        return None

    # On success we summarise the response shape — useful for live
    # observation during Phase 6 integration testing.
    print(
        f"[Gatekeeper] PASSED — {len(response.diagnoses)} diagnosis(es), "
        f"confidence={response.confidence_overall}."
    )
    return response
