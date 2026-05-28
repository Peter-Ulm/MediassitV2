# -*- coding: utf-8 -*-
"""
contextualize/context_builder.py
--------------------------------
Builds the situating context prepended to each STG chunk before embedding,
following Anthropic's Contextual Retrieval.

Hybrid strategy:
  * Structural prefix (always, deterministic) from chapter/section metadata.
  * LLM blurb (only for thin/ambiguous chunks) via the role3_llm provider.
"""

from __future__ import annotations

from dataclasses import dataclass

# Separator between chapter and section in the structural prefix.
_SEP = " › "  # " › "  (U+203A single right-pointing angle quotation mark)

# A chunk shorter than this many words is "thin" and benefits from an LLM blurb.
THIN_WORD_THRESHOLD = 12
# Never send chunks longer than this to the LLM: they are not thin, and a long
# prefix would push real content out of MiniLM's 256-token window.
MAX_WORDS_FOR_LLM = 200


def build_structural_prefix(metadata: dict) -> str:
    """'Chapter X › Section: ' from metadata. Empty string if neither present."""
    chapter = (metadata.get("chapter") or "").strip()
    section = (metadata.get("section") or "").strip()
    parts = [p for p in (chapter, section) if p]
    if not parts:
        return ""
    return _SEP.join(parts) + ": "


def is_thin_chunk(text: str, metadata: dict, word_threshold: int = THIN_WORD_THRESHOLD) -> bool:
    """True if the chunk is too short or is just a repeat of its section heading."""
    if len(text.split()) < word_threshold:
        return True
    section = (metadata.get("section") or "").strip().lower()
    return bool(section) and text.strip().lower() == section


def assemble_contextualized_text(prefix: str, blurb: str, chunk_text: str) -> str:
    """Combine prefix + blurb + original chunk. Context goes on its own line."""
    context = (prefix + blurb).strip()
    if not context:
        return chunk_text
    return f"{context}\n\n{chunk_text}"
