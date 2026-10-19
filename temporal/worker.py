"""Run:  python -m temporal.worker   (needs a Temporal server, e.g. `temporal server start-dev`)"""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from temporal import activities as acts
from temporal.workflows import IncidentResponse

TASK_QUEUE = "deployguard"


async def main() -> None:
    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    with ThreadPoolExecutor(max_workers=10) as pool:
        worker = Worker(client, task_queue=TASK_QUEUE, workflows=[IncidentResponse],
                        activities=[acts.fetch_telemetry, acts.score_release, acts.ai_verdict,
                                    acts.trigger_rollback, acts.check_health],
                        activity_executor=pool)
        print(f"Worker running on task queue '{TASK_QUEUE}'. Ctrl+C to stop.")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
