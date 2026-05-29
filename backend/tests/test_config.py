from app.core.config import Settings


def test_db_and_jwt_settings_have_defaults(monkeypatch):
    for k in ("DATABASE_URL", "JWT_SECRET", "JWT_EXPIRE_MINUTES", "JWT_ALGORITHM"):
        monkeypatch.delenv(k, raising=False)
    s = Settings()
    assert s.DATABASE_URL.startswith("sqlite:///")
    assert s.JWT_ALGORITHM == "HS256"
    assert s.JWT_EXPIRE_MINUTES == 480
    assert isinstance(s.JWT_SECRET, str) and len(s.JWT_SECRET) > 0
