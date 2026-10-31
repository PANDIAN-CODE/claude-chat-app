import io

MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 90 >>
stream
BT /F1 12 Tf 72 712 Td (The quick brown fox is an animal that jumps over lazy dogs) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f
trailer
<< /Size 6 /Root 1 0 R >>
startxref
0
%%EOF
"""


def _auth_header(client, email="docs@test.com"):
    client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    res = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_requires_auth(client):
    res = client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
    )
    assert res.status_code == 401


def test_reject_non_pdf(client):
    headers = _auth_header(client)
    res = client.post(
        "/api/documents/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=headers,
    )
    assert res.status_code == 400


def test_upload_and_list_document(client):
    headers = _auth_header(client, "upload@test.com")
    res = client.post(
        "/api/documents/upload",
        files={"file": ("animals.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["filename"] == "animals.pdf"

    list_res = client.get("/api/documents", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_delete_document(client):
    headers = _auth_header(client, "delete@test.com")
    upload_res = client.post(
        "/api/documents/upload",
        files={"file": ("animals.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        headers=headers,
    )
    doc_id = upload_res.json()["id"]

    del_res = client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert del_res.status_code == 204

    list_res = client.get("/api/documents", headers=headers)
    assert list_res.json() == []


def test_chat_cites_uploaded_document(client):
    headers = _auth_header(client, "rag@test.com")
    client.post(
        "/api/documents/upload",
        files={"file": ("animals.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        headers=headers,
    )

    res = client.post(
        "/api/chat/stream",
        json={"message": "What animal jumps over lazy dogs?"},
        headers=headers,
    )
    assert res.status_code == 200
    citations = res.headers.get("X-Citations")
    assert citations is not None
    import json

    parsed = json.loads(citations)
    assert len(parsed) == 1
    assert parsed[0]["filename"] == "animals.pdf"


def test_chat_no_citations_without_documents(client):
    headers = _auth_header(client, "nodocs@test.com")
    res = client.post(
        "/api/chat/stream", json={"message": "hello"}, headers=headers
    )
    assert res.status_code == 200
    import json

    assert json.loads(res.headers.get("X-Citations")) == []
