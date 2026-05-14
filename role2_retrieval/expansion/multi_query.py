"""
expansion/multi_query.py
------------------------
Stage 4.3 — LLM-Based Multi-Query Generation

Instead of searching with one query, we generate N clinical reformulations
of the same symptom description, search with all of them, and merge the
results. This dramatically improves recall — especially for symptoms that
could be described in multiple ways.

Example:
    Input:  "patient has fever and cannot walk"
    Output: [
        "patient has fever and cannot walk",                    ← original
        "high temperature with mobility impairment",            ← variant 1
        "pyrexia with inability to ambulate or leg weakness",   ← variant 2
    ]
"""

from __future__ import annotations
import json
import os

from role2_retrieval.utils.config import config
from role2_retrieval.utils.logger import get_logger

log = get_logger(__name__)


MULTI_QUERY_SYSTEM_PROMPT = """You are a medical query reformulation assistant for a clinical decision support system
serving Tanzanian healthcare facilities.

Your task: Given a clinical symptom description, generate {n} alternative phrasings of the same
symptoms using proper medical terminology. Each reformulation should:
- Describe the SAME symptoms as the original
- Use different clinical vocabulary (e.g. replace lay terms with medical terms)
- Be useful for searching Tanzania Standard Treatment Guidelines

IMPORTANT: Respond ONLY with a valid JSON object. No other text.
Format:
{{
  "variants": [
    "reformulation 1",
    "reformulation 2"
  ]
}}"""


def _call_openai(prompt: str, n: int) -> list[str]:
    """Call OpenAI GPT to generate query variants."""
    from openai import OpenAI

    client = OpenAI(api_key=config.openai_api_key)
    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {
                "role": "system",
                "content": MULTI_QUERY_SYSTEM_PROMPT.format(n=n),
            },
            {
                "role": "user",
                "content": f"Original symptom description: {prompt}\n\nGenerate {n} reformulations.",
            },
        ],
        temperature=0.4,       # slightly creative but clinically grounded
        max_tokens=400,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    return data.get("variants", [])


def _call_ollama(prompt: str, n: int) -> list[str]:
    """Call local Ollama (Llama 3) to generate query variants."""
    import requests

    payload = {
        "model": config.ollama_model,
        "messages": [
            {
                "role": "system",
                "content": MULTI_QUERY_SYSTEM_PROMPT.format(n=n),
            },
            {
                "role": "user",
                "content": (
                    f"Original symptom description: {prompt}\n\n"
                    f"Generate {n} reformulations. Respond ONLY with JSON."
                ),
            },
        ],
        "stream": False,
        "format": "json",
    }
    resp = requests.post(
        f"{config.ollama_base_url}/api/chat",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"]
    data = json.loads(content)
    return data.get("variants", [])


def generate_query_variants(query: str, n: int | None = None) -> list[str]:
    """
    Generate n clinical reformulations of the input query.

    Args:
        query: Expanded symptom description (output of expand_with_synonyms).
        n:     Number of variants to generate. Defaults to config.multi_query_count.

    Returns:
        List of variant strings (does NOT include the original — callers
        should prepend it themselves, as pipeline.py does).
    """
    n = n or config.multi_query_count

    log.info(f"Generating {n} query variants for: '{query[:60]}'")

    try:
        if config.llm_provider == "gpt":
            variants = _call_openai(query, n)
        else:
            variants = _call_ollama(query, n)

        # Safety: filter empty strings and truncate to n
        variants = [v.strip() for v in variants if v.strip()][:n]
        log.info(f"Generated {len(variants)} variants.")
        return variants

    except Exception as exc:
        # Multi-query is an enhancement — if it fails, degrade gracefully.
        log.warning(f"Multi-query generation failed ({exc}). Using original query only.")
        return []