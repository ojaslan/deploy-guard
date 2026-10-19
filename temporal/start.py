"""Control the incident workflow.

  python -m temporal.start start --base-url http://<your-eb-url> [--rollback-to gh-xxxx-N]
  python -m temporal.start status  <workflow-id>
  python -m temporal.start approve <workflow-id> --by yourname
  python -m temporal.start reject  <workflow-id> --by yourname
  python -m temporal.start result  <workflow-id>
"""
import argparse
import asyncio
import json
import os
import time

from temporalio.client import Client

from temporal.workflows import IncidentParams, IncidentResponse
from temporal.worker import TASK_QUEUE


async def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--base-url", required=True)
    s.add_argument("--repo", default="ojaslan/deploy-guard")
    s.add_argument("--rollback-to", default="")
    s.add_argument("--approval-minutes", type=int, default=30)
    s.add_argument("--settle-seconds", type=int, default=60)
    for name in ("status", "approve", "reject", "result"):
        c = sub.add_parser(name)
        c.add_argument("workflow_id")
        c.add_argument("--by", default="operator")
    a = ap.parse_args()

    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    if a.cmd == "start":
        wid = f"incident-{int(time.time())}"
        await client.start_workflow(
            IncidentResponse.run,
            IncidentParams(a.base_url.rstrip("/"), a.repo, a.rollback_to, a.approval_minutes * 60, a.settle_seconds),
            id=wid, task_queue=TASK_QUEUE)
        print(f"Started {wid}\nUI: http://localhost:8233/namespaces/default/workflows/{wid}")
        return
    h = client.get_workflow_handle(a.workflow_id)
    if a.cmd == "status":
        print(json.dumps(await h.query(IncidentResponse.status), indent=2))
    elif a.cmd == "approve":
        await h.signal(IncidentResponse.approve, a.by)
        print("Approved.")
    elif a.cmd == "reject":
        await h.signal(IncidentResponse.reject, a.by)
        print("Rejected.")
    else:
        print(json.dumps(await h.result(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
