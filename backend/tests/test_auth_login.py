from app.core.security import hash_password
from app.db.models import User


def _seed_user(db, email="dr@x.test", pw="DemoPass123", role="clinician", active=True):
    db.add(User(id="u1", email=email, name="Dr X",
                password_hash=hash_password(pw), role=role, is_active=active))
    db.commit()


def test_login_success_returns_token_and_user(client, db_session):
    c, app = client
    _seed_user(db_session)
    r = c.post("/api/v1/auth/login", json={"username": "dr@x.test", "password": "DemoPass123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and body["user"]["email"] == "dr@x.test"


def test_login_bad_password_401(client, db_session):
    c, app = client
    _seed_user(db_session)
    r = c.post("/api/v1/auth/login", json={"username": "dr@x.test", "password": "nope"})
    assert r.status_code == 401


def test_login_inactive_user_401(client, db_session):
    c, app = client
    _seed_user(db_session, active=False)
    r = c.post("/api/v1/auth/login", json={"username": "dr@x.test", "password": "DemoPass123"})
    assert r.status_code == 401
