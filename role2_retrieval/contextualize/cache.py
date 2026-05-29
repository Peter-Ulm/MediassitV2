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
