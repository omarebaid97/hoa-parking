def test_docs_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_noindex_header_present(client):
    resp = client.get("/")
    assert resp.headers.get("x-robots-tag", "").startswith("noindex")


def test_noindex_meta_tag_present(client):
    resp = client.get("/")
    assert 'name="robots" content="noindex' in resp.text


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
