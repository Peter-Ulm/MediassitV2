"""
retrieval/searcher.py
---------------------
Stage 3.3 — Querying ChromaDB and Top-k Retrieval

Wraps Role 1's ChromaDB collection and exposes a clean search interface.
All metadata filtering is coordinated with Athuman (Role 1) based on the
agreed metadata schema.

Expected metadata fields (confirm with Role 1):
    - 'section'    : STG chapter/section name
    - 'disease'    : primary disease category
    - 'page'       : source page number (optional)
"""

from __future__ import annotations

from dataclasses import dataclass

import chromadb
import numpy as np

from role2_retrieval.utils.chroma_compat import ensure_chroma_compatibility
from role2_retrieval.utils.config import config
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """A single chunk returned from the vector database."""
    chunk_id: str
    text: str
    score: float          # cosine similarity (higher = more relevant)
    metadata: dict

    def __repr__(self) -> str:
        return (
            f"RetrievedChunk(id={self.chunk_id!r}, "
            f"score={self.score:.4f}, "
            f"text='{self.text[:60]}...')"
        )


class STGSearcher:
    """
    Wraps ChromaDB to provide STG chunk retrieval.

    Usage:
        searcher = STGSearcher()
        chunks = searcher.search(query_vector, k=5)
    """

    def __init__(self) -> None:
        log.info(f"Connecting to ChromaDB at: {config.chroma_path}")
        ensure_chroma_compatibility(config.chroma_path, config.chroma_collection)
        self._client = chromadb.PersistentClient(path=config.chroma_path)
        self._collection = self._client.get_collection(config.chroma_collection)
        doc_count = self._collection.count()
        log.info(
            f"Connected to collection '{config.chroma_collection}' "
            f"({doc_count} chunks indexed)."
        )

    def search(
        self,
        query_vector: np.ndarray,
        k: int | None = None,
        where: dict | None = None,
    ) -> list[RetrievedChunk]:
        """
        Retrieve the top-k most similar STG chunks for a query vector.

        Args:
            query_vector: Normalised 1-D embedding from encoder.encode_query().
            k:            Number of results to return. Defaults to config.top_k.
            where:        Optional ChromaDB metadata filter, e.g.
                          {"disease": "malaria"}.
                          Coordinate with Role 1 for available fields.

        Returns:
            List of RetrievedChunk sorted by descending similarity score.
        """
        k = k or config.top_k

        query_kwargs: dict = {
            "query_embeddings": [query_vector.tolist()],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        log.info(f"Searching Chroma for top-{k} chunks.")
        results = self._collection.query(**query_kwargs)

        chunks: list[RetrievedChunk] = []
        for idx in range(len(results["ids"][0])):
            chunk_id = results["ids"][0][idx]
            text     = results["documents"][0][idx]
            # Chroma returns L2 distance; convert to similarity score.
            # For normalised vectors: cosine_sim = 1 - (L2_dist² / 2)
            distance = results["distances"][0][idx]
            score    = 1.0 - (distance / 2.0)
            metadata = results["metadatas"][0][idx] if results["metadatas"] else {}

            chunks.append(RetrievedChunk(
                chunk_id=chunk_id,
                text=text,
                score=score,
                metadata=metadata,
            ))

        log.info(
            f"Retrieved {len(chunks)} chunks. "
            f"Top score: {chunks[0].score:.4f}" if chunks else "No chunks found."
        )
        return chunks

    def search_many(
        self,
        query_vectors: list[np.ndarray],
        k: int | None = None,
    ) -> list[list[RetrievedChunk]]:
        """
        Search with multiple query vectors (for multi-query expansion).
        Returns one list of chunks per query vector.
        """
        return [self.search(vec, k=k) for vec in query_vectors]

    @staticmethod
    def deduplicate(
        chunk_lists: list[list[RetrievedChunk]],
    ) -> list[RetrievedChunk]:
        """
        Merge and deduplicate results from multiple searches.
        When the same chunk appears more than once, keep the highest score.

        Used by multi-query retrieval (Stage 4.3).
        """
        seen: dict[str, RetrievedChunk] = {}
        for chunks in chunk_lists:
            for chunk in chunks:
                if chunk.chunk_id not in seen or chunk.score > seen[chunk.chunk_id].score:
                    seen[chunk.chunk_id] = chunk
        # Sort by descending score
        return sorted(seen.values(), key=lambda c: c.score, reverse=True)
