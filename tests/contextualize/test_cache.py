from role2_retrieval.contextualize.cache import cache_key, load_cache, save_cache


def test_cache_key_is_deterministic():
    assert cache_key("id1", "hello") == cache_key("id1", "hello")


def test_cache_key_changes_with_text():
    assert cache_key("id1", "hello") != cache_key("id1", "world")


def test_load_missing_returns_empty(tmp_path):
    assert load_cache(str(tmp_path / "nope.json")) == {}


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / "cache.json")
    save_cache({"a": "b"}, path)
    assert load_cache(path) == {"a": "b"}
