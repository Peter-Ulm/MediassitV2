# STG Re-chunking Implementation Plan

> Executed inline (no subagents) to conserve usage. Spec:
> `docs/superpowers/specs/2026-05-30-stg-rechunking-design.md`.

**Goal:** Re-chunk the source STG PDF into ~150-word substantive chunks and rebuild the
contextual index as a new collection, so consults ground instead of falling back.

**Architecture:** PyMuPDF extract → chapter-aware sliding-window chunker (`scripts/parse_stg.py`)
→ reuse the extracted `contextualize_and_embed()` from `build_contextual_index.py`
→ fresh collection `mediassist_stg_rechunked` @ `vector_store/chroma_rechunked_db`.

**Tech:** PyMuPDF (fitz), sentence-transformers (all-MiniLM-L6-v2), ChromaDB 1.5.8, pytest.

---

### Task 1: Add dependency
- [ ] Add `pymupdf` to `requirements.txt`. Verify `python -c "import fitz; print(fitz.__doc__)"`.

### Task 2: `scripts/parse_stg.py` (TDD on pure functions)
**Files:** Create `scripts/parse_stg.py`; Test `tests/test_parse_stg.py`.

Functions:
- `detect_chapter(line) -> str|None` — `^\s*CHAPTER\s+[A-Z0-9]+` (case-insensitive on the
  word CHAPTER but heading is uppercase); returns the stripped heading line or None.
- `detect_section(line) -> str|None` — exact case-insensitive match against KNOWN_SECTIONS
  set (Diagnostic Criteria, Clinical features, Signs and symptoms, Investigations,
  Pharmacological Treatment, Non-Pharmacological Treatment, Treatment, Management,
  Prevention, Referral, CAUTION, NOTE). Returns canonical label or None.
- `chunk_chapter_text(words_with_pages, words_per_chunk=150, overlap_words=30)
  -> list[(text, page_start, page_end)]` — slide a window; step = words_per_chunk-overlap.
- `parse_and_chunk(pdf_path, words_per_chunk=150, overlap_words=30, content_start_floor=30)
  -> list[dict]` — extract pages (fitz), skip until first chapter at page>=floor, walk
  lines tracking current chapter/section, accumulate (word,page) tuples per (chapter,section)
  run, flush to chunks, build records `{id, text, metadata{chapter,section,page_start,page_end}}`.
- `extract_pages(pdf_path) -> list[(page_no:int, text:str)]` via fitz.

Tests (synthetic, no real PDF):
- detect_chapter matches "CHAPTER NINE: RESPIRATORY DISEASES", rejects "Chapter summary".
- detect_section matches "Diagnostic Criteria"/"CAUTION", rejects "Random line".
- chunk_chapter_text: 320 words @150/30 → 3 chunks, overlap present, page spans correct.
- chunk_chapter_text: <150 words → 1 chunk.

Verify: `python -m pytest tests/test_parse_stg.py -v` → PASS.

### Task 3: Extract `contextualize_and_embed()` in `build_contextual_index.py`
**Files:** Modify `scripts/build_contextual_index.py`.
- Pull the contextualize-loop + embed + write-collection body of `build()` into
  `contextualize_and_embed(records, target_collection, target_path, use_llm)` where
  `records=[{id,text,metadata}]`. `build()` now: read legacy source → records → call it.
- Verify legacy path still imports/parses: `python -c "import scripts.build_contextual_index"`.

### Task 4: `scripts/build_stg_index.py`
**Files:** Create `scripts/build_stg_index.py`.
- CLI args: `--pdf data/stg/STG.pdf`, `--target mediassist_stg_rechunked`,
  `--target-path vector_store/chroma_rechunked_db`, `--no-llm` (default on).
- `records = parse_and_chunk(pdf)` → print chunk-quality report (count, median words,
  count of <=3-word chunks; assert zero <=3-word) → `contextualize_and_embed(records, ...)`.

### Task 5: Build on the real PDF + chunk-quality gate
- Copy `C:\Users\USER\Desktop\STG.pdf` → `data/stg/STG.pdf` (gitignored).
- Run `python -m scripts.build_stg_index --no-llm`. Confirm: zero <=3-word chunks,
  median >=120 words, ~few-thousand chunks.

### Task 6: Grounding gate + retrieval eval
- Point a temporary consult at the new collection; run ~4 representative symptom strings;
  assert each returns a grounded differential (not FALLBACK_RESPONSE).
- Run `python -m scripts.eval_retrieval` against the new collection; compare chapter hit-rate.

### Task 7: Repoint + document
- Update `.env` (CHROMA_PATH/CHROMA_COLLECTION → rechunked) and document in `.env.example`.
- Add `data/stg/` to `.gitignore`.

### Finish
- Tests green (`tests/` and `backend/tests` run separately). Commit per task.
- Use finishing-a-development-branch to wrap up.
