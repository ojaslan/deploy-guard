import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app import history, telemetry
from app import main as app_main
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def aws_env(monkeypatch):
    """Isolate from the developer's real AWS setup (.env is loaded by the app at import)."""
    for k, v in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
                 "AWS_DEFAULT_REGION": "us-east-1", "AWS_REGION": "us-east-1",
                 "AWS_EC2_METADATA_DISABLED": "true"}.items():
        monkeypatch.setenv(k, v)
    for k in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    monkeypatch.setenv("DG_HISTORY_PATH", str(tmp_path / "h.json"))
    monkeypatch.delenv("DG_DDB_TABLE", raising=False)
    telemetry.reset()


def test_telemetry_counts_and_skips_health():
    client.get("/health")
    client.get("/metrics/self")
    for _ in range(3):
        client.get("/history")
    d = client.get("/metrics/self").json()
    assert d["requests"] == 3 and d["error_rate"] == 0.0
    assert d["latency_ms"] is not None and d["health_status"] == "healthy"


def test_telemetry_error_rate_and_unhealthy(monkeypatch):
    client.get("/history")
    client.get("/history")

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_main, "calculate_risk", boom)
    r = client.get("/analyze", params={"error_rate": 1, "latency_ms": 1})
    assert r.status_code == 500
    d = client.get("/metrics/self").json()
    assert d["requests"] == 3 and d["errors_5xx"] == 1
    assert d["error_rate"] == pytest.approx(33.33, abs=0.01)
    assert d["health_status"] == "unhealthy"


def test_telemetry_no_traffic():
    d = client.get("/metrics/self").json()
    assert d["requests"] == 0 and d["error_rate"] is None and d["latency_ms"] is None


def test_version_and_headers():
    r = client.get("/version")
    assert r.status_code == 200 and "version" in r.json()
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-request-id"]


@mock_aws
def test_dynamodb_history(monkeypatch):
    aws_env(monkeypatch)
    boto3.client("dynamodb").create_table(
        TableName="t",
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "ts", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                              {"AttributeName": "ts", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    monkeypatch.setenv("DG_DDB_TABLE", "t")
    for i in range(3):
        history.save_analysis({"risk_score": i, "risk_level": "LOW"})
    recs = history.load_history()
    assert [r["risk_score"] for r in recs] == [0, 1, 2] and "timestamp" in recs[0]
    client.get("/analyze", params={"error_rate": 1, "latency_ms": 1})
    assert len(client.get("/history").json()) == 4


def test_storage_failure_does_not_break_api(monkeypatch):
    monkeypatch.setenv("DG_DDB_TABLE", "does-not-exist")
    aws_env(monkeypatch)
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "1")
    r = client.get("/analyze", params={"error_rate": 1, "latency_ms": 1})
    assert r.status_code == 200
    