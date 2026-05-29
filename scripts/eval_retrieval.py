# scripts/eval_retrieval.py
"""
Side-by-side retrieval eval: old legacy index vs new contextual index.

Metrics (chapter-level ground truth):
  * hit-rate@k  - fraction of vignettes with a correct-chapter chunk in top k
  * MRR         - mean reciprocal rank of the first correct-chapter chunk

A retrieval target is a (path, collection) pair. Run from the repo root:
    python -m scripts.eval_retrieval
"""

from __future__ import annotations

import json

from role2_retrieval.retrieval.pipeline import retrieve
from role2_retrieval.utils.config import config

VIGNETTES = "eval/vignettes.jsonl"
K = 5

# The legacy bundled index is at a FIXED location; do not use config.chroma_path,
# which is repointed at the contextual index at go-live.
LEGACY_PATH = "vector_store/chroma_db"
LEGACY_COLLECTION = "mediassist_stg"


def _load():
    with open(VIGNETTES, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _first_correct_rank(chunks, expected: list[str]) -> int | None:
    for rank, c in enumerate(chunks, start=1):
        if c.metadata.get("chapter") in expected:
            return rank
    return None


def _score(path: str, collection: str, use_hybrid: bool, vignettes: list[dict]) -> tuple[float, float]:
    hits = 0
    rr_sum = 0.0
    for v in vignettes:
        chunks = retrieve(v["query"], k=K, collection=collection, path=path,
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
        ("OLD legacy index (dense+rerank)", LEGACY_PATH, LEGACY_COLLECTION, False),
        ("NEW ctx index   (dense+rerank)", config.ctx_chroma_path, "mediassist_stg_ctx", False),
        ("NEW ctx index   (hybrid+rerank)", config.ctx_chroma_path, "mediassist_stg_ctx", True),
    ]
    print(f"{'config':36s}  hit-rate@5   MRR")
    print("-" * 64)
    for label, path, coll, hybrid in configs:
        hr, mrr = _score(path, coll, hybrid, vignettes)
        print(f"{label:36s}  {hr:8.2%}   {mrr:.3f}")

    print("\nPer-vignette (NEW ctx hybrid):")
    for v in vignettes:
        chunks = retrieve(v["query"], k=K, collection="mediassist_stg_ctx",
                          path=config.ctx_chroma_path, use_hybrid=True, rerank_top_n=K)
        rank = _first_correct_rank(chunks[:K], v["expected_chapters"])
        top_ch = chunks[0].metadata.get("chapter") if chunks else "-"
        flag = "ok " if rank else "MISS"
        print(f"  [{flag}] rank={rank}  top='{(top_ch or '')[:40]}'  q='{v['query'][:50]}'")


if __name__ == "__main__":
    main()
