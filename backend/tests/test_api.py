import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = tmp_path / "blackout.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + database.as_posix())
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health_and_protocols(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    protocols = client.get("/protocols")
    assert protocols.status_code == 200
    names = {item["id"] for item in protocols.json()["protocols"]}
    assert names == {"aave-v3", "compound-v3"}


def test_demo_portfolio_and_history(client):
    response = client.get("/portfolio/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] is True
    assert body["data_quality"] == "demo"
    assert body["summary"]["worst_account_key"] == "arbitrum:aave-v3:core"
    assert body["summary"]["worst_health_factor"] == pytest.approx(1.1)
    assert body["positions"]
    assert any(alert["code"] == "health_high" for alert in body["alerts"])

    positions = client.get("/portfolio/demo/positions")
    assert positions.status_code == 200
    assert positions.json()["positions"]

    risk = client.get("/portfolio/demo/risk")
    assert risk.status_code == 200
    assert any(item["id"] == "eth_plus_20" for item in risk.json()["stress"])

    alerts = client.get("/portfolio/demo/alerts")
    assert alerts.status_code == 200
    assert alerts.json()["alerts"]

    history = client.get("/portfolio/demo/history")
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_invalid_address(client):
    response = client.get("/portfolio/not-a-wallet")
    assert response.status_code == 400


def test_watchlist(client):
    created = client.post(
        "/watchlist",
        json={"address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045", "label": "Example"},
    )
    assert created.status_code == 200
    assert created.json()["label"] == "Example"
    listed = client.get("/watchlist")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    removed = client.delete("/watchlist/" + created.json()["address"])
    assert removed.status_code == 204
    assert client.get("/watchlist").json() == []
