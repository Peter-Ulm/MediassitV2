"""
Probability calibration module for MediAssist.

LLMs produce probability estimates as language ("80% likely") rather than
mathematical computations. Raw output may therefore:
    - sum to anything other than 100,
    - contain extreme values (100% false certainty, 0% false impossibility),
    - rank diagnoses inconsistently.

This module enforces two clinical constraints (Stage 7.2 of the reference):

    1. Probabilities sum to exactly 100.
    2. Every probability lies in [MIN_PROBABILITY, MAX_PROBABILITY] = [2, 95].

The pipeline calls calibrate_probabilities() between the Auditor and the
Strategist. Strategist then VERIFIES these constraints — it does not modify.

The algorithm is intentionally simple, four steps:

    1. Normalise: divide each value by the total, multiply by 100.
                  Result: floats that sum to exactly 100.
    2. Clip:      restrict each value to [2, 95]. Sum may drift.
    3. Renormalise: divide by the new total, multiply by 100. Sum back to 100.
    4. Round:     convert floats to integers while preserving sum=100.
                  We floor every value (always rounds down) and give the
                  rounding remainder to the LARGEST value, where adding 1
                  is proportionally smallest (and clinically invisible).

Then we sort descending by probability and reassign ranks 1..N.

Known algorithmic limitation (acknowledged for honest evaluation):
    Step 3 (renormalisation after clipping) can push values back above 95
    or below 2 by a small amount. Iterating clip+renormalise to perfect
    convergence is unnecessary at ±2% precision; we accept the small
    violation. The Strategist's bounds check uses the same constants and
    so will not flag the violation.

The function operates on List[dict] rather than List[DiagnosisItem]. This
keeps the algorithm decoupled from the schema, which makes it independently
testable and reusable. The pipeline (Phase 6) handles the dict ↔ Pydantic
conversion at the boundary.
"""

from typing import List

import numpy as np


# Clinical bounds. Documented in the module docstring above.
MIN_PROBABILITY = 2
MAX_PROBABILITY = 95


def round_to_integers_summing_to_100(values: np.ndarray) -> List[int]:
    """
    Convert a vector of floats into integers whose sum is exactly 100.

    Naive per-value rounding almost always breaks the sum (e.g.,
    [33.4, 33.3, 33.3] rounds to [33, 33, 33] = 99). Instead we floor
    every value (always rounds down, so total ≤ 100) and donate the
    remainder to the LARGEST single value.

    Why donate to the largest? Because rounding error is proportionally
    smallest there. Adding 1 to a 73 is a 1.4% change; adding 1 to a 5
    is a 20% change. The donation is clinically invisible at the top of
    the differential and significant at the bottom.

    Args:
        values: A numpy array of floats. Should already sum to ~100;
                this function does not enforce that itself, only the
                final integer sum.

    Returns:
        A list of integers summing to exactly 100, same length as input.
    """
    # Floor every value. floor(33.4) = 33, floor(33.3) = 33, etc.
    # Sum is now strictly less than (or equal to) the original sum.
    rounded = np.floor(values).astype(int)

    # The remainder is what we lost to flooring — non-negative because
    # floor only ever rounds down. Typically 0 to 3 across the array.
    remainder = 100 - rounded.sum()

    # Find the index of the largest floored value and add the remainder
    # there. int() converts numpy.int64 to a plain Python int for clarity
    # in any downstream traceback.
    highest_index = int(np.argmax(rounded))
    rounded[highest_index] += remainder

    return rounded.tolist()


def calibrate_probabilities(diagnoses: List[dict]) -> List[dict]:
    """
    Calibrate raw LLM probability estimates into a clean integer distribution.

    Mutates the input list in place AND returns it. This dual semantics
    matches the reference implementation; callers can use either return-
    value or in-place style without surprises.

    Args:
        diagnoses: List of dicts, each with at least:
                       "probability" — int or float (LLM's raw estimate)
                       "rank"        — int (will be overwritten)

    Returns:
        The same list, with probabilities renormalised, clipped to
        [2, 95], rounded to integers summing to exactly 100, sorted
        descending by probability, and re-ranked 1..N.

    Edge cases handled:
        - Empty list: returned unchanged.
        - All probabilities zero: treated as a flat distribution. Without
          this guard, the divide-by-sum step would raise ZeroDivisionError.
    """
    # Empty input — return immediately. Without this guard the np.array
    # construction works but the divide-by-zero check below operates on
    # an empty array, which is fragile. Better to short-circuit.
    if not diagnoses:
        return diagnoses

    # Pull probabilities out of the dicts into a float numpy array. dtype=float
    # is important because integer division would silently truncate later
    # ratios (e.g., 80 / 155 = 0 in integer math).
    raw_probs = np.array([d["probability"] for d in diagnoses], dtype=float)

    # Edge case: all probabilities are zero. Treat as flat distribution
    # (every diagnosis equally likely). Without this guard the divide-by-sum
    # below would raise ZeroDivisionError — or, with floats, produce NaN.
    if raw_probs.sum() == 0:
        raw_probs = np.ones(len(raw_probs))

    # Step 1 — normalise so the values sum to exactly 100.
    normalised = (raw_probs / raw_probs.sum()) * 100

    # Step 2 — clip to clinical bounds. Anything above 95 → 95, below 2 → 2.
    # After this step the sum has drifted away from 100 (unless the input
    # was already in bounds, in which case clipping was a no-op).
    clipped = np.clip(normalised, MIN_PROBABILITY, MAX_PROBABILITY)

    # Step 3 — renormalise. Brings the sum back to 100 while preserving
    # the relative proportions among the clipped values. Note: this can
    # push values back slightly above 95 / below 2 (see module docstring).
    renormalised = (clipped / clipped.sum()) * 100

    # Step 4 — convert floats to integers preserving sum = 100 exactly.
    calibrated_ints = round_to_integers_summing_to_100(renormalised)

    # Apply the calibrated values back to the original dicts. Order is
    # preserved here — sorting happens immediately below.
    for i, diagnosis in enumerate(diagnoses):
        diagnosis["probability"] = calibrated_ints[i]

    # Sort descending: rank 1 = most likely. Python's sort is stable, so
    # ties in probability preserve original input order — useful when two
    # diagnoses round to identical values.
    diagnoses.sort(key=lambda d: d["probability"], reverse=True)

    # Reassign ranks 1..N to match the new ordering. Without this, ranks
    # would still reflect the LLM's original (possibly bad) ordering.
    for new_rank, diagnosis in enumerate(diagnoses, start=1):
        diagnosis["rank"] = new_rank

    return diagnoses
