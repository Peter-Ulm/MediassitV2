# Re-chunk the STG from source — Design

**Date:** 2026-05-30
**Status:** Approved (design), pending implementation plan
**Author:** MediAssist team

## Problem

The retrieval corpus is fragmented. The current contextual index (`mediassist_stg_ctx`)
contains **3,724 chunks with a median length of 2 words**; **61% are ≤3-word bare
titles** ("Diagnostic Criteria", "CAUTION", "Pharmacological Treatment"). The original
ingestion split the STG at its sub-block *headings* and separated those headings from
the body text beneath them.

Consequence: retrieval serves title fragments, the LLM has no clinical content to ground
on, and the role3 **Auditor** correctly forces the safe `FALLBACK_RESPONSE` ("Unable to
generate diagnosis"). This is a *retrieval/chunking* defect, not an LLM defect — the
prompt-hardening and Sanitizer work (on `perf/faster-llm`) cannot fix it because the
chunks themselves carry no groundable text.

**Goal:** Re-chunk the source STG PDF into coherent, substantive chunks so consults
return grounded differentials instead of falling back.

## Source material

- `STG.pdf` — "Tanzania Standard Treatment Guidelines, Sixth Edition 2021", 618 pages,
  **no PDF bookmarks/outline**.
- Front matter: cover, foreword, acknowledgements, **Table of Contents pp.5–28**,
  acronyms (~p.30), "PART I" (~p.35). **Clinical content starts ~p.35.**
- Body is organised by uppercase `CHAPTER <NUMBER>: <TITLE>` headings (reliably
  detectable). Within chapters: conditions, each with sub-blocks like *Diagnostic
  Criteria*, *Clinical features*, *Pharmacological Treatment*, *CAUTION*.

## Parser decision: PyMuPDF (fitz)

Verified empirically: PyMuPDF extracts clean text ("affordable essential medicines at all
times") where `pypdf` mangles word boundaries ("a ffordable"). Clean text is a hard
prerequisite for grounding (the Auditor matches ≥6-char words against the corpus), so
**PyMuPDF is the parser**. `pymupdf` is added to `requirements.txt`.

## Chunking strategy: Hybrid (chapter-aware sliding window + opportunistic section tags)

This was the chosen approach. It is robust (does not depend on fragile section-heading
detection) while still tagging sections where they are cleanly recognisable.

1. **Extract** clean text per page via `fitz`, retaining each page's 1-based number.
2. **Skip front matter:** ignore everything before the first real chapter heading that
   appears *after* the Table of Contents. Detection: the first line matching the chapter
   pattern at a page index ≥ a `content_start_floor` (default page 30) — the TOC lists
   chapter names but is before p.30, so this skips it. Never chunk the cover/TOC/acronyms.
3. **Chapter-aware:** maintain a "current chapter" as we walk pages in order. A line
   matching `^CHAPTER\s+[A-Z0-9]+` (optionally followed by `:` and a title) updates the
   current chapter. Every chunk is tagged with the chapter active at its start.
4. **Sliding window within the running text of each chapter:** accumulate words into
   **~150-word chunks with ~30-word overlap.** *Why 150:* `all-MiniLM-L6-v2` only embeds
   ~256 tokens; the structural prefix (`Chapter › Section:`) plus the chunk must fit, so
   ~150 words is the largest size that embeds without truncation while still carrying real
   clinical content. The **full** chunk text is stored as `raw_text` and fed to the LLM
   for grounding (grounding is not limited by the embedding window).
5. **Opportunistic section tags (hybrid part):** maintain a "current section" updated when
   a line is (case-insensitively) one of a known label set
   (`Diagnostic Criteria`, `Clinical features`, `Signs and symptoms`, `Investigations`,
   `Pharmacological Treatment`, `Non-Pharmacological Treatment`, `Treatment`, `Management`,
   `Prevention`, `Referral`, `CAUTION`, `NOTE`) — or a short ALL-CAPS / Title-Case line
   that looks like a condition heading (heuristic, best-effort). Chunks inherit the section
   active at their start. If none is known, `section` is left empty. We never *depend* on
   this for chunk boundaries — it is metadata only.

**Output of the chunker:** a list of records shaped exactly like the existing build
consumes:

```python
{
  "id": "stg-<NNNN>",            # zero-padded running index
  "text": "<~150 words of clean STG body text>",
  "metadata": {
      "chapter": "CHAPTER NINE: RESPIRATORY DISEASES",  # or "" if unknown
      "section": "Diagnostic Criteria",                  # or "" best-effort
      "page_start": 212,
      "page_end": 213,
  },
}
```

This matches the keys the contextualize+embed loop already reads
(`chapter`, `section`, `page_start`, `page_end`), so it drops straight in.

## Index build: reuse the existing contextual pipeline

`scripts/build_contextual_index.py` already does: read records → `contextualize()` (structural
prefix + LLM blurb *only for thin <12-word chunks*) → re-embed with `all-MiniLM-L6-v2` →
write a fresh collection into a **separate** ChromaDB directory (avoiding the legacy-schema
compactor bug). We reuse this with two changes:

- **Extract its core** `build()` body into `contextualize_and_embed(records, target_collection,
  target_path, use_llm)` so both the legacy-source path and the new PDF path share the
  contextualize+embed+write logic (DRY). `build_contextual_index.py`'s existing entry point
  keeps working unchanged (it just calls the extracted core with legacy-sourced records).
- **New thin wrapper** `scripts/build_stg_index.py`: `parse_and_chunk(pdf_path)` →
  `contextualize_and_embed(records, ...)`.

Because ~150-word chunks are never "thin" (<12 words), **no LLM blurbs fire** — the build
runs structural-prefix-only, fast and fully offline. We will pass `--no-llm` for
determinism regardless.

**A/B, not overwrite:** build into a NEW collection `mediassist_stg_rechunked` at
`vector_store/chroma_rechunked_db`. The current `mediassist_stg_ctx` is left intact for
comparison and rollback. Retrieval is repointed (via `.env` `CHROMA_PATH` /
`CHROMA_COLLECTION`) to the rechunked index **only after** it passes verification.

## Components / files

| File | Responsibility |
|---|---|
| `scripts/parse_stg.py` (new) | PyMuPDF parse → front-matter skip → chapter detect → ~150-word sliding-window chunk (±30 overlap) → opportunistic section tags → list of `{id,text,metadata}` records. Pure functions, unit-testable on synthetic page lists. |
| `scripts/build_contextual_index.py` (modify) | Extract `contextualize_and_embed(records, target_collection, target_path, use_llm)`; legacy entry point unchanged. |
| `scripts/build_stg_index.py` (new) | `parse_and_chunk(pdf_path)` → `contextualize_and_embed(...)` into `mediassist_stg_rechunked` @ `vector_store/chroma_rechunked_db`. CLI: `--pdf`, `--target`, `--target-path`, `--no-llm`. |
| `tests/test_parse_stg.py` (new) | Unit tests for the chunker on synthetic pages. |
| `requirements.txt` (modify) | add `pymupdf`. |
| `.env.example` (modify) | document repointing `CHROMA_PATH`/`CHROMA_COLLECTION` to the rechunked index after verification. |

The PDF lives at a configurable path (`--pdf`, default `data/stg/STG.pdf`). It is copied
into `data/stg/` for the build but **git-ignored** (9 MB binary; not committed unless the
team later decides to bundle it).

## Public interfaces

```python
# scripts/parse_stg.py
def parse_and_chunk(
    pdf_path: str,
    *,
    words_per_chunk: int = 150,
    overlap_words: int = 30,
    content_start_floor: int = 30,
) -> list[dict]:
    """Return [{'id','text','metadata'}] records for the index builder."""

# helpers (each independently testable)
def extract_pages(pdf_path: str) -> list[tuple[int, str]]:        # (page_no, clean_text)
def detect_chapter(line: str) -> str | None                       # chapter heading or None
def detect_section(line: str) -> str | None                       # known section label or None
def chunk_chapter_text(
    words_with_pages: list[tuple[str, int]],                      # (word, page_no)
    *, words_per_chunk: int, overlap_words: int,
) -> list[tuple[str, int, int]]                                   # (text, page_start, page_end)

# scripts/build_contextual_index.py (extracted, reused)
def contextualize_and_embed(
    records: list[dict], target_collection: str, target_path: str, use_llm: bool
) -> None: ...
```

## Verification (the acceptance gates)

1. **Chunk-quality gate** (cheap, runs in the build): assert median chunk ≥ ~120 words and
   **zero chunks ≤ 3 words**; report total count (expect a few thousand).
2. **End-to-end grounding gate** (the real test): run a set of representative consults
   (e.g. *fever 3 days + chills*, *cough + weight loss*, *acute watery diarrhoea*,
   *chest pain*) against the rechunked index and assert each returns a **grounded
   differential**, not `FALLBACK_RESPONSE`. This is the behaviour that is currently broken.
3. **No retrieval regression:** re-run the existing 16-vignette chapter-hit eval
   (`scripts/eval_retrieval.py`) against the rechunked index; chapter hit-rate must not
   drop materially vs the current index.
4. **No test regression:** `tests/` and `backend/tests` still green (run separately — the
   duplicate `test_config.py` basename collides when both trees are collected together).

Swap `.env` to the rechunked index only after gates 1–3 pass.

## Error handling

- **Tables (drug-dose grids):** PyMuPDF linearises table text; structure is lost but the
  words remain, which is what grounding needs. Acceptable.
- **Chapter detection miss:** text stays under the last-known chapter; the sliding window
  does not depend on perfect chapter detection, so chunks are still substantive.
- **Blank/figure-only pages:** skipped (no words contributed).
- **Section detection miss:** `section` left empty — metadata only, never a chunk boundary.

## Out of scope

- LLM/latency changes (separate `perf/faster-llm` branch).
- Perfect table/column reconstruction (linear text suffices for grounding).
- Bundling the PDF into git, and onward contribution (PR to the friend's repo) — handled
  after verification, same as previous features.

## Build order (for the plan)

1. Add `pymupdf`; write `parse_stg.py` helpers + `tests/test_parse_stg.py` (TDD).
2. Extract `contextualize_and_embed(...)` from `build_contextual_index.py` (legacy path
   stays green).
3. Write `scripts/build_stg_index.py` (parse → contextualize+embed → fresh collection).
4. Run on the real PDF; assert the chunk-quality gate.
5. End-to-end grounding gate + retrieval eval; compare against the current index.
6. Repoint `.env` to the rechunked index; document in `.env.example`.
