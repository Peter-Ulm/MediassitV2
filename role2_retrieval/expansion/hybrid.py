"""
expansion/hybrid.py
-------------------
Stage 4.4 — Hybrid Dense + Sparse (BM25) Search

Combines vector similarity (dense) with keyword matching (BM25/sparse)
using Reciprocal Rank Fusion (RRF) to produce a single merged ranking.

Best for queries containing:
- Specific drug names ("artesunate", "amoxicillin")
- Medical codes or exact condition names
- Terms that appear verbatim in the STG

Usage (after dense retrieval is working):
    from expansion.hybrid import HybridSearcher
    searcher = HybridSearcher(all_chunk_texts)
    hybrid_results = searcher.search(query, dense_chunks, top_n=5)
"""

from __future__ import annotations
from dataclasses import dataclass

# NOTE: rank_bm25 is imported lazily inside HybridSearcher.__init__ (not here),
# so importing this module — which the pipeline does unconditionally — never
# requires rank_bm25. It is only needed when hybrid retrieval (USE_HYBRID=true)
# actually instantiates a HybridSearcher.

from role2_retrieval.retrieval.searcher import RetrievedChunk
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

# RRF constant — 60 is the standard value from the original RRF paper
_RRF_K = 60


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenization for BM25."""
    return text.lower().split()


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],  # lists of chunk_ids in rank order
    k: int = _RRF_K,
) -> dict[str, float]:
    """
    Reciprocal Rank Fusion: combine multiple ranked lists into one score.

    RRF score for doc d = Σ_r  1 / (k + rank_r(d))

    Args:
        ranked_lists: Each inner list is a list of chunk_ids ordered best→worst.
        k:            Smoothing constant (default 60).

    Returns:
        Dict mapping chunk_id → combined RRF score (higher = better).
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


class HybridSearcher:
    """
    Wraps BM25 sparse retrieval and combines it with dense results via RRF.

    Instantiation requires all the chunk texts from ChromaDB so we can
    build the BM25 index. This should be done ONCE and reused.

    Args:
        chunk_texts:    List of all STG chunk texts (in the same order as chunk_ids).
        chunk_ids:      Corresponding chunk IDs.
        chunk_metadata: Corresponding metadata dicts.
    """

    def __init__(
        self,
        chunk_texts: list[str],
        chunk_ids: list[str],
        chunk_metadata: list[dict] | None = None,
    ) -> None:
        self._chunk_texts    = chunk_texts
        self._chunk_ids      = chunk_ids
        self._chunk_metadata = chunk_metadata or [{} for _ in chunk_texts]

        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:  # fail loudly, not silently-empty
            raise ImportError(
                "Hybrid retrieval (USE_HYBRID=true) needs the 'rank_bm25' package. "
                "Install it with:  pip install rank_bm25   "
                "(or rerun: pip install -r requirements.txt). "
                "To run without hybrid, set USE_HYBRID=false."
            ) from exc

        log.info(f"Building BM25 index over {len(chunk_texts)} chunks...")
        tokenized = [_tokenize(t) for t in chunk_texts]
        self._bm25 = BM25Okapi(tokenized)
        log.info("BM25 index built.")

    def sparse_search(self, query: str, k: int = 10) -> list[RetrievedChunk]:
        """Return top-k chunks by BM25 keyword score."""
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        # Get indices sorted by descending score
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for idx in top_indices:
            md = self._chunk_metadata[idx]
            results.append(RetrievedChunk(
                chunk_id=self._chunk_ids[idx],
                text=md.get("raw_text") or self._chunk_texts[idx],
                score=float(scores[idx]),
                metadata=md,
            ))
        return results

    def hybrid_search(
        self,
        query: str,
        dense_chunks: list[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        """
        Combine dense (vector) and sparse (BM25) results via RRF.

        Args:
            query:        Original clinical query.
            dense_chunks: Results from dense vector search (already ranked).
            top_n:        How many final results to return.

        Returns:
            Re-ranked list of RetrievedChunk using combined RRF scores.
        """
        sparse_chunks = self.sparse_search(query, k=len(dense_chunks) * 2)

        dense_ranked  = [c.chunk_id for c in dense_chunks]
        sparse_ranked = [c.chunk_id for c in sparse_chunks]

        rrf_scores = reciprocal_rank_fusion([dense_ranked, sparse_ranked])

        # Build a lookup of chunk_id → RetrievedChunk from both result sets
        chunk_lookup: dict[str, RetrievedChunk] = {}
        for c in dense_chunks + sparse_chunks:
            if c.chunk_id not in chunk_lookup:
                chunk_lookup[c.chunk_id] = c

        # Sort by RRF score and return top_n
        sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:top_n]

        results = []
        for cid in sorted_ids:
            if cid in chunk_lookup:
                chunk = chunk_lookup[cid]
                # Replace score with normalised RRF score
                results.append(RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    score=rrf_scores[cid],
                    metadata=chunk.metadata,
                ))
        log.info(f"Hybrid search returned {len(results)} chunks (RRF fusion).")
        return results