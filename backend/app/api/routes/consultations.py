"""
Consultation routes — in-memory CRUD.

The frontend treats a "consultation" as the persistent record of a doctor's
diagnostic session: patient meta + symptoms + the produced DiagnosisResult +
free-text notes. We store these in a process-local dict for the demo. A real
deployment would back this with a database.

Difference vs the prototype: create_consultation now runs the REAL diagnose
service (Role 2 retrieval + Role 3 LLM), so consultations contain real
ChromaDB-grounded diagnoses instead of a hand-written stub.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.routes.diagnosis import _build_recommended_tests
from app.core.logger import logger
from app.schemas.api import (
    Diagnosis,
    DiagnoseResponse,
    EvidenceItem,
    PatientMeta,
    RecommendedTest,
)
from app.services.diagnose import diagnose

router = APIRouter()


# Process-local store. Restarting the backend wipes consultations — fine for
# a demo, swap for a database in production.
_consultations: Dict[str, "Consultation"] = {}


class Consultation(BaseModel):
    id: str
    patient: PatientMeta
    symptoms: str
    results: DiagnoseResponse
    notes: str = ""
    status: str = "draft"  # 'draft' | 'completed'
    createdAt: str


class ConsultationSummary(BaseModel):
    id: str
    patient: PatientMeta
    summary: str
    createdAt: str
    status: str


class CreateConsultationRequest(BaseModel):
    patient: PatientMeta
    symptoms: str
    meta: Optional[dict] = None


class UpdateConsultationRequest(BaseModel):
    symptoms: Optional[str] = None
    results: Optional[DiagnoseResponse] = None
    notes: Optional[str] = None
    status: Optional[str] = None


def _to_diagnose_response(symptoms: str) -> DiagnoseResponse:
    """Run the real pipeline and adapt to the API response model."""
    result = diagnose(symptoms)
    response = result.response
    retrieved_by_excerpt = {c.text: c for c in result.retrieved}

    diagnoses: List[Diagnosis] = []
    for d in response.diagnoses:
        match = next(
            (c for excerpt, c in retrieved_by_excerpt.items()
             if d.evidence and d.evidence in excerpt),
            None,
        )
        chapter = (
            (match.metadata.get("chapter") if match and match.metadata else None)
            or d.source_section
        )
        diagnoses.append(Diagnosis(
            name=d.condition,
            probability=d.probability / 100.0,
            reasoning=d.reasoning,
            evidenceRefs=[match.chunk_id] if match else [],
            evidence=[
                EvidenceItem(
                    source=f"Tanzania STG — {chapter}" if chapter else "Tanzania STG",
                    excerpt=d.evidence,
                    chapter=chapter,
                    section=d.source_section,
                    relevance_score=match.score if match else None,
                )
            ],
        ))

    warning = None
    if response.pipeline_confidence == "low":
        warning = (
            "Low pipeline confidence — treat as advisory only and perform "
            "manual clinical assessment."
        )

    return DiagnoseResponse(
        diagnoses=diagnoses,
        followUps=response.follow_up_questions,
        recommendedTests=_build_recommended_tests(response.recommended_tests),
        confidence_overall=response.confidence_overall,
        pipeline_confidence=response.pipeline_confidence,
        warning=warning,
        retrieval_ms=result.retrieval_ms,
        llm_ms=result.llm_ms,
        total_ms=result.total_ms,
    )


@router.post("/consultations", response_model=Consultation)
def create_consultation(request: CreateConsultationRequest) -> Consultation:
    results = _to_diagnose_response(request.symptoms)
    consultation = Consultation(
        id=f"consult-{uuid4().hex[:8]}",
        patient=request.patient,
        symptoms=request.symptoms,
        results=results,
        notes="",
        status="draft",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
    _consultations[consultation.id] = consultation
    logger.info(f"created consultation {consultation.id}")
    return consultation


@router.get("/consultations", response_model=List[ConsultationSummary])
def list_consultations() -> List[ConsultationSummary]:
    return [
        ConsultationSummary(
            id=c.id,
            patient=c.patient,
            summary=c.symptoms[:80] + ("..." if len(c.symptoms) > 80 else ""),
            createdAt=c.createdAt,
            status=c.status,
        )
        # Newest first
        for c in sorted(_consultations.values(), key=lambda x: x.createdAt, reverse=True)
    ]


@router.get("/consultations/{consultation_id}", response_model=Consultation)
def get_consultation(consultation_id: str) -> Consultation:
    consultation = _consultations.get(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


@router.patch("/consultations/{consultation_id}", response_model=Consultation)
def update_consultation(
    consultation_id: str,
    request: UpdateConsultationRequest,
) -> Consultation:
    consultation = _consultations.get(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")

    updates = request.model_dump(exclude_unset=True)
    updated = consultation.model_copy(update=updates)
    _consultations[consultation_id] = updated
    logger.info(f"updated consultation {consultation_id}")
    return updated
