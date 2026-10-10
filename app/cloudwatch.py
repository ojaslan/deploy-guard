import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

router = APIRouter()
NAMESPACE = "AWS/ElasticBeanstalk"


def _query(env_name: str, region: str, minutes: int):
    cw = boto3.client("cloudwatch", region_name=region)
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)

    def q(qid, metric, stat):
        return {
            "Id": qid,
            "MetricStat": {
                "Metric": {
                    "Namespace": NAMESPACE,
                    "MetricName": metric,
                    "Dimensions": [{"Name": "EnvironmentName", "Value": env_name}],
                },
                "Period": 60,
                "Stat": stat,
            },
            "ReturnData": True,
        }

    resp = cw.get_metric_data(
        MetricDataQueries=[
            q("total", "ApplicationRequestsTotal", "Sum"),
            q("err5xx", "ApplicationRequests5xx", "Sum"),
            q("p90", "ApplicationLatencyP90", "Average"),
            q("health", "EnvironmentHealth", "Maximum"),
        ],
        StartTime=start,
        EndTime=end,
    )
    return {r["Id"]: r["Values"] for r in resp["MetricDataResults"]}


@router.get("/metrics/live")
def live_metrics(minutes: int = 10):
    env_name = os.getenv("EB_ENVIRONMENT_NAME", "").strip()
    region = os.getenv("AWS_REGION", "").strip()
    if not env_name or not region:
        raise HTTPException(500, "Set AWS_REGION and EB_ENVIRONMENT_NAME.")
    try:
        v = _query(env_name, region, minutes)
    except NoCredentialsError:
        raise HTTPException(500, "No AWS credentials found. Run: aws configure")
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(502, f"CloudWatch error: {type(e).__name__}: {e}")

    total = sum(v.get("total", []))
    errors = sum(v.get("err5xx", []))
    p90 = v.get("p90", [])
    health_vals = v.get("health", [])
    if not total and not health_vals:
        raise HTTPException(
            404,
            f"No datapoints for '{env_name}' in the last {minutes} min. Check name/region, "
            "enhanced health, and that the app has traffic.",
        )
    worst = max(health_vals) if health_vals else None  # 0 OK, 1 Info, 15 Warning, 20 Degraded, 25 Severe
    return {
        "source": "cloudwatch",
        "environment": env_name,
        "window_minutes": minutes,
        "error_rate": round(errors / total * 100, 2) if total else None,
        "latency_ms": round(max(p90) * 1000, 1) if p90 else None,
        "health_status": None if worst is None else ("healthy" if worst <= 1 else "unhealthy"),
        "raw": {"requests": total, "errors_5xx": errors, "environment_health_max": worst},
    }
