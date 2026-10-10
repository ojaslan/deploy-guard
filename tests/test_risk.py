import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    monkeypatch.setenv("DG_HISTORY_PATH", str(tmp_path / "history.json"))


def analyze(er, lat, hs):
    r = client.get("/analyze", params={"error_rate": er, "latency_ms": lat, "health_status": hs})
    assert r.status_code == 200
    return r.json()


@pytest.mark.parametrize(
    "er, lat, hs, score, level",
    [
        (0.5, 120, "healthy", 2, "LOW"),
        (7.25, 200, "healthy", 29, "LOW"),
        (7.5, 200, "healthy", 30, "MEDIUM"),
        (2.0, 850, "healthy", 38, "MEDIUM"),
        (12.0, 300, "healthy", 45, "MEDIUM"),
        (0.0, 100, "unhealthy", 30, "MEDIUM"),
        (10.0, 200, "unhealthy", 70, "HIGH"),
        (12.0, 1200, "unhealthy", 100, "HIGH"),
        (100.0, 120000, "unhealthy", 100, "HIGH"),
    ],
)
def test_risk_scoring(er, lat, hs, score, level):
    d = analyze(er, lat, hs)
    assert d["risk_score"] == pytest.approx(score, abs=0.05)
    assert d["risk_level"] == level


def test_shape_and_history():
    d = analyze(2.0, 150, "healthy")
    for k in ("risk_score", "risk_level", "metrics", "recommendation"):
        assert k in d
    assert len(client.get("/history").json()) == 1


def test_validation():
    assert client.get("/analyze", params={"error_rate": -1, "latency_ms": 1}).status_code == 422
    assert client.get("/analyze", params={"error_rate": 1, "latency_ms": 1, "health_status": "x"}).status_code == 422


def test_health_and_simulate():
    assert client.get("/health").status_code == 200
    for s in ("normal", "error", "slow"):
        assert client.get("/simulate", params={"scenario": s}).json()["simulated"] is True
