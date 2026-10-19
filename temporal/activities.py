"""Temporal activities: every call that touches the outside world lives here."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from temporalio import activity
from temporalio.exceptions import ApplicationError


def _http(url, body=None, headers=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        # 4xx (except 429) will not get better by retrying
        retryable = not (400 <= e.code < 500 and e.code != 429)
        raise ApplicationError(f"HTTP {e.code}: {detail}", non_retryable=not retryable) from e


@activity.defn
def fetch_telemetry(base_url: str) -> dict:
    _, t = _http(f"{base_url}/metrics/self?minutes=10")
    if t.get("error_rate") is None or t.get("latency_ms") is None:
        raise ApplicationError("No API traffic in the last 10 minutes, nothing to score.", non_retryable=True)
    return t


@activity.defn
def score_release(base_url: str, t: dict) -> dict:
    q = urllib.parse.urlencode({"error_rate": t["error_rate"], "latency_ms": t["latency_ms"],
                                "health_status": t["health_status"]})
    _, d = _http(f"{base_url}/analyze?{q}")
    return d


@activity.defn
def ai_verdict(base_url: str, t: dict, risk_level: str) -> dict:
    """Ask the LLM. If the AI is unavailable, fall back to the deterministic risk level."""
    fallback = {"HIGH": "ROLLBACK", "MEDIUM": "INVESTIGATE"}.get(risk_level, "OK")
    try:
        _, d = _http(f"{base_url}/diagnose", body={
            "error_rate": t["error_rate"], "latency_ms": t["latency_ms"],
            "health_status": t["health_status"], "source": "app-telemetry", "requests": t.get("requests")})
        m = re.search(r"VERDICT:\s*(OK|INVESTIGATE|ROLLBACK)", d.get("diagnosis", ""), re.I)
        if m:
            return {"verdict": m.group(1).upper(), "ai_available": True, "diagnosis": d["diagnosis"]}
        return {"verdict": fallback, "ai_available": False, "error": "no VERDICT line in AI reply"}
    except Exception as e:  # AI is advisory: never let it block the workflow
        return {"verdict": fallback, "ai_available": False, "error": str(e)[:200]}


@activity.defn
def trigger_rollback(repo: str, version_label: str) -> dict:
    """Starts the GitHub 'Rollback' workflow. Needs GITHUB_DISPATCH_TOKEN (actions: write)."""
    token = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()
    if not token or not version_label:
        return {"dispatched": False, "reason": "no GITHUB_DISPATCH_TOKEN or no rollback_to version: roll back manually"}
    _http(f"https://api.github.com/repos/{repo}/actions/workflows/rollback.yml/dispatches",
          body={"ref": "main", "inputs": {"version_label": version_label}},
          headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"})
    return {"dispatched": True, "version_label": version_label}


@activity.defn
def check_health(base_url: str) -> dict:
    _, d = _http(f"{base_url}/health")
    return d
