from role2_retrieval.utils.config import Config


def test_use_hybrid_defaults_false(monkeypatch):
    monkeypatch.delenv("USE_HYBRID", raising=False)
    assert Config().use_hybrid is False


def test_use_hybrid_env_override(monkeypatch):
    monkeypatch.setenv("USE_HYBRID", "true")
    assert Config().use_hybrid is True
