"""
LLM provider factory.

Reads LLM_PROVIDER from the environment and returns the configured concrete
provider, instantiated once and cached. The caller never sees which backend
is in use — the orchestrator and the FastAPI startup both depend only on the
abstract LLMProvider interface.

    LLM_PROVIDER=openai   →  hosted OpenAI (gpt-4o-mini by default)
    LLM_PROVIDER=ollama   →  local Ollama (offline, no data leaves device)

The cache matters: building OllamaProvider initialises an HTTP client; building
OpenAIProvider validates the API key. We do not want to repeat that per request.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

from role3_llm.providers.base import LLMProvider

load_dotenv()


# Map of accepted aliases → canonical key. We accept both the modern names
# and the prototype names ("gpt", "llama") so existing .env files still work.
_ALIASES = {
    "openai": "openai",
    "gpt": "openai",
    "ollama": "ollama",
    "llama": "ollama",
}


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    raw = os.getenv("LLM_PROVIDER", "ollama")
    key = _ALIASES.get(raw.lower().strip())

    # Imports are deferred so a deployment that only uses one provider does
    # not need the other's SDK installed.
    if key == "openai":
        from role3_llm.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    if key == "ollama":
        from role3_llm.providers.ollama_provider import OllamaProvider
        return OllamaProvider()

    raise ValueError(
        f"Unknown LLM_PROVIDER: '{raw}'. Set LLM_PROVIDER to "
        "'openai' or 'ollama' in your .env file."
    )
