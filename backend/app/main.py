"""
MediAssist backend — FastAPI app factory.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Startup sequence:
    1. Resolve CHROMA_PATH to an absolute path so it survives cwd changes.
    2. Verify the Ollama provider can reach the daemon (if LLM_PROVIDER=ollama).
    3. Optionally preload the Ollama model so the first request is fast.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logger import logger


def _resolve_chroma_path() -> None:
    """
    Convert relative CHROMA_PATH to absolute so it works regardless of
    where uvicorn is launched from. Role 2's searcher reads os.getenv
    via its config dataclass at import time, so we set the env var here
    BEFORE the searcher module is imported.
    """
    raw = os.getenv("CHROMA_PATH", settings.CHROMA_PATH)
    p = Path(raw)
    if not p.is_absolute():
        # Repo root = parent of "backend/"
        repo_root = Path(__file__).resolve().parents[2]
        p = repo_root / raw
    os.environ["CHROMA_PATH"] = str(p)
    logger.info(f"CHROMA_PATH resolved to {p}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _resolve_chroma_path()

    if settings.LLM_PROVIDER in {"ollama", "llama"} and settings.OLLAMA_WARMUP_ON_STARTUP:
        try:
            from role3_llm.factory import get_llm_provider

            provider = get_llm_provider()
            if hasattr(provider, "warmup"):
                logger.info(
                    f"Warming up Ollama model {provider.model}... "
                    "(this can take 5-15 s on first run)"
                )
                provider.warmup()
                logger.info(f"Ollama model {provider.model} ready.")
        except Exception as exc:
            logger.warning(
                f"Ollama warmup failed: {type(exc).__name__}: {exc}. "
                "Continuing — the first diagnosis request will pay cold-start cost."
            )

    yield
    # No teardown needed: chroma client and ollama client are cheap to drop.


def create_app() -> FastAPI:
    _resolve_chroma_path()

    # Import routes after resolving CHROMA_PATH. The diagnosis route imports
    # Role 2, whose config reads CHROMA_PATH at import time.
    from app.api.routes import admin, auth, consultations, diagnosis, health
    from app.db.base import init_db
    init_db()

    app = FastAPI(
        title="MediAssist API",
        description=(
            "AI-powered Clinical Decision Support System for Tanzanian "
            "healthcare facilities. Retrieves relevant Tanzania Standard "
            "Treatment Guidelines via a local RAG pipeline and produces a "
            "ranked differential diagnosis."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    app.include_router(diagnosis.router, prefix="/api/v1", tags=["diagnosis"])
    app.include_router(consultations.router, prefix="/api/v1", tags=["consultations"])

    return app


app = create_app()
