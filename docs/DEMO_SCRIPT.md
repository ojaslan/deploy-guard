# 2-minute demo script

**0:00 Problem (15s).** "Teams ship releases without knowing how risky they are, and rollbacks happen too late. DeployGuard scores a release from real traffic, explains it, and drives a safe rollback."

**0:15 Live app (15s).** Open the Elastic Beanstalk URL. Point at the `BUILD <commit>` chip: "this is the commit currently live, deployed by GitHub Actions with keyless AWS login."

**0:30 Incident Lab (45s).** Tab "Incident Lab" -> "Run full incident demo". Narrate the six steps as they tick: it breaks a demo route, sends 40 requests, reads the service's own telemetry (real error rate, real p90), scores it HIGH, asks the LLM, and shows VERDICT: ROLLBACK.

**1:15 Rollback (30s).** Click the rollback link -> GitHub Actions -> Rollback -> run with the previous version label. Show the job go green, then refresh the dashboard: the BUILD chip shows the older commit.

**1:45 Close (15s).** "Tested, containerised, deployed by a pipeline with smoke tests, history stored in DynamoDB. Limits: single instance, HTTP only; next is HTTPS and multi-instance metrics."

Tips: say only what you have actually run. If the AI step is slow, keep talking over the telemetry numbers. Do not show the Environment properties page (it contains your key).
