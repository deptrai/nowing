---
stepsCompleted: ['step-01-preflight', 'step-02-generate-pipeline', 'step-03-configure-quality-gates', 'step-04-validate-and-summary', 'step-01-preflight-e2e', 'step-02-generate-pipeline-e2e', 'step-03-configure-quality-gates-e2e', 'step-04-validate-and-summary-e2e', 'step-04-validate-and-summary-2026-05-01']
lastStep: 'step-04-validate-and-summary-2026-05-01'
lastSaved: '2026-05-01'
---

# CI/CD Pipeline Progress

## Step 01 — Preflight Checks

### Git Repository
- ✅ `.git/` exists
- ✅ Remote: `nowing` → https://github.com/deptrai/nowing.git

### Test Stack Type
- **detected_stack_type: `frontend`**
- Indicators: `vitest.config.ts`, `next.config.ts`, `nowing_web/` present
- No backend test config found in frontend subdirectory scope

### Test Framework
- **Framework: `vitest`** (v3.2.4)
- Config: `nowing_web/vitest.config.ts`
- Setup: `nowing_web/vitest.setup.ts`
- Environment: `jsdom`
- Test script: `vitest` (via `npm test`)
- Coverage: `v8` provider

### Local Test Run
- ✅ `npx vitest run` → **295 PASS, 0 FAIL**

### CI Platform
- **Detected: `github-actions`**
- Existing workflows found in `.github/workflows/`:
  - `backend-tests.yml` — Python pytest (unit + integration)
  - `code-quality.yml` — pre-commit, biome, ruff, security scan
  - `desktop-release.yml`
  - `docker-build.yml`
- **Gap identified:** No frontend Vitest workflow exists yet

### Environment Context
- Package manager: **pnpm** (`pnpm-lock.yaml` present, lockfileVersion 9.0)
- Node.js: v25.9.0 (local), no `.nvmrc` → will pin to **Node 22 LTS** in CI
- Working directory: `nowing_web/`
- Existing `code-quality.yml` uses `pnpm/action-setup@v4`

---

## Step 02 — Generate Pipeline

### Output
- **Created:** `.github/workflows/frontend-tests.yml`

### Configuration
- **Trigger:** `push`/`pull_request` to `main`/`dev` with `paths: nowing_web/**`
- **Schedule:** Weekly burn-in Sunday 02:00 UTC
- **Concurrency:** cancel-in-progress per workflow+ref
- **Node:** 22 LTS (pinned)
- **Package manager:** pnpm + `pnpm/action-setup@v4`
- **Cache:** pnpm store keyed on `nowing_web/pnpm-lock.yaml`

### Jobs
| Job | Trigger | Key action |
|-----|---------|-----------|
| `lint` | all triggers | `pnpm exec next lint` in `nowing_web/` |
| `test` | all triggers (needs lint) | `pnpm exec vitest run --coverage`, uploads coverage artifact |
| `burn-in` | PR + schedule only (needs test) | 10-iteration loop `|| exit 1` |
| `report` | always (needs test + burn-in) | GitHub Step Summary table |

---

## Step 03 — Quality Gates

- **Burn-in:** ✅ enabled (frontend stack → targets UI flakiness)
  - 10 iterations, `|| exit 1` gates promotion
  - Failure artifacts uploaded with 7-day retention
- **Contract testing:** N/A (`tea_use_pactjs_utils: false`)
- **Security:** no `${{ inputs.* }}` in `run:` blocks (no reusable workflow inputs in this file)
- **Coverage artifacts:** uploaded on `always()` with 14-day retention

---

## Step 04 — Validate & Summary

### Checklist

| Item | Status |
|------|--------|
| CI config file created at correct path | ✅ `.github/workflows/frontend-tests.yml` |
| YAML syntactically valid | ✅ |
| Framework commands correct for stack (vitest, not playwright) | ✅ |
| Node version matches project intent (22 LTS) | ✅ |
| pnpm setup matches existing `code-quality.yml` pattern | ✅ |
| Burn-in enabled (frontend stack) | ✅ 10 iterations |
| Burn-in exits on failure | ✅ `|| exit 1` |
| Burn-in runs on PR + schedule only | ✅ |
| Coverage artifacts uploaded | ✅ 14-day retention |
| Burn-in failure artifacts uploaded | ✅ 7-day retention |
| No secrets hardcoded | ✅ |
| No browser install (vitest/jsdom — no Playwright) | ✅ correctly omitted |
| Paths filter on `nowing_web/**` | ✅ avoids false triggers |
| Concurrency cancel-in-progress | ✅ |

---

## Round 2 — E2E + API CI (2026-04-22)

### Step 1: Preflight ✅
- Stack: `fullstack` (Playwright + pytest)
- Gaps: no `e2e-tests.yml`, `backend-tests.yml` missing API layer

### Step 2: Generate Pipeline ✅
- **Created:** `.github/workflows/e2e-tests.yml`
  - install → burn-in (PR only, 5 iters) → e2e (2 shards, fail-fast:false) → report
  - Services: Postgres + backend Docker image
- **Updated:** `.github/workflows/backend-tests.yml`
  - Added `api-tests` job: `pytest tests/api/` + Postgres service
  - `test-gate` now requires unit + integration + api-tests

### Step 3: Quality Gates ✅
- Burn-in: 5 iterations on changed E2E specs (PR only)
- Slack notification on failure (`SLACK_WEBHOOK_URL` secret, optional)
- Required secrets: `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`, `SLACK_WEBHOOK_URL` (opt)

### Step 4: Validate & Summary ✅
- All validation checks passed (see checklist)
- Manual start confirmed: `nohup uvicorn` + `nohup pnpm start` (không dùng Docker)
- Postgres services container retained (infrastructure only)
- Security: script injection mitigated via `env:` intermediaries
- Artifacts: 7-day (burn-in) + 14-day (e2e shards)
- `backend-tests.yml` updated: api-tests job + test-gate updated

