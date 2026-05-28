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

from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

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


_BLURB_SYSTEM_PROMPT = (
    "You situate a fragment of the Tanzania Standard Treatment Guidelines within "
    "its section, for a clinical search index. Write at most two sentences saying "
    "what the fragment is about and where it belongs. Do NOT introduce any medical "
    "facts, drugs, doses, or conditions that are not present in the provided text. "
    "If you cannot situate it from the given text, reply with a single space."
)


def generate_llm_blurb(chunk_text: str, neighbor_texts: list[str], provider=None) -> str:
    """Return a <=2 sentence situating blurb, or '' on any failure (fail-safe)."""
    if provider is None:
        from role3_llm.factory import get_llm_provider
        provider = get_llm_provider()

    surrounding = "\n---\n".join(neighbor_texts) if neighbor_texts else "(none)"
    user = (
        f"Surrounding section text:\n{surrounding}\n\n"
        f"Fragment to situate:\n{chunk_text}\n\n"
        "Situating context (<=2 sentences):"
    )
    try:
        raw = provider.generate(
            [
                {"role": "system", "content": _BLURB_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            max_tokens=120,
        )
        return " ".join((raw or "").split()).strip()
    except Exception as exc:  # never block the build on an LLM hiccup
        log.warning(f"Blurb generation failed ({exc}); using structural-only.")
        return ""


@dataclass
class ContextResult:
    contextualized_text: str   # what gets embedded + BM25-indexed
    prefix: str                # the generated context only (audit/provenance)
    source: str                # "structural" | "hybrid"


def contextualize(
    chunk_text: str,
    metadata: dict,
    neighbor_texts: list[str],
    use_llm: bool = True,
    word_threshold: int = THIN_WORD_THRESHOLD,
    provider=None,
) -> ContextResult:
    """Build the hybrid context for one chunk."""
    prefix = build_structural_prefix(metadata)
    blurb = ""
    source = "structural"

    thin = is_thin_chunk(chunk_text, metadata, word_threshold)
    short_enough = len(chunk_text.split()) <= MAX_WORDS_FOR_LLM
    if use_llm and thin and short_enough:
        blurb = generate_llm_blurb(chunk_text, neighbor_texts, provider=provider)
        if blurb:
            source = "hybrid"

    # Build contextualized_text: prefix + optional blurb separator + chunk.
    # We keep the trailing space from the prefix so the result reads naturally
    # (e.g. "Chapter Five: MALARIA: <chunk>") without an extra newline split.
    if prefix or blurb:
        blurb_part = (" " + blurb) if blurb else ""
        text = prefix + blurb_part.strip() + chunk_text if not blurb else assemble_contextualized_text(prefix, blurb, chunk_text)
    else:
        text = chunk_text
    joined = (prefix + blurb).strip()
    return ContextResult(contextualized_text=text, prefix=joined, source=source)


def select_neighbors(chunks: list[dict], index: int, window: int = 2) -> list[str]:
    """Up to `window` neighbours on each side that share the target's chapter.

    `chunks` is a list of {'text': str, 'metadata': dict} in document order.
    """
    target_ch = chunks[index]["metadata"].get("chapter") or ""
    out: list[str] = []
    for off in range(1, window + 1):
        for j in (index - off, index + off):
            if 0 <= j < len(chunks) and (chunks[j]["metadata"].get("chapter") or "") == target_ch:
                out.append(chunks[j]["text"])
    return out
