"""
Sanitizer — pre-Gatekeeper robustness pass.

Smaller/faster local models occasionally pad the differential with a trailing
speculative diagnosis that has empty `evidence`, or emit probabilities that do
not sum to 100. The strict Gatekeeper schema rejects the ENTIRE response for one
such flaw — discarding otherwise-valid, grounded diagnoses and forcing the
fallback. That brittleness is what this node removes.

The Sanitizer runs BEFORE the Gatekeeper and:
  1. Leniently parses the raw model output to a dict.
  2. Drops diagnosis items that cannot pass the schema (missing/empty/too-short
     `evidence`, `reasoning`, or `condition`).
  3. Renormalises the surviving probabilities to sum to exactly 100 (reusing the
     calibration module) so the Gatekeeper's sum check passes.

It is conservative: it only ever DROPS unsupported items or rescales numbers —
it never invents clinical content. If no usable diagnosis remains it returns
None and the orchestrator serves the fallback. If the text cannot be parsed at
all, it returns the original text unchanged and lets the Gatekeeper reject it
(parse failures are not this node's concern).

Position in the validation pipeline:

    Sanitizer   ──→ Drop unusable diagnoses, renormalise   ← THIS FILE (new)
    Gatekeeper  ──→ JSON valid? Schema correct?
    Auditor     ──→ Every diagnosis grounded in STG?
    Strategist  ──→ Probabilities sensible? Coherent?
"""

from __future__ import annotations

import json
from typing import Optional

from role3_llm.calibration import calibrate_probabilities

# Mirror the schema's per-field minimums (shared/schemas.py DiagnosisItem) so a
# dropped item is exactly one the Gatekeeper would have rejected.
_MIN_EVIDENCE = 10
_MIN_REASONING = 10
_MIN_CONDITION = 2


def _loads(raw: str):
    """Best-effort parse to a Python object. Strips a ```json fence if present."""
    try:
        return json.loads(raw)
    except Exception:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            try:
                return json.loads(text.strip())
            except Exception:
                return None
        return None


def _usable(item: object) -> bool:
    """True if the diagnosis item has the non-empty fields the schema requires."""
    if not isinstance(item, dict):
        return False
    evidence = item.get("evidence")
    reasoning = item.get("reasoning")
    condition = item.get("condition")
    return (
        isinstance(evidence, str) and len(evidence.strip()) >= _MIN_EVIDENCE
        and isinstance(reasoning, str) and len(reasoning.strip()) >= _MIN_REASONING
        and isinstance(condition, str) and len(condition.strip()) >= _MIN_CONDITION
    )


def sanitize_response(raw_text: str) -> Optional[str]:
    """
    Drop unusable diagnosis items and renormalise probabilities.

    Returns:
        - cleaned JSON string, ready for the Gatekeeper, OR
        - the original `raw_text` if it could not be parsed (Gatekeeper decides), OR
        - None if it parsed but no usable diagnosis remained (serve fallback).
    """
    data = _loads(raw_text)
    if not isinstance(data, dict) or not isinstance(data.get("diagnoses"), list):
        return raw_text  # not our concern — let the Gatekeeper handle/reject it

    diagnoses = data["diagnoses"]
    kept = [d for d in diagnoses if _usable(d)]

    if not kept:
        print(
            f"[Sanitizer] dropped all {len(diagnoses)} diagnosis(es) — none had "
            "usable evidence. Serving fallback."
        )
        return None

    dropped = len(diagnoses) - len(kept)
    if dropped:
        print(f"[Sanitizer] dropped {dropped} unusable diagnosis(es); kept {len(kept)}.")

    # Always renormalise the survivors to sum to exactly 100 so the Gatekeeper's
    # 98–102 sum check passes (also fixes a model that was simply off, e.g. 95).
    data["diagnoses"] = calibrate_probabilities(kept)
    return json.dumps(data)
