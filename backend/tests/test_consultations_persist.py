def test_consultation_persists_across_sessions(client, db_session, monkeypatch):
    c, app = client
    from app.api.routes import consultations as mod
    from app.schemas.api import DiagnoseResponse
    from app.core.security import hash_password, create_access_token
    from app.db.models import User

    db_session.add(User(id="u1", email="d@x.test", name="D",
                        password_hash=hash_password("x"), role="clinician", is_active=True))
    db_session.commit()
    hdr = {"Authorization": f"Bearer {create_access_token('u1', 'clinician')}"}

    monkeypatch.setattr(mod, "_to_diagnose_response",
                        lambda symptoms: DiagnoseResponse(diagnoses=[], followUps=[], recommendedTests=[]))

    resp = c.post("/api/v1/consultations", headers=hdr, json={
        "patient": {"age": 30, "sex": "male"}, "symptoms": "fever and chills"})
    assert resp.status_code == 200
    cid = resp.json()["id"]

    got = c.get(f"/api/v1/consultations/{cid}", headers=hdr)
    assert got.status_code == 200
    assert got.json()["symptoms"] == "fever and chills"
