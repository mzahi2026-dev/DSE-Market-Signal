from fastapi.testclient import TestClient
from backend.main import app
from pathlib import Path


def test_frontend_files_exist():
    frontend_dir = Path("frontend")
    assert (frontend_dir / "index.html").exists()
    assert (frontend_dir / "styles.css").exists()
    assert (frontend_dir / "app.js").exists()


def test_frontend_serving():
    with TestClient(app) as client:
        res = client.get("/")
        assert res.status_code == 200
        html = res.text
        # Verify TradingView-style components
        assert 'id="left-sidebar"' in html
        assert 'id="right-sidebar"' in html
        assert 'id="toggle-left"' in html
        assert 'id="toggle-right"' in html
        assert 'id="health-badge"' in html
        assert 'id="market-status"' in html
        assert 'id="chart-container"' in html
        assert 'id="priceChart"' in html


def test_frontend_static_assets():
    with TestClient(app) as client:
        css = client.get("/styles.css")
        assert css.status_code == 200
        assert "--bg-primary" in css.text

        js = client.get("/app.js")
        assert js.status_code == 200
        assert "setupSidebarToggles" in js.text

