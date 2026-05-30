"""
Local Ollama provider for MediAssist.

Why this file is rewritten compared to the prototype:
    The prototype reused OpenAI's HTTP client against Ollama's /v1 compatibility
    layer. That works, but it forfeits Ollama's native features that matter
    for our latency target:

      * `format="json"`         — server-side JSON enforcement, eliminating
                                  a whole class of Gatekeeper failures.
      * `keep_alive="30m"`      — keeps the model resident in RAM/VRAM so the
                                  second-and-onwards call skips the 5-15 s
                                  cold-start.
      * `options.num_predict`   — explicit output cap.
      * `options.num_ctx`       — explicit context window, lets us size the
                                  KV cache to what we actually need.

    Calling Ollama's native /api/chat endpoint via the `ollama` Python package
    gives us all of the above and is simpler than the OpenAI-compat shim.

Defaults:
    OLLAMA_MODEL     = "llama3.2:3b"
        ~2 GB, fits in CPU RAM comfortably and is roughly 3x faster than the
        7B at JSON-structured clinical reasoning — the right default for the
        CPU-only target machine. For maximum reasoning depth (slower), set
        OLLAMA_MODEL=mistral:7b-instruct after `ollama pull mistral:7b-instruct`.

    OLLAMA_KEEP_ALIVE = "30m"
        Keeps the model warm for half an hour after the last call. Without
        this, the model unloads after the default 5 minutes and the next
        request pays the full cold-start cost.

Hardware note:
    Ollama auto-detects CUDA / Metal / ROCm. If your laptop has an Nvidia
    GPU with >= 4 GB VRAM, the 7B model will run on it without configuration
    and be roughly 5-10x faster than CPU-only mode. Verify with:
        ollama ps
"""

from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv
import ollama

from role3_llm.providers.base import LLMProvider

load_dotenv()


class OllamaProvider(LLMProvider):
    """Native-API Ollama backend optimised for latency and JSON reliability."""

    def __init__(self, host: str | None = None) -> None:
        resolved_host = (
            host
            or os.getenv("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        )
        # strip any trailing /v1 left over from old OpenAI-compat configs
        if resolved_host.endswith("/v1"):
            resolved_host = resolved_host[: -len("/v1")]

        self.host = resolved_host
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
        self.num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

        # Client is cheap to construct; cache once so the underlying httpx
        # connection pool is reused across calls.
        self._client = ollama.Client(host=self.host)

    def _installed_model_names(self) -> set[str]:
        """Return installed Ollama model names across ollama-python versions."""
        listing = self._client.list()
        models = listing.get("models", []) if isinstance(listing, dict) else getattr(listing, "models", [])

        names: set[str] = set()
        for model in models:
            if isinstance(model, dict):
                name = model.get("name") or model.get("model")
            else:
                name = getattr(model, "name", None) or getattr(model, "model", None)
            if name:
                names.add(str(name))
        return names

    def generate(self, messages: List[dict], max_tokens: int = 1000) -> str:
        """
        Generate a JSON response from the local model.

        Notes on the parameters:
          format="json"          — Ollama enforces valid JSON on the server.
          keep_alive             — model stays loaded for 30 minutes.
          options.num_predict    — output token cap (mirrors OpenAI max_tokens).
          options.num_ctx        — input + output context window.
          options.temperature    — 0.0 for clinical reproducibility.
        """
        response = self._client.chat(
            model=self.model,
            messages=messages,
            format="json",
            keep_alive=self.keep_alive,
            options={
                "temperature": 0.0,
                "num_predict": max_tokens,
                "num_ctx": self.num_ctx,
            },
        )
        return response["message"]["content"]

    def health_check(self) -> bool:
        """
        Cheap probe: list installed models and verify the configured model is
        present. No inference. Fast.

        We intentionally do NOT call generate() here — the orchestrator should
        not pay 5-15 s of cold-start cost just to check whether Ollama is up.
        """
        try:
            return self.model in self._installed_model_names()
        except Exception:
            return False

    def warmup(self) -> None:
        """
        Optional preload: load the model into RAM/VRAM before the first request.

        Calling /api/generate with no prompt and keep_alive set is Ollama's
        documented way to preload. Call this at FastAPI startup so the first
        doctor request doesn't pay cold-start.
        """
        try:
            self._client.generate(
                model=self.model,
                prompt="",
                keep_alive=self.keep_alive,
            )
        except Exception:
            # Warmup is best-effort. Real failures will surface on the first
            # generate() call with a useful exception.
            pass
