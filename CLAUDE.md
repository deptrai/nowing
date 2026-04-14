# SurfSense — Claude Code Guide

## Tech Stack
- Frontend: Next.js 15 + TypeScript + Tailwind (in `surfsense_web/`)
- Backend: FastAPI + Python 3.12 + SQLAlchemy (in `surfsense_backend/`)
- Auth: FastAPI-Users with JWT
- DB: PostgreSQL via Alembic migrations

## Key Patterns
- Formatting: Biome for TS/TSX (`pnpm biome format --write <file>`), Ruff for Python (`ruff format <file> && ruff check --fix <file>`)
- Tests: Vitest for frontend (`pnpm test`), pytest-asyncio for backend (`pytest`)
- Migrations: Alembic in `surfsense_backend/migrations/versions/` — check latest number before creating new one
- Admin guard: use `current_superuser` dependency from `surfsense_backend/app/users.py`

## BMAD Artifacts
- Planning: `_bmad-output/planning-artifacts/`
- Implementation: `_bmad-output/implementation-artifacts/`
- Sprint status: `_bmad-output/planning-artifacts/*sprint-status*`

## Reference Docs (read when needed)
- Admin/RBAC patterns → `surfsense_backend/app/routes/admin_routes.py`
- Stripe billing → `_bmad-output/planning-artifacts/story-5.2*.md`
- Model config architecture → `_bmad-output/planning-artifacts/story-5.6*.md`
- Frontend user/auth atoms → `surfsense_web/atoms/user/user-query.atoms.ts`
