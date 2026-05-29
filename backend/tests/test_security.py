import time
import pytest
from app.core import security


def test_password_hash_roundtrip():
    h = security.hash_password("DemoPass123")
    assert h != "DemoPass123"
    assert security.verify_password("DemoPass123", h) is True
    assert security.verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = security.create_access_token(user_id="u1", role="clinician")
    payload = security.decode_access_token(token)
    assert payload["sub"] == "u1"
    assert payload["role"] == "clinician"


def test_expired_token_rejected():
    token = security.create_access_token(user_id="u1", role="clinician", expires_minutes=-1)
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_tampered_token_rejected():
    token = security.create_access_token(user_id="u1", role="clinician")
    with pytest.raises(security.TokenError):
        security.decode_access_token(token + "x")
