"""Health check — reports backend + LLM + ChromaDB readiness."""

from __future__ import annotations

import time
import os

from fastapi import APIRouter

from app.core.config import settings
from role3_llm.factory import get_llm_provider

router = APIRouter()


_BOOT_TIME = time.time()


@router.get("/health")
def health() -> dict:
    """
    Returns:
        status: "ok" | "degraded"
        llm:   { provider, model, healthy }
        chroma:{ collection, indexed }
        uptime_seconds
    """
    # LLM
    try:
        provider = get_llm_provider()
        llm_healthy = provider.health_check()
        llm_model = getattr(provider, "model", "unknown")
    except Exception as exc:
        llm_healthy = False
        llm_model = f"error: {type(exc).__name__}"

    # Chroma
    try:
        import chromadb
        from pathlib import Path

        chroma_path = Path(os.getenv("CHROMA_PATH", settings.CHROMA_PATH)).resolve()
        client = chromadb.PersistentClient(path=str(chroma_path))
        col = client.get_collection(settings.CHROMA_COLLECTION)
        chunk_count = col.count()
        chroma_ok = chunk_count > 0
    except Exception as exc:
        chunk_count = 0
        chroma_ok = False

    status = "ok" if (llm_healthy and chroma_ok) else "degraded"

    return {
        "status": status,
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": llm_model,
            "healthy": llm_healthy,
        },
        "chroma": {
            "collection": settings.CHROMA_COLLECTION,
            "indexed_chunks": chunk_count,
            "healthy": chroma_ok,
        },
        "uptime_seconds": int(time.time() - _BOOT_TIME),
    }
