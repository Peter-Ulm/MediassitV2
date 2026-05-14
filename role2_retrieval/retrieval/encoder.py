"""
retrieval/encoder.py
--------------------
Stage 3.1 — Query Encoding Pipeline

Converts a raw symptom description string into a normalised embedding
vector using the same sentence-transformer model Role 1 used to encode
the STG knowledge base.

KEY RULE: The embedding model here MUST match Role 1's model.
          Mixing models produces garbage similarity scores.
          Default: all-MiniLM-L6-v2
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from role2_retrieval.utils.config import config
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

# Module-level model cache — load once, reuse everywhere
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (loads only once per process)."""
    global _model
    if _model is None:
        log.info(f"Loading embedding model: {config.embedding_model}")
        _model = SentenceTransformer(config.embedding_model)
        log.info("Embedding model loaded.")
    return _model


def preprocess_query(query: str) -> str:
    """
    Light preprocessing for clinical symptom text.

    Rules:
    - Strip leading/trailing whitespace.
    - Collapse multiple spaces into one.
    - Do NOT aggressively lowercase or remove punctuation —
      medical abbreviations like 'SOB', 'BP', 'Hb' carry meaning.
    """
    if not isinstance(query, str):
        raise TypeError(f"Query must be a string, got {type(query)}")
    query = query.strip()
    # Collapse multiple whitespace
    query = " ".join(query.split())
    if len(query) < 3:
        raise ValueError(f"Query too short (< 3 chars): '{query}'")
    return query


def encode_query(query: str) -> np.ndarray:
    """
    Encode a single symptom query into a normalised embedding vector.

    Args:
        query: Raw symptom description from the doctor.

    Returns:
        1-D numpy array of shape (embedding_dim,), L2-normalised.
        Normalisation is required for cosine similarity via dot product.
    """
    query = preprocess_query(query)
    model = _get_model()

    log.info(f"Encoding query: '{query[:80]}{'...' if len(query) > 80 else ''}'")
    # normalize_embeddings=True → vectors are unit length → cosine sim = dot product
    vector = model.encode(query, normalize_embeddings=True, show_progress_bar=False)
    return np.array(vector, dtype=np.float32)


def encode_batch(queries: list[str]) -> np.ndarray:
    """
    Encode multiple queries in one batch (more efficient than a loop).

    Args:
        queries: List of symptom description strings.

    Returns:
        2-D numpy array of shape (len(queries), embedding_dim).
    """
    processed = [preprocess_query(q) for q in queries]
    model = _get_model()
    log.info(f"Batch-encoding {len(processed)} queries.")
    vectors = model.encode(processed, normalize_embeddings=True, show_progress_bar=False)
    return np.array(vectors, dtype=np.float32)


# ── Manual cosine similarity (Stage 3.2) ─────────────────────────────────────
def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    If both vectors are already L2-normalised (which encode_query guarantees),
    this is simply the dot product — O(d) and numerically stable.

    cos(θ) = (A · B) / (||A|| * ||B||)
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def similarity_matrix(query_vecs: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    """
    Compute pairwise cosine similarity between all query and document vectors.

    Args:
        query_vecs: shape (n_queries, dim)
        doc_vecs:   shape (n_docs, dim)

    Returns:
        shape (n_queries, n_docs) — entry [i, j] = cosine_sim(query_i, doc_j)
    """
    # Normalise rows just in case they are not already unit vectors
    q_norm = query_vecs / (np.linalg.norm(query_vecs, axis=1, keepdims=True) + 1e-10)
    d_norm = doc_vecs  / (np.linalg.norm(doc_vecs,   axis=1, keepdims=True) + 1e-10)
    return q_norm @ d_norm.T