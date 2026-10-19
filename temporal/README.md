# Durable incident response with Temporal

`IncidentResponse` is a Temporal workflow: **read live telemetry -> score -> AI verdict -> wait for a human approval -> trigger the rollback workflow -> verify health**.
Its state lives in Temporal's history, so a crashed worker or restarted machine resumes exactly where it stopped, even while waiting for an approval. Every external call is an activity with retries; the rollback trigger is never retried automatically. If the AI is down, the verdict falls back to the deterministic risk level.

Runs next to the app (laptop or any server), not inside the Elastic Beanstalk container.

## Run it (Windows)
1. Get the Temporal CLI: download the `windows_amd64` zip from https://github.com/temporalio/cli/releases and extract `temporal.exe`.
2. `pip install -r temporal\requirements.txt` (venv on)
3. Terminal A: `temporal.exe server start-dev`   (UI: http://localhost:8233)
4. Terminal B: `python -m temporal.worker`
5. Break the live service and generate traffic (PowerShell, use your URL):
   ```
   $u = "http://<your-eb-url>"
   Invoke-RestMethod -Method Post "$u/demo/mode" -ContentType "application/json" -Body '{"mode":"failing"}'
   1..40 | ForEach-Object { try { Invoke-RestMethod "$u/demo/work" | Out-Null } catch {} }
   ```
6. Terminal C: `python -m temporal.start start --base-url http://<your-eb-url>` (prints a workflow id)
7. `python -m temporal.start status <id>` shows "waiting for human approval". Then `approve <id> --by yourname` (or `reject`), then `result <id>`.

**Durability demo:** while it waits, stop the worker (Ctrl+C), start it again, run `status`: same stage. Then approve.

**Real rollback trigger (optional):** set `GITHUB_DISPATCH_TOKEN` (fine-grained token with Actions read/write on the repo) in the worker's terminal and pass `--rollback-to <version label>`. Without them the outcome is `approved_manual_rollback_needed` and you roll back by hand from GitHub Actions.

## Tests
`python -m pytest temporal -q` (downloads Temporal's test server on first run). Cases: no action, approve -> rollback, reject, approval timeout, manual fallback.
