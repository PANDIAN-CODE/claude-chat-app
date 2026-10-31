import services.usage_service as usage_service


def _auth_header(client, email="usage@test.com"):
    client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    res = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_usage_endpoint_starts_empty(client):
    headers = _auth_header(client)
    res = client.get("/api/chat/usage", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_usage_recorded_after_chat(client):
    headers = _auth_header(client, "usage2@test.com")
    client.post("/api/chat/stream", json={"message": "hello"}, headers=headers)

    res = client.get("/api/chat/usage", headers=headers)
    assert res.status_code == 200
    # mock mode still records a usage row, with zero cost/tokens
    assert len(res.json()) == 1
    assert res.json()[0]["cost_usd"] == 0.0


def test_rate_limit_blocks_after_threshold(client, monkeypatch):
    monkeypatch.setattr(usage_service, "RATE_LIMIT_MAX_MESSAGES", 2)
    headers = _auth_header(client, "ratelimited@test.com")

    r1 = client.post("/api/chat/stream", json={"message": "one"}, headers=headers)
    r2 = client.post("/api/chat/stream", json={"message": "two"}, headers=headers)
    r3 = client.post("/api/chat/stream", json={"message": "three"}, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
