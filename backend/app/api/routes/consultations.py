"""
Consultation routes — DB-backed CRUD.

The frontend treats a "consultation" as the persistent record of a doctor's
diagnostic session: patient meta + symptoms + the produced DiagnosisResult +
free-text notes. Records are stored in SQLite via SQLAlchemy.

Difference vs the prototype: create_consultation now runs the REAL diagnose
service (Role 2 retrieval + Role 3 LLM), so consultations contain real
ChromaDB-grounded diagnoses instead of a hand-written stub.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes.diagnosis import _build_recommended_tests
from app.core.logger import logger
from app.db.base import get_db
from app.db.models import Consultation as ConsultationRow
from app.schemas.api import (
    Diagnosis,
    DiagnoseResponse,
    EvidenceItem,
    PatientMeta,
    RecommendedTest,
)
from app.services.diagnose import diagnose

router = APIRouter()

_PLACEHOLDER_OWNER = "unassigned"  # replaced by the real user in Task 6


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


def _to_api(row: ConsultationRow) -> Consultation:
    return Consultation(
        id=row.id, patient=row.patient, symptoms=row.symptoms,
        results=row.results, notes=row.notes, status=row.status,
        createdAt=row.created_at.isoformat(),
    )


@router.post("/consultations", response_model=Consultation)
def create_consultation(request: CreateConsultationRequest, db: Session = Depends(get_db)) -> Consultation:
    results = _to_diagnose_response(request.symptoms)
    row = ConsultationRow(
        id=f"consult-{uuid4().hex[:8]}",
        owner_user_id=_PLACEHOLDER_OWNER,
        patient=request.patient.model_dump(),
        symptoms=request.symptoms,
        results=results.model_dump(),
        notes="",
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"created consultation {row.id}")
    return _to_api(row)


@router.get("/consultations", response_model=List[ConsultationSummary])
def list_consultations(db: Session = Depends(get_db)) -> List[ConsultationSummary]:
    rows = db.query(ConsultationRow).order_by(ConsultationRow.created_at.desc()).all()
    return [
        ConsultationSummary(
            id=r.id, patient=r.patient,
            summary=r.symptoms[:80] + ("..." if len(r.symptoms) > 80 else ""),
            createdAt=r.created_at.isoformat(), status=r.status,
        )
        for r in rows
    ]


@router.get("/consultations/{consultation_id}", response_model=Consultation)
def get_consultation(consultation_id: str, db: Session = Depends(get_db)) -> Consultation:
    row = db.get(ConsultationRow, consultation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return _to_api(row)


@router.patch("/consultations/{consultation_id}", response_model=Consultation)
def update_consultation(consultation_id: str, request: UpdateConsultationRequest,
                        db: Session = Depends(get_db)) -> Consultation:
    row = db.get(ConsultationRow, consultation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    updates = request.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    logger.info(f"updated consultation {consultation_id}")
    return _to_api(row)
