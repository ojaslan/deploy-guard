import json
import logging
import os
import random
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse

from app import telemetry
from app.cloudwatch import router as cloudwatch_router
from app.demo import router as demo_router
from app.diagnosis import router as diagnosis_router
from app.history import load_history, save_analysis
from app.risk import calculate_risk
from app.rollback import router as rollback_router

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("deployguard")

app = FastAPI(title="DeployGuard", version="3.0.0")
START = time.time()
BASE = Path(__file__).resolve().parent
INDEX = BASE / "static" / "index.html"
VERSION_FILE = BASE / "version.txt"

app.include_router(diagnosis_router)
app.include_router(cloudwatch_router)
app.include_router(rollback_router)
app.include_router(demo_router)


@app.middleware("http")
async def observe(request: Request, call_next):
    """Request id, JSON access log, telemetry and basic security headers."""
    start = time.perf_counter()
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    path = request.url.path
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    finally:
        ms = (time.perf_counter() - start) * 1000
        if not path.startswith(telemetry.SKIP_PREFIXES):
            telemetry.record(status, ms)
        log.info(json.dumps({"rid": rid, "method": request.method, "path": path,
                             "status": status, "ms": round(ms, 1)}))
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _page():
    return FileResponse(INDEX, media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/", include_in_schema=False)
def root():
    return _page()


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return _page()


@app.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": round(time.time() - START, 1)}


@app.get("/version")
def version():
    """Build id written by the pipeline (git commit); 'dev' when running locally."""
    try:
        v = VERSION_FILE.read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        v = "dev"
    return {"version": v}


@app.get("/config")
def config():
    return {"repo": os.getenv("DG_REPO", "ojaslan/deploy-guard")}


@app.get("/metrics/self")
def metrics_self(minutes: int = Query(10, ge=1, le=15)):
    return telemetry.snapshot(minutes)


@app.get("/analyze")
def analyze(
    error_rate: float = Query(..., ge=0, le=100),
    latency_ms: float = Query(..., ge=0),
    health_status: str = Query("healthy", pattern="^(healthy|unhealthy)$"),
):
    result = calculate_risk(error_rate, latency_ms, health_status)
    result["metrics"] = {
        "error_rate_percent": error_rate,
        "latency_ms": latency_ms,
        "health_status": health_status,
    }
    save_analysis(result)
    return result


@app.get("/history")
def history():
    return load_history()


@app.get("/simulate")
def simulate(scenario: str = Query("normal", pattern="^(normal|error|slow)$")):
    if scenario == "error":
        er, lat, hs = random.uniform(8, 20), random.uniform(200, 500), "unhealthy"
    elif scenario == "slow":
        er, lat, hs = random.uniform(0, 3), random.uniform(800, 2000), "healthy"
    else:
        er, lat, hs = random.uniform(0, 1.5), random.uniform(80, 200), "healthy"
    er, lat = round(er, 2), round(lat, 1)
    result = calculate_risk(er, lat, hs)
    result["metrics"] = {"error_rate_percent": er, "latency_ms": lat, "health_status": hs}
    result["simulated"] = True
    save_analysis(result)
    return result
