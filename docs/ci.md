# CI/CD Pipeline Guide — Nowing E2E

## Overview

Pipeline: GitHub Actions — `.github/workflows/e2e-tests.yml`

Stack: Fullstack (Next.js + FastAPI)  
Framework: Playwright (Chromium)  
Package manager: pnpm + uv

---

## Triggers

| Trigger | Jobs run |
|---------|----------|
| Push to `main` or `dev` | install → e2e (2 shards) → report |
| Pull Request to `main` or `dev` | install → burn-in + e2e → report |
| Cron (Sunday 03:00 UTC) | install → e2e → report |

Path filters: `nowing_web/**`, `nowing_backend/**`, `.github/workflows/e2e-tests.yml`

---

## Jobs

### `install`
- Sets up pnpm, Node 22, UV
- Installs frontend and backend dependencies
- Caches Playwright browsers and Python `.venv`

### `burn-in` (PR only)
- Detects changed E2E spec files vs base branch
- Runs 5 iterations on those specs
- Fails if any iteration fails (flaky detection gate)

### `e2e` (2 shards, parallel)
- Starts PostgreSQL (pgvector/pgvector:pg17) as service
- Starts FastAPI backend on `:8000`
- Builds and starts Next.js on `:4998`
- Runs `playwright test --shard=N/2 --reporter=html,junit`
- Uploads test results as artifacts (14-day retention)

### `report`
- Downloads all shard artifacts
- Sends Telegram notification on failure (optional)
- Writes GitHub Step Summary

---

## Secrets

See `docs/ci-secrets-checklist.md` for required secrets.

---

## Local Scripts

| Script | Description |
|--------|-------------|
| `scripts/test-changed.sh [base]` | Run only changed specs vs `base` branch |
| `scripts/burn-in.sh [N] [base]` | Burn-in N iterations on changed specs |
| `scripts/ci-local.sh` | Mirror CI environment locally |

---

## Troubleshooting

**Tests pass locally, fail in CI**  
Run `scripts/ci-local.sh` with `CI=true` to replicate CI timeouts and retry behavior.

**Burn-in detects flakiness**  
Check `burn-in-failures` artifact for trace files. Common causes: race conditions, selector instability, async timing.

**Backend startup timeout**  
The backend health check polls `/health` every 2s for up to 60s. Check `/tmp/backend.log` artifact.

**Cache miss**  
Cache key is `pnpm-lock.yaml` hash. If lockfile changes, full reinstall occurs (expected).
