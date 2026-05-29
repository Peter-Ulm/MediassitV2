from role2_retrieval.contextualize.context_builder import contextualize, select_neighbors


class _FakeProvider:
    def generate(self, messages, max_tokens=120): return "Situating blurb."


def test_long_chunk_is_structural_only():
    text = " ".join(["word"] * 30)
    res = contextualize(text, {"chapter": "Chapter Five: MALARIA"}, [], provider=_FakeProvider())
    assert res.source == "structural"
    assert res.contextualized_text.startswith("Chapter Five: MALARIA:")
    assert "Situating blurb." not in res.contextualized_text


def test_thin_chunk_gets_hybrid_blurb():
    res = contextualize("Diagnostic Criteria",
                        {"chapter": "Chapter Five: MALARIA", "section": "Malaria"},
                        ["neighbour"], provider=_FakeProvider())
    assert res.source == "hybrid"
    assert "Situating blurb." in res.contextualized_text


def test_select_neighbors_same_chapter_only():
    chunks = [
        {"text": "a", "metadata": {"chapter": "C1"}},
        {"text": "b", "metadata": {"chapter": "C1"}},
        {"text": "c", "metadata": {"chapter": "C2"}},
    ]
    # index 1: neighbour 0 (C1) included, neighbour 2 (C2) excluded
    assert select_neighbors(chunks, 1, window=1) == ["a"]
