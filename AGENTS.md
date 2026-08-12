# Agent Notes — Nowing

## Integration test setup (local)

Integration tests (`@pytest.mark.integration`) require a real PostgreSQL database with pgvector.

```bash
# 1. Start Postgres + Redis (from repo root)
docker compose -f docker/docker-compose.deps-only.yml up -d db redis

# 2. Run migrations (from nowing_backend/)
cd nowing_backend
uv run alembic upgrade head

# 3. Run integration tests
uv run pytest tests/integration/ -m integration -q

# Or specific test file:
uv run pytest tests/integration/test_okf_export_bundle.py -q
uv run pytest tests/integration/document_upload/test_okf_read.py -q
```

The test database defaults to `postgresql+asyncpg://postgres:postgres@localhost:5432/nowing_test`.
Override with `TEST_DATABASE_URL=...` if needed.

Unit tests (`@pytest.mark.unit`) do NOT require a database and run anywhere:
```bash
cd nowing_backend
uv run pytest tests/unit/ -m unit -q
```

## Mutation gate (cosmic-ray)

Run mutation testing on a service module:
```bash
# Standard service (app/services/{name}.py)
python scripts/mutation-gate.py --services token_quota --project-root . --timeout 120.0

# Deep module path (e.g. app/capabilities/core/access/web_citation.py)
python scripts/mutation-gate.py --services capabilities/core/access/web_citation --project-root . --timeout 120.0

# Multiple modules (comma-separated)
python scripts/mutation-gate.py --services services/okf/redaction,services/okf/validator --project-root . --timeout 60.0
```

Output: `_bmad-output/test-artifacts/mutation-nowing-{service}-{timestamp}.json`

## Story 4.8g / 4.8e / 9.2 chat regression verification commands

Backend (from `nowing_backend/`):

```bash
ruff check app/schemas/new_chat.py app/routes/new_chat_routes.py app/tasks/chat/streaming/flows/new_chat/orchestrator.py app/capabilities/core/access/agent.py app/services/token_tracking_service.py
pytest tests/unit/capabilities/access/test_agent_tools.py tests/integration/capabilities/chainlens/research/test_research_cost_metering.py -q
```

Evals (from `nowing_evals/`):

```bash
ruff check src/nowing_evals/suites/chat/regression/runner.py
python -m pytest tests -q
python -m nowing_evals run chat regression --search-space-id 446 --profile quick --environment local --concurrency 1
python -m nowing_evals run chat regression --search-space-id 446 --profile full --tags deep-research --modes speed,balanced,quality,auto --timeout 600 --environment local --concurrency 1
python -m nowing_evals report --suite chat
```

Notes:
- Default `--timeout` is now 600s so `chat-research-001` can complete in local benchmark mode.
- `NewChatRequest.mode` is threaded through to `chainlens.research`; the per-mode benchmark matrix should show different latency/cost.
- Deep-research cost is added to the chat turn's `data-token-usage` SSE when `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=true`.

## Story 8.11 verification commands

Backend (from `nowing_backend/`):

```bash
ruff check app/users.py app/routes/admin_global_model_connections_routes.py app/schemas/admin_global_model_connections.py app/services/global_model_catalog.py app/services/pricing_registration.py app/services/auto_model_pin_service.py tests/integration/routes/test_admin_global_model_connections.py
ruff format app/routes/admin_global_model_connections_routes.py app/services/global_model_catalog.py tests/integration/routes/test_admin_global_model_connections.py
pytest tests/integration/routes/test_admin_global_model_connections.py -q
pytest tests/integration/test_pat_fail_closed_authz.py tests/unit/services/test_model_connections.py tests/unit/services/test_pricing_registration.py tests/unit/services/test_auto_model_pin_service.py tests/unit/tasks/chat/streaming/test_llm_bundle.py -q
```

Frontend (from `nowing_web/`):

```bash
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/global-model-connections/page.tsx app/admin/admin-shell.tsx app/admin/layout.tsx atoms/model-connections/admin-global-model-connections.atoms.ts contracts/types/admin-global-model-connections.types.ts lib/apis/admin-global-models-api.service.ts
```

## Story 8.10 verification commands

Docs / README / vision sync (from repo root):

```bash
python3 scripts/check-docs-drift.py
```

Frontend typecheck (from `nowing_web/`) for changed TSX files:

```bash
pnpm tsc --noEmit
pnpm exec biome check app/layout.tsx components/seo/json-ld.tsx components/homepage/hero-section.tsx components/homepage/compare-table.tsx 'app/(home)/free/page.tsx' messages/en.json messages/ko.json --diagnostic-level=error
```

## Production auth cookie domain

When the Nowing frontend (`nowing.net`), backend (`api.nowing.net`) and Zero cache (`zero.nowing.net`) run on different subdomains, the backend must set auth cookies with a shared parent domain. If `COOKIE_DOMAIN` is left empty, the `nowing_session` and `nowing_refresh` cookies are host-only for `api.nowing.net`; the browser will not send them to `zero.nowing.net`, causing Zero sync to return 401 and the dashboard to log the user out after the auth-retry limit is exhausted.

Fix: set `COOKIE_DOMAIN=nowing.net` (or `.nowing.net`) in the backend production environment.

Verification:
- Login response `Set-Cookie` headers should include `Domain=nowing.net`.
- After logging in, the user should stay on `/dashboard/*` for at least 2 minutes without console `TransformFailed 401` errors.

Notes:
- `pnpm lint` does not work because Next.js 16 CLI no longer exposes a `lint` subcommand and `eslint-plugin-react-hooks` is not installed.
- `pnpm test` is not configured in `package.json`; use Playwright (`test:e2e*`) or backend pytest for verification.

## Story 11.1 verification commands (Telegram Notification Foundation)

Backend (from `nowing_backend/`):

```bash
ruff check app/db.py app/schemas/users.py app/routes/users_routes.py app/notifications/types.py app/notifications/constants.py app/gateway/telegram/formatting.py app/automations/runtime/executor.py app/automations/services/telegram_notifications.py app/automations/tasks/notify_run_complete.py app/celery_app.py alembic/versions/187_add_user_notification_preferences.py tests/unit/automations/test_telegram_notification_formatter.py tests/integration/automations/test_run_notification.py tests/integration/routes/test_user_notification_preferences.py
ruff format app/db.py app/schemas/users.py app/routes/users_routes.py app/notifications/types.py app/notifications/constants.py app/gateway/telegram/formatting.py app/automations/runtime/executor.py app/automations/services/telegram_notifications.py app/automations/tasks/notify_run_complete.py app/celery_app.py alembic/versions/187_add_user_notification_preferences.py tests/unit/automations/test_telegram_notification_formatter.py tests/integration/automations/test_run_notification.py tests/integration/routes/test_user_notification_preferences.py
pytest tests/unit/automations/test_telegram_notification_formatter.py tests/integration/automations/test_run_notification.py tests/integration/routes/test_user_notification_preferences.py -q
pytest tests/unit/gateway/ -q
pytest tests/integration/gateway/test_telegram_inbox.py -q
```

Frontend (from `nowing_web/`):

```bash
pnpm tsc --noEmit
pnpm exec biome check app/dashboard/\[workspace_id\]/user-settings/components/MessagingChannelsContent.tsx app/dashboard/\[workspace_id\]/automations/\[automation_id\]/automation-detail-content.tsx app/dashboard/\[workspace_id\]/automations/\[automation_id\]/components/automation-runs-section.tsx app/dashboard/\[workspace_id\]/automations/\[automation_id\]/components/run-row.tsx contracts/types/user.types.ts
```

## Story 11.3 verification commands (Telegram interactive bot & commands)

Backend (from `nowing_backend/`):

```bash
ruff check app/gateway/telegram/commands.py app/gateway/telegram/callbacks.py app/gateway/inbox_processor.py app/gateway/base/commands.py tests/unit/gateway/test_telegram_commands.py tests/unit/gateway/test_telegram_callbacks.py tests/integration/gateway/test_telegram_inbox.py
ruff format app/gateway/telegram/commands.py app/gateway/telegram/callbacks.py app/gateway/inbox_processor.py app/gateway/base/commands.py tests/unit/gateway/test_telegram_commands.py tests/unit/gateway/test_telegram_callbacks.py tests/integration/gateway/test_telegram_inbox.py
pytest tests/unit/gateway/ -q
pytest tests/integration/gateway/test_telegram_inbox.py -q
```

## Story 10.x verification commands (scraper platform accounts + phone fetch)

Backend (from `nowing_backend/`):

```bash
ruff check app/proprietary/platforms/batdongsan app/proprietary/platforms/muaban_bds app/services/scraper_platform_account_service.py app/routes/admin_scraper_platform_accounts_routes.py app/capabilities/batdongsan/scrape/executor.py
pytest tests/unit/platforms/batdongsan -q
pytest tests/unit/platforms/muaban_bds -q
```

Frontend (from `nowing_web/`):

```bash
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/scraper-accounts/page.tsx lib/apis/scraper-platform-accounts-api.service.ts
```

Docs drift (from repo root):

```bash
python3 scripts/check-docs-drift.py
```

## Story 8.12 verification commands (Workspace Limits)

Backend (from `nowing_backend/`):

```bash
ruff check app/services/workspace_limits.py app/routes/workspaces_routes.py app/routes/documents_routes.py app/routes/rbac_routes.py app/capabilities/core/access/rest.py app/db.py app/schemas/workspace.py app/schemas/__init__.py app/config/__init__.py alembic/versions/189_add_workspace_plan_and_limits.py tests/integration/services/test_workspace_limits.py
ruff format app/services/workspace_limits.py app/routes/workspaces_routes.py app/routes/documents_routes.py app/routes/rbac_routes.py app/capabilities/core/access/rest.py app/db.py app/schemas/workspace.py app/schemas/__init__.py app/config/__init__.py alembic/versions/189_add_workspace_plan_and_limits.py tests/integration/services/test_workspace_limits.py
pytest tests/integration/services/test_workspace_limits.py -q
```

Frontend (from `nowing_web/`):

```bash
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/dashboard/\[workspace_id\]/workspace-settings/layout-shell.tsx app/dashboard/\[workspace_id\]/workspace-settings/limits/page.tsx components/settings/workspace-limits-manager.tsx lib/apis/workspaces-api.service.ts lib/query-client/cache-keys.ts contracts/types/workspace.types.ts messages/en.json
```

Notes:
- `tests/integration/document_upload/test_document_upload.py` may fail locally if `ETL_SERVICE` is unset; that is an environment issue unrelated to this story.

## Story 4.8 verification commands

Chat benchmark telemetry + regression suite (from `nowing_evals/`):

```bash
ruff check src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py src/nowing_evals/core/cli.py src/nowing_evals/core/registry.py src/nowing_evals/suites/chat/ tests/core/test_clients.py tests/core/test_cli_ingest_report.py tests/suites/chat/test_regression.py
ruff format src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py src/nowing_evals/core/cli.py src/nowing_evals/core/registry.py src/nowing_evals/suites/chat/ tests/core/test_clients.py tests/core/test_cli_ingest_report.py tests/suites/chat/test_regression.py
python -m pytest tests/core/test_clients.py tests/core/test_cli_ingest_report.py tests/suites/chat/test_regression.py -q
python -m pytest -q
python -m nowing_evals benchmarks list
```

Smoke (requires auth + search space):

```bash
python -m nowing_evals ingest chat regression
python -m nowing_evals run chat regression --search-space-id <SEARCH_SPACE_ID> --concurrency 1
python -m nowing_evals report --suite chat
```

## Story 9.1a verification commands (Research Degradation & Self-Host Independence)

Backend (from `nowing_backend/`):

```bash
ruff check app/capabilities/chainlens/research app/capabilities/core/access/rest.py app/capabilities/core/access/agent.py tests/unit/capabilities/chainlens/research tests/unit/capabilities/access/test_rest_router.py tests/unit/capabilities/access/test_agent_tools.py
ruff format app/capabilities/chainlens/research app/capabilities/core/access/rest.py app/capabilities/core/access/agent.py tests/unit/capabilities/chainlens/research tests/unit/capabilities/access/test_rest_router.py tests/unit/capabilities/access/test_agent_tools.py
pytest tests/unit/capabilities/chainlens/research -q
pytest tests/unit/capabilities/access/test_rest_router.py tests/unit/capabilities/access/test_agent_tools.py -q
pytest tests/unit/capabilities/test_billing.py tests/unit/utils/test_crawl_classifier.py -q
```

E2E (from `nowing_web/`, requires backend with `CHAINLENS_API_KEY=""` and `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=true` so the agent research tool returns its result inline in the hermetic fake environment):

```bash
docker compose -f docker/docker-compose.deps-only.yml up -d db redis
cd nowing_backend
CHAINLENS_API_KEY="" DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=true uv run python tests/e2e/run_backend.py
# in another shell:
CHAINLENS_API_KEY="" DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=true uv run python tests/e2e/run_celery.py
# in another shell:
cd nowing_web
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8001 pnpm build
# `next start` is not compatible with `output: standalone`; use the standalone server:
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8001 PORT=3000 node .next/standalone/nowing_web/server.js
# in another shell:
PLAYWRIGHT_NO_WEB_SERVER=1 NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8001 NOWING_BACKEND_INTERNAL_URL=http://localhost:8001 pnpm test:e2e tests/research/research-degradation.spec.ts
# and the chat/agent path:
PLAYWRIGHT_NO_WEB_SERVER=1 NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8001 NOWING_BACKEND_INTERNAL_URL=http://localhost:8001 pnpm test:e2e tests/research/research-degradation-chat.spec.ts
```

## Local dev server startup (smoke)

Start the full local stack (backend on host, deps in Docker). Default ports `5432` and `6379` are often taken by a host Postgres/Redis or other projects, so use `5434` and `6380`.

```bash
# 1. Docker deps (Postgres + Redis, zero-cache needs them)
cd /Users/luisphan/Documents/GitHub/nowing
POSTGRES_PORT=5434 REDIS_PORT=6380 docker compose -f docker/docker-compose.deps-only.yml up -d db redis

# 2. Migrations (from nowing_backend/)
cd nowing_backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing uv run alembic upgrade head

# If alembic ran create_all on a fresh DB, zero_publication may be missing. Create it:
uv run python -c "
from sqlalchemy import create_engine
from app.zero_publication import ensure_publication
engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5434/nowing')
with engine.connect() as conn:
    ensure_publication(conn)
    conn.commit()
"

# 3. Start zero-cache
POSTGRES_PORT=5434 REDIS_PORT=6380 docker compose -f docker/docker-compose.deps-only.yml up -d zero-cache
# Wait for healthy:
# docker ps --filter 'name=zero-cache' --format '{{.Status}}'

# 4. Start backend (from nowing_backend/)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing uv run python main.py

# 5. Start frontend (from nowing_web/)
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000 \
NOWING_BACKEND_INTERNAL_URL=http://localhost:8000 \
NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848 \
pnpm dev
```

### Important env/cookie gotchas

- `nowing_web/.env.local` should use `http://localhost:8000` for backend URLs, NOT `http://127.0.0.1:8001`. The previous `8001` port is no longer used.
- `NEXT_PUBLIC_ZERO_CACHE_URL` must be `http://localhost:4848` (not `127.0.0.1:4848`). The `nowing_session` cookie is `HttpOnly; SameSite=Lax` and is only sent when the browser connects to the same `localhost` host as the page. Using `127.0.0.1` makes zero-cache forward an empty cookie to `/api/zero/query`, causing `401 TransformFailed`.
- `nowing_backend/.env` should point `DATABASE_URL` to the Docker Postgres port (e.g. `postgresql+asyncpg://postgres:postgres@localhost:5434/nowing`). `5432` may be a separate host Postgres that zero-cache cannot reach.
- If `lsof -i :5432` or `lsof -i :6379` show a host service, keep using `5434`/`6380`. Both the `POSTGRES_PORT`/`REDIS_PORT` env vars and the backend `DATABASE_URL`/`REDIS_URL` must agree.

### Smoke test

1. Open `http://localhost:3000/login`
2. Register or log in with `e2e-test@nowing.net` / `E2eTestPassword123!`
3. Navigate to `/dashboard/1/new-chat` — console should be clean (0 errors)
4. Navigate to `/dashboard/1/usage` — console should be clean
