import pytest
from fastapi.testclient import TestClient

from app import demo, telemetry
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    monkeypatch.setenv("DG_HISTORY_PATH", str(tmp_path / "h.json"))
    monkeypatch.delenv("DG_DDB_TABLE", raising=False)
    telemetry.reset()
    demo._state.update(mode="healthy", until=0.0)


def test_failing_mode_creates_real_error_rate_and_high_risk():
    assert client.post("/demo/mode", json={"mode": "failing"}).json()["mode"] == "failing"
    for _ in range(40):
        client.get("/demo/work")
    t = client.get("/metrics/self").json()
    assert t["error_rate"] > 30 and t["health_status"] == "unhealthy"
    r = client.get("/analyze", params={"error_rate": t["error_rate"], "latency_ms": t["latency_ms"],
                                       "health_status": t["health_status"]}).json()
    assert r["risk_level"] == "HIGH"


def test_slow_mode_raises_latency():
    client.post("/demo/mode", json={"mode": "slow"})
    for _ in range(3):
        client.get("/demo/work")
    assert client.get("/metrics/self").json()["latency_ms"] >= 500


def test_mode_reverts_after_ttl_and_validates(monkeypatch):
    client.post("/demo/mode", json={"mode": "failing"})
    demo._state["until"] = 0.0
    assert client.get("/demo/mode").json()["mode"] == "healthy"
    assert client.post("/demo/mode", json={"mode": "explode"}).status_code == 422


def test_config_and_diagnose_accepts_telemetry_fields(monkeypatch):
    assert "/" in client.get("/config").json()["repo"]
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from app import diagnosis
    monkeypatch.setattr(diagnosis, "load_dotenv", lambda *a, **k: None)
    diagnosis._calls.clear()
    body = {"error_rate": 50, "latency_ms": 100, "health_status": "unhealthy",
            "source": "app-telemetry", "requests": 40}
    assert client.post("/diagnose", json=body).status_code == 500  # no key: validated, reached the key check
