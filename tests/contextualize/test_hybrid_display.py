from role2_retrieval.expansion.hybrid import HybridSearcher


def test_sparse_search_returns_raw_text():
    hs = HybridSearcher(
        chunk_texts=["Chapter Five: MALARIA: blurb about fever and malaria treatment"],
        chunk_ids=["c1"],
        chunk_metadata=[{"raw_text": "fever and malaria treatment"}],
    )
    out = hs.sparse_search("fever malaria", k=1)
    assert out[0].text == "fever and malaria treatment"
