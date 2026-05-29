from app.db.models import User
from app.services import users


def test_seed_demo_creates_clinician_and_admin(db_session, monkeypatch):
    # Point the seed at the in-memory test session.
    import scripts.seed_demo as sd
    monkeypatch.setattr(sd, "init_db", lambda: None)
    monkeypatch.setattr(sd, "SessionLocal", lambda: db_session)
    # Prevent the test session from being closed by the script.
    monkeypatch.setattr(db_session, "close", lambda: None)

    sd.main()

    emails = {u.email: u.role for u in db_session.query(User).all()}
    assert emails.get("dr.demo@mediassist.test") == "clinician"
    assert emails.get("admin.demo@mediassist.test") == "admin"
