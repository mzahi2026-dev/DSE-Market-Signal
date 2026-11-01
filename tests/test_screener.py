from fastapi.testclient import TestClient
from backend.main import app
from backend.screener import (
    screen_stocks,
    add_to_watchlist,
    get_watchlist,
    remove_from_watchlist
)


def test_screener_scan():
    # Scan all
    res = screen_stocks()
    assert isinstance(res, list)
    if res:
        first = res[0]
        assert "symbol" in first
        assert "confidence" in first
        assert "signal" in first


def test_watchlist_operations():
    # Add GP to watchlist
    add_res = add_to_watchlist("GP", note="Core telecom holding")
    assert add_res["symbol"] == "GP"
    assert add_res["status"] == "added"

    # Retrieve watchlist
    wl = get_watchlist()
    assert len(wl) >= 1
    gp_item = next((item for item in wl if item["symbol"] == "GP"), None)
    assert gp_item is not None
    assert gp_item["note"] == "Core telecom holding"
    assert "price" in gp_item
    assert "signal" in gp_item
    assert "ai_consensus" in gp_item

    # Remove GP
    del_res = remove_from_watchlist("GP")
    assert del_res["symbol"] == "GP"
    assert del_res["status"] == "removed"


def test_api_screener_and_watchlist():
    with TestClient(app) as client:
        # Screener API
        scan_res = client.get("/screener/scan?min_confidence=30")
        assert scan_res.status_code == 200
        assert "matches" in scan_res.json()

        # Watchlist Add API
        add_res = client.post("/watchlist/add?symbol=GP&note=API_test")
        assert add_res.status_code == 200

        # Watchlist Get API
        get_res = client.get("/watchlist")
        assert get_res.status_code == 200
        assert len(get_res.json()["watchlist"]) >= 1

        # Watchlist Delete API
        del_res = client.delete("/watchlist/GP")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "removed"

        # Screener live-market and auto-sync endpoints
        lm_res = client.get("/screener/live-market?top_n=3")
        assert lm_res.status_code == 200
        assert "stocks" in lm_res.json()


