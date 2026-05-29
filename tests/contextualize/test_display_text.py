from role2_retrieval.retrieval.searcher import display_text


def test_prefers_raw_text():
    assert display_text("Ch9 > ...: If fever give X", {"raw_text": "If fever give X"}) == "If fever give X"


def test_falls_back_to_document_when_no_raw_text():
    assert display_text("plain fragment", {}) == "plain fragment"
