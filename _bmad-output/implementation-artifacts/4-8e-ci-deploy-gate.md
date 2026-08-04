---
baseline_commit: e3de8a948
baseline_branch: develop
story_key: 4-8e-ci-deploy-gate
status: ready-for-dev
---

# Story 4.8e: CI / deploy gate for chat regression

**Status:** ready-for-dev  
**Epic:** 4 — Chat & Agents  
**Priority:** HIGH  
**Requirements:** NFR-10  

## Story

As a release engineer,
I want the `chat/regression` benchmark to run automatically before a deploy is marked successful,
So that production chat quality/latency/cost regressions block the rollout.

## Context

- `chat/regression` (4.8b) is already a registered benchmark in `nowing_evals`.
- Nowing deploys via Dokploy with auto-deploy on `production` branch.
- There is **no staging environment** (per memory: "Nowing chỉ có production, không có staging").
- The benchmark needs a live backend and a `search_space_id`, so the CI step must run against the **newly deployed build** in a post-deploy smoke phase, or against a long-lived `eval` search space.

## Acceptance Criteria

1. **Dokploy post-deploy step**
   - **Given** a production deploy completes,  
     **When** Dokploy `post-deploy` (or a GitHub Action triggered by deploy) runs,  
     **Then** it executes `python -m nowing_evals run chat regression --search-space-id $CHAT_EVAL_SEARCH_SPACE_ID`.

2. **Gate decision**
   - **Given** the benchmark metrics,  
     **When** any gate threshold in `gate.yaml` is violated,  
     **Then** the step fails, the deploy is marked unhealthy, and a notification is sent.

3. **Slack/Telegram notification**
   - **Given** the benchmark fails,  
     **When** the gate is violated,  
     **Then** a message is sent with a link to the run artifact and the failing metrics.

4. **Cost cap**
   - **Given** the benchmark runs in CI,  
     **When** it is configured,  
     **Then** it has a `--max-cases` / `--n` limit and a `max_total_cost_micros` guard to avoid runaway spending.

5. **Dry-run / ratified mode**
   - **Given** `gate.yaml` has `baseline_ratified: false`,  
     **When** the gate runs,  
     **Then** it logs a warning but does not block deploy until `baseline_ratified` is flipped.

## Tasks / Subtasks

### CI wiring

- [ ] Add a Dokploy service or post-deploy command in `.dokploy/` or `docker/nowing-eval/`.
- [ ] Or add a GitHub Action `.github/workflows/chat-regression-gate.yml` triggered by `deployment_status` or `workflow_dispatch`.
- [ ] Provide environment variables:
   - `NOWING_API_BASE`
   - `NOWING_JWT` or `NOWING_USER_EMAIL` + `NOWING_USER_PASSWORD`
   - `CHAT_EVAL_SEARCH_SPACE_ID`
   - `CHAT_EVAL_WORKSPACE_ID` (optional, for report context)
   - `CHAT_EVAL_MAX_CASES`
   - `SLACK_WEBHOOK_URL` / `TELEGRAM_BOT_TOKEN` + chat ID

### Gate runner

- [ ] Add `--max-total-cost-micros` and `--max-cases` to `chat/regression` `add_run_args`.
- [ ] In `runner.py`, after aggregation, compare `overall` metrics against `gate.yaml` thresholds.
- [ ] If `baseline_ratified: false`, warn and continue (exit 0) unless `--fail-on-unratified` is set.
- [ ] If a threshold is exceeded, write a `gate-fail.json` and raise `RuntimeError`.

### Notification

- [ ] Add `nowing_evals/src/nowing_evals/core/notifications.py` (or reuse existing) to send Slack/Telegram with run summary.
- [ ] Notification includes: suite, benchmark, run timestamp, failing threshold, current value, link to `run_artifact.json`.

### Docs

- [ ] Update `docs/ops/deploy-gate.md` or `README.md` with the CI step.
- [ ] Update `.env.example` with `CHAT_EVAL_*` variables.

### Tests

- [ ] Unit test for `gate.yaml` parsing and threshold comparison.
- [ ] Unit test for cost-cap early-exit.
- [ ] Respx-mocked test for Slack/Telegram notification payload.

## Verification

```bash
cd nowing_evals
python -m nowing_evals run chat regression --search-space-id 42 --n 2 --max-total-cost-micros 500000 --dry-run
ruff check src/nowing_evals/suites/chat/regression/ src/nowing_evals/core/notifications.py
ruff format ...
python -m pytest tests/suites/chat/test_regression.py tests/suites/chat/test_gate.py -q
```

## References

- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`
- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- `docs/ops/deploy-gate.md` (create or update)
