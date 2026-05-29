"""
Diagnosis endpoints — the canonical path the frontend uses.

POST /diagnosis/retrieve  : returns the STG chunks Role 2 selected
POST /diagnosis/generate  : full pipeline (retrieve -> LLM -> validated response)
"""

from __future__ import annotations

import time
import uuid
from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.logger import logger
from app.db.models import User
from app.schemas.api import (
    Diagnosis,
    DiagnoseRequest,
    DiagnoseResponse,
    EvidenceItem,
    RecommendedTest,
)
from app.services.diagnose import diagnose, retrieve_only

router = APIRouter()


def _build_recommended_tests(test_strings: List[str]) -> List[RecommendedTest]:
    """Role 3 returns plain strings; frontend wants {test, rationale}."""
    return [
        RecommendedTest(test=t, rationale="Recommended by Tanzania STG")
        for t in test_strings
    ]


@router.post("/diagnosis/retrieve")
def retrieve_documents(request: DiagnoseRequest, current_user: User = Depends(get_current_user)) -> dict:
    """
    Returns the STG chunks Role 2 retrieved for the given symptoms — WITHOUT
    running the LLM. Used by the frontend's evidence-preview panel.

    Cost characteristics: one ChromaDB query + one cross-encoder rerank.
    Typically completes in 100-400 ms. The LLM is never invoked.
    """
    result = retrieve_only(request.symptoms)
    retrieved_docs = [
        {
            "id": c.chunk_id,
            "source": (
                f"Tanzania STG — {c.metadata.get('chapter', 'Unknown chapter')}"
                if c.metadata else "Tanzania STG"
            ),
            "section": c.metadata.get("section") if c.metadata else None,
            "title": c.metadata.get("chapter") if c.metadata else None,
            "excerpt": c.text,
            "score": c.score,
        }
        for c in result.retrieved
    ]
    return {
        "retrievedDocs": retrieved_docs,
        "embeddingsMeta": {
            "model": "all-MiniLM-L6-v2",
            "latency_ms": result.retrieval_ms,
        },
    }


@router.post("/diagnosis/generate", response_model=DiagnoseResponse)
def generate_diagnosis(request: DiagnoseRequest, current_user: User = Depends(get_current_user)) -> DiagnoseResponse:
    """Full retrieve → LLM pipeline. The frontend's primary endpoint."""

    logger.info(
        f"POST /diagnosis/generate symptoms_len={len(request.symptoms)} "
        f"age={request.patientMeta.age} sex={request.patientMeta.sex}"
    )

    result = diagnose(request.symptoms)
    response = result.response

    # Map retrieved chunks to a quick lookup so evidenceRefs can point at IDs
    retrieved_by_excerpt = {c.text: c for c in result.retrieved}

    diagnoses: List[Diagnosis] = []
    for d in response.diagnoses:
        # Find the chunk this evidence quote came from (best-effort)
        match = next(
            (c for excerpt, c in retrieved_by_excerpt.items()
             if d.evidence and d.evidence in excerpt),
            None,
        )
        chapter = (
            (match.metadata.get("chapter") if match and match.metadata else None)
            or d.source_section
        )
        evidence_items = [
            EvidenceItem(
                source=f"Tanzania STG — {chapter}" if chapter else "Tanzania STG",
                excerpt=d.evidence,
                chapter=chapter,
                section=d.source_section,
                relevance_score=match.score if match else None,
            )
        ]
        evidence_refs = [match.chunk_id] if match else []

        diagnoses.append(Diagnosis(
            name=d.condition,
            probability=d.probability / 100.0,
            reasoning=d.reasoning,
            evidenceRefs=evidence_refs,
            evidence=evidence_items,
        ))

    warning = None
    if response.pipeline_confidence == "low":
        warning = (
            "Low pipeline confidence — the LLM output did not meet calibration "
            "thresholds. Treat as advisory only and perform manual clinical "
            "assessment."
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
        request_id=str(uuid.uuid4()),
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
