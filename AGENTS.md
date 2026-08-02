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
