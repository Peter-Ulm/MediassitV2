"""
retrieval/pipeline.py
---------------------
Full retrieval pipeline:
    raw query
       → synonym expansion
       → multi-query generation
       → encode all queries
       → search ChromaDB (per query)
       → deduplicate & merge
       → cross-encoder re-ranking
       → context-window-aware chunk selection
       → return final chunks

This is the single entry point that Role 3 calls.
"""

from __future__ import annotations

from role2_retrieval.retrieval.encoder import encode_query, encode_batch
from role2_retrieval.retrieval.searcher import STGSearcher, RetrievedChunk
from role2_retrieval.expansion.synonyms import expand_with_synonyms
from role2_retrieval.expansion.multi_query import generate_query_variants
from role2_retrieval.reranking.reranker import Reranker
from role2_retrieval.utils.config import config
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

# Module-level singletons (initialised on first call)
_searchers: dict[tuple[str, str], STGSearcher] = {}
_reranker: Reranker | None = None


def _get_searcher(collection: str | None = None, path: str | None = None) -> STGSearcher:
    name = collection or config.chroma_collection
    p = path or config.chroma_path
    key = (p, name)
    if key not in _searchers:
        _searchers[key] = STGSearcher(collection=name, path=p)
    return _searchers[key]


def _get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def retrieve(
    query: str,
    k: int | None = None,
    use_expansion: bool | None = None,
    use_multi_query: bool | None = None,
    use_reranking: bool | None = None,
    rerank_top_n: int | None = None,
    collection: str | None = None,
    path: str | None = None,
) -> list[RetrievedChunk]:
    """
    Full retrieval pipeline for a single clinical symptom query.

    Args:
        query:           Raw symptom description from the doctor/UI.
        k:               How many candidates to retrieve initially.
        use_expansion:   Override config.use_synonym_expansion.
        use_multi_query: Override config.use_multi_query.
        use_reranking:   Override config.use_reranking.
        rerank_top_n:    How many chunks to keep after re-ranking.

    Returns:
        Ordered list of the best RetrievedChunk objects, ready for the
        prompt builder (prompts/builder.py).
    """
    k               = k or config.top_k
    use_expansion   = use_expansion   if use_expansion   is not None else config.use_synonym_expansion
    use_multi_query = use_multi_query if use_multi_query is not None else config.use_multi_query
    use_reranking   = use_reranking   if use_reranking   is not None else config.use_reranking
    rerank_top_n    = rerank_top_n    or config.rerank_top_n
    coll = collection or config.chroma_collection
    p = path or config.chroma_path

    log.info(f"[Pipeline] Query: '{query[:80]}'")

    # ── Step 1: Synonym expansion ─────────────────────────────────────────
    expanded_query = query
    if use_expansion:
        expanded_query = expand_with_synonyms(query)
        log.info(f"[Pipeline] Expanded query: '{expanded_query[:100]}'")

    # ── Step 2: Multi-query generation ───────────────────────────────────
    all_queries = [expanded_query]
    if use_multi_query:
        variants = generate_query_variants(expanded_query, n=config.multi_query_count)
        all_queries = [expanded_query] + variants
        log.info(f"[Pipeline] Generated {len(variants)} query variants.")

    # ── Step 3: Encode all queries ────────────────────────────────────────
    query_vectors = encode_batch(all_queries)

    # ── Step 4: Search ChromaDB with each query vector ────────────────────
    searcher = _get_searcher(coll, p)
    chunk_lists = searcher.search_many(
        [query_vectors[i] for i in range(len(all_queries))],
        k=k,
    )

    # ── Step 5: Deduplicate and merge ─────────────────────────────────────
    merged_chunks = STGSearcher.deduplicate(chunk_lists)
    log.info(f"[Pipeline] {len(merged_chunks)} unique chunks after deduplication.")

    # ── Step 6: Cross-encoder re-ranking ─────────────────────────────────
    if use_reranking and merged_chunks:
        reranker = _get_reranker()
        # Use the original (unexpanded) query for re-ranking — cross-encoder
        # handles semantic matching directly, so we don't want to confuse it
        # with expanded text.
        merged_chunks = reranker.rerank(query, merged_chunks, top_n=rerank_top_n)
        log.info(f"[Pipeline] {len(merged_chunks)} chunks after re-ranking.")

    return merged_chunks