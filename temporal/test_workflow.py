"""Run with:  python -m pytest temporal -q   (downloads Temporal's test server on first run)."""
import os
import uuid

import pytest
from temporalio import activity
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal.workflows import IncidentParams, IncidentResponse

pytestmark = pytest.mark.asyncio
CALLS = []


async def start_env():
    """Local dev server if TEMPORAL_CLI points at the `temporal` binary, else Temporal's time-skipping test server."""
    cli = os.getenv("TEMPORAL_CLI")
    if cli:
        return await WorkflowEnvironment.start_local(dev_server_existing_path=cli)
    return await WorkflowEnvironment.start_time_skipping()


def make_activities(level="HIGH", verdict="ROLLBACK", dispatched=True):
    @activity.defn(name="fetch_telemetry")
    async def fetch_telemetry(base_url: str) -> dict:
        return {"error_rate": 70.0, "latency_ms": 120.0, "health_status": "unhealthy", "requests": 40}

    @activity.defn(name="score_release")
    async def score_release(base_url: str, t: dict) -> dict:
        return {"risk_score": 70.0, "risk_level": level}

    @activity.defn(name="ai_verdict")
    async def ai_verdict(base_url: str, t: dict, risk_level: str) -> dict:
        return {"verdict": verdict, "ai_available": True}

    @activity.defn(name="trigger_rollback")
    async def trigger_rollback(repo: str, version_label: str) -> dict:
        CALLS.append(version_label)
        return {"dispatched": dispatched, "version_label": version_label}

    @activity.defn(name="check_health")
    async def check_health(base_url: str) -> dict:
        return {"status": "ok"}

    return [fetch_telemetry, score_release, ai_verdict, trigger_rollback, check_health]


async def run_case(env: WorkflowEnvironment, acts, signal=None, **params):
    client: Client = env.client
    queue = f"q-{uuid.uuid4().hex[:6]}"
    async with Worker(client, task_queue=queue, workflows=[IncidentResponse], activities=acts):
        h = await client.start_workflow(IncidentResponse.run, IncidentParams("http://x", **{"settle_seconds": 0, **params}),
                                        id=f"t-{uuid.uuid4().hex[:6]}", task_queue=queue)
        if signal:
            await h.signal(getattr(IncidentResponse, signal), "tester")
        return await h.result()


async def test_no_action_when_not_rollback():
    async with await start_env() as env:
        r = await run_case(env, make_activities("LOW", "OK"))
    assert r["outcome"] == "no_action"


async def test_rollback_after_approval():
    CALLS.clear()
    async with await start_env() as env:
        r = await run_case(env, make_activities(), signal="approve", rollback_to="gh-abc-1")
    assert r["outcome"] == "rolled_back" and r["decided_by"] == "tester"
    assert CALLS == ["gh-abc-1"] and r["post_rollback_health"]["status"] == "ok"


async def test_rejected_does_not_roll_back():
    CALLS.clear()
    async with await start_env() as env:
        r = await run_case(env, make_activities(), signal="reject")
    assert r["outcome"] == "rejected" and CALLS == []


async def test_times_out_without_approval():
    CALLS.clear()
    async with await start_env() as env:
        r = await run_case(env, make_activities(), approval_seconds=2)
    assert r["outcome"] == "approval_timed_out" and CALLS == []


async def test_manual_rollback_when_no_token():
    async with await start_env() as env:
        r = await run_case(env, make_activities(dispatched=False), signal="approve")
    assert r["outcome"] == "approved_manual_rollback_needed"
