---
stepsCompleted: ['step-01-preflight', 'step-02-generate-pipeline', 'step-03-configure-quality-gates', 'step-04-validate-and-summary']
lastStep: 'step-04-validate-and-summary'
lastSaved: '2026-04-21'
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

### Next Steps for User

1. **Commit & push** `.github/workflows/frontend-tests.yml`
2. **Open a PR** → triggers lint + test + burn-in
3. **Monitor** the Actions tab — first run should show 295 pass, ~14s
4. No secrets required for this workflow (Vitest + pnpm, no external services)
5. Optional: add coverage badge to `nowing_web/README.md` once first run completes
