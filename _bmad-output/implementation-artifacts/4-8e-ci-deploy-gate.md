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
- [x] Create `docs/ops/deploy-gate.md` with the full CI step.

### Tests

- [x] Existing unit tests for `gate.yaml` parsing and threshold comparison via `tests/suites/chat/test_regression.py`.
- [x] Unit test for cost-cap early-exit.
- [x] Respx-mocked test for Slack/Telegram notification payload.

## Verification

```bash
cd nowing_evals
python -m nowing_evals run chat regression --search-space-id 42 --n 2 --max-total-cost-micros 500000 --help
python -m nowing_evals run chat regression --search-space-id 42 --n 2 --max-total-cost-micros 500000 --fail-on-unratified
ruff check src/nowing_evals/suites/chat/regression/ src/nowing_evals/core/notifications.py
ruff format src/nowing_evals/suites/chat/regression/ src/nowing_evals/core/notifications.py
python -m pytest tests/suites/chat/test_regression.py -q
```

### Review Findings

- [x] [Review][Patch] Workflow references non-existent GitHub Action versions `[.github/workflows/chat-regression-gate.yml:44,47,52]` — high
- [x] [Review][Patch] Missing dataset ingestion step before running benchmark `[.github/workflows/chat-regression-gate.yml:68-74]` — medium
- [x] [Review][Patch] Missing --n / max-cases input in GitHub Action `[.github/workflows/chat-regression-gate.yml, runner.py:648]` — high
- [x] [Review][Patch] Missing --backend-build-id in workflow inputs/run step `[.github/workflows/chat-regression-gate.yml]` — medium
- [x] [Review][Patch] Missing --fail-on-unratified in workflow inputs/run step `[.github/workflows/chat-regression-gate.yml, runner.py:1169]` — medium
- [x] [Review][Patch] actions/upload-artifact only uploads run_artifact.json, omits raw.jsonl `[.github/workflows/chat-regression-gate.yml:81]` — medium
- [x] [Review][Patch] cancel-in-progress: true may abort running evaluations `[.github/workflows/chat-regression-gate.yml:34-36]` — low
- [x] [Review][Patch] Missing NOWING_JWT support in workflow env `[.github/workflows/chat-regression-gate.yml:60-67]` — low
- [x] [Review][Patch] CHAT_EVAL_* env vars not parsed by config/runner `[.env.example:100-102, core/config.py]` — medium
- [x] [Review][Patch] Telegram/Slack Markdown escaping edge cases remain `[notifications.py:29-39]` — low
- [x] [Review][Patch] Artifact URL concatenation missing slash normalization `[notifications.py:19-26]` — medium
- [x] [Review][Patch] notifications.py reads os.environ directly instead of Config `[notifications.py:207-209]` — low
- [x] [Review][Patch] Cost cap raises before artifact write and notification `[runner.py:1106-1110,1133,1148]` — high
- [x] [Review][Patch] max_total_cost_micros truthiness treats 0 as falsy `[runner.py:1107]` — medium
- [x] [Review][Patch] gate_violations not stored in run_artifact.json `[runner.py:1134-1143]` — low
- [x] [Review][Patch] Notification only sent on gate_violations, not cost cap/unratified `[runner.py:1107-1173]` — medium
- [x] [Review][Patch] run_artifact_str is absolute local path when URL prefix unset `[runner.py:1146]` — low
- [x] [Review][Patch] Missing docs/ops/deploy-gate.md and README updates `[README.md:89-135]` — medium
- [x] [Review][Patch] Missing unit test for cost-cap early-exit `[tests/suites/chat/test_regression.py]` — medium
- [x] [Review][Patch] Missing respx-mocked test for Slack/Telegram notification payload `[tests/core/]` — medium
- [x] [Review][Patch] Missing test coverage for gate failure notifications and unratified handling `[tests/suites/chat/test_regression.py]` — high

## Code status note

Implemented and merged. The `chat-regression-gate.yml` GitHub Action triggers by `workflow_dispatch`, runs the benchmark with cost cap and notification env vars, and uploads the run artifact plus raw trace. `ChatRegressionBenchmark` evaluates `gate.yaml` thresholds (including the new operational metrics), logs a warning when `baseline_ratified: false`, raises `RuntimeError` on violations only when ratified or when `--fail-on-unratified` is passed, and notifies on cost-cap failures too. `nowing_evals/src/nowing_evals/core/notifications.py` sends Slack/Telegram with the failing thresholds and a link to `run_artifact.json`; `Config` now exposes `CHAT_EVAL_*` and notification settings. `nowing_evals/.env.example`, `README.md`, and `docs/ops/deploy-gate.md` document the gate. Unit tests cover cost-cap early-exit, notification payload, and unratified handling.

## References

- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`
- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- `docs/ops/deploy-gate.md` (create or update)
