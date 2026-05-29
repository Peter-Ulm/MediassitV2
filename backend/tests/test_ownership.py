from app.core.security import hash_password, create_access_token
from app.db.models import User
from app.schemas.api import DiagnoseResponse


def _seed(db, uid, email, role="clinician"):
    db.add(User(id=uid, email=email, name=email, password_hash=hash_password("x"),
                role=role, is_active=True))
    db.commit()


def _auth(uid, role="clinician"):
    return {"Authorization": f"Bearer {create_access_token(user_id=uid, role=role)}"}


def _stub(mod, monkeypatch):
    monkeypatch.setattr(mod, "_to_diagnose_response",
                        lambda s: DiagnoseResponse(diagnoses=[], followUps=[], recommendedTests=[]))


def test_clinician_cannot_read_other_users_consultation(client, db_session, monkeypatch):
    c, app = client
    from app.api.routes import consultations as mod
    _stub(mod, monkeypatch)
    _seed(db_session, "ua", "a@x.test")
    _seed(db_session, "ub", "b@x.test")

    made = c.post("/api/v1/consultations", headers=_auth("ua"),
                  json={"patient": {"age": 30, "sex": "male"}, "symptoms": "fever"})
    assert made.status_code == 200
    cid = made.json()["id"]

    assert c.get(f"/api/v1/consultations/{cid}", headers=_auth("ua")).status_code == 200
    assert c.get(f"/api/v1/consultations/{cid}", headers=_auth("ub")).status_code == 404


def test_admin_can_read_any_consultation(client, db_session, monkeypatch):
    c, app = client
    from app.api.routes import consultations as mod
    _stub(mod, monkeypatch)
    _seed(db_session, "ua", "a@x.test")
    _seed(db_session, "adm", "admin@x.test", role="admin")

    made = c.post("/api/v1/consultations", headers=_auth("ua"),
                  json={"patient": {"age": 30, "sex": "male"}, "symptoms": "fever"})
    cid = made.json()["id"]
    assert c.get(f"/api/v1/consultations/{cid}", headers=_auth("adm")).status_code == 200
