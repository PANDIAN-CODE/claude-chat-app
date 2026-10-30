def test_register_and_login(client):
    res = client.post("/api/auth/register", json={"email": "a@test.com", "password": "secret123"})
    assert res.status_code == 201
    assert res.json()["email"] == "a@test.com"

    res2 = client.post("/api/auth/login", json={"email": "a@test.com", "password": "secret123"})
    assert res2.status_code == 200
    assert "access_token" in res2.json()


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "b@test.com", "password": "secret123"})
    res = client.post("/api/auth/login", json={"email": "b@test.com", "password": "wrong"})
    assert res.status_code == 401


def test_duplicate_register(client):
    client.post("/api/auth/register", json={"email": "c@test.com", "password": "secret123"})
    res = client.post("/api/auth/register", json={"email": "c@test.com", "password": "secret123"})
    assert res.status_code == 400


def test_protected_route_requires_token(client):
    res = client.get("/api/chat/conversations")
    assert res.status_code == 401
