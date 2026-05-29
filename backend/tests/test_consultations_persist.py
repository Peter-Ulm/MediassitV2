def test_consultation_persists_across_sessions(client, monkeypatch):
    c, app = client
    # Stub the LLM pipeline so no Ollama call happens.
    from app.api.routes import consultations as mod
    from app.schemas.api import DiagnoseResponse

    monkeypatch.setattr(mod, "_to_diagnose_response",
                        lambda symptoms: DiagnoseResponse(
                            diagnoses=[], followUps=[], recommendedTests=[]))

    resp = c.post("/api/v1/consultations", json={
        "patient": {"age": 30, "sex": "male"}, "symptoms": "fever and chills"})
    assert resp.status_code == 200
    cid = resp.json()["id"]

    got = c.get(f"/api/v1/consultations/{cid}")
    assert got.status_code == 200
    assert got.json()["symptoms"] == "fever and chills"
