"""
Diagnose service.

Two entry points:

    retrieve_only(symptoms)
        Runs ONLY Role 2's retrieval (ChromaDB + cross-encoder rerank).
        Used by the /diagnosis/retrieve evidence-preview endpoint.
        Never touches the LLM.

    diagnose(symptoms)
        Full retrieve + LLM pipeline. Used by /diagnosis/generate and by
        consultation creation. Reuses retrieve_only() so we never duplicate
        the retrieval path.

Both functions swallow their internal exceptions and return a result object —
the API layer therefore never has to handle a raw retrieval or LLM failure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, List

from app.core.logger import logger
from role3_llm.parser import FALLBACK_RESPONSE
from shared.schemas import DiagnosticResponse


@dataclass
class RetrieveResult:
    retrieved: List[Any]
    retrieval_ms: int


@dataclass
class DiagnoseResult:
    response: DiagnosticResponse
    retrieved: List[Any]
    retrieval_ms: int
    llm_ms: int
    total_ms: int


def retrieve_only(symptoms: str) -> RetrieveResult:
    """Retrieval-only path. No LLM call — safe to use for evidence preview."""
    t = time.perf_counter()
    try:
        from role2_retrieval.retrieval.pipeline import retrieve as role2_retrieve

        retrieved = role2_retrieve(symptoms)
    except Exception as exc:
        logger.error(
            f"Retrieval failed ({type(exc).__name__}: {exc}) — returning empty."
        )
        retrieved = []
    retrieval_ms = int((time.perf_counter() - t) * 1000)
    logger.info(f"retrieve_only chunks={len(retrieved)} retrieval_ms={retrieval_ms}")
    return RetrieveResult(retrieved=retrieved, retrieval_ms=retrieval_ms)


def diagnose(symptoms: str) -> DiagnoseResult:
    """Full pipeline: retrieval then LLM reasoning."""
    t_total = time.perf_counter()

    retrieve_result = retrieve_only(symptoms)
    chunk_texts = [c.text for c in retrieve_result.retrieved]

    t_llm = time.perf_counter()
    if not chunk_texts:
        response = FALLBACK_RESPONSE
    else:
        try:
            from role3_llm.main import run_mediassist_pipeline

            response = run_mediassist_pipeline(symptoms, chunk_texts)
        except Exception as exc:
            logger.error(
                f"LLM pipeline failed ({type(exc).__name__}: {exc}) — returning fallback."
            )
            response = FALLBACK_RESPONSE
    llm_ms = int((time.perf_counter() - t_llm) * 1000)

    total_ms = int((time.perf_counter() - t_total) * 1000)
    logger.info(
        f"diagnose chunks={len(retrieve_result.retrieved)} "
        f"retrieval_ms={retrieve_result.retrieval_ms} "
        f"llm_ms={llm_ms} total_ms={total_ms}"
    )

    return DiagnoseResult(
        response=response,
        retrieved=retrieve_result.retrieved,
        retrieval_ms=retrieve_result.retrieval_ms,
        llm_ms=llm_ms,
        total_ms=total_ms,
    )
