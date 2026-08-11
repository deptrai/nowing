# Nowing — Hướng dẫn kiểm thử

**Ngày cập nhật:** 2026-08-11

Tài liệu này tóm tắt chiến lược kiểm thử của Nowing, các lệnh chạy thường dùng và các cổng chất lượng.

## Chiến lược kiểm thử

Dự án sử dụng **nhiều lớp kiểm thử**:

- **Unit tests** (`@pytest.mark.unit`) — không cần DB, chạy nhanh.
- **Integration tests** (`@pytest.mark.integration`) — cần PostgreSQL thật với pgvector và Redis.
- **Contract tests** (`@pytest.mark.contract`) — kiểm tra hợp đồng ChainLens.
- **E2E tests** (Playwright) — frontend chạy với backend thật hoặc fake.
- **Evals harness** (`nowing_evals`) — benchmark chat regression, memory recall, canonical entity.
- **Mutation gate** (`cosmic-ray` / `scripts/mutation-gate.py`) — đo chất lượng test suite.

## Backend (`nowing_backend/`)

### Chuẩn bị integration test

```bash
# 1. Start Postgres + Redis (từ repo root)
docker compose -f docker/docker-compose.deps-only.yml up -d db redis

# 2. Chạy migrations (từ nowing_backend/)
cd nowing_backend
uv run alembic upgrade head
```

### Chạy test

```bash
cd nowing_backend

# Unit tests
uv run pytest tests/unit/ -m unit -q

# Integration tests
uv run pytest tests/integration/ -m integration -q

# Cụ thể (ví dụ)
uv run pytest tests/integration/test_okf_export_bundle.py -q
uv run pytest tests/integration/document_upload/test_okf_read.py -q
```

### Mutation gate

```bash
# Chạy trên một service module
cd nowing_backend
python scripts/mutation-gate.py --services token_quota --project-root . --timeout 120.0

# Module sâu
python scripts/mutation-gate.py --services capabilities/core/access/web_citation --project-root . --timeout 120.0

# Nhiều module
python scripts/mutation-gate.py --services services/okf/redaction,services/okf/validator --project-root . --timeout 60.0
```

Output: `_bmad-output/test-artifacts/mutation-nowing-{service}-{timestamp}.json`.

## Frontend (`nowing_web/`)

### Typecheck & lint

```bash
cd nowing_web
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 <paths>
```

### E2E (Playwright)

```bash
cd nowing_web
pnpm test:e2e
pnpm test:e2e:prod
pnpm test:e2e:ui
```

## Evals (`nowing_evals/`)

```bash
cd nowing_evals

# List benchmarks
python -m nowing_evals benchmarks list

# Chat regression (local)
python -m nowing_evals run chat regression \
  --search-space-id 446 \
  --profile quick \
  --environment local \
  --concurrency 1

# Chat regression (full)
python -m nowing_evals run chat regression \
  --search-space-id 446 \
  --profile full \
  --tags deep-research \
  --modes speed,balanced,quality,auto \
  --timeout 600 \
  --environment local \
  --concurrency 1

# Báo cáo
python -m nowing_evals report --suite chat
```

## CI / GitHub Actions

Các workflow chính trong `.github/workflows/`:

- `backend-tests.yml` — pytest backend.
- `code-quality.yml` — ruff / biome.
- `e2e-tests.yml` — Playwright.
- `chat-regression-gate.yml` — `nowing_evals` chat regression.
- `memory-recall-gate.yml` — memory recall eval.
- `memory-recall-release-gate.yml` — release gate.
- `mutation-gate.yml` — cosmic-ray mutation.
- `chainlens-research-mutation-gate.yml` — mutation for ChainLens.
- `docker-build.yml` — build/push images.
- `desktop-release.yml` — desktop release.
- `obsidian-plugin-lint.yml` — lint Obsidian plugin.
- `release-obsidian-plugin.yml` — release plugin.
- `test.yml` — tổng hợp test.
- `notary-status.yml` — notary checks.

## Cổng chất lượng hiện tại

- **E3.9 memory recall eval-gate**: baseline ratified 2026-08-04, 168 tests passed.
- **E4.8 chat regression**: baseline pending measured run.
- **E8.7 auto-extract spend cap**: 59 tests passed.
- **E16.1 masothue mutation**: PASS_WITH_WARNINGS 61.12% (cuối cùng đạt).
- **Code reviews mở**: 13-3, 15-1 (CHANGES_REQUESTED — các P0 đã fix, một số P1/P2 còn).

## Tài liệu liên quan

- [nowing-mutation-gate-reference.md](./nowing-mutation-gate-reference.md)
- [ci.md](./ci.md)
