---
baseline_commit: e3de8a948
baseline_branch: develop
story_key: 4-8e-ci-deploy-gate
status: review
---

# Story 4.8e: CI / deploy gate for chat regression

**Status:** review  
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

- [x] Add a GitHub Action `.github/workflows/chat-regression-gate.yml` triggered by `workflow_dispatch` (Dokploy post-deploy can call `gh workflow run`).
- [x] Provide environment variables:
   - `NOWING_API_BASE`
   - `NOWING_USER_EMAIL` + `NOWING_USER_PASSWORD`
   - `CHAT_EVAL_SEARCH_SPACE_ID`
   - `CHAT_EVAL_WORKSPACE_ID` (optional)
   - `CHAT_EVAL_MAX_CASES`
   - `SLACK_WEBHOOK_URL` / `TELEGRAM_BOT_TOKEN` + chat ID

### Gate runner

- [x] Add `--max-total-cost-micros` to `chat/regression` `add_run_args` (`--n` already caps cases).
- [x] Add `--fail-on-unratified` flag.
- [x] In `runner.py`, compare metrics (including operational) against `gate.yaml` thresholds.
- [x] If `baseline_ratified: false`, warn and continue unless `--fail-on-unratified` is set.
- [x] If a threshold is exceeded, raise `RuntimeError`.

### Notification

- [x] Add `nowing_evals/src/nowing_evals/core/notifications.py` to send Slack/Telegram with run summary.
- [x] Notification includes: suite, benchmark, run timestamp, failing threshold, link to `run_artifact.json`.

### Docs

- [x] Update `nowing_evals/.env.example` with `CHAT_EVAL_*` + notification variables.
- [x] Update `nowing_evals/README.md` with the CI gate and `chat/regression` usage.
- [ ] Create `docs/ops/deploy-gate.md` with the full CI step.

### Tests

- [x] Existing unit tests for `gate.yaml` parsing and threshold comparison via `tests/suites/chat/test_regression.py`.
- [ ] Unit test for cost-cap early-exit.
- [ ] Respx-mocked test for Slack/Telegram notification payload.

## Verification

```bash
cd nowing_evals
python -m nowing_evals run chat regression --search-space-id 42 --n 2 --max-total-cost-micros 500000 --help
python -m nowing_evals run chat regression --search-space-id 42 --n 2 --max-total-cost-micros 500000 --fail-on-unratified
ruff check src/nowing_evals/suites/chat/regression/ src/nowing_evals/core/notifications.py
ruff format src/nowing_evals/suites/chat/regression/ src/nowing_evals/core/notifications.py
python -m pytest tests/suites/chat/test_regression.py -q
```

## Code status note

Implemented and merged. The `chat-regression-gate.yml` GitHub Action triggers by `workflow_dispatch`, runs the benchmark with cost cap and notification env vars, and uploads the run artifact. `ChatRegressionBenchmark` evaluates `gate.yaml` thresholds (including the new operational metrics), logs a warning when `baseline_ratified: false`, and raises `RuntimeError` on violations only when ratified or when `--fail-on-unratified` is passed. `nowing_evals/src/nowing_evals/core/notifications.py` sends Slack/Telegram with the failing thresholds and a link to `run_artifact.json`. `nowing_evals/.env.example` and `README.md` document the variables. Gaps: `docs/ops/deploy-gate.md` is not created; dedicated unit tests for the cost-cap early-exit and notification payload are missing.

## References

- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`
- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- `docs/ops/deploy-gate.md` (create or update)
