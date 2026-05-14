"""
Shared Pydantic schemas for MediAssist.

This module defines the JSON contract between Role 3 (Peter — LLM Integration)
and Role 4 (Benson — Backend API). Both teammates import the same models, so
there is exactly one definition of the contract and any change breaks both
sides simultaneously rather than silently.

Hierarchy:
    DiagnosticResponse
    ├── diagnoses: list of 1 to 5 DiagnosisItem
    ├── follow_up_questions: list of strings (at least 1)
    ├── recommended_tests: list of strings (at least 1)
    └── confidence_overall: "low" | "medium" | "high"

This is the Gatekeeper node from Stage 5.2 of the reference document. Any LLM
output that does not match this schema is rejected before it reaches a doctor.

Note on Pydantic versions:
    The reference document uses Pydantic v1 syntax (`@validator`, `min_items`).
    This file uses Pydantic v2 syntax (`@field_validator`, `min_length`) because
    Pydantic v1 reached end-of-life in 2024. The constraints are identical;
    only the decorator names and field-keyword names differ.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Bump when any field is added, removed, or renamed.
# Benson's backend can log or assert on this at startup to detect contract drift.
SCHEMA_VERSION = "1.1.0"


class DiagnosisItem(BaseModel):
    """
    A single ranked diagnosis with grounded evidence.

    Each DiagnosisItem represents one possible condition the LLM has identified,
    along with the reasoning and the specific STG passage that supports it. The
    `evidence` field is what the Auditor node uses to verify grounding — if the
    LLM fabricated a quote that does not appear in the retrieved chunks, the
    Auditor catches it.
    """

    # rank: 1 = most likely diagnosis, 5 = least likely. We cap at 5 to prevent
    # the LLM from producing an unwieldy 15-item differential a doctor cannot scan.
    rank: int = Field(
        ge=1,
        le=5,
        description="Position in the differential. 1 is most likely.",
    )

    # condition: a short clinical name. min_length=2 rejects empty or one-letter
    # nonsense; we deliberately do not enforce a maximum because some conditions
    # have long official names (e.g. 'Severe Acute Respiratory Syndrome').
    condition: str = Field(
        min_length=2,
        description="The diagnosed condition, e.g. 'Malaria'.",
    )

    # probability: integer 0–100. The LLM's raw estimate; the calibration module
    # in Stage 7.2 will renormalise these to sum to exactly 100 with min/max bounds.
    probability: int = Field(
        ge=0,
        le=100,
        description="LLM-estimated probability before calibration.",
    )

    # reasoning: a short clinical explanation tying symptoms to this condition.
    # min_length=10 prevents one-word answers like 'Yes' or 'Likely'.
    reasoning: str = Field(
        min_length=10,
        description="Why this diagnosis fits the patient's symptoms.",
    )

    # evidence: a direct quote or close paraphrase from the STG. The Auditor
    # node compares this against Willard's retrieved chunks to verify grounding.
    evidence: str = Field(
        min_length=10,
        description="Direct quote or close paraphrase from the STG.",
    )

    # source_section: which STG section the evidence came from. Lets a doctor
    # open the STG and verify the recommendation themselves.
    source_section: str = Field(
        description="The STG section the evidence is drawn from.",
    )


class DiagnosticResponse(BaseModel):
    """
    The complete structured output returned to the doctor's UI.

    Produced by Peter's pipeline, validated by the Gatekeeper, and consumed by
    Benson's backend, which then forwards it to Jesca's frontend.
    """

    # diagnoses: between 1 and 5 ranked DiagnosisItems. Note the v2 names —
    # min_length / max_length — replace v1's min_items / max_items.
    diagnoses: List[DiagnosisItem] = Field(
        min_length=1,
        max_length=5,
        description="Differential diagnosis, top-ranked first.",
    )

    # follow_up_questions: at least one. Drives the Clinical Interrogator agent
    # downstream — these become the next questions the doctor asks the patient.
    follow_up_questions: List[str] = Field(
        min_length=1,
        description="Questions the doctor should ask to disambiguate.",
    )

    # recommended_tests: at least one diagnostic test (e.g. 'mRDT for Malaria').
    recommended_tests: List[str] = Field(
        min_length=1,
        description="Diagnostic tests to confirm or rule out diagnoses.",
    )

    # confidence_overall: the LLM's self-reported confidence. A closed set of
    # three values — Literal rejects anything outside this set (e.g. 'medium-high').
    confidence_overall: Literal["low", "medium", "high"] = Field(
        description="LLM's self-reported confidence in its own output.",
    )

    # pipeline_confidence: the Strategist's computed verdict, written back by
    # run_mediassist_pipeline() after Stage 8. None until the pipeline sets it;
    # Benson's backend should prefer this over confidence_overall when present.
    pipeline_confidence: Optional[Literal["low", "medium", "high"]] = Field(
        default=None,
        description="Strategist-computed confidence, set by the pipeline after calibration.",
    )

    @field_validator("diagnoses")
    @classmethod
    def probabilities_must_sum_to_about_100(
        cls,
        diagnoses: List[DiagnosisItem],
    ) -> List[DiagnosisItem]:
        """
        Soft check that probabilities are roughly normalised.

        We accept 98–102 (not strictly 100) because the LLM produces integer
        approximations and may be off by one or two. The Strategist's calibration
        module in role3/calibration.py will enforce an exact sum of 100 later;
        this check is a sanity guard at the validation boundary.
        """
        total = sum(item.probability for item in diagnoses)
        if not 98 <= total <= 102:
            raise ValueError(
                f"Probabilities sum to {total}; must be between 98 and 102."
            )
        return diagnoses
