from role2_retrieval.contextualize.context_builder import (
    build_structural_prefix,
    is_thin_chunk,
    assemble_contextualized_text,
)


def test_prefix_chapter_and_section():
    md = {"chapter": "Chapter Nine: RESPIRATORY DISEASE CONDITIONS",
          "section": "Treatment of Pneumonia"}
    assert build_structural_prefix(md) == (
        "Chapter Nine: RESPIRATORY DISEASE CONDITIONS › Treatment of Pneumonia: "
    )


def test_prefix_chapter_only():
    assert build_structural_prefix({"chapter": "Chapter Five: MALARIA"}) == "Chapter Five: MALARIA: "


def test_prefix_empty_when_no_metadata():
    assert build_structural_prefix({}) == ""


def test_thin_chunk_short_text():
    assert is_thin_chunk("Diagnostic Criteria", {}) is True


def test_thin_chunk_long_text_is_not_thin():
    text = " ".join(["word"] * 30)
    assert is_thin_chunk(text, {}) is False


def test_thin_chunk_equals_section_heading():
    text = " ".join(["Treatment", "of", "Pneumonia", "and", "more", "filler",
                      "words", "to", "exceed", "the", "twelve", "word", "limit"])
    assert is_thin_chunk(text, {"section": text}) is True


def test_assemble_with_prefix_and_blurb():
    out = assemble_contextualized_text("Chapter Five: MALARIA: ", "This is the malaria intro.", "Body text.")
    assert out == "Chapter Five: MALARIA: This is the malaria intro.\n\nBody text."


def test_assemble_no_context_returns_chunk():
    assert assemble_contextualized_text("", "", "Body text.") == "Body text."
