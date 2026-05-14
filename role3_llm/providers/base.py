"""
Abstract base class for LLM providers.

This file defines the interface that every LLM backend must satisfy. The
orchestrator (role3/main.py) calls `provider.generate(messages)` and
`provider.health_check()` without knowing — or caring — which concrete
backend is active. Switching from OpenAI (development) to a local Ollama
model (production) is a one-character change in `.env`, with zero changes
to any pipeline code.

This is the Strategy pattern from Stage 6.1 of the reference document.
LLMProvider plays the role of the strategy interface; GPTProvider and
LlamaProvider (in sibling files) are concrete strategies that fulfil it.

How the contract is enforced:
    Methods marked with @abstractmethod cannot have a default implementation.
    Any subclass that fails to override every @abstractmethod is impossible
    to instantiate — Python raises TypeError at construction time. This
    means a teammate cannot accidentally ship a provider that is missing a
    required method; the test for "is the contract satisfied?" runs the
    moment they write `MyProvider()`.
"""

from abc import ABC, abstractmethod
from typing import List


class LLMProvider(ABC):
    """
    Interface every concrete LLM provider must implement.

    Subclasses must implement `generate` and `health_check`. The third
    method, `get_provider_name`, is concrete — it is inherited as-is and
    rarely needs to be overridden.
    """

    @abstractmethod
    def generate(self, messages: List[dict], max_tokens: int = 1000) -> str:
        """
        Send chat messages to the LLM and return its raw text response.

        Args:
            messages:   List of message dicts in OpenAI chat format. Each
                        dict has at least "role" and "content" keys, e.g.
                            {"role": "system",  "content": "You are a..."},
                            {"role": "user",    "content": "Patient has..."}
            max_tokens: Hard ceiling on tokens the model may generate. The
                        model stops at this number even if the JSON it was
                        producing is incomplete — which is why the parser
                        in Phase 4 must check `finish_reason == "length"`
                        and treat such responses as failures.

        Returns:
            The model's raw text output. May contain markdown code fences,
            explanatory prose before or after the JSON, or trailing commas.
            The parser (role3/parser.py, Phase 4) is responsible for
            cleaning and validating this string into a DiagnosticResponse.
        """
        # Abstract methods have no body — `pass` is a syntactic placeholder.
        # Concrete subclasses provide the real implementation.
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Verify the provider is reachable and responsive.

        Called by the orchestrator at the start of every pipeline run. If
        this returns False, we serve the fallback response immediately
        rather than firing a main request that will fail seconds later.

        Implementations should be cheap — a tiny "ping" call, not a full
        diagnostic generation — because this runs on every request.

        Returns:
            True  if the provider responds successfully to a minimal probe.
            False on any error: network, auth, server down, or otherwise.
                  Implementations should NOT raise — they should catch
                  every exception and return False.
        """
        pass

    def get_provider_name(self) -> str:
        """
        Return the concrete provider's class name for logging.

        This is a concrete (non-abstract) method on the base class. Every
        subclass inherits it for free; output is automatically the
        subclass's own name (e.g. "GPTProvider", "LlamaProvider"). Used
        in parser failure logs and the Phase 7 benchmark report to record
        which backend produced a given response.
        """
        # __class__ refers to the actual concrete class of the instance,
        # so this method "knows" whether it is being called on a GPTProvider
        # or a LlamaProvider without any per-subclass code.
        return self.__class__.__name__
