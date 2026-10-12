# DeployGuard

AI-assisted deployment risk and rollback helper, built for the **Build on Elastic Beanstalk Hackathon by TrainWithShubham**.

Give it error rate, latency and health. A deterministic engine scores the release (LOW / MEDIUM / HIGH), then an LLM explains what to investigate and whether to consider a rollback.

![Architecture](docs/architecture.svg)

## Components
| Part | Tech | File |
|---|---|---|
| Risk engine + API | FastAPI | `app/main.py`, `app/risk.py` |
| Dashboard | single HTML page served by FastAPI | `app/static/index.html` |
| AI diagnosis | Groq (`openai/gpt-oss-120b`, configurable) | `app/diagnosis.py` |
| Live metrics | AWS CloudWatch (boto3) | `app/cloudwatch.py` |
| History | local JSON (development storage only) | `app/history.py` |
| Container | Docker | `Dockerfile`, `docker-compose.yml` |
| CI/CD | GitHub Actions + OIDC | `.github/workflows/` |
| Infrastructure | Terraform | `terraform/` |

## Deployment model
One Elastic Beanstalk Docker environment (`deployguard-prod`) runs a single container. FastAPI serves both the API and the dashboard page, so there is one URL, one image and no CORS setup.

Pipeline (`ci-cd.yml`): **test** -> **docker-build** (builds the image, health-checks `/health` and the dashboard page) -> **deploy** (creates an immutable version labelled with the commit, waits for it to become healthy, smoke-tests it). Deploy uses the GitHub Environment `production` (add required reviewers for an approval gate) and assumes an AWS role through OIDC, so no AWS keys are stored in GitHub.

Rollback: **Actions -> Rollback** lists versions, then redeploys the one you choose.

## Live demo (GitHub Pages)
Settings -> Pages -> Deploy from a branch (`main`, `/ (root)`) serves the root `index.html`, a copy of `app/static/index.html`. Pages has no backend, so it runs in **demo mode**: scoring in the browser (same rules as the API), history in the browser, AI and CloudWatch disabled. After editing the dashboard, run `copy app\static\index.html index.html` and push.

Demo URL: `https://ojaslan.github.io/deploy-guard/`

## Infrastructure as code
`terraform/` builds the Elastic Beanstalk environment, IAM roles and the GitHub OIDC role. See `terraform/README.md`.

## Status (what is verified)
| Feature | Status |
|---|---|
| Risk scoring, validation, history | Automated tests |
| CloudWatch math, rollback API safety logic | Unit tests with mocked AWS |
| Workflows and scripts | Linted (actionlint, shellcheck) |
| Docker image builds and passes health checks | Runs in CI on every push |
| Dashboard page logic | Exercised in jsdom against the real API, and in demo mode (not yet checked in a real browser) |
| Demo-mode scoring vs API scoring | Compared on 400 random inputs, 0 mismatches |
| Elastic Beanstalk deploy via pipeline, live CloudWatch | Verify after setup (see runbook) |

## Run locally
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env      # edit; never commit .env
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 (dashboard) and http://127.0.0.1:8000/docs (API).
Or: `docker compose up --build`

## Tests
```
python -m pytest -q
```

## Known limitations
- Single-instance environment over plain HTTP. HTTPS needs a custom domain + ACM certificate + load balancer.
- No login on the dashboard; `/diagnose` has a global rate limit.
- History is a local JSON file and resets on redeploy.
- Risk weights are simple heuristics. AI output is advisory only.
