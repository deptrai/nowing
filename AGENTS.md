# Agent Notes — Nowing

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
