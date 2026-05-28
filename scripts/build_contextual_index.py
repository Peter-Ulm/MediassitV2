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
