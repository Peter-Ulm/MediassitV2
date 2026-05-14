"""
Typed FastAPI settings. Loads from `.env` at the repo root.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ────────────────────────────────────────────────────────────────
    LLM_PROVIDER: str = "ollama"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral:7b-instruct"
    OLLAMA_KEEP_ALIVE: str = "30m"
    OLLAMA_NUM_CTX: int = 4096

    # ── Retrieval / Knowledge base ─────────────────────────────────────────
    CHROMA_PATH: str = "vector_store/chroma_db"
    CHROMA_COLLECTION: str = "mediassist_stg"
    TOP_K: int = 5
    RERANK_TOP_N: int = 3
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── API surface ────────────────────────────────────────────────────────
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    ALLOWED_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    )

    # If True, the backend preloads the Ollama model at startup so the first
    # request does not pay the 5-15 s cold-start cost. Costs 5-15 s of boot
    # time and ~4 GB of RAM/VRAM. Recommended ON for demo machines, OFF for
    # CI where Ollama is not running.
    OLLAMA_WARMUP_ON_STARTUP: bool = True

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        allowed = {"openai", "ollama", "gpt", "llama"}
        if v.lower() not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of {allowed}, got '{v}'")
        return v.lower()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
