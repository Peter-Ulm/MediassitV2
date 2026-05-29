import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # repo root
from scripts.create_user import create_user
from app.db.models import User
from app.core.security import verify_password


def test_create_user_persists_hashed(db_session):
    create_user(db_session, email="admin@x.test", name="Admin",
                password="StrongPass1", role="admin")
    u = db_session.query(User).filter(User.email == "admin@x.test").first()
    assert u is not None and u.role == "admin"
    assert u.password_hash != "StrongPass1"
    assert verify_password("StrongPass1", u.password_hash)
