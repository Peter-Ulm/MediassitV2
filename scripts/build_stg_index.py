# scripts/build_stg_index.py
"""
Build the STG retrieval index FROM THE SOURCE PDF (re-chunk path).

Parses STG.pdf into substantive ~150-word chunks (scripts/parse_stg.py), then reuses
the contextual pipeline (scripts/build_contextual_index.contextualize_and_embed) to
embed them into a NEW, fresh collection — leaving the current contextual index intact
for A/B comparison and rollback.

Run from the repo root (use the project venv):

    .venv/Scripts/python.exe -m scripts.build_stg_index

Default output: collection 'mediassist_stg_rechunked' at 'vector_store/chroma_rechunked_db'.
Repoint retrieval at it (via .env CHROMA_PATH/CHROMA_COLLECTION) only after the grounding
gate passes.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys

from scripts.build_contextual_index import contextualize_and_embed
from scripts.parse_stg import parse_and_chunk
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)

# A chunk this short or shorter is a bare-title fragment — the exact defect we are
# fixing. The build aborts if any survive, so a bad parse never reaches the index.
_MIN_USEFUL_WORDS = 3


def report_chunk_quality(records: list[dict]) -> None:
    """Print a quality report and HARD-FAIL the build if fragmentation reappears."""
    if not records:
        log.error("Parser produced 0 chunks — chapter detection likely failed. Aborting.")
        sys.exit(1)

    word_counts = [len(r["text"].split()) for r in records]
    tiny = [r for r in records if len(r["text"].split()) <= _MIN_USEFUL_WORDS]
    log.info(
        "Chunk-quality report: count=%d  median_words=%d  min=%d  max=%d  <=%d-word=%d",
        len(records),
        int(statistics.median(word_counts)),
        min(word_counts),
        max(word_counts),
        _MIN_USEFUL_WORDS,
        len(tiny),
    )
    if tiny:
        log.error(
            "%d chunk(s) are <=%d words (bare-title fragmentation). Aborting build.",
            len(tiny), _MIN_USEFUL_WORDS,
        )
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the STG index from the source PDF.")
    ap.add_argument("--pdf", default="data/stg/STG.pdf")
    ap.add_argument("--target", default="mediassist_stg_rechunked")
    ap.add_argument("--target-path", default="vector_store/chroma_rechunked_db")
    ap.add_argument("--words-per-chunk", type=int, default=150)
    ap.add_argument("--overlap-words", type=int, default=30)
    ap.add_argument("--content-start-floor", type=int, default=30)
    # Offline by default: 150-word chunks are never "thin", so LLM blurbs never fire.
    # --use-llm only matters if you lower --words-per-chunk below the thin threshold.
    ap.add_argument("--use-llm", action="store_true", help="allow LLM situating blurbs for thin chunks")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        log.error("PDF not found at %s. Copy STG.pdf there (it is git-ignored).", args.pdf)
        sys.exit(1)

    log.info("Parsing + chunking %s ...", args.pdf)
    records = parse_and_chunk(
        args.pdf,
        words_per_chunk=args.words_per_chunk,
        overlap_words=args.overlap_words,
        content_start_floor=args.content_start_floor,
    )
    report_chunk_quality(records)

    contextualize_and_embed(records, args.target, args.target_path, use_llm=args.use_llm)
    log.info("Done. Index '%s' built at %s.", args.target, args.target_path)


if __name__ == "__main__":
    main()
