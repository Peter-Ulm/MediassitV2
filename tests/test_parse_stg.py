"""Unit tests for the STG re-chunker (scripts/parse_stg.py).

All synthetic — no real PDF — so they run fast and pin the chunking behaviour
that fixes the bare-title fragmentation.
"""

from scripts.parse_stg import (
    chunk_chapter_text,
    chunk_pages,
    detect_chapter,
    detect_section,
)


def test_detect_chapter_matches_real_headings():
    assert detect_chapter("CHAPTER NINE: RESPIRATORY DISEASES") == "CHAPTER NINE: RESPIRATORY DISEASES"
    assert detect_chapter("CHAPTER 12 SOMETHING") == "CHAPTER 12 SOMETHING"


def test_detect_chapter_rejects_prose_and_sections():
    assert detect_chapter("Chapter summary follows below") is None  # lowercase 'hapter'
    assert detect_chapter("Diagnostic Criteria") is None
    assert detect_chapter("This CHAPTER NINE reference appears mid-sentence in a long line of prose text") is None  # too long


def test_detect_section_canonicalises_known_labels():
    assert detect_section("Diagnostic Criteria") == "Diagnostic Criteria"
    assert detect_section("pharmacological treatment:") == "Pharmacological Treatment"
    assert detect_section("CAUTION") == "CAUTION"
    assert detect_section("A random clinical sentence") is None


def test_chunk_chapter_text_windows_with_overlap():
    # 320 words across pages, all in one section.
    items = [(f"w{i}", 100 + i // 100, "Treatment") for i in range(320)]
    chunks = chunk_chapter_text(items, words_per_chunk=150, overlap_words=30)
    assert len(chunks) == 3  # 0-150, 120-270, 240-320
    first_words = chunks[0][0].split()
    second_words = chunks[1][0].split()
    assert len(first_words) == 150
    # step = 120, so chunk 2 starts at w120 and overlaps chunk 1's tail (w120..w149).
    assert second_words[0] == "w120"
    assert "w120" in first_words
    assert chunks[0][3] == "Treatment"  # section carried through


def test_chunk_chapter_text_short_run_is_single_chunk():
    items = [(f"w{i}", 5, "Diagnosis") for i in range(50)]
    chunks = chunk_chapter_text(items, words_per_chunk=150, overlap_words=30)
    assert len(chunks) == 1
    assert chunks[0][1] == 5 and chunks[0][2] == 5  # page span


def test_chunk_pages_skips_front_matter_and_tags_metadata():
    body = " ".join(f"clinical{i}" for i in range(200))
    treat = " ".join(f"drug{i}" for i in range(80))
    pages = [
        # Front matter before the floor: a stray CHAPTER line + body must be ignored.
        (5, "CHAPTER TWO ............ 12\nTable of contents body text ignored"),
        (35, f"CHAPTER ONE: GENERAL\nDiagnostic Criteria\n{body}\nTreatment\n{treat}"),
    ]
    records = chunk_pages(pages, words_per_chunk=150, overlap_words=30, content_start_floor=30)

    assert records, "expected chunks from the content page"
    # Nothing from the TOC page (page 5) leaked in.
    assert all("Table of contents" not in r["text"] for r in records)
    # Chapter detected from the in-content heading.
    assert all(r["metadata"]["chapter"] == "CHAPTER ONE: GENERAL" for r in records)
    # Section metadata is best-effort tagged.
    sections = {r["metadata"]["section"] for r in records}
    assert "Diagnostic Criteria" in sections
    # No bare-title fragments: every chunk has real content.
    assert all(len(r["text"].split()) > 3 for r in records)
    # ids are stable + zero-padded.
    assert records[0]["id"] == "stg-00001"


def test_chunk_pages_without_any_chapter_yields_nothing():
    # Defensive: if no chapter is ever detected, no body is emitted (caught by the
    # build-time chunk-quality gate rather than silently indexing front matter).
    pages = [(35, "just some prose with no heading at all\nmore prose")]
    assert chunk_pages(pages, content_start_floor=30) == []
