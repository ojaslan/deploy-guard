import random
import time

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.cloudwatch import router as cloudwatch_router
from app.diagnosis import router as diagnosis_router
from app.history import load_history, save_analysis
from app.risk import calculate_risk
from app.rollback import router as rollback_router

app = FastAPI(title="DeployGuard", version="1.0.0")
START = time.time()

app.include_router(diagnosis_router)
app.include_router(cloudwatch_router)
app.include_router(rollback_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return """<html><body style="font-family:sans-serif;background:#080d18;color:#edf4ff;padding:40px">
<h1>DeployGuard API</h1>
<p>Backend is running. Interactive docs: <a style="color:#64a8ff" href="/docs">/docs</a></p>
<p>The full dashboard runs separately with Streamlit (port 8501).</p></body></html>"""


@app.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": round(time.time() - START, 1)}


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
