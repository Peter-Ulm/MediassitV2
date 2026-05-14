"""
Strategist validation node.

The third of three validation nodes. Where the Gatekeeper checked
field-level structure and the Auditor checked external grounding, the
Strategist checks INTER-FIELD COHERENCE — relationships between fields
that the earlier nodes cannot see.

Checks performed:

    1. Probabilities sum to ~100 (hard).
    2. No probability is at an unrealistic extreme < 2% or > 95% (hard).
    3. Ranks are sequential starting from 1: [1, 2, 3, ...] (hard).
    4. Probabilities are non-increasing with rank — rank 1 has the
       highest probability, and so on (hard).
    5. confidence_overall is consistent with the top probability:
            top ≥ 60% suggests "high"
            top < 40% suggests "low"
            otherwise   "medium"
       Mismatch is logged as a WARNING but does NOT fail the response —
       confidence rating is partly subjective and a doctor or upstream
       node may legitimately disagree with the heuristic.

Returns True if every HARD check passes (warnings do not affect the
return value). Returns False on any hard failure.

Position in the production pipeline:

    Gatekeeper           ──→ JSON valid? Schema correct?
    Auditor              ──→ Every diagnosis grounded in STG?
    calibrate_probabilities() ──→ Renormalise sums and bounds (Phase 5)
    Strategist           ──→ Inter-field coherence?               ← THIS FILE

Strategist runs AFTER calibration in production, so it sees an already-
calibrated response and primarily verifies the calibrator did its job
plus the relationship checks calibration cannot perform on its own.
"""

from typing import Literal, Optional

from shared.schemas import DiagnosticResponse


# Probability bounds. After calibration, every probability should fall
# inside [MIN_PROBABILITY, MAX_PROBABILITY]. The Strategist verifies this
# after the fact — calibration is what enforces it.
MIN_PROBABILITY = 2
MAX_PROBABILITY = 95

# Tolerance around 100 for the sum check. Calibration produces an exact
# sum of 100, but allowing ±2 lets Strategist run usefully against
# uncalibrated test inputs and against production data with rounding drift.
SUM_TOLERANCE = 2

# Heuristic thresholds for the soft confidence-coherence check. Numbers
# chosen on reference Stage 7.3's qualitative scoring rubric — "top
# diagnosis at least 60%" is the rough boundary at which confidence
# language shifts from "medium" to "high" in clinical notes.
HIGH_CONFIDENCE_TOP_THRESHOLD = 60
LOW_CONFIDENCE_TOP_THRESHOLD = 40


def strategist_check(
    response: DiagnosticResponse,
) -> Optional[Literal["low", "medium", "high"]]:
    """
    Run all coherence checks on a DiagnosticResponse.

    Args:
        response: A DiagnosticResponse that has passed Gatekeeper and
                  Auditor and (in production) been calibrated.

    Returns:
        The pipeline-computed confidence level ("low" | "medium" | "high")
        if all HARD checks pass. Soft warnings do not affect this.
        None if any hard check fails. The reason is printed.
    """
    diagnoses = response.diagnoses

    # ─── Check 1 (HARD): probabilities sum to ~100 ─────────────────────
    total = sum(d.probability for d in diagnoses)
    if abs(total - 100) > SUM_TOLERANCE:
        print(
            f"[Strategist] FAILED — probabilities sum to {total}, "
            f"expected 100±{SUM_TOLERANCE}."
        )
        return None

    # ─── Check 2 (HARD): no extreme probabilities ──────────────────────
    extreme_conditions = [
        d.condition
        for d in diagnoses
        if d.probability < MIN_PROBABILITY or d.probability > MAX_PROBABILITY
    ]
    if extreme_conditions:
        print(
            f"[Strategist] FAILED — probabilities outside "
            f"[{MIN_PROBABILITY}, {MAX_PROBABILITY}]: "
            f"{', '.join(extreme_conditions)}."
        )
        return None

    # ─── Check 3 (HARD): ranks are sequential 1..N ─────────────────────
    expected_ranks = list(range(1, len(diagnoses) + 1))
    actual_ranks = [d.rank for d in diagnoses]
    if actual_ranks != expected_ranks:
        print(
            f"[Strategist] FAILED — ranks are {actual_ranks}, "
            f"expected {expected_ranks}."
        )
        return None

    # ─── Check 4 (HARD): probabilities non-increasing with rank ────────
    # By definition, rank 1 should have the highest probability. We check
    # each consecutive pair: prob[i] must be ≥ prob[i+1]. Allows equal
    # probabilities (ties are clinically possible and the schema does not
    # forbid them).
    probabilities = [d.probability for d in diagnoses]
    for i in range(len(probabilities) - 1):
        if probabilities[i] < probabilities[i + 1]:
            print(
                f"[Strategist] FAILED — probabilities not in rank order: "
                f"rank {i + 1} has {probabilities[i]}% but rank {i + 2} "
                f"has {probabilities[i + 1]}%."
            )
            return None

    # ─── Check 5 (SOFT): confidence_overall coherent with top probability ──
    # Compute the pipeline's verdict from the calibrated probabilities.
    # Mismatch with the LLM's self-reported confidence_overall is logged as
    # a WARNING but does NOT fail the response — confidence is partly
    # subjective. The computed value is returned so the orchestrator can
    # write it back into pipeline_confidence on the DiagnosticResponse.
    top_probability = probabilities[0]
    if top_probability >= HIGH_CONFIDENCE_TOP_THRESHOLD:
        pipeline_conf: Literal["low", "medium", "high"] = "high"
    elif top_probability < LOW_CONFIDENCE_TOP_THRESHOLD:
        pipeline_conf = "low"
    else:
        pipeline_conf = "medium"

    if response.confidence_overall != pipeline_conf:
        print(
            f"[Strategist] WARNING — top probability {top_probability}% "
            f"suggests confidence='{pipeline_conf}', "
            f"but LLM reported '{response.confidence_overall}'. "
            "Not a hard failure."
        )

    print(
        f"[Strategist] PASSED — sum={total}, top={top_probability}%, "
        f"pipeline_confidence={pipeline_conf}."
    )
    return pipeline_conf
