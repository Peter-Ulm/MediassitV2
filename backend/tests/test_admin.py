from app.core.security import hash_password, create_access_token
from app.db.models import User, AuditLog
from app.services import users


def _seed(db, uid, email, role):
    db.add(User(id=uid, email=email, name=email, password_hash=hash_password("StrongPass1"),
                role=role, is_active=True))
    db.commit()


def _auth(uid):
    return {"Authorization": f"Bearer {create_access_token(user_id=uid, role='x')}"}


def test_admin_routes_require_admin(client, db_session):
    c, app = client
    _seed(db_session, "clin", "clin@x.test", "clinician")
    assert c.get("/api/v1/admin/users").status_code == 401
    assert c.get("/api/v1/admin/users", headers=_auth("clin")).status_code == 403


def test_admin_can_create_list_and_audit(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    r = c.post("/api/v1/admin/users", headers=_auth("adm"),
               json={"email": "new@x.test", "name": "New", "password": "StrongPass1", "role": "clinician"})
    assert r.status_code == 200 and r.json()["email"] == "new@x.test"
    assert "password_hash" not in r.json()
    listing = c.get("/api/v1/admin/users", headers=_auth("adm")).json()
    assert any(u["email"] == "new@x.test" for u in listing)
    assert db_session.query(AuditLog).filter(AuditLog.action == "USER_CREATE").count() == 1


def test_duplicate_email_rejected(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    body = {"email": "dup@x.test", "name": "D", "password": "StrongPass1", "role": "clinician"}
    assert c.post("/api/v1/admin/users", headers=_auth("adm"), json=body).status_code == 200
    assert c.post("/api/v1/admin/users", headers=_auth("adm"), json=body).status_code == 400


def test_patch_deactivate_and_role(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    target = users.create_user(db_session, email="t@x.test", name="T", password="StrongPass1", role="clinician")
    assert c.patch(f"/api/v1/admin/users/{target.id}", headers=_auth("adm"),
                   json={"isActive": False}).json()["isActive"] is False
    assert c.patch(f"/api/v1/admin/users/{target.id}", headers=_auth("adm"),
                   json={"role": "admin"}).json()["role"] == "admin"


def test_reset_password_lets_user_log_in(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    target = users.create_user(db_session, email="t2@x.test", name="T2", password="OldPass1", role="clinician")
    assert c.post(f"/api/v1/admin/users/{target.id}/reset-password", headers=_auth("adm"),
                  json={"password": "BrandNew2"}).status_code == 200
    assert c.post("/api/v1/auth/login", json={"username": "t2@x.test", "password": "BrandNew2"}).status_code == 200


def test_admin_cannot_lock_self_out(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    assert c.patch("/api/v1/admin/users/adm", headers=_auth("adm"), json={"isActive": False}).status_code == 400
    assert c.patch("/api/v1/admin/users/adm", headers=_auth("adm"), json={"role": "clinician"}).status_code == 400


def test_create_user_short_password_400(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    r = c.post("/api/v1/admin/users", headers=_auth("adm"),
               json={"email": "short@x.test", "name": "S", "password": "abc", "role": "clinician"})
    assert r.status_code == 400


def test_reset_password_short_400(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    target = users.create_user(db_session, email="rp@x.test", name="RP", password="StrongPass1", role="clinician")
    r = c.post(f"/api/v1/admin/users/{target.id}/reset-password", headers=_auth("adm"), json={"password": "abc"})
    assert r.status_code == 400
