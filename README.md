# DeployGuard

AI-assisted deployment risk and rollback helper, built for the **Build on Elastic Beanstalk Hackathon by TrainWithShubham**.

Give it error rate, latency and health. A deterministic engine scores the release (LOW / MEDIUM / HIGH), then an LLM explains what to investigate and whether to consider a rollback.

![Architecture](docs/architecture.svg)

## Components
| Part | Tech | File |
|---|---|---|
| Risk engine + API | FastAPI | `app/main.py`, `app/risk.py` |
| AI diagnosis | Groq (`openai/gpt-oss-120b`, configurable) | `app/diagnosis.py` |
| Live metrics | AWS CloudWatch (boto3) | `app/cloudwatch.py` |
| Dashboard | Streamlit | `app/dashboard.py` |
| History | local JSON (development storage only) | `app/history.py` |
| Containers | Docker, docker-compose | `Dockerfile`, `Dockerfile.dashboard` |
| CI/CD | GitHub Actions + OIDC | `.github/workflows/` |

## Deployment model
Two Elastic Beanstalk Docker environments (single instance each):
- `deployguard-backend-prod`: FastAPI container
- `deployguard-frontend-prod`: Streamlit container (nginx override for WebSockets in `deploy/frontend/.platform`)

Pipeline (`ci-cd.yml`): **test** -> **docker-build** (builds both images, health-checks both containers) -> **deploy-backend** -> **deploy-frontend**. Each deploy creates an immutable version labelled with the commit, waits for it to become healthy, and smoke-tests it. Deploy jobs use the GitHub Environment `production` (add required reviewers for an approval gate) and assume an AWS role through OIDC, so no AWS keys are stored in GitHub.

Rollback: **Actions -> Rollback** lists versions, then redeploys the one you choose.

## Status (what is verified)
| Feature | Status |
|---|---|
| Risk scoring, validation, history | Automated tests |
| CloudWatch math, rollback API safety logic | Unit tests with mocked AWS |
| Workflows and scripts | Linted (actionlint, shellcheck) |
| Docker images build and pass health checks | Runs in CI on every push |
| Elastic Beanstalk deploy via pipeline, WebSockets, live CloudWatch | Verify after setup (see runbook) |

## Run locally
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env      # edit; never commit .env
uvicorn app.main:app --reload
streamlit run app/dashboard.py
```
Or: `docker compose up --build`

## Tests
```
python -m pytest -q
```

## Known limitations
- Single-instance environments over plain HTTP. HTTPS needs a custom domain + ACM certificate + load balancer.
- No login on the dashboard; `/diagnose` has a global rate limit.
- History is a local JSON file and resets on redeploy.
- Risk weights are simple heuristics. AI output is advisory only.
