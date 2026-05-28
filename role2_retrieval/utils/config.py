"""
Role 2 retrieval configuration.

All defaults are tuned to integrate with the canonical knowledge base built
by Role 1 (Athuman): the ChromaDB lives at `vector_store/chroma_db` and the
collection is called `mediassist_stg` with `all-MiniLM-L6-v2` embeddings.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Must match the embedding model used to build the ChromaDB. Knowledge
    # engine (Role 1) uses sentence-transformers/all-MiniLM-L6-v2.
    embedding_model: str = field(
        default_factory=lambda: os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
    )

    # ChromaDB is bundled at vector_store/chroma_db inside the repo. The
    # backend resolves this to an absolute path at startup.
    chroma_path: str = field(
        default_factory=lambda: os.getenv("CHROMA_PATH", "vector_store/chroma_db")
    )
    chroma_collection: str = field(
        default_factory=lambda: os.getenv("CHROMA_COLLECTION", "mediassist_stg")
    )

    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", "5")))
    rerank_top_n: int = field(
        default_factory=lambda: int(os.getenv("RERANK_TOP_N", "3"))
    )

    # Output token budget is bounded by the LLM, not the retriever. We leave
    # this generous because gpt-4o-mini (128k) and llama3.2 (128k) easily
    # accommodate the 5 chunks we typically return.
    max_context_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "6000"))
    )

    cross_encoder_model: str = field(
        default_factory=lambda: os.getenv(
            "CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
    )

    multi_query_count: int = field(
        default_factory=lambda: int(os.getenv("MULTI_QUERY_COUNT", "3"))
    )
    use_synonym_expansion: bool = field(
        default_factory=lambda: os.getenv("USE_SYNONYM_EXPANSION", "true").lower() == "true"
    )
    # Default multi-query OFF: it requires extra LLM calls per request which
    # multiplies latency on Ollama hardware. Turn on for accuracy benchmarks.
    use_multi_query: bool = field(
        default_factory=lambda: os.getenv("USE_MULTI_QUERY", "false").lower() == "true"
    )
    use_reranking: bool = field(
        default_factory=lambda: os.getenv("USE_RERANKING", "true").lower() == "true"
    )

    # Contextual BM25: fuse dense + sparse (BM25 over contextualized text) via
    # RRF before reranking. Off by default until the contextual index is built.
    use_hybrid: bool = field(
        default_factory=lambda: os.getenv("USE_HYBRID", "false").lower() == "true"
    )

    def validate(self) -> None:
        if self.top_k < 1:
            raise ValueError("TOP_K must be at least 1.")
        if self.rerank_top_n > self.top_k:
            raise ValueError("RERANK_TOP_N cannot exceed TOP_K.")


config = Config()
