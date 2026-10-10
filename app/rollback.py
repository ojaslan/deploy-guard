"""Explicit, opt-in rollback to a previous Elastic Beanstalk application version.

Safety rules:
- Disabled unless DEPLOYGUARD_ADMIN_TOKEN is set on the server.
- Every call needs the header X-Admin-Token with that value.
- Nothing is executed unless confirm=true is sent.
- A successful call only SUBMITS the request to Elastic Beanstalk; check `eb status`.
Real-AWS behavior is not verified. Needs IAM: elasticbeanstalk:DescribeEnvironments,
DescribeApplicationVersions, UpdateEnvironment.
"""
import hmac
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel


def require_admin(x_admin_token: str = Header(default="")):
    expected = os.getenv("DEPLOYGUARD_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(403, "Rollback is disabled. Set DEPLOYGUARD_ADMIN_TOKEN on the server to enable it.")
    if not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "Invalid admin token.")


router = APIRouter(prefix="/rollback", tags=["rollback"], dependencies=[Depends(require_admin)])


def _eb():
    region = os.getenv("AWS_REGION", "").strip()
    env = os.getenv("EB_ENVIRONMENT_NAME", "").strip()
    if not region or not env:
        raise HTTPException(500, "Set AWS_REGION and EB_ENVIRONMENT_NAME.")
    return boto3.client("elasticbeanstalk", region_name=region), env


def _wrap(e: Exception):
    if isinstance(e, NoCredentialsError):
        return HTTPException(500, "No AWS credentials found.")
    return HTTPException(502, f"AWS error: {type(e).__name__}: {e}")


@router.get("/versions")
def versions():
    client, env = _eb()
    try:
        envs = client.describe_environments(EnvironmentNames=[env])["Environments"]
        if not envs:
            raise HTTPException(404, f"Environment '{env}' not found.")
        current = envs[0].get("VersionLabel")
        app_name = envs[0]["ApplicationName"]
        vs = client.describe_application_versions(ApplicationName=app_name, MaxRecords=10)
        items = sorted(vs["ApplicationVersions"], key=lambda v: v["DateCreated"], reverse=True)
        return {"environment": env, "current_version": current,
                "available_versions": [v["VersionLabel"] for v in items]}
    except HTTPException:
        raise
    except (ClientError, BotoCoreError) as ex:
        raise _wrap(ex)


class RollbackRequest(BaseModel):
    version_label: str
    confirm: bool = False


@router.post("")
def rollback(req: RollbackRequest):
    if not req.confirm:
        return {"executed": False,
                "message": "Dry run only. Send confirm=true to actually start the rollback.",
                "target_version": req.version_label}
    client, env = _eb()
    try:
        client.update_environment(EnvironmentName=env, VersionLabel=req.version_label)
    except (ClientError, BotoCoreError) as ex:
        raise _wrap(ex)
    return {"executed": True,
            "message": "Rollback request submitted to Elastic Beanstalk. It is NOT complete yet. "
                       "Check `eb status` or the console for the result.",
            "target_version": req.version_label}
