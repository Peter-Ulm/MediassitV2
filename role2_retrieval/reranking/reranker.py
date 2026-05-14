"""
reranking/reranker.py
---------------------
Stage 6.1 — Cross-Encoder Re-ranking

Two-stage retrieval architecture:
  Stage 1 (bi-encoder, fast):   all-MiniLM-L6-v2 — encodes query & docs
                                  independently → cosine similarity → top-k
  Stage 2 (cross-encoder, accurate): ms-marco-MiniLM-L-6-v2 — processes
                                  (query, doc) TOGETHER → more accurate scores
                                  but only runs on the small top-k candidate set.

Why cross-encoders are more accurate:
    Bi-encoders cannot attend between query and document tokens.
    Cross-encoders feed both through the same transformer, allowing
    full cross-attention → much richer relevance signal.

Why we don't use cross-encoders for the full database:
    The STG may have thousands of chunks. Running a cross-encoder
    on every one per query would take minutes — unacceptable for a
    clinical tool. So we only re-rank the top-k from Stage 1.
"""

from __future__ import annotations

from sentence_transformers import CrossEncoder

from role2_retrieval.retrieval.searcher import RetrievedChunk
from role2_retrieval.utils.config import config
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

_cross_encoder: CrossEncoder | None = None


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        log.info(f"Loading cross-encoder: {config.cross_encoder_model}")
        _cross_encoder = CrossEncoder(config.cross_encoder_model)
        log.info("Cross-encoder loaded.")
    return _cross_encoder


class Reranker:
    """
    Wraps a sentence-transformers CrossEncoder to re-rank retrieved chunks.

    Usage:
        reranker = Reranker()
        reranked = reranker.rerank(query, chunks, top_n=3)
    """

    def __init__(self) -> None:
        self._model = _get_cross_encoder()

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Score (query, chunk_text) pairs with the cross-encoder and re-sort.

        Args:
            query:   The original clinical query (NOT the expanded version —
                     cross-encoders work best with the natural phrasing).
            chunks:  Candidate chunks from the bi-encoder retrieval stage.
            top_n:   How many top-ranked chunks to return. Defaults to
                     config.rerank_top_n. If None, returns all re-ranked.

        Returns:
            Re-ordered list of RetrievedChunk with updated scores,
            best first, limited to top_n.
        """
        if not chunks:
            return []

        top_n = top_n or config.rerank_top_n

        # Build (query, document_text) pairs for the cross-encoder
        pairs = [(query, chunk.text) for chunk in chunks]

        log.info(
            f"Re-ranking {len(pairs)} candidate chunks with cross-encoder..."
        )
        scores = self._model.predict(pairs, show_progress_bar=False)

        # Attach cross-encoder scores to chunks and sort
        scored_chunks = sorted(
            zip(chunks, scores),
            key=lambda t: t[1],
            reverse=True,
        )

        results = []
        for chunk, score in scored_chunks[:top_n]:
            results.append(RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                score=float(score),        # replace bi-encoder score with CE score
                metadata=chunk.metadata,
            ))

        log.info(
            f"Re-ranking done. Top chunk score: {results[0].score:.4f}"
            if results else "No chunks after re-ranking."
        )
        return results