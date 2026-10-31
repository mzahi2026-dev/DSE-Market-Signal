from fastapi.testclient import TestClient
from backend.main import app

def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

def test_empty_prices():
    with TestClient(app) as client:
        r = client.get("/prices?symbol=TESTINVALID")
        assert r.status_code == 200
        assert r.json()["rows"] == []

def test_batch_limit():
    with TestClient(app) as client:
        r = client.post("/collect?days=8")
        assert r.status_code == 400
