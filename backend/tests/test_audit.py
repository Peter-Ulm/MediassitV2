from app.core.security import hash_password, create_access_token
from app.db.models import User, AuditLog
from app.schemas.api import DiagnoseResponse


def _seed(db):
    db.add(User(id="u1", email="d@x.test", name="D",
                password_hash=hash_password("DemoPass123"), role="clinician", is_active=True))
    db.commit()


def test_login_success_and_failure_are_audited(client, db_session):
    c, app = client
    _seed(db_session)
    c.post("/api/v1/auth/login", json={"username": "d@x.test", "password": "DemoPass123"})
    c.post("/api/v1/auth/login", json={"username": "d@x.test", "password": "wrong"})
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert "LOGIN_SUCCESS" in actions and "LOGIN_FAILED" in actions


def test_consultation_create_is_audited(client, db_session, monkeypatch):
    c, app = client
    _seed(db_session)
    from app.api.routes import consultations as mod
    monkeypatch.setattr(mod, "_to_diagnose_response",
                        lambda s: DiagnoseResponse(diagnoses=[], followUps=[], recommendedTests=[]))
    hdr = {"Authorization": f"Bearer {create_access_token('u1', 'clinician')}"}
    c.post("/api/v1/consultations", headers=hdr,
           json={"patient": {"age": 30, "sex": "male"}, "symptoms": "fever"})
    assert db_session.query(AuditLog).filter(AuditLog.action == "CONSULTATION_CREATE").count() == 1
