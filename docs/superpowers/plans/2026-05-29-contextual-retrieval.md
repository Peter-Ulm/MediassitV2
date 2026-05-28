# Contextual Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-index the Tanzania STG with Anthropic-style contextual retrieval (structural + LLM context prepended before embedding, plus contextual BM25) so retrieved evidence reflects what each chunk actually *is*, not just keyword overlap.

**Architecture:** A one-time offline script reads the existing 3,724 chunks from ChromaDB, prepends a hybrid context (deterministic chapter/section prefix + an LLM blurb only for thin/ambiguous chunks), and re-embeds into a NEW collection `mediassist_stg_ctx`. The query pipeline gains a config-switchable collection and wires in the already-built (but unused) `HybridSearcher` for contextual BM25 + RRF fusion before reranking. The old collection stays for A/B + instant rollback.

**Tech Stack:** Python 3.12, ChromaDB, sentence-transformers (`all-MiniLM-L6-v2`), `rank_bm25`, pytest. LLM blurbs go through the existing `role3_llm` provider abstraction (Ollama/OpenAI via `LLM_PROVIDER`).

**Spec:** [docs/superpowers/specs/2026-05-29-contextual-retrieval-design.md](../specs/2026-05-29-contextual-retrieval-design.md)

---

## File Structure

| File | Responsibility |
|---|---|
| `conftest.py` (root) | Put repo root on `sys.path` so tests can import `role2_retrieval`, `role3_llm`, `shared`. |
| `role2_retrieval/contextualize/__init__.py` | Package marker + public exports. |
| `role2_retrieval/contextualize/context_builder.py` | Pure context logic: structural prefix, thin-chunk detection, assembly, LLM blurb, `contextualize()` orchestrator, neighbour selection. |
| `role2_retrieval/contextualize/cache.py` | JSON cache for generated contexts (idempotent re-runs). |
| `scripts/build_contextual_index.py` | Offline job: read old collection → contextualize → embed → write `mediassist_stg_ctx`. |
| `role2_retrieval/utils/config.py` | MODIFY: add `use_hybrid` flag. |
| `role2_retrieval/retrieval/searcher.py` | MODIFY: per-collection construction + display `raw_text`. |
| `role2_retrieval/retrieval/pipeline.py` | MODIFY: collection override + contextual BM25/RRF step. |
| `role2_retrieval/expansion/hybrid.py` | MODIFY: sparse results display `raw_text`. |
| `scripts/eval_retrieval.py` | Side-by-side old-vs-new retrieval eval. |
| `eval/vignettes.jsonl` | Tagged clinical vignettes (ground truth = expected chapter). |
| `tests/contextualize/test_*.py` | Unit tests for the pure context logic. |

**Conventions to follow:** module docstrings like the existing files; `from __future__ import annotations`; `get_logger(__name__)` for logging; dataclasses for value objects; module-level singletons via a private `_get_*()` accessor (as in `pipeline.py`/`encoder.py`).

---

### Task 1: Test scaffolding + `use_hybrid` config flag

**Files:**
- Create: `conftest.py`
- Create: `tests/__init__.py`, `tests/contextualize/__init__.py`
- Modify: `role2_retrieval/utils/config.py`
- Test: `tests/contextualize/test_config.py`

- [ ] **Step 1: Create root `conftest.py`** so pytest can import the packages.

```python
# conftest.py
"""Ensure the repo root is importable in tests (role2_retrieval, role3_llm, shared)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
```

- [ ] **Step 2: Create empty package markers.**

```python
# tests/__init__.py  (empty)
```
```python
# tests/contextualize/__init__.py  (empty)
```

- [ ] **Step 3: Write the failing test** for the new config flag.

```python
# tests/contextualize/test_config.py
from role2_retrieval.utils.config import Config


def test_use_hybrid_defaults_false(monkeypatch):
    monkeypatch.delenv("USE_HYBRID", raising=False)
    assert Config().use_hybrid is False


def test_use_hybrid_env_override(monkeypatch):
    monkeypatch.setenv("USE_HYBRID", "true")
    assert Config().use_hybrid is True
```

- [ ] **Step 4: Run test to verify it fails.**

Run: `python -m pytest tests/contextualize/test_config.py -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'use_hybrid'`

- [ ] **Step 5: Add the flag** in `role2_retrieval/utils/config.py`, immediately after the `use_reranking` field (around line 67).

```python
    # Contextual BM25: fuse dense + sparse (BM25 over contextualized text) via
    # RRF before reranking. Off by default until the contextual index is built.
    use_hybrid: bool = field(
        default_factory=lambda: os.getenv("USE_HYBRID", "false").lower() == "true"
    )
```

- [ ] **Step 6: Run test to verify it passes.**

Run: `python -m pytest tests/contextualize/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit.**

```bash
git add conftest.py tests/__init__.py tests/contextualize/__init__.py tests/contextualize/test_config.py role2_retrieval/utils/config.py
git commit -m "test: scaffolding + use_hybrid config flag"
```

---

### Task 2: Structural prefix, thin-chunk detection, assembly

**Files:**
- Create: `role2_retrieval/contextualize/__init__.py`
- Create: `role2_retrieval/contextualize/context_builder.py`
- Test: `tests/contextualize/test_context_builder.py`

- [ ] **Step 1: Write the failing tests** (pure functions, no model/LLM).

```python
# tests/contextualize/test_context_builder.py
from role2_retrieval.contextualize.context_builder import (
    build_structural_prefix,
    is_thin_chunk,
    assemble_contextualized_text,
)


def test_prefix_chapter_and_section():
    md = {"chapter": "Chapter Nine: RESPIRATORY DISEASE CONDITIONS",
          "section": "Treatment of Pneumonia"}
    assert build_structural_prefix(md) == (
        "Chapter Nine: RESPIRATORY DISEASE CONDITIONS › Treatment of Pneumonia: "
    )


def test_prefix_chapter_only():
    assert build_structural_prefix({"chapter": "Chapter Five: MALARIA"}) == "Chapter Five: MALARIA: "


def test_prefix_empty_when_no_metadata():
    assert build_structural_prefix({}) == ""


def test_thin_chunk_short_text():
    assert is_thin_chunk("Diagnostic Criteria", {}) is True


def test_thin_chunk_long_text_is_not_thin():
    text = " ".join(["word"] * 30)
    assert is_thin_chunk(text, {}) is False


def test_thin_chunk_equals_section_heading():
    text = " ".join(["Treatment", "of", "Pneumonia", "and", "more", "filler",
                      "words", "to", "exceed", "the", "twelve", "word", "limit"])
    assert is_thin_chunk(text, {"section": text}) is True


def test_assemble_with_prefix_and_blurb():
    out = assemble_contextualized_text("Chapter Five: MALARIA: ", "This is the malaria intro.", "Body text.")
    assert out == "Chapter Five: MALARIA: This is the malaria intro.\n\nBody text."


def test_assemble_no_context_returns_chunk():
    assert assemble_contextualized_text("", "", "Body text.") == "Body text."
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/contextualize/test_context_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'role2_retrieval.contextualize'`

- [ ] **Step 3: Create the package + implement the pure functions.**

```python
# role2_retrieval/contextualize/__init__.py
"""Contextual retrieval: prepend situating context to chunks before embedding."""
```

```python
# role2_retrieval/contextualize/context_builder.py
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
_SEP = " › "  # " > "

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
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/contextualize/test_context_builder.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit.**

```bash
git add role2_retrieval/contextualize/__init__.py role2_retrieval/contextualize/context_builder.py tests/contextualize/test_context_builder.py
git commit -m "feat: structural prefix + thin-chunk detection for contextual retrieval"
```

---

### Task 3: Context cache (idempotent re-runs)

**Files:**
- Create: `role2_retrieval/contextualize/cache.py`
- Test: `tests/contextualize/test_cache.py`

- [ ] **Step 1: Write the failing tests.**

```python
# tests/contextualize/test_cache.py
from role2_retrieval.contextualize.cache import cache_key, load_cache, save_cache


def test_cache_key_is_deterministic():
    assert cache_key("id1", "hello") == cache_key("id1", "hello")


def test_cache_key_changes_with_text():
    assert cache_key("id1", "hello") != cache_key("id1", "world")


def test_load_missing_returns_empty(tmp_path):
    assert load_cache(str(tmp_path / "nope.json")) == {}


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / "cache.json")
    save_cache({"a": "b"}, path)
    assert load_cache(path) == {"a": "b"}
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/contextualize/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'role2_retrieval.contextualize.cache'`

- [ ] **Step 3: Implement the cache.**

```python
# role2_retrieval/contextualize/cache.py
"""JSON cache so re-running the build never re-calls the LLM for unchanged chunks."""

from __future__ import annotations

import hashlib
import json
import os


def cache_key(chunk_id: str, text: str) -> str:
    """Stable key from chunk id + a hash of its text (so edits invalidate)."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{chunk_id}:{digest}"


def load_cache(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_cache(cache: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/contextualize/test_cache.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit.**

```bash
git add role2_retrieval/contextualize/cache.py tests/contextualize/test_cache.py
git commit -m "feat: JSON context cache for idempotent index builds"
```

---

### Task 4: LLM blurb generation (provider-agnostic, fails safe)

**Files:**
- Modify: `role2_retrieval/contextualize/context_builder.py`
- Test: `tests/contextualize/test_blurb.py`

Uses `role3_llm.factory.get_llm_provider()` (returns an object with `.generate(messages, max_tokens) -> str`). On ANY error, returns `""` so the build falls back to structural-only.

- [ ] **Step 1: Write the failing tests** with a fake provider (no real LLM call).

```python
# tests/contextualize/test_blurb.py
from role2_retrieval.contextualize.context_builder import generate_llm_blurb


class _FakeProvider:
    def __init__(self, reply): self._reply = reply
    def generate(self, messages, max_tokens=120): return self._reply


class _BoomProvider:
    def generate(self, messages, max_tokens=120): raise RuntimeError("llm down")


def test_blurb_returns_cleaned_text():
    out = generate_llm_blurb("Diagnostic Criteria", ["neighbour text"],
                             provider=_FakeProvider("  This section lists\n malaria criteria.  "))
    assert out == "This section lists malaria criteria."


def test_blurb_failure_returns_empty_string():
    assert generate_llm_blurb("x", [], provider=_BoomProvider()) == ""
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/contextualize/test_blurb.py -v`
Expected: FAIL — `ImportError: cannot import name 'generate_llm_blurb'`

- [ ] **Step 3: Add `generate_llm_blurb` to `context_builder.py`** (append after `assemble_contextualized_text`, and add the logger import near the top imports).

```python
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

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
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/contextualize/test_blurb.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit.**

```bash
git add role2_retrieval/contextualize/context_builder.py tests/contextualize/test_blurb.py
git commit -m "feat: provider-agnostic LLM blurb generation with fail-safe fallback"
```

---

### Task 5: `contextualize()` orchestrator + neighbour selection

**Files:**
- Modify: `role2_retrieval/contextualize/context_builder.py`
- Modify: `role2_retrieval/contextualize/__init__.py` (exports)
- Test: `tests/contextualize/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests.**

```python
# tests/contextualize/test_orchestrator.py
from role2_retrieval.contextualize.context_builder import contextualize, select_neighbors


class _FakeProvider:
    def generate(self, messages, max_tokens=120): return "Situating blurb."


def test_long_chunk_is_structural_only():
    text = " ".join(["word"] * 30)
    res = contextualize(text, {"chapter": "Chapter Five: MALARIA"}, [], provider=_FakeProvider())
    assert res.source == "structural"
    assert res.contextualized_text.startswith("Chapter Five: MALARIA: ")
    assert "Situating blurb." not in res.contextualized_text


def test_thin_chunk_gets_hybrid_blurb():
    res = contextualize("Diagnostic Criteria",
                        {"chapter": "Chapter Five: MALARIA", "section": "Malaria"},
                        ["neighbour"], provider=_FakeProvider())
    assert res.source == "hybrid"
    assert "Situating blurb." in res.contextualized_text


def test_select_neighbors_same_chapter_only():
    chunks = [
        {"text": "a", "metadata": {"chapter": "C1"}},
        {"text": "b", "metadata": {"chapter": "C1"}},
        {"text": "c", "metadata": {"chapter": "C2"}},
    ]
    # index 1: neighbour 0 (C1) included, neighbour 2 (C2) excluded
    assert select_neighbors(chunks, 1, window=1) == ["a"]
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/contextualize/test_orchestrator.py -v`
Expected: FAIL — `ImportError: cannot import name 'contextualize'`

- [ ] **Step 3: Add `ContextResult`, `contextualize`, `select_neighbors`** to `context_builder.py`.

```python
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

    text = assemble_contextualized_text(prefix, blurb, chunk_text)
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
```

- [ ] **Step 4: Update package exports.**

```python
# role2_retrieval/contextualize/__init__.py
"""Contextual retrieval: prepend situating context to chunks before embedding."""

from role2_retrieval.contextualize.context_builder import (
    ContextResult,
    contextualize,
    select_neighbors,
    build_structural_prefix,
)

__all__ = ["ContextResult", "contextualize", "select_neighbors", "build_structural_prefix"]
```

- [ ] **Step 5: Run to verify pass.**

Run: `python -m pytest tests/contextualize/ -v`
Expected: PASS (all context tests green)

- [ ] **Step 6: Commit.**

```bash
git add role2_retrieval/contextualize/ tests/contextualize/test_orchestrator.py
git commit -m "feat: contextualize() orchestrator + chapter-aware neighbour selection"
```

---

### Task 6: Offline build script `build_contextual_index.py`

**Files:**
- Create: `scripts/build_contextual_index.py`

Reads `mediassist_stg`, contextualizes every chunk (with cache), re-embeds with the same model, writes `mediassist_stg_ctx`. Idempotent: deletes the target collection first. Metadata values are coerced to scalars (Chroma rejects `None`).

- [ ] **Step 1: Write the script.**

```python
# scripts/build_contextual_index.py
"""
Build the contextual STG index.

Reads every chunk from the source ChromaDB collection, prepends a hybrid
situating context (structural prefix + LLM blurb for thin chunks), re-embeds
the contextualized text with the SAME model, and writes a NEW collection.

The source collection is never modified. Run from the repo root:

    python -m scripts.build_contextual_index
"""

from __future__ import annotations

import argparse

import chromadb
from sentence_transformers import SentenceTransformer

from role2_retrieval.contextualize.cache import cache_key, load_cache, save_cache
from role2_retrieval.contextualize.context_builder import contextualize, select_neighbors
from role2_retrieval.utils.config import config
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

CACHE_PATH = "vector_store/context_cache.json"
EMBED_BATCH = 128


def _scalar(value):
    """Chroma metadata must be str/int/float/bool — coerce None/other to ''."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build(target_collection: str, source_collection: str, use_llm: bool) -> None:
    client = chromadb.PersistentClient(path=config.chroma_path)

    src = client.get_collection(source_collection)
    raw = src.get(include=["documents", "metadatas"])
    ids = raw["ids"]
    docs = raw["documents"]
    metas = raw["metadatas"]
    log.info(f"Read {len(ids)} chunks from '{source_collection}'.")

    # Document order for neighbour windows: group by chapter, then page.
    order = sorted(
        range(len(ids)),
        key=lambda i: ((metas[i].get("chapter") or ""), metas[i].get("page_start") or 0, i),
    )
    ordered = [{"id": ids[i], "text": docs[i], "metadata": metas[i]} for i in order]

    cache = load_cache(CACHE_PATH)
    cache_hits = llm_calls = 0

    out_ids, out_docs, out_metas = [], [], []
    for idx, rec in enumerate(ordered):
        key = cache_key(rec["id"], rec["text"])
        if key in cache:
            ctx_text, prefix, source = cache[key]["text"], cache[key]["prefix"], cache[key]["source"]
            cache_hits += 1
        else:
            neighbors = select_neighbors(ordered, idx, window=2)
            res = contextualize(rec["text"], rec["metadata"], neighbors, use_llm=use_llm)
            ctx_text, prefix, source = res.contextualized_text, res.prefix, res.source
            if source == "hybrid":
                llm_calls += 1
            cache[key] = {"text": ctx_text, "prefix": prefix, "source": source}

        md = rec["metadata"]
        out_ids.append(rec["id"])
        out_docs.append(ctx_text)
        out_metas.append({
            "raw_text": rec["text"],
            "context_prefix": prefix,
            "context_source": source,
            "chapter": _scalar(md.get("chapter")),
            "section": _scalar(md.get("section")),
            "page_start": _scalar(md.get("page_start")),
            "page_end": _scalar(md.get("page_end")),
        })

        if idx % 200 == 0:
            log.info(f"Contextualized {idx}/{len(ordered)} (cache_hits={cache_hits}, llm_calls={llm_calls})")
            save_cache(cache, CACHE_PATH)

    save_cache(cache, CACHE_PATH)
    log.info(f"Contextualization done. cache_hits={cache_hits}, llm_calls={llm_calls}")

    # Re-embed contextualized text with the SAME model used for queries.
    log.info(f"Loading embedding model: {config.embedding_model}")
    model = SentenceTransformer(config.embedding_model)

    # Fresh target collection.
    try:
        client.delete_collection(target_collection)
        log.info(f"Deleted existing '{target_collection}'.")
    except Exception:
        pass
    dst = client.create_collection(target_collection, metadata={"hnsw:space": "l2"})

    for start in range(0, len(out_ids), EMBED_BATCH):
        chunk_docs = out_docs[start:start + EMBED_BATCH]
        embeddings = model.encode(chunk_docs, normalize_embeddings=True, show_progress_bar=False)
        dst.add(
            ids=out_ids[start:start + EMBED_BATCH],
            documents=chunk_docs,
            embeddings=[e.tolist() for e in embeddings],
            metadatas=out_metas[start:start + EMBED_BATCH],
        )
        log.info(f"Embedded + wrote {min(start + EMBED_BATCH, len(out_ids))}/{len(out_ids)}")

    log.info(f"Built '{target_collection}' with {dst.count()} chunks.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the contextual STG index.")
    ap.add_argument("--target", default="mediassist_stg_ctx")
    ap.add_argument("--source", default="mediassist_stg")
    ap.add_argument("--no-llm", action="store_true", help="structural-only (skip LLM blurbs)")
    args = ap.parse_args()
    build(args.target, args.source, use_llm=not args.no_llm)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the build** (use `--no-llm` first for a fast, deterministic dry run that needs no LLM).

Run: `python -m scripts.build_contextual_index --no-llm`
Expected: log ends with `Built 'mediassist_stg_ctx' with 3724 chunks.`

- [ ] **Step 3: Verify the new collection** — count matches, docs carry the structural prefix, metadata carries `raw_text`.

Run:
```bash
python -c "import chromadb; c=chromadb.PersistentClient(path='vector_store/chroma_db'); col=c.get_collection('mediassist_stg_ctx'); r=col.get(limit=3, include=['documents','metadatas']); print('count', col.count()); [print('---', repr(d[:90]), '| raw:', repr(m.get('raw_text')[:50]), '| src:', m.get('context_source')) for d,m in zip(r['documents'], r['metadatas'])]"
```
Expected: `count 3724`; each printed doc begins with `Chapter ... :` and `raw:` shows the original clinical text.

- [ ] **Step 4: Commit.**

```bash
git add scripts/build_contextual_index.py
git commit -m "feat: offline build script for contextual STG index"
```

> Note: the built `vector_store/chroma_db` and `vector_store/context_cache.json` are data artifacts. Commit them only if the repo already tracks the prebuilt DB (it does — README calls it "bundled prebuilt"); otherwise add them in Task 10 alongside the go-live flip. Decide per repo policy at that step.

---

### Task 7: Per-collection searcher + display `raw_text`

**Files:**
- Modify: `role2_retrieval/retrieval/searcher.py`
- Modify: `role2_retrieval/retrieval/pipeline.py`
- Test: `tests/contextualize/test_display_text.py`

The clinician must see the clean clinical line, not our context prefix. The searcher returns `raw_text` (when present) as `RetrievedChunk.text`, while the embeddings/BM25 still use the contextualized `documents`.

- [ ] **Step 1: Write the failing test** for the display helper.

```python
# tests/contextualize/test_display_text.py
from role2_retrieval.retrieval.searcher import display_text


def test_prefers_raw_text():
    assert display_text("Ch9 > ...: If fever give X", {"raw_text": "If fever give X"}) == "If fever give X"


def test_falls_back_to_document_when_no_raw_text():
    assert display_text("plain fragment", {}) == "plain fragment"
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/contextualize/test_display_text.py -v`
Expected: FAIL — `ImportError: cannot import name 'display_text'`

- [ ] **Step 3: Add `display_text` and use it in `STGSearcher.search`; add a `collection` constructor arg.** In `role2_retrieval/retrieval/searcher.py`:

Add this module-level helper after the `RetrievedChunk` dataclass:
```python
def display_text(documents: str, metadata: dict) -> str:
    """Clinician-facing text: the original chunk (raw_text) when available."""
    return (metadata or {}).get("raw_text") or documents
```

Change `__init__` to accept a collection name (default keeps current behaviour):
```python
    def __init__(self, collection: str | None = None) -> None:
        collection = collection or config.chroma_collection
        log.info(f"Connecting to ChromaDB at: {config.chroma_path}")
        ensure_chroma_compatibility(config.chroma_path, collection)
        self._client = chromadb.PersistentClient(path=config.chroma_path)
        self._collection = self._client.get_collection(collection)
        doc_count = self._collection.count()
        log.info(
            f"Connected to collection '{collection}' "
            f"({doc_count} chunks indexed)."
        )
```

In `search()`, replace the text/metadata assembly inside the loop (current lines ~100-106) with:
```python
            chunk_id = results["ids"][0][idx]
            documents = results["documents"][0][idx]
            distance = results["distances"][0][idx]
            score    = 1.0 - (distance / 2.0)
            metadata = results["metadatas"][0][idx] if results["metadatas"] else {}
            text     = display_text(documents, metadata)
```

- [ ] **Step 4: Add per-collection singletons + `collection` override in `pipeline.py`.** Replace the `_searcher` singleton block (lines ~30-39) with a dict cache:

```python
# Module-level singletons (initialised on first call)
_searchers: dict[str, STGSearcher] = {}
_reranker: Reranker | None = None


def _get_searcher(collection: str | None = None) -> STGSearcher:
    name = collection or config.chroma_collection
    if name not in _searchers:
        _searchers[name] = STGSearcher(collection=name)
    return _searchers[name]
```

In `retrieve()`, add `collection: str | None = None` to the signature, and at the top of the body resolve and use it:
```python
    coll = collection or config.chroma_collection
```
Then change the searcher acquisition (line ~97) to `searcher = _get_searcher(coll)`.

- [ ] **Step 5: Run to verify pass + no regressions.**

Run: `python -m pytest tests/ -v`
Expected: PASS (display_text tests pass; nothing else breaks)

- [ ] **Step 6: Smoke-check retrieval against the new collection returns clean text.**

Run:
```bash
python -c "from role2_retrieval.retrieval.pipeline import retrieve; r=retrieve('fever for 3 days with chills, no cough, no chest pain', collection='mediassist_stg_ctx', use_reranking=False); print(r[0].text[:120]); print('NO PREFIX IN TEXT:', '›' not in r[0].text)"
```
Expected: prints a clean clinical line and `NO PREFIX IN TEXT: True`.

- [ ] **Step 7: Commit.**

```bash
git add role2_retrieval/retrieval/searcher.py role2_retrieval/retrieval/pipeline.py tests/contextualize/test_display_text.py
git commit -m "feat: per-collection searcher + clinician-facing raw_text display"
```

---

### Task 8: Wire in Contextual BM25 (HybridSearcher + RRF)

**Files:**
- Modify: `role2_retrieval/expansion/hybrid.py`
- Modify: `role2_retrieval/retrieval/pipeline.py`
- Test: `tests/contextualize/test_hybrid_display.py`

BM25 is built over the contextualized `documents` (contextual BM25), but sparse results display `raw_text`.

- [ ] **Step 1: Write the failing test** for sparse-result display.

```python
# tests/contextualize/test_hybrid_display.py
from role2_retrieval.expansion.hybrid import HybridSearcher


def test_sparse_search_returns_raw_text():
    hs = HybridSearcher(
        chunk_texts=["Chapter Five: MALARIA: blurb about fever and malaria treatment"],
        chunk_ids=["c1"],
        chunk_metadata=[{"raw_text": "fever and malaria treatment"}],
    )
    out = hs.sparse_search("fever malaria", k=1)
    assert out[0].text == "fever and malaria treatment"
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/contextualize/test_hybrid_display.py -v`
Expected: FAIL — assertion error (`.text` is the contextualized document, not `raw_text`).

- [ ] **Step 3: Use `raw_text` in `HybridSearcher.sparse_search`.** In `role2_retrieval/expansion/hybrid.py`, inside `sparse_search`, change the `RetrievedChunk(...)` construction so `text` prefers `raw_text`:

```python
        for idx in top_indices:
            md = self._chunk_metadata[idx]
            results.append(RetrievedChunk(
                chunk_id=self._chunk_ids[idx],
                text=md.get("raw_text") or self._chunk_texts[idx],
                score=float(scores[idx]),
                metadata=md,
            ))
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/contextualize/test_hybrid_display.py -v`
Expected: PASS

- [ ] **Step 5: Add a hybrid-searcher singleton + wire the fusion step into `pipeline.py`.**

Add imports at the top of `pipeline.py`:
```python
from role2_retrieval.expansion.hybrid import HybridSearcher
```

Add the singleton accessor (next to `_get_searcher`):
```python
_hybrid_searchers: dict[str, HybridSearcher] = {}


def _get_hybrid_searcher(collection: str) -> HybridSearcher:
    """Build (once per collection) a BM25 index over the contextualized docs."""
    if collection not in _hybrid_searchers:
        searcher = _get_searcher(collection)
        raw = searcher._collection.get(include=["documents", "metadatas"])
        _hybrid_searchers[collection] = HybridSearcher(
            chunk_texts=raw["documents"],
            chunk_ids=raw["ids"],
            chunk_metadata=raw["metadatas"],
        )
    return _hybrid_searchers[collection]
```

Add `use_hybrid: bool | None = None` to the `retrieve()` signature and resolve it with the others:
```python
    use_hybrid = use_hybrid if use_hybrid is not None else config.use_hybrid
```

Insert the fusion step **after** dedup (Step 5) and **before** reranking (Step 6):
```python
    # ── Step 5b: Contextual BM25 + RRF fusion ────────────────────────────
    if use_hybrid and merged_chunks:
        hybrid = _get_hybrid_searcher(coll)
        merged_chunks = hybrid.hybrid_search(query, merged_chunks, top_n=k)
        log.info(f"[Pipeline] {len(merged_chunks)} chunks after hybrid RRF fusion.")
```

- [ ] **Step 6: Run the full suite.**

Run: `python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 7: Smoke-check hybrid retrieval runs end to end.**

Run:
```bash
python -c "from role2_retrieval.retrieval.pipeline import retrieve; r=retrieve('productive cough 3 weeks night sweats weight loss', collection='mediassist_stg_ctx', use_hybrid=True); [print(c.metadata.get('chapter'), '|', c.text[:60]) for c in r]"
```
Expected: runs without error; top chapters are clinically plausible (TB/respiratory).

- [ ] **Step 8: Commit.**

```bash
git add role2_retrieval/expansion/hybrid.py role2_retrieval/retrieval/pipeline.py tests/contextualize/test_hybrid_display.py
git commit -m "feat: wire contextual BM25 + RRF fusion into retrieval pipeline"
```

---

### Task 9: Side-by-side evaluation harness

**Files:**
- Create: `eval/vignettes.jsonl`
- Create: `scripts/eval_retrieval.py`

Ground truth is chapter-level (sections are noisy). A vignette "hits" at rank *r* if the chunk at rank *r* has `metadata['chapter']` in `expected_chapters`.

- [ ] **Step 1: Create the vignette set** (16 cases, real chapter labels from the STG; includes the screenshot case).

```jsonl
{"query": "Fever for 3 days with chills, headache, reduced appetite, no cough, no chest pain, no shortness of breath", "expected_chapters": ["Chapter Five: MALARIA", "Chapter One: SYNDROMIC APPROACH"], "note": "screenshot case - must NOT rank respiratory first"}
{"query": "Cough with fever, difficulty breathing and chest pain for two days", "expected_chapters": ["Chapter Nine: RESPIRATORY DISEASE CONDITIONS"], "note": "legitimate pneumonia"}
{"query": "Productive cough for three weeks with night sweats and weight loss", "expected_chapters": ["Chapter Seven: TUBERCULOSIS AND LEPROSY"], "note": "TB"}
{"query": "Severe headache with neck stiffness, photophobia and high fever", "expected_chapters": ["Chapter Eight: NERVOUS SYSTEM DISEASE CONDITIONS"], "note": "meningitis"}
{"query": "Profuse watery diarrhoea with vomiting and signs of dehydration", "expected_chapters": ["Chapter Ten: GASTROINTESTINAL DISEASE CONDITIONS"], "note": "gastroenteritis/cholera"}
{"query": "Crushing chest pain radiating to the left arm with sweating and breathlessness", "expected_chapters": ["Chapter Twenty: CARDIOVASCULAR DISEASE CONDITIONS"], "note": "ACS"}
{"query": "Generalised weakness, pallor and fatigue with shortness of breath on exertion", "expected_chapters": ["Chapter Three: HAEMATOLOGICAL DISEASE CONDITIONS"], "note": "anaemia"}
{"query": "Severe toothache with swollen gum and facial swelling", "expected_chapters": ["Chapter Sixteen: ORAL AND DENTAL CONDITION"], "note": "dental abscess"}
{"query": "Ear pain with discharge and reduced hearing for several days", "expected_chapters": ["Chapter Fifteen: EAR, NOSE AND THROAT DISEASES"], "note": "otitis media"}
{"query": "Recurrent convulsions and loss of consciousness in a known epileptic", "expected_chapters": ["Chapter Eight: NERVOUS SYSTEM DISEASE CONDITIONS"], "note": "epilepsy"}
{"query": "Persistent low mood, loss of interest, insomnia and thoughts of self harm", "expected_chapters": ["Chapter Twenty Three: MENTAL HEALTH CONDITIONS"], "note": "depression"}
{"query": "Child who swallowed rat poison, now drooling and vomiting", "expected_chapters": ["Chapter Twenty Five: POISONING"], "note": "poisoning"}
{"query": "Pregnant woman at 34 weeks with severe headache, high blood pressure and leg swelling", "expected_chapters": ["Chapter Eleven: OBSTETRICS, GYNECOLOGY AND CONTRACEPTION"], "note": "pre-eclampsia"}
{"query": "HIV positive patient with oral thrush, chronic diarrhoea and weight loss", "expected_chapters": ["Chapter Six: HIV/AIDS"], "note": "advanced HIV"}
{"query": "Road traffic accident with a deep bleeding leg laceration", "expected_chapters": ["Chapter Eighteen: TRAUMA & INJURIES"], "note": "trauma"}
{"query": "High fever with a rash and bleeding gums in an outbreak setting", "expected_chapters": ["Chapter Four: NOTIFIABLE DISEASES", "Chapter Five: MALARIA"], "note": "VHF / notifiable"}
```

- [ ] **Step 2: Write the eval script.**

```python
# scripts/eval_retrieval.py
"""
Side-by-side retrieval eval: old collection vs new contextual collection.

Metrics (chapter-level ground truth):
  * hit-rate@k  - fraction of vignettes with a correct-chapter chunk in top k
  * MRR         - mean reciprocal rank of the first correct-chapter chunk

Run from the repo root:
    python -m scripts.eval_retrieval
"""

from __future__ import annotations

import json

from role2_retrieval.retrieval.pipeline import retrieve

VIGNETTES = "eval/vignettes.jsonl"
K = 5


def _load():
    with open(VIGNETTES, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _first_correct_rank(chunks, expected: list[str]) -> int | None:
    for rank, c in enumerate(chunks, start=1):
        if c.metadata.get("chapter") in expected:
            return rank
    return None


def _score(collection: str, use_hybrid: bool, vignettes: list[dict]) -> tuple[float, float]:
    hits = 0
    rr_sum = 0.0
    for v in vignettes:
        chunks = retrieve(v["query"], k=K, collection=collection,
                          use_hybrid=use_hybrid, rerank_top_n=K)
        rank = _first_correct_rank(chunks[:K], v["expected_chapters"])
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank
    n = len(vignettes)
    return hits / n, rr_sum / n


def main() -> None:
    vignettes = _load()
    print(f"Evaluating {len(vignettes)} vignettes @k={K}\n")

    configs = [
        ("OLD  (mediassist_stg, dense only)", "mediassist_stg", False),
        ("NEW  (mediassist_stg_ctx, dense)", "mediassist_stg_ctx", False),
        ("NEW  (mediassist_stg_ctx, hybrid)", "mediassist_stg_ctx", True),
    ]
    print(f"{'config':42s}  hit-rate@5   MRR")
    print("-" * 70)
    for label, coll, hybrid in configs:
        hr, mrr = _score(coll, hybrid, vignettes)
        print(f"{label:42s}  {hr:8.2%}   {mrr:.3f}")

    print("\nPer-vignette (NEW hybrid):")
    for v in vignettes:
        chunks = retrieve(v["query"], k=K, collection="mediassist_stg_ctx",
                          use_hybrid=True, rerank_top_n=K)
        rank = _first_correct_rank(chunks[:K], v["expected_chapters"])
        top_ch = chunks[0].metadata.get("chapter") if chunks else "-"
        flag = "ok " if rank else "MISS"
        print(f"  [{flag}] rank={rank}  top='{top_ch[:40]}'  q='{v['query'][:50]}'")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the eval.**

Run: `python -m scripts.eval_retrieval`
Expected: a 3-row table prints. Success criteria: the NEW rows show **hit-rate@5 ≥ the OLD row** (target improvement), and the first per-vignette line (the screenshot case) does NOT have `top='Chapter Nine: RESPIRATORY...'`.

- [ ] **Step 4: If the screenshot case still misses,** record the actual top chapters it returns (the per-vignette dump shows them) and note them in the plan's follow-up — do not tune blindly here; the negation issue is a documented `role3_llm` fast-follow.

- [ ] **Step 5: Commit.**

```bash
git add eval/vignettes.jsonl scripts/eval_retrieval.py
git commit -m "test: side-by-side retrieval eval harness with clinical vignettes"
```

---

### Task 10: Go-live (config flip) + final verification

**Files:**
- Modify: `.env`, `.env.example`

Only flip to the new collection **if Task 9 showed improvement**. Rollback is reverting these two lines.

- [ ] **Step 1: Point the live app at the contextual index.** In `.env` (and mirror the keys, without secrets, in `.env.example`):

```
CHROMA_COLLECTION=mediassist_stg_ctx
USE_HYBRID=true
```

- [ ] **Step 2: Run the existing smoke test.**

Run: `python scripts/smoke_test.py`
Expected: completes without error (retrieval path now uses the contextual collection).

- [ ] **Step 3: Verify in the running app** — start the backend, run the screenshot query through the UI / `/api/v1/diagnosis/retrieve`, and confirm the evidence shown is a clean clinical line and pneumonia treatment is no longer the top evidence for the no-respiratory fever case. (Use the `verify` or `run` skill to launch the app.)

- [ ] **Step 4: Commit the go-live flip** (and the rebuilt DB artifacts if repo policy tracks them — see Task 6 note).

```bash
git add .env.example
# include .env and vector_store artifacts only if the repo tracks them
git commit -m "feat: switch live retrieval to contextual index + contextual BM25"
```

---

## Self-Review

**Spec coverage:**
- Phase A offline build → Tasks 2–6. ✅
- Hybrid context (structural always + LLM for thin chunks) → Tasks 2, 4, 5. ✅
- New collection + config flip + rollback → Tasks 6, 7, 10. ✅
- Contextual BM25 (activate HybridSearcher) → Task 8. ✅
- Clinician sees clean `raw_text` → Tasks 7, 8. ✅
- Context cache for reproducible/cheap re-runs → Tasks 3, 6. ✅
- Validation harness (≥15 vignettes incl. screenshot case, old-vs-new, hit-rate@5 + MRR) → Task 9. ✅
- Token-budget guard (skip LLM blurb on long chunks) → Task 5 (`MAX_WORDS_FOR_LLM`). ✅
- Non-goals (negation, re-chunking) → not implemented by design; called out in Task 9 Step 4. ✅

**Placeholder scan:** No TBD/TODO; every code step has complete code; vignettes are concrete with real chapter labels. ✅

**Type/name consistency:** `contextualize()` returns `ContextResult(contextualized_text, prefix, source)` — consumed with those exact names in Task 6. `display_text(documents, metadata)` defined in Task 7, used in Tasks 7–8. `_get_searcher(collection)` / `_get_hybrid_searcher(collection)` / `retrieve(..., collection=, use_hybrid=)` consistent across Tasks 7–9. `HybridSearcher(chunk_texts, chunk_ids, chunk_metadata)` matches the existing constructor. ✅
