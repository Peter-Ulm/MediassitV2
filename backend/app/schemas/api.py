"""
Public request/response shapes for the backend API.

Frontend (Jesca) calls these. Internally we adapt to/from Role 3's canonical
DiagnosticResponse via app.services.diagnose.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────────────────

class PatientMeta(BaseModel):
    age: int = Field(ge=0, le=120)
    sex: str = Field(description="'male' | 'female' | 'other'")
    vitals: Optional[dict] = None


class DiagnoseRequest(BaseModel):
    symptoms: str = Field(min_length=3)
    patientMeta: PatientMeta


# ── Response ─────────────────────────────────────────────────────────────

class EvidenceItem(BaseModel):
    source: str
    excerpt: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    relevance_score: Optional[float] = None


class Diagnosis(BaseModel):
    name: str
    probability: float  # 0..1 to match frontend mocks
    reasoning: str
    evidenceRefs: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    accepted: Optional[bool] = None


class RecommendedTest(BaseModel):
    test: str
    rationale: str


class DiagnoseResponse(BaseModel):
    diagnoses: List[Diagnosis]
    followUps: List[str]
    recommendedTests: List[RecommendedTest]
    confidence_overall: Optional[str] = None
    pipeline_confidence: Optional[str] = None
    warning: Optional[str] = None
    retrieval_ms: Optional[int] = None
    llm_ms: Optional[int] = None
    total_ms: Optional[int] = None
    request_id: Optional[str] = None
    generated_at: Optional[str] = None
