"""Durable incident response: measure -> score -> AI verdict -> human approval -> rollback -> verify.

State lives in Temporal's history, so a crashed worker or restarted laptop resumes exactly where it was,
including while waiting days for an approval.
"""
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal import activities as acts


@dataclass
class IncidentParams:
    base_url: str
    repo: str = "ojaslan/deploy-guard"
    rollback_to: str = ""
    approval_seconds: int = 1800
    settle_seconds: int = 60


RETRY = RetryPolicy(initial_interval=timedelta(seconds=2), backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=30), maximum_attempts=5)
NO_RETRY = RetryPolicy(maximum_attempts=1)  # a rollback trigger must never be repeated automatically
TIMEOUT = timedelta(seconds=45)


@workflow.defn
class IncidentResponse:
    def __init__(self) -> None:
        self._decision: Optional[str] = None
        self._by = ""
        self._stage = "starting"

    @workflow.signal
    def approve(self, by: str = "unknown") -> None:
        if self._decision is None:
            self._decision, self._by = "approved", by

    @workflow.signal
    def reject(self, by: str = "unknown") -> None:
        if self._decision is None:
            self._decision, self._by = "rejected", by

    @workflow.query
    def status(self) -> dict:
        return {"stage": self._stage, "decision": self._decision, "by": self._by}

    @workflow.run
    async def run(self, p: IncidentParams) -> dict:
        self._stage = "reading telemetry"
        t = await workflow.execute_activity(acts.fetch_telemetry, p.base_url,
                                            start_to_close_timeout=TIMEOUT, retry_policy=RETRY)
        self._stage = "scoring the release"
        score = await workflow.execute_activity(acts.score_release, args=[p.base_url, t],
                                                start_to_close_timeout=TIMEOUT, retry_policy=RETRY)
        self._stage = "asking the AI"
        v = await workflow.execute_activity(acts.ai_verdict, args=[p.base_url, t, score["risk_level"]],
                                            start_to_close_timeout=TIMEOUT, retry_policy=RETRY)
        result = {"telemetry": t, "risk_score": score["risk_score"], "risk_level": score["risk_level"],
                  "verdict": v["verdict"], "ai_available": v["ai_available"]}

        if v["verdict"] != "ROLLBACK":
            self._stage = "done"
            return {**result, "outcome": "no_action"}

        self._stage = "waiting for human approval"
        try:
            await workflow.wait_condition(lambda: self._decision is not None,
                                          timeout=timedelta(seconds=p.approval_seconds))
        except asyncio.TimeoutError:
            self._stage = "done"
            return {**result, "outcome": "approval_timed_out"}
        if self._decision == "rejected":
            self._stage = "done"
            return {**result, "outcome": "rejected", "decided_by": self._by}

        self._stage = "rolling back"
        rb = await workflow.execute_activity(acts.trigger_rollback, args=[p.repo, p.rollback_to],
                                             start_to_close_timeout=TIMEOUT, retry_policy=NO_RETRY)
        result.update(rollback=rb, decided_by=self._by)
        if not rb["dispatched"]:
            self._stage = "done"
            return {**result, "outcome": "approved_manual_rollback_needed"}

        self._stage = "verifying"
        await workflow.sleep(timedelta(seconds=p.settle_seconds))
        health = await workflow.execute_activity(acts.check_health, p.base_url,
                                                 start_to_close_timeout=TIMEOUT, retry_policy=RETRY)
        self._stage = "done"
        return {**result, "post_rollback_health": health, "outcome": "rolled_back"}
