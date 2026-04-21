---
stepsCompleted: ['step-01-preflight', 'step-02-select-framework', 'step-03-scaffold-framework', 'step-04-docs-and-scripts', 'step-05-validate-and-summary']
lastStep: 'step-05-validate-and-summary'
lastSaved: '2026-04-22'
---

# Test Framework Setup — Progress Document

## Step 1: Preflight Checks ✅

### Stack Detection
- **detected_stack**: `fullstack`
- **Frontend**: `nowing_web/` — Next.js 15, React 19, TypeScript, pnpm, Tailwind CSS 4
- **Backend**: `nowing_backend/` — Python 3.12, FastAPI, uvicorn, asyncpg/PostgreSQL

### Prerequisites
- `nowing_web/package.json` ✅
- No existing E2E framework (playwright.config / cypress.config) ✅
- `nowing_backend/pyproject.toml` ✅

### Current Test State
- Vitest (unit tests) already configured in `nowing_web/`
- No E2E tests
- No API integration tests

### Key Dependencies (frontend)
- Next.js 15, React 19, TypeScript
- pnpm package manager
- Vitest (existing unit test runner)
- Tailwind CSS 4, Radix UI, PlateJS, BlockNote, ElectricSQL

### Key Dependencies (backend)
- Python 3.12, FastAPI, uvicorn
- asyncpg, PostgreSQL, pgvector
- Alembic (migrations)
- Playwright already in backend deps (for scraping/automation, NOT testing)

## Step 4: Documentation & Scripts ✅

### Files Created
- `nowing_web/playwright/README.md` — Setup, architecture, fixtures, best practices, CI notes
- `nowing_backend/Makefile` — pytest shortcuts: `make test`, `test-unit`, `test-integration`, `test-api`, `test-cov`, `test-fast`

### Scripts (package.json — already added in step 3)
- `test:e2e`, `test:e2e:ui`, `test:e2e:debug`, `test:e2e:headed`, `test:e2e:report`

### Backend pytest commands (pyproject.toml — already configured)
- `uv run pytest` — all tests
- `uv run pytest -m unit` — fast loop
- `uv run pytest -m integration` — requires DB
- `uv run pytest --cov=app` — coverage
