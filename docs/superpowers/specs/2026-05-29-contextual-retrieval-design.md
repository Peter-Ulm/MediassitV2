# Contextual Retrieval for MediAssist — Design

**Date:** 2026-05-29
**Status:** Approved (design); pending implementation plan
**Owner:** Role 2 (Retrieval)

## Problem

MediAssist retrieves Tanzania STG evidence with a dense bi-encoder
(`all-MiniLM-L6-v2`) + cross-encoder reranker. The chunks in ChromaDB were
embedded as **context-free fragments**. Examples pulled from the live
`mediassist_stg` collection:

- `"Diagnostic Criteria"` (an entire chunk — just a heading)
- `"This chapter deals with symptoms..."`
- `"If there is fever give A: Cotrimoxazole (PO) 18 mg/kg 12 hourly for 5 days
  to treat possible secondary pneumonia"`

Because each fragment was embedded with no knowledge of where it sits in the
document, keyword-shaped matches surface even when clinically wrong. Observed
failure: for *"Fever for 3 days with chills, headache, reduced appetite,
**no cough, no chest pain, no shortness of breath**"*, the system ranked
**Pneumonia #1 (67%)** and cited the pneumonia *treatment* line as evidence —
despite the patient having no respiratory signs.

## Goal

Adopt **Anthropic's Contextual Retrieval** (Sept 2024): prepend a short
situating context to each chunk **before** embedding and BM25 indexing, so each
chunk's vector and keyword profile reflect *what it is and where it belongs*.
Target the full recipe — **Contextual Embeddings + Contextual BM25 +
reranking** (reranking already exists).

## Non-goals (documented fast-follows)

- **Negation handling** ("no cough"). Embeddings cannot represent negation;
  this belongs in the `role3_llm` ranking prompt. Out of scope here.
- **Re-chunking** the fragmented chunks (e.g. merging the standalone
  `"Diagnostic Criteria"` into its section). Requires reliable STG parsing;
  separate spec. This design re-contextualizes the **existing** chunk
  boundaries.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Source material | Re-contextualize the **existing 3,724 chunks** already in ChromaDB (text + chapter/section/page metadata). No PDF parsing. |
| Context method | **Hybrid** — deterministic structural prefix on every chunk + LLM blurb only for thin/ambiguous chunks. |
| Sparse retrieval | **Activate Contextual BM25** — wire the existing unused `HybridSearcher` into the pipeline over the contextualized text. |
| Index swap | Write a **new collection** (`mediassist_stg_ctx`); switch via config flag; keep old collection for A/B + instant rollback. |
| Evidence display | Show the **clean clinical line** (`raw_text`) to the clinician; keep the context blurb internal (provenance/audit only). |
| Validation | **Side-by-side eval** on ~15–20 tagged clinical vignettes; ship only on measured improvement. |

## Architecture

### Phase A — Offline contextualization & index build (one-time, re-runnable)

New script `scripts/build_contextual_index.py`:

1. **Read** all ids, documents, metadatas from `mediassist_stg`.
2. **Contextualize** each chunk (see below).
3. **Re-embed** the contextualized text with the **same** model
   (`all-MiniLM-L6-v2`, via `role2_retrieval/retrieval/encoder.py`) so the rest
   of the pipeline is unchanged.
4. **Write** to new collection `mediassist_stg_ctx`. Metadata carries:
   - `raw_text` — the original clinical chunk (shown as evidence)
   - `context_prefix` — the generated context (audit/provenance)
   - `context_source` — `structural` | `hybrid`
   - plus the original `chapter`/`section`/`page_*` fields
5. **Cache** every generated context (especially LLM blurbs) to disk
   (`vector_store/context_cache.json`, keyed by `chunk_id + hash(text)`), so
   re-runs are free and reproducible.

### Contextualization logic (`role2_retrieval/contextualize/context_builder.py`)

- **Structural prefix (always, deterministic):**
  `"{chapter} › {section}: "` (omit `section` when absent). Terse.
- **LLM blurb (conditional):** triggered when the chunk is
  - shorter than a word threshold (default ~12 words), **or**
  - effectively a bare heading (matches/equals its section title).

  For triggered chunks, send the LLM the chunk **plus a small window of
  neighbouring chunks** from the same chapter (ordered by page) with a strict
  prompt:

  > "Situate this fragment within its section in at most two sentences. Do NOT
  > introduce any medical facts, drugs, doses, or conditions that are not
  > present in the provided text. If you cannot situate it from the given text,
  > return an empty string."

  Reuses the `role3_llm` provider factory (Ollama or OpenAI).
- **Final stored text** = `prefix + (blurb + " ") + "\n\n" + original_chunk`.

**Guardrails:**
- MiniLM truncates at 256 tokens → keep the prefix terse and **skip the LLM
  blurb on already-long chunks** (they are not "thin" and we must not push real
  content out of the window).
- LLM failure for any chunk → fall back to **structural-only** for that chunk;
  never block the build. Log the count of fallbacks.

### Phase B — Query-time pipeline change

Edit only `role2_retrieval/retrieval/pipeline.py` and
`role2_retrieval/utils/config.py`:

- Searcher reads from `mediassist_stg_ctx` (config-driven collection name).
- After dedup, run the **existing `HybridSearcher`** (BM25 built over the
  contextualized texts pulled from the collection) and fuse with dense results
  via **Reciprocal Rank Fusion**, **before** the cross-encoder rerank.
  `HybridSearcher` is built once as a module-level singleton at startup.
- Cross-encoder rerank and the `role3_llm` stage are unchanged. Reranking runs
  against the **raw clinical text** (tunable during eval).

New data flow:

```
query → synonym expansion → multi-query → encode all
      → dense search (mediassist_stg_ctx)
      → dedup
      → BM25 sparse (contextualized texts) → RRF fuse        ← NEW
      → cross-encoder rerank
      → top-N → role3 LLM
```

### Config flags (`role2_retrieval/utils/config.py`)

- `chroma_collection` — switch between `mediassist_stg` (old) and
  `mediassist_stg_ctx` (new). Rollback = flip this.
- `use_hybrid` — enable/disable the BM25+RRF step.

## Error handling

- Per-chunk LLM blurb failure → structural-only fallback (build never aborts).
- New collection missing at query time → fall back to old collection; log a
  warning.
- Build writes a *new* collection; the live app is unaffected until the config
  flag flips.

## Validation & success criteria

- `eval/vignettes.jsonl`: ~15–20 clinical vignettes (incl. the fever/no-
  respiratory case), each tagged with the STG chapter/section that *should* be
  retrieved.
- `scripts/eval_retrieval.py`: runs `retrieve()` against **old vs new**
  collections and reports, side by side:
  - **hit-rate@5** — is an expected-section chunk in the top 5?
  - **rank of first correct chunk** (MRR-style).
- **Ship criteria:** hit-rate@5 improves with no major regressions, AND the
  fever/no-respiratory case no longer surfaces the pneumonia *treatment* line as
  top evidence (correct syndromic/fever section ranks above it).
- Old collection retained → rollback is one config flip.

## New / changed files

| File | Change |
|---|---|
| `scripts/build_contextual_index.py` | NEW — offline build job |
| `role2_retrieval/contextualize/__init__.py` | NEW |
| `role2_retrieval/contextualize/context_builder.py` | NEW — prefix + LLM blurb + thresholds |
| `role2_retrieval/retrieval/pipeline.py` | MODIFY — wire in BM25/RRF step |
| `role2_retrieval/utils/config.py` | MODIFY — `use_hybrid`, ctx collection name |
| `scripts/eval_retrieval.py` | NEW — side-by-side eval harness |
| `eval/vignettes.jsonl` | NEW — tagged clinical vignettes |

## Open implementation details (resolve in plan)

- Exact thin-chunk thresholds (word count, heading detection heuristic).
- Neighbour-window size for LLM context (e.g. ±2 chunks by page order).
- Whether the reranker should see contextualized vs raw text (decide via eval).
