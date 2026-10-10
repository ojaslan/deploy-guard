import pytest
from fastapi.testclient import TestClient

from app import cloudwatch, rollback
from app.main import app

client = TestClient(app)
H = {"X-Admin-Token": "secret"}


def test_rollback_disabled_without_token(monkeypatch):
    monkeypatch.delenv("DEPLOYGUARD_ADMIN_TOKEN", raising=False)
    assert client.post("/rollback", json={"version_label": "v1"}).status_code == 403
    assert client.get("/rollback/versions").status_code == 403


def test_rollback_wrong_token(monkeypatch):
    monkeypatch.setenv("DEPLOYGUARD_ADMIN_TOKEN", "secret")
    assert client.post("/rollback", json={"version_label": "v1"}, headers={"X-Admin-Token": "bad"}).status_code == 401


class FakeEB:
    def __init__(self):
        self.updated = None

    def describe_environments(self, **kw):
        return {"Environments": [{"ApplicationName": "deployguard", "VersionLabel": "v2"}]}

    def describe_application_versions(self, **kw):
        from datetime import datetime
        return {"ApplicationVersions": [
            {"VersionLabel": "v1", "DateCreated": datetime(2026, 1, 1)},
            {"VersionLabel": "v2", "DateCreated": datetime(2026, 2, 1)}]}

    def update_environment(self, **kw):
        self.updated = kw


def test_rollback_dry_run_and_confirm(monkeypatch):
    monkeypatch.setenv("DEPLOYGUARD_ADMIN_TOKEN", "secret")
    fake = FakeEB()
    monkeypatch.setattr(rollback, "_eb", lambda: (fake, "deployguard-env"))
    r = client.post("/rollback", json={"version_label": "v1"}, headers=H)
    assert r.json()["executed"] is False and fake.updated is None
    v = client.get("/rollback/versions", headers=H).json()
    assert v["current_version"] == "v2" and v["available_versions"] == ["v2", "v1"]
    r = client.post("/rollback", json={"version_label": "v1", "confirm": True}, headers=H)
    assert r.json()["executed"] is True
    assert fake.updated == {"EnvironmentName": "deployguard-env", "VersionLabel": "v1"}


def test_cloudwatch_math(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("EB_ENVIRONMENT_NAME", "e")
    monkeypatch.setattr(cloudwatch, "_query", lambda *a: {
        "total": [50, 50], "err5xx": [5, 5], "p90": [0.2, 0.5], "health": [0, 1]})
    d = client.get("/metrics/live").json()
    assert d["error_rate"] == 10.0 and d["latency_ms"] == 500.0 and d["health_status"] == "healthy"
    monkeypatch.setattr(cloudwatch, "_query", lambda *a: {
        "total": [10], "err5xx": [0], "p90": [0.1], "health": [20]})
    assert client.get("/metrics/live").json()["health_status"] == "unhealthy"


def test_cloudwatch_no_data(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("EB_ENVIRONMENT_NAME", "e")
    monkeypatch.setattr(cloudwatch, "_query", lambda *a: {})
    assert client.get("/metrics/live").status_code == 404


def test_diagnose_rate_limit_and_missing_key(monkeypatch):
    from app import diagnosis
    diagnosis._calls.clear()
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(diagnosis, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("DG_DIAG_RATE_PER_MIN", "2")
    body = {"error_rate": 1, "latency_ms": 1, "health_status": "healthy"}
    assert client.post("/diagnose", json=body).status_code == 500
    assert client.post("/diagnose", json=body).status_code == 500
    assert client.post("/diagnose", json=body).status_code == 429
    diagnosis._calls.clear()
