"""
Token counting utility for MediAssist.

LLMs have a hard maximum on input size (context window). Sending more than
that produces one of two failure modes:

    1. Hard rejection — API returns "context_length_exceeded".
    2. Silent truncation — the model sees only the first N tokens and
       produces a confused answer with no warning. This is the most
       dangerous failure mode in the system, because the output looks
       valid to a doctor but was generated from incomplete input.

To prevent both, the orchestrator (role3/main.py) calls count_tokens()
before every provider.generate() call. If the count exceeds our budget,
we return the fallback response instead of firing a doomed request.

Token budget (sized for the smallest supported model — mistral:7b-instruct
and llama3.x both expose an 8,192-token context window):

    System prompt:        300 tokens
    Retrieved guidelines: 4,000 tokens
    Patient data:         500 tokens
    Output space:         1,000 tokens
    -------------------------------------
    Total:                5,800 tokens (under the 8k context ceiling)

For gpt-4o-mini and llama3.2 (both 128k context) we have far more headroom,
but we keep the budget conservative so a single tuning change in the .env
can swap models without overflowing.

The function below counts only the INPUT portion. Output space is reserved
separately by setting max_tokens on the LLM call itself.
"""

from typing import List

import tiktoken


# Each chat message is wrapped by the API in a small JSON envelope of the form
# {"role": "...", "content": "..."}. That envelope costs roughly four tokens
# regardless of content length. This figure comes from OpenAI's official
# "How to count tokens" cookbook. Naming it as a constant makes the formula
# self-documenting where it's used below.
_PER_MESSAGE_OVERHEAD_TOKENS = 4


def count_tokens(messages: List[dict], model: str = "gpt-4o-mini") -> int:
    """
    Count the total input tokens a list of chat messages will consume.

    The default tokenizer is gpt-4o-mini's (o200k_base). Mistral and Llama use
    different tokenizers, but o200k_base produces a count that is within a few
    percent of theirs — close enough for context-window guarding.

    Args:
        messages: List of message dicts in OpenAI chat format.
        model:    Model name passed to tiktoken.encoding_for_model.

    Returns:
        Total token count including per-message envelope overhead.

    Raises:
        KeyError: If any message dict is missing the "content" key. We do not
                  catch this — failing loudly here is safer than miscounting.
    """
    try:
        encoder = tiktoken.encoding_for_model(model)
    except KeyError:
        # Unknown model name (e.g. an Ollama-only model). Fall back to the
        # encoder gpt-4o-mini uses — close enough for sizing purposes.
        encoder = tiktoken.get_encoding("o200k_base")

    total = 0
    for message in messages:
        # Add the fixed envelope cost first — paid once per message regardless
        # of how short or long the content is.
        total += _PER_MESSAGE_OVERHEAD_TOKENS

        # Then count the tokens inside the actual content string.
        total += len(encoder.encode(message["content"]))

    return total
