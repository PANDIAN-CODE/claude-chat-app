def _auth_header(client, email="chat@test.com"):
    client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    res = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_chat_stream_requires_auth(client):
    res = client.post("/api/chat/stream", json={"message": "hi"})
    assert res.status_code == 401


def test_chat_stream_mock_mode_creates_conversation(client):
    headers = _auth_header(client)
    res = client.post("/api/chat/stream", json={"message": "hello"}, headers=headers)
    assert res.status_code == 200
    assert "hello" in res.text.lower()
    assert "X-Conversation-Id" in res.headers


def test_conversation_list_and_history(client):
    headers = _auth_header(client, "history@test.com")
    stream_res = client.post("/api/chat/stream", json={"message": "hello there"}, headers=headers)
    conv_id = int(stream_res.headers["X-Conversation-Id"])

    list_res = client.get("/api/chat/conversations", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    messages_res = client.get(f"/api/chat/conversations/{conv_id}/messages", headers=headers)
    assert messages_res.status_code == 200
    roles = [m["role"] for m in messages_res.json()]
    assert roles == ["user", "assistant"]


def test_conversation_isolated_per_user(client):
    headers_a = _auth_header(client, "user-a@test.com")
    client.post("/api/chat/stream", json={"message": "hi from a"}, headers=headers_a)

    headers_b = _auth_header(client, "user-b@test.com")
    res = client.get("/api/chat/conversations", headers=headers_b)
    assert res.json() == []


def test_cannot_access_other_users_conversation(client):
    headers_a = _auth_header(client, "owner@test.com")
    stream_res = client.post("/api/chat/stream", json={"message": "secret"}, headers=headers_a)
    conv_id = int(stream_res.headers["X-Conversation-Id"])

    headers_b = _auth_header(client, "intruder@test.com")
    res = client.get(f"/api/chat/conversations/{conv_id}/messages", headers=headers_b)
    assert res.status_code == 404
