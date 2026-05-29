"""Contextual retrieval: prepend situating context to chunks before embedding."""

from role2_retrieval.contextualize.context_builder import (
    ContextResult,
    contextualize,
    select_neighbors,
    build_structural_prefix,
)

__all__ = ["ContextResult", "contextualize", "select_neighbors", "build_structural_prefix"]
