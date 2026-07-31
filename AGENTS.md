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

Notes:
- `pnpm lint` does not work because Next.js 16 CLI no longer exposes a `lint` subcommand and `eslint-plugin-react-hooks` is not installed.
- `pnpm test` is not configured in `package.json`; use Playwright (`test:e2e*`) or backend pytest for verification.
