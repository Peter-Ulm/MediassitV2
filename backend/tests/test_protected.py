def test_generate_requires_auth(client):
    c, app = client
    r = c.post("/api/v1/diagnosis/generate",
               json={"symptoms": "fever", "patientMeta": {"age": 30, "sex": "male"}})
    assert r.status_code == 401


def test_list_consultations_requires_auth(client):
    c, app = client
    assert c.get("/api/v1/consultations").status_code == 401
