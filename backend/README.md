# AI QA & Testing Agent (Django + Celery)

End-to-end pipeline:
- GitHub PR webhook -> Django (/webhook/gh/)
- Celery orchestrates jobs (static analysis -> AI test gen -> execution -> triage -> patch suggestion -> report)
- Results visible in dashboard at http://localhost:8000/

## Prerequisites
- Docker + Docker Compose
- A GitHub Personal Access Token (classic) with repo read access
- A GitHub webhook secret (any string you set both in GitHub and .env)

## Quick Start

1) Copy env:
\`\`\`
cp .env.example .env
\`\`\`

2) Edit `.env`:
- DJANGO_SECRET_KEY: any random string
- GITHUB_TOKEN: your PAT (or GitHub App token)
- GITHUB_WEBHOOK_SECRET: your chosen secret
- Optional: HF_API_KEY/HF_INFERENCE_API_URL to enable LLM test generation

3) Build and start:
\`\`\`
docker compose up --build
\`\`\`

4) Open Dashboard:
- http://localhost:8000/

5) Set GitHub webhook (on your repo):
- Payload URL: http://localhost:8000/webhook/gh/
- Content type: application/json
- Secret: same as GITHUB_WEBHOOK_SECRET
- Events: "Pull requests"

6) Trigger:
- Open or update a PR. The pipeline will run automatically.

## Notes
- Tests run inside the Celery worker container in an ephemeral workspace. For stronger isolation, consider Docker-in-Docker or a dedicated "runner" service.
- Static analysis uses bandit/flake8/semgrep; results summarized in job logs and PR comment.
- AI generation falls back to a heuristic AST-based generator if no HF API is configured.

\`\`\`
