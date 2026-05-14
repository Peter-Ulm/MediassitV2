"""
OpenAI provider for MediAssist.

Uses the modern Chat Completions JSON-mode (response_format={"type":"json_object"})
which is supported by gpt-4o-mini, gpt-4o, and the gpt-4-turbo family. JSON mode
removes a whole class of Gatekeeper failures because the API itself refuses to
return anything but a parseable JSON object.

Defaults:
    OPENAI_MODEL = "gpt-4o-mini"
        gpt-4o-mini is OpenAI's current price/performance pick: cheaper per token
        than the retired gpt-3.5-turbo, smarter, and supports native JSON mode.
        Set OPENAI_MODEL=gpt-4o for the higher-quality (but pricier) tier.
"""

from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

from role3_llm.providers.base import LLMProvider

load_dotenv()


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions backend with JSON-mode enforcement."""

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("sk-replace"):
            raise ValueError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and "
                "fill in your real OpenAI key. Get one at "
                "https://platform.openai.com/api-keys."
            )

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def generate(self, messages: List[dict], max_tokens: int = 1000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        if response.choices[0].finish_reason == "length":
            print(
                f"Warning: {self.model} response was cut off at "
                f"max_tokens={max_tokens}. JSON is likely incomplete."
            )

        return response.choices[0].message.content

    def health_check(self) -> bool:
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
