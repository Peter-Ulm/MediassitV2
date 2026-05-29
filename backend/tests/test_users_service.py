import pytest
from app.services import users
from app.core.security import verify_password


def test_create_user_hashes_and_persists(db_session):
    u = users.create_user(db_session, email="a@x.test", name="A", password="StrongPass1", role="clinician")
    assert u.password_hash != "StrongPass1"
    assert verify_password("StrongPass1", u.password_hash)
    assert u.role == "clinician" and u.is_active is True


def test_create_user_duplicate_email_raises(db_session):
    users.create_user(db_session, email="a@x.test", name="A", password="StrongPass1", role="clinician")
    with pytest.raises(ValueError):
        users.create_user(db_session, email="a@x.test", name="B", password="StrongPass1", role="clinician")


def test_create_user_bad_role_raises(db_session):
    with pytest.raises(ValueError):
        users.create_user(db_session, email="b@x.test", name="B", password="StrongPass1", role="superuser")


def test_set_active_and_set_role(db_session):
    u = users.create_user(db_session, email="c@x.test", name="C", password="StrongPass1", role="clinician")
    assert users.set_active(db_session, u.id, False).is_active is False
    assert users.set_role(db_session, u.id, "admin").role == "admin"


def test_set_role_invalid_raises(db_session):
    u = users.create_user(db_session, email="d@x.test", name="D", password="StrongPass1", role="clinician")
    with pytest.raises(ValueError):
        users.set_role(db_session, u.id, "wizard")


def test_reset_password_changes_hash(db_session):
    u = users.create_user(db_session, email="e@x.test", name="E", password="StrongPass1", role="clinician")
    users.reset_password(db_session, u.id, "NewPass2")
    assert verify_password("NewPass2", db_session.get(type(u), u.id).password_hash)


def test_missing_user_raises_usernotfound(db_session):
    with pytest.raises(users.UserNotFound):
        users.set_active(db_session, "nope", True)


def test_create_user_short_password_raises(db_session):
    with pytest.raises(ValueError):
        users.create_user(db_session, email="short@x.test", name="S", password="abc", role="clinician")


def test_reset_password_short_raises(db_session):
    u = users.create_user(db_session, email="r@x.test", name="R", password="StrongPass1", role="clinician")
    with pytest.raises(ValueError):
        users.reset_password(db_session, u.id, "abc")
