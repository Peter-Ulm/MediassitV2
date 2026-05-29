import uuid
from app.db.models import User, Consultation, AuditLog


def test_user_consultation_audit_roundtrip(db_session):
    u = User(id="u1", email="a@b.test", name="A", password_hash="x", role="clinician")
    db_session.add(u)
    db_session.commit()

    c = Consultation(
        id="c1", owner_user_id="u1", patient={"age": 30, "sex": "male"},
        symptoms="fever", results={"diagnoses": []}, notes="", status="draft",
    )
    db_session.add(c)
    db_session.add(AuditLog(user_id="u1", action="CONSULTATION_CREATE",
                            target_type="consultation", target_id="c1"))
    db_session.commit()

    assert db_session.get(User, "u1").email == "a@b.test"
    assert db_session.get(Consultation, "c1").patient["age"] == 30
    assert db_session.query(AuditLog).count() == 1
