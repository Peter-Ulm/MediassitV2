from role2_retrieval.contextualize.context_builder import generate_llm_blurb


class _FakeProvider:
    def __init__(self, reply): self._reply = reply
    def generate(self, messages, max_tokens=120): return self._reply


class _BoomProvider:
    def generate(self, messages, max_tokens=120): raise RuntimeError("llm down")


def test_blurb_returns_cleaned_text():
    out = generate_llm_blurb("Diagnostic Criteria", ["neighbour text"],
                             provider=_FakeProvider("  This section lists\n malaria criteria.  "))
    assert out == "This section lists malaria criteria."


def test_blurb_failure_returns_empty_string():
    assert generate_llm_blurb("x", [], provider=_BoomProvider()) == ""
