# scripts/parse_stg.py
"""
Parse + re-chunk the Tanzania STG PDF into substantive, groundable chunks.

Why this exists: the original ingestion split the STG at its sub-block *headings*
and separated those headings from their body text, leaving a corpus that is 61%
bare titles ("Diagnostic Criteria", "CAUTION"). Retrieval then served titles, the
LLM had nothing to ground on, and the role3 Auditor forced the safe fallback.

Strategy (hybrid — see docs/superpowers/specs/2026-05-30-stg-rechunking-design.md):
  * PyMuPDF (fitz) for clean text (pypdf mangles word boundaries).
  * Skip front matter (TOC etc.) until the first CHAPTER heading at/after a page floor.
  * Chapter-aware: track the current CHAPTER heading; flush a chunk run on chapter change.
  * Sliding window of ~150 words (±30 overlap) over each chapter's running body text —
    sized to fit all-MiniLM-L6-v2's 256-token embedding window once the structural
    "Chapter › Section:" prefix is prepended at build time.
  * Section tags are best-effort metadata only (never a chunk boundary): a chunk inherits
    the section heading active at its first word.

Public API:
    parse_and_chunk(pdf_path, ...) -> list[{"id","text","metadata"}]   # reads the PDF
    chunk_pages(pages, ...)        -> same                              # pure, testable
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

# A chapter heading line: uppercase "CHAPTER" + a number-word/digit token. Case-sensitive
# on CHAPTER so prose like "Chapter summary" does not match; length-capped so a sentence
# that merely mentions a chapter is not mistaken for a heading.
_CHAPTER_RE = re.compile(r"^CHAPTER\s+[A-Z0-9][A-Z0-9\-]*\b")
_MAX_HEADING_LEN = 80

# Known STG sub-block labels → canonical form. Best-effort: only used as metadata.
_KNOWN_SECTIONS = {
    "diagnostic criteria": "Diagnostic Criteria",
    "diagnosis": "Diagnosis",
    "clinical features": "Clinical features",
    "clinical presentation": "Clinical features",
    "signs and symptoms": "Signs and symptoms",
    "investigations": "Investigations",
    "pharmacological treatment": "Pharmacological Treatment",
    "non-pharmacological treatment": "Non-Pharmacological Treatment",
    "non pharmacological treatment": "Non-Pharmacological Treatment",
    "treatment": "Treatment",
    "management": "Management",
    "prevention": "Prevention",
    "referral": "Referral",
    "caution": "CAUTION",
    "note": "NOTE",
}


def extract_pages(pdf_path: str) -> List[Tuple[int, str]]:
    """Return [(page_no (1-based), clean_text)] for every page via PyMuPDF."""
    doc = fitz.open(pdf_path)
    try:
        return [(i + 1, page.get_text("text")) for i, page in enumerate(doc)]
    finally:
        doc.close()


def detect_chapter(line: str) -> Optional[str]:
    """Return the chapter-heading line (stripped) if `line` is one, else None."""
    s = line.strip()
    if not s or len(s) > _MAX_HEADING_LEN:
        return None
    return s if _CHAPTER_RE.match(s) else None


def detect_section(line: str) -> Optional[str]:
    """Return the canonical section label if `line` is a known sub-block heading, else None."""
    s = line.strip().rstrip(":").strip().lower()
    return _KNOWN_SECTIONS.get(s)


def chunk_chapter_text(
    items: List[Tuple[str, int, str]],
    words_per_chunk: int = 150,
    overlap_words: int = 30,
) -> List[Tuple[str, int, int, str]]:
    """
    Sliding-window chunk a chapter's running body.

    `items` is a list of (word, page_no, section) in reading order. Returns
    (text, page_start, page_end, section) where section is the one active at the
    chunk's first word. The final window always reaches the end (no tiny tail chunk).
    """
    n = len(items)
    if n == 0:
        return []
    step = max(1, words_per_chunk - overlap_words)
    out: List[Tuple[str, int, int, str]] = []
    i = 0
    while i < n:
        window = items[i:i + words_per_chunk]
        text = " ".join(w for w, _, _ in window)
        pages = [p for _, p, _ in window]
        section = window[0][2]
        out.append((text, min(pages), max(pages), section))
        if i + words_per_chunk >= n:
            break
        i += step
    return out


def chunk_pages(
    pages: List[Tuple[int, str]],
    words_per_chunk: int = 150,
    overlap_words: int = 30,
    content_start_floor: int = 30,
) -> List[dict]:
    """
    Turn extracted pages into index records. Pure (no I/O) so it is unit-testable.

    Walks pages in order, skipping everything until the first CHAPTER heading at a page
    >= content_start_floor (this drops the cover/TOC/acronyms). Within a chapter, body
    words accumulate (tracking the active section per word) and are flushed into
    sliding-window chunks whenever a new chapter begins.
    """
    records: List[dict] = []
    counter = 0
    current_chapter = ""
    current_section = ""
    started = False
    buf: List[Tuple[str, int, str]] = []

    def flush() -> None:
        nonlocal counter, buf
        if not buf:
            return
        for text, ps, pe, sec in chunk_chapter_text(buf, words_per_chunk, overlap_words):
            counter += 1
            records.append({
                "id": f"stg-{counter:05d}",
                "text": text,
                "metadata": {
                    "chapter": current_chapter,
                    "section": sec,
                    "page_start": ps,
                    "page_end": pe,
                },
            })
        buf = []

    for page_no, page_text in pages:
        for line in page_text.split("\n"):
            chapter = detect_chapter(line)
            if chapter is not None and page_no >= content_start_floor:
                flush()
                current_chapter = chapter
                current_section = ""
                started = True
                continue
            if not started:
                continue  # still in front matter
            section = detect_section(line)
            if section is not None:
                current_section = section
                continue  # heading itself is metadata, not body
            for word in line.split():
                buf.append((word, page_no, current_section))
    flush()
    return records


def parse_and_chunk(
    pdf_path: str,
    words_per_chunk: int = 150,
    overlap_words: int = 30,
    content_start_floor: int = 30,
) -> List[dict]:
    """Read the STG PDF and return index records (see chunk_pages)."""
    pages = extract_pages(pdf_path)
    return chunk_pages(
        pages,
        words_per_chunk=words_per_chunk,
        overlap_words=overlap_words,
        content_start_floor=content_start_floor,
    )
