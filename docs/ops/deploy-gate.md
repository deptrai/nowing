# Deploy gate for chat regression

This document describes how the `chat/regression` deploy gate works and how to wire it into CI.

## Story

Story 4.8e: CI / deploy gate for chat regression.

## Overview

The chat regression benchmark is intended to run automatically after a production deploy so that quality, latency, cost, and stability regressions can block an unhealthy rollout.

Because Nowing has no staging environment, the benchmark runs against the newly deployed build using a long-lived `search_space_id` (the eval SearchSpace) and a cost cap.

## Triggers

The GitHub Action lives in `.github/workflows/chat-regression-gate.yml`. It is currently triggered manually via `workflow_dispatch` and can be invoked from a Dokploy post-deploy hook with:

```bash
gh workflow run chat-regression-gate.yml \
  -f environment=production \
  -f search_space_id=42 \
  -f n=10 \
  -f max_total_cost_micros=500000
```

## Workflow inputs

| Input | Required | Default | Purpose |
|-------|----------|---------|---------|
| `environment` | yes | `production` | Environment label (`local` or `production`) |
| `search_space_id` | yes | — | `SearchSpace` id for thread creation |
| `n` | yes | `10` | Max cases to run (`--n`) |
| `modes` | yes | `speed,balanced,quality` | Comma-separated chat modes |
| `concurrency` | yes | `1` | Concurrent cases |
| `max_total_cost_micros` | yes | `500000` | Cost cap in micros (e.g. 500000 = $0.50) |
| `backend_build_id` | no | — | Deployed build/commit id (`--backend-build-id`) |
| `fail_on_unratified` | yes | `false` | Fail the run if `gate.yaml` is not ratified |

## Required secrets and vars

| Secret / Var | Purpose |
|--------------|---------|
| `NOWING_API_BASE` | Nowing backend URL |
| `NOWING_USER_EMAIL` + `NOWING_USER_PASSWORD` | Local auth mode (required unless `NOWING_JWT` is used) |
| `NOWING_JWT` + `NOWING_REFRESH_TOKEN` | Google/JWT auth mode (optional) |
| `SLACK_WEBHOOK_URL` | Slack gate failure notification |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram gate failure notification |
| `NOWING_EVALS_ARTIFACT_URL_PREFIX` | Public prefix for artifact links in notifications |

## Behaviour

1. The workflow ingests the default sample dataset with `ingest chat regression`.
2. It runs `run chat regression` with the supplied inputs.
3. If the total run cost exceeds `max_total_cost_micros`, the run fails after writing the artifact and sending a notification.
4. If any `gate.yaml` threshold is exceeded:
   - If `baseline_ratified: true`, the step fails.
   - If `baseline_ratified: false`, a warning is logged and the step continues (unless `fail_on_unratified=true`).
5. The run artifact (`run_artifact.json` and `raw.jsonl`) is uploaded to GitHub Actions.

## Cost-cap and notification ordering

The runner always writes `run_artifact.json` before raising any error and attempts to send a Slack/Telegram notification with the failing reason(s) and a link to the artifact. This ensures post-mortem data is available even when the gate fails.

## Environment defaults

The runner also reads `CHAT_EVAL_SEARCH_SPACE_ID`, `CHAT_EVAL_WORKSPACE_ID`, and `CHAT_EVAL_MAX_CASES` from the environment via `Config`. CLI flags take precedence.

## Local verification

```bash
cd nowing_evals
python -m nowing_evals run chat regression \
  --search-space-id 42 \
  --n 2 \
  --max-total-cost-micros 500000 \
  --environment local
```
