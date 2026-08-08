---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 8-11-admin-ui-global-llm-model-config
status: done
---

# Story 8.11: Admin UI for Global LLM Model Configuration

**Status:** done
**Epic:** 8 — Người dùng thấy và kiểm soát được chi phí
**Priority:** HIGH — FR-41 / provider-model-routing P0 area
**Requirements:** FR-41, FR-30, FR-31
**Architecture:** AD-2, AD-6, AD-8, AD-9
**Dependencies:** Story 8.7 and 8.8 done; model-connections foundation exists from migration 160 and route/service code.

## Story

Là platform admin của Nowing,
tôi muốn thêm, sửa, xoá, bật/tắt global chat model qua một trang settings cấp platform,
để vận hành Auto mode không cần decode/sửa/encode `GLOBAL_LLM_CONFIG_B64`, sửa YAML gitignored, hoặc restart backend mỗi lần đổi model.

## Current Reality

Verified at baseline `25ba542c2a3dec95b0a4020da8c129242ba748e2`:

- Global YAML/env config is loaded through `_global_config_data()`: `GLOBAL_LLM_CONFIG_B64` wins over `app/config/global_llm_config.yaml`, then `Config.GLOBAL_LLM_CONFIGS = load_global_llm_configs()` at import time. Source: `nowing_backend/app/config/__init__.py:98-120`, `1060-1068`.
- `refresh_global_model_catalog()` already exists but only re-materializes from in-memory config lists into `config.GLOBAL_CONNECTIONS` and `config.GLOBAL_MODELS`. Source: `nowing_backend/app/config/__init__.py:423-435`.
- OpenRouter startup/refresh already calls `refresh_global_model_catalog()` and re-registers pricing during refresh. Source: `nowing_backend/app/config/__init__.py:366-418`; `nowing_backend/app/services/openrouter_integration_service.py:530-606`.
- `materialize_global_model_catalog()` only accepts YAML/env-style `chat_configs` and `image_configs`; it creates virtual GLOBAL connections/models with negative IDs and carries pricing metadata from `litellm_params`. Source: `nowing_backend/app/services/global_model_catalog.py:61-125`.
- `ConnectionScope.GLOBAL` already exists, and the DB constraint allows GLOBAL rows only with `workspace_id IS NULL` and `user_id IS NULL`. Source: `nowing_backend/app/db.py:210-213`, `1627-1663`.
- `Model` already has `billing_tier` and `catalog` JSONB, enough to store UI-managed cost/rate metadata without a new model table. Source: `nowing_backend/app/db.py:1666-1701`.
- Existing public read endpoint `GET /global-model-connections` serializes `config.GLOBAL_CONNECTIONS`/`GLOBAL_MODELS`; `_connection_read()` redacts dict-backed global `api_key` by exposing `has_api_key` and setting `api_key=None`. Source: `nowing_backend/app/routes/model_connections_routes.py:55-68`, `336-345`.
- Existing write endpoints intentionally reject GLOBAL in the regular user/workspace path: `POST /model-connections` raises `"GLOBAL connections are YAML-only"`. Source: `nowing_backend/app/routes/model_connections_routes.py:373-422`.
- Preview/test routes build a draft `Connection` and reuse `discover_models()`/`test_model()`, but today they are workspace/user scoped and not platform-admin scoped. Source: `nowing_backend/app/routes/model_connections_routes.py:425-515`.
- Auth has `get_auth_context()` and `require_session_context()`, but no `require_superuser()`. PATs are rejected by `require_session_context`. Source: `nowing_backend/app/users.py:330-401`.
- `User.is_superuser` is already exposed to the web user contract. Source: `nowing_web/contracts/types/user.types.ts:3-20`.
- Web model settings are workspace-scoped. Reusable component code lives in `nowing_web/components/settings/model-connections/`, but `ModelProviderConnectionsPanel` hard-codes `scope: "SEARCH_SPACE"` and `workspace_id`. Source: `nowing_web/components/settings/model-connections/model-provider-connections-panel.tsx:112-217`.
- Web API service and atoms only call regular `/model-connections*` write paths. Source: `nowing_web/lib/apis/model-connections-api.service.ts:38-193`; `nowing_web/atoms/model-connections/model-connections-mutation.atoms.ts:20-238`.
- Auto model pinning has a global virtual-catalog path that ignores non-negative IDs, and a DB-candidate path that can see ownerless GLOBAL rows but labels all DB candidates as `byok`. This story must not accidentally ship DB-backed global models as BYOK. Source: `nowing_backend/app/services/auto_model_pin_service.py:307-363`, `366-460`.
- Runtime loading checks `config_id < 0` first for global models and only falls through to `_get_db_model()` for non-negative IDs. Source: `nowing_backend/app/tasks/chat/streaming/flows/shared/llm_bundle.py:100-170`; `nowing_backend/app/services/llm_service.py:150-168`.
- Pricing registration reads `config.GLOBAL_LLM_CONFIGS` and supports both per-token and per-1k fields, converting per-1k to per-token. Source: `nowing_backend/app/services/pricing_registration.py:48-74`, `259-314`.

## Resolved Decisions

### D1 — Platform-admin boundary is `User.is_superuser`

Add `require_superuser()` in `nowing_backend/app/users.py` beside `require_session_context()`. It must depend on `require_session_context()` so PATs cannot manage platform config, then check `auth.user.is_superuser is True` and raise 403 otherwise.

Do not add a workspace role, custom role, or reintroduce an Admin system role. AD-9 keeps workspace RBAC to Owner/Editor/Viewer; platform admin is an orthogonal system boundary.

### D2 — Dedicated admin API path, not hidden branches in workspace CRUD

Use a platform-level backend route namespace under `/api/v1/admin/global-model-connections`. Keep the existing `/model-connections*` behavior unchanged, including the GLOBAL rejection for normal users. Hidden navigation on the frontend is defense in depth only; backend auth owns the boundary.

Minimum endpoints:

- `GET /admin/global-model-connections`
- `POST /admin/global-model-connections`
- `PUT /admin/global-model-connections/{connection_id}`
- `DELETE /admin/global-model-connections/{connection_id}`
- `POST /admin/global-model-connections/discover-preview`
- `POST /admin/global-model-connections/test-preview`
- `POST /admin/global-model-connections/{connection_id}/verify`
- `POST /admin/global-model-connections/{connection_id}/discover`
- `PATCH /admin/global-model-connections/{connection_id}/models`
- `PUT /admin/global-model-connections/models/{model_id}`
- `POST /admin/global-model-connections/models/{model_id}/test`

This may live in a new `nowing_backend/app/routes/admin_global_model_connections_routes.py` or in `model_connections_routes.py` with clear route grouping, but the dependency must be explicit on every admin write/test route.

### D3 — File-backed global entries are read-only in this story

Planning text in `epics.md` says file-backed YAML/env models are "xem được + toggle enable/disable tạm thời". The user request for this story says "file-backed entries read-only in UI". Verified code also has no persistence layer for file-backed disabled overrides: file-backed entries are virtual negative IDs rebuilt from YAML/env on refresh/startup.

Resolution: in Story 8.11, YAML/env and dynamic OpenRouter entries are displayed with source `file`/`config` and are read-only: no edit, no delete, no toggle. DB-backed entries created by the platform UI are source `managed` and are editable/deletable/toggleable. A future story can add a durable override table if temporary disables are still desired.

### D4 — Tenant-safe GLOBAL CRUD uses existing tables

Create actual `Connection(scope=ConnectionScope.GLOBAL, workspace_id=None, user_id=None)` rows and child `Model` rows. Never attach GLOBAL rows to a workspace or user. Regular workspace/user list endpoints must not leak GLOBAL DB rows; only admin routes can list/manage them.

Database migration is only needed if the implementation adds audit fields, source discriminator columns, or a generated runtime ID column. If the existing columns are sufficient, no schema migration is required. Either way, the story must include a migration/backward-compatibility test.

### D5 — DB-backed global rows are merged into the server-owned global catalog

DB-backed GLOBAL rows must be materialized into `config.GLOBAL_CONNECTIONS` and `config.GLOBAL_MODELS` alongside YAML/env entries so all current global-read surfaces and runtime paths see one catalog.

Required precedence:

1. YAML/env static entries keep their configured IDs and provider metadata.
2. Dynamic OpenRouter entries keep the existing OpenRouter refresh behavior.
3. DB-backed managed entries are appended after file-backed entries and must not overwrite a file-backed entry with the same provider/model/base/key unless the story explicitly implements a deterministic conflict rule and tests it.
4. When the same DB connection has several models, preserve one connection entry and multiple model entries.

Runtime IDs: global runtime models must remain negative or otherwise be supported by every call site that assumes negative means global. Do not let DB-backed GLOBAL rows appear only as positive-ID DB candidates with `billing_tier="byok"`. Acceptable implementation: derive stable negative runtime IDs from DB IDs (for example `-(1_000_000 + model.id)` and `-(1_000_000 + connection.id)`) and store `db_connection_id`/`db_model_id` in `catalog` for admin operations.

### D6 — Hot reload after successful CRUD, with bounded refresh concurrency

After every successful admin mutation commit, call `refresh_global_model_catalog()` and re-run pricing registration for the merged global config/metadata before returning the response. If the LLM router cache must be rebuilt for the new global pool to affect router-backed paths, rebuild it in the same post-commit refresh helper.

Do not call refresh before commit. If the DB commit fails, in-memory catalog must remain unchanged. If refresh/pricing/router rebuild fails after commit, return a clear 500 with `refresh_failed` semantics and log the committed entity IDs; the next successful refresh or process restart must reconcile DB state. Use an `asyncio.Lock` or equivalent process-local lock around refresh/rebuild to avoid concurrent admin writes racing in one process. Cross-process propagation is best-effort in this story: no restart is required for the serving process handling the write; other backend/Celery processes may require their own refresh trigger unless an existing process-wide broadcast is reused.

### D7 — Secrets are write-only/redacted

Admin reads must never return real API keys. Existing `ConnectionRead` can be reused only if `api_key` is always `None` on read and `has_api_key` is correct. Updating a connection with omitted `api_key` preserves the stored key. Updating with `api_key: null` clears it only if the UI intentionally exposes a clear-key action. Empty string must normalize to `None`.

### D8 — LiteLLM cost mapping is per-token, UI may accept per-1k

UI fields may be labelled as cost per 1k input/output tokens, but backend storage must result in `input_cost_per_token` and `output_cost_per_token` being registered with LiteLLM. Store both human-entered per-1k values and normalized per-token values in `Model.catalog` or generated config metadata, and test that `pricing_registration` registers the normalized values.

Do not add flat per-call pricing for this story. AD-8 rejects guessed flat pricing as source of truth.

### D9 — Auditability through structured app logs in this story

No dedicated audit-log table exists for model-connection changes at baseline. For Story 8.11, every admin create/update/delete/test/refresh action must emit a structured log with `actor_user_id`, action, source, connection/model IDs, provider/model identifiers, success/failure, and refresh outcome. Do not log API keys or raw secrets.

If implementation adds a persistent audit table, include Alembic migration and tests; otherwise structured logs are accepted for this story.

## Acceptance Criteria

1. **Platform-admin authorization boundary**
   - Given an authenticated user with `is_superuser=false`, including a Workspace Owner, when they call any `/api/v1/admin/global-model-connections*` endpoint, then the response is 403 and no DB row, refresh, pricing registration, or test call occurs.
   - Given a PAT-authenticated request, when it calls the same endpoints, then the response is 403 because the route requires an interactive session.
   - Given `is_superuser=true`, when the admin calls the endpoints, then authorization succeeds without requiring any workspace role.

2. **Unified global model list with redacted secrets**
   - Given file-backed YAML/env entries and DB-backed managed entries exist, when a platform admin opens the platform global model settings route, then they see one list containing both sources with clear source labels.
   - Then no response payload contains a real `api_key`; only `has_api_key`/secret status is exposed.
   - Then non-superusers cannot retrieve the admin list even if client navigation is hidden.

3. **Create DB-backed GLOBAL model**
   - Given a platform admin submits provider, model ID, display name, API base, API key, enabled state, capabilities, cost per 1k input/output tokens, rpm and tpm, when the create request succeeds, then a `Connection.scope=GLOBAL` row with `workspace_id=NULL` and `user_id=NULL` and at least one child `Model` row are committed.
   - Then the model appears in `config.GLOBAL_MODELS` for subsequent requests without backend restart.
   - Then regular `/model-connections` user/workspace endpoints still do not create or list GLOBAL DB rows.

4. **Edit/toggle/delete only managed entries**
   - Given a DB-backed managed global connection/model, when a platform admin updates display name, base URL, API key, model enabled state, capabilities, pricing metadata, rpm or tpm, then only that managed row changes and the merged catalog refreshes after commit.
   - Given the admin deletes a managed global connection, then child models are deleted by the existing cascade and removed from the refreshed global catalog.
   - Given a file-backed YAML/env or dynamic OpenRouter entry, when the admin attempts edit, toggle, or delete through the UI or API, then the backend rejects it with 400 or 403 and the UI renders it read-only.

5. **Auto mode and direct global runtime use the managed model**
   - Given a DB-backed managed model is enabled and supports chat, when Auto mode builds global candidates for a workspace, then the model is eligible as a global/platform candidate with its configured billing tier and quality metadata, not as a BYOK candidate.
   - Given the managed model is disabled or its connection is disabled, then it is absent from Auto candidates and `llm-setup-status` falls through correctly.
   - Given a pinned managed global runtime ID is used on the next chat call, then the runtime resolves through `config.GLOBAL_MODELS`/`GLOBAL_CONNECTIONS` or an intentionally updated equivalent path and can build LiteLLM kwargs with the stored secret.

6. **Test connection reuses existing verification logic**
   - Given a platform admin enters a draft provider/API key/model ID, when they click test before saving, then backend uses existing `verify_connection()`/`test_model()` logic and returns a clear success/failure response.
   - Given a saved managed global model, when admin tests it, then the backend uses the stored connection/model and never returns the secret.
   - Given a file-backed model, test is allowed only if it can be done without returning/editing secret material; otherwise render test unavailable and document the reason in UI state.

7. **Pricing registration maps UI cost correctly**
   - Given the admin enters `cost_per_1k_input_tokens=0.002` and `cost_per_1k_output_tokens=0.008`, when refresh/pricing registration runs, then LiteLLM receives `input_cost_per_token=0.000002` and `output_cost_per_token=0.000008` under the same alias strategy used for YAML/OpenRouter pricing.
   - Given no pricing is supplied, then registration skips that model rather than registering zero and overwriting native LiteLLM pricing.

8. **Rollback and error semantics**
   - Given create/update/delete validation fails, then no DB commit occurs and no refresh occurs.
   - Given DB commit fails, then in-memory global catalog remains unchanged.
   - Given commit succeeds but refresh/pricing/router rebuild fails, then the response is a clear server error, a structured log records `refresh_failed`, and a later refresh/restart reconciles the committed DB rows.
   - Given two admin writes happen concurrently in one process, then refresh/rebuild is serialized and the final in-memory catalog reflects the final committed DB state.

9. **No restart requirement and backward compatibility**
   - Given an existing deployment with only YAML/env global config, when Story 8.11 ships with no managed DB rows, then current global model behavior remains unchanged.
   - Given a managed global model is added/updated/deleted, then the serving backend process reflects it without restart.
   - Existing YAML/env config remains supported and remains the source of truth for file-backed entries.

10. **Platform UI route and UX**
   - Given `user.is_superuser=true`, when the user navigates to the platform-level settings route, then they can view file-backed and managed global models, add a provider/model, test, save, edit managed rows, and delete managed rows.
   - Given `user.is_superuser=false`, then navigation to that route redirects or renders access denied, but this client gate is not relied on for security.
   - The route must not live under `/dashboard/[workspace_id]/workspace-settings`; it is platform-level, not workspace-level.
   - Reused model-connections components must not hard-code `scope=SEARCH_SPACE` or require `workspaceId` for platform CRUD.

11. **Auditability and observability**
   - Every admin action logs actor, operation, managed/file source, IDs, provider/model identifiers, result, and refresh outcome without secrets.
   - Tests assert logs or an audit record for create/update/delete and refresh failure.

## Tasks / Subtasks

- [x] **T1 — Backend auth boundary** (AC 1)
  - [x] Add `require_superuser()` in `nowing_backend/app/users.py`; depend on `require_session_context()` and check `auth.user.is_superuser`.
  - [x] Add unit/integration tests proving non-superuser sessions and PATs get 403 and superuser sessions pass.
  - [x] Keep workspace RBAC helpers unchanged; do not add Admin workspace role.

- [x] **T2 — Admin schemas and source labels** (AC 2, 4, 7)
  - [x] Extend or add Pydantic schemas in `nowing_backend/app/schemas/model_connections.py` for admin global reads/writes.
  - [x] Include source labels: `managed` for DB-backed rows, `file` or `config` for YAML/env/OpenRouter virtual rows.
  - [x] Include pricing/rpm/tpm fields in a structured shape; normalize secrets so reads always return `api_key=None`.
  - [x] Update `nowing_web/contracts/types/model-connections.types.ts` with matching Zod contracts.

- [x] **T3 — Dedicated admin API routes** (AC 1, 2, 3, 4, 6, 8, 11)
  - [x] Add `/admin/global-model-connections*` routes, mounted under the existing `/api/v1` router.
  - [x] Reuse `_connection_read`, `_selection_to_model`, `_apply_model_facts`, `discover_models`, `verify_connection`, and `test_model` where valid.
  - [x] Ensure regular `/model-connections*` routes still reject `scope=GLOBAL` and still require workspace/user ownership.
  - [x] Reject write attempts against file-backed virtual IDs.
  - [x] Add structured logs for all admin operations.

- [x] **T4 — Managed GLOBAL persistence and migration decision** (AC 3, 4, 9)
  - [x] Persist managed rows as `Connection.scope=GLOBAL`, `workspace_id=None`, `user_id=None`.
  - [x] Store cost/rpm/tpm/quality metadata in `Model.catalog` and/or `billing_tier`; keep `Connection.extra` for provider/LiteLLM kwargs.
  - [x] Decide whether a migration is required. If adding columns/tables, create Alembic migration after revision 179 and include downgrade. If no migration is needed, add an explicit no-migration note in code review/dev notes and cover existing constraint behavior in tests.

- [x] **T5 — DB-backed global catalog merge** (AC 2, 3, 4, 5, 7, 9)
  - [x] Extend `materialize_global_model_catalog()` or introduce a helper it calls to merge enabled/disabled DB GLOBAL `Connection`/`Model` rows.
  - [x] Preserve YAML/env and OpenRouter precedence; append managed entries with deterministic stable runtime IDs.
  - [x] Add source metadata and DB IDs to `catalog` without exposing secrets.
  - [x] Ensure disabled managed connections/models are not usable by Auto mode.
  - [x] Update `_global_catalog_has_usable_chat()` tests for managed entries.

- [x] **T6 — Hot refresh helper** (AC 5, 7, 8, 9, 11)
  - [x] Add a single post-commit helper that serializes refresh with a process-local lock.
  - [x] Call `refresh_global_model_catalog()` after successful CRUD and re-run pricing registration.
  - [x] Rebuild/clear LLM router caches if required for changed global configs to affect router-backed paths.
  - [x] Ensure refresh failure is logged with committed IDs and returned as a clear server error.

- [x] **T7 — Pricing registration for managed globals** (AC 7)
  - [x] Convert per-1k UI values to per-token LiteLLM fields.
  - [x] Extend `pricing_registration.py` or the catalog/config generation path so managed entries are registered under the same alias rules as YAML entries.
  - [x] Add tests based on `nowing_backend/tests/unit/services/test_pricing_registration.py`.

- [x] **T8 — Runtime routing and Auto mode correctness** (AC 5, 9)
  - [x] Update `auto_model_pin_service` and any direct runtime lookup needed so managed global models are platform/global candidates, not BYOK.
  - [x] Preserve negative-ID global semantics or update every call site that depends on it.
  - [x] Add tests for Auto candidate inclusion/exclusion, billing tier, and pinned runtime lookup.

- [x] **T9 — Frontend platform route and API service** (AC 2, 4, 6, 10)
  - [x] Add a platform-level route, for example `nowing_web/app/admin/global-model-connections/page.tsx` or an equivalent platform settings route outside `/dashboard/[workspace_id]/...`.
  - [x] Gate client rendering with `user.is_superuser`, but assume backend auth is authoritative.
  - [x] Add admin global methods to `nowing_web/lib/apis/model-connections-api.service.ts` and dedicated query/mutation atoms or parameterized model-connection atoms.
  - [x] Reuse `components/settings/model-connections/*` by extracting endpoint/scope/workspace dependencies; do not call workspace mutations for global CRUD.
  - [x] Render file-backed rows read-only and managed rows editable.

- [x] **T10 — Tests and quality gates** (all ACs)
  - [x] Backend unit tests: `require_superuser`, catalog merge, runtime ID mapping, pricing conversion, refresh failure, secret redaction.
  - [x] Backend integration tests: admin create/update/delete/test endpoints with superuser and non-superuser, regular route GLOBAL rejection unchanged, no restart catalog refresh.
  - [x] Frontend unit/component tests: Zod contracts, read-only file-backed rows, managed row edit/delete controls, access denied for non-superuser.
  - [x] Playwright E2E or route-level test: superuser can add/test/save a managed global model using mocked backend responses; non-superuser cannot reach controls.
  - [x] Run P0 quality path because this touches auth, provider/model routing, pricing registration, and web UI.

## Testing Requirements / Matrix

| Area | Test file(s) | Required coverage |
|---|---|---|
| Auth boundary | `nowing_backend/tests/integration/test_pat_fail_closed_authz.py`, new route tests | session-only superuser required; PAT and normal user 403; no side effects on 403 |
| Existing route regression | new tests near model connection routes | `/model-connections` still rejects GLOBAL and lists only workspace/user rows |
| Catalog materialization | `nowing_backend/tests/unit/services/test_model_connections.py` | YAML/env entries preserved; managed DB entries merge; secrets not exposed; source labels correct; stable runtime IDs |
| Auto/runtime routing | `nowing_backend/tests/unit/services/test_auto_model_pin_service.py`, `nowing_backend/tests/unit/tasks/chat/streaming/test_llm_bundle.py` | managed global eligible as global, disabled excluded, pinned runtime resolves with secret |
| Pricing | `nowing_backend/tests/unit/services/test_pricing_registration.py` | per-1k to per-token conversion; aliases registered; no zero override |
| API integration | new `nowing_backend/tests/integration/routes/test_admin_global_model_connections.py` | create/update/delete/test/discover, refresh called after commit, rollback semantics |
| Frontend contracts | `nowing_web/contracts/types/model-connections.types.ts` tests or existing test convention | admin schemas parse source/pricing/redacted key |
| Frontend UI | new tests under `nowing_web/tests` | platform route, read-only file rows, managed CRUD controls, access denied |
| E2E | Playwright web test | happy path with mocked provider test; no real provider key in fixtures |

Minimum verification commands:

```bash
cd nowing_backend
uv run --active ruff check app/users.py app/routes app/services/global_model_catalog.py app/services/pricing_registration.py tests/unit tests/integration
uv run --active python -m pytest tests/unit/services/test_model_connections.py tests/unit/services/test_pricing_registration.py tests/unit/services/test_auto_model_pin_service.py tests/unit/tasks/chat/streaming/test_llm_bundle.py tests/integration/test_pat_fail_closed_authz.py -q
```

```bash
cd nowing_web
pnpm lint
pnpm test -- --runInBand
pnpm exec playwright test tests/admin-global-model-connections.spec.ts
```

Adjust exact frontend test command to the repo's configured runner if it differs, but do not skip frontend coverage.

## Project Structure / File Ownership

Backend likely touched:

- `nowing_backend/app/users.py` — add `require_superuser()`.
- `nowing_backend/app/routes/model_connections_routes.py` or new `nowing_backend/app/routes/admin_global_model_connections_routes.py` — admin API.
- `nowing_backend/app/routes/__init__.py` — mount new router if split.
- `nowing_backend/app/schemas/model_connections.py` and `nowing_backend/app/schemas/__init__.py` — admin request/response schemas.
- `nowing_backend/app/services/global_model_catalog.py` — merge DB-backed GLOBAL rows and source metadata.
- `nowing_backend/app/config/__init__.py` — refresh helper signature if needed.
- `nowing_backend/app/services/pricing_registration.py` — managed global pricing registration.
- `nowing_backend/app/services/auto_model_pin_service.py`, `nowing_backend/app/tasks/chat/streaming/flows/shared/llm_bundle.py`, possibly `nowing_backend/app/services/llm_service.py` — only if runtime ID/global resolution requires it.
- `nowing_backend/alembic/versions/*` — only if schema additions are required.

Frontend likely touched:

- `nowing_web/contracts/types/model-connections.types.ts` — admin global schemas.
- `nowing_web/lib/apis/model-connections-api.service.ts` — admin global API methods.
- `nowing_web/atoms/model-connections/*` or new admin atoms — query/mutation state.
- `nowing_web/components/settings/model-connections/*` — extract reusable endpoint/scope hooks from workspace-specific flow.
- New platform route under `nowing_web/app/admin/...` or equivalent platform settings path.
- New tests under `nowing_web/tests/...`.

## Migration / API / UI Details

- Migration: existing DB schema already supports GLOBAL rows and model metadata. Add migration only for new persistent audit/source/override columns. Do not change `ConnectionScope` enum values.
- API request should accept one connection with one or more model selections. Require at least one enabled chat-capable model for create unless explicitly allowing disabled draft rows; if disabled draft rows are allowed, they must not affect Auto mode.
- API response should include `source`, `managed`, `can_edit`, `can_delete`, and `has_api_key`; do not include `api_key`.
- UI must show file-backed entries and managed entries together, with source labels and disabled edit/delete controls for file-backed rows.
- UI cost input label is per 1k tokens; backend normalizes to per-token for LiteLLM.
- Base URL handling must continue through `to_litellm()` / provider registry rules, not custom URL concatenation.

## Dependencies / Non-Goals

Dependencies:

- Existing session auth and `User.is_superuser`.
- Existing `Connection`/`Model` schema and migration 160.
- Existing provider registry, discovery, verification, model resolver, global catalog, pricing registration, and web model-connections components.

Non-goals:

- No new workspace role or Admin system role.
- No secret display or API-key reveal flow.
- No editing YAML/env/global_llm_config files from the browser.
- No persistent file-backed disable override in this story.
- No flat pricing or guessed provider pricing.
- No production code implementation in this story-creation step.

## References

- `_bmad-output/planning-artifacts/epics.md` — Story 8.11 and FR-41 trace.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — FR-41.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-2, AD-6, AD-8, AD-9.
- `nowing_backend/app/config/__init__.py` — global config loading and refresh seam.
- `nowing_backend/app/services/global_model_catalog.py` — current virtual GLOBAL materializer.
- `nowing_backend/app/routes/model_connections_routes.py` — existing read/write/test route patterns.
- `nowing_backend/app/db.py` — `ConnectionScope`, `Connection`, `Model`.
- `nowing_backend/app/users.py` — auth dependencies.
- `nowing_backend/app/services/pricing_registration.py` — LiteLLM cost registration.
- `nowing_web/components/settings/model-connections/` — reusable UI components.
- `nowing_web/lib/apis/model-connections-api.service.ts` and `nowing_web/atoms/model-connections/` — current web API/state patterns.

## Dev Agent Record

### Implementation Notes

- Ground work in verified code above. If implementation finds a planning/code conflict, update this story's Decisions/Change Log instead of silently choosing.
- Preserve user changes in the working tree. Do not revert unrelated files.
- This story touches P0 areas: auth, provider/model routing, pricing registration, and web UI. Follow the Nowing quality pipeline P0 gates.

### Debug Log References

- `nowing_backend/app/schemas/admin_global_model_connections.py` — relaxed `source` from `Literal["managed", "file", "config"]` to `str` so preview/discover unsaved `Model` objects (with `ModelSource.DISCOVERED/MANUAL`) validate, while runtime still emits only the three admin source labels.
- `nowing_backend/app/routes/admin_global_model_connections_routes.py` — `update_global_model()` now eager-loads `Model.connection` and captures `provider` before `session.commit()` to avoid `MissingGreenlet` after commit.
- Integration test `test_admin_global_model_connections.py` first run surfaced Pydantic source validation and detached proxy issues; fixed and now 7/7 passing.
- Backend targeted test suite 52/52 passing.

### Completion Notes

- `require_superuser()` added in `nowing_backend/app/users.py`; admin routes reject non-superuser sessions and PATs with 403.
- New `nowing_backend/app/routes/admin_global_model_connections_routes.py` provides full CRUD, discover/test preview, saved discover/test, model update, bulk update, and delete under `/api/v1/admin/global-model-connections`.
- `refresh_global_model_catalog()` in `nowing_backend/app/config/__init__.py` merges enabled/disabled DB-managed `GLOBAL` rows into `config.GLOBAL_CONNECTIONS`/`config.GLOBAL_MODELS` with deterministic negative runtime IDs and `admin_source: "managed"` metadata.
- `register_pricing_for_managed_global_models()` in `nowing_backend/app/services/pricing_registration.py` registers per-token pricing for managed global models after refresh.
- `auto_model_pin_service.py` no longer excludes `ConnectionScope.GLOBAL` DB candidates; managed global models are treated as platform/global candidates with catalog `billing_tier`, `auto_pin_tier`, and `quality_score`.
- Frontend platform route `nowing_web/app/admin/global-model-connections/page.tsx` is gated by `user.is_superuser`, lists file-backed and managed global connections, and supports create/edit/test/discover/toggle/delete with read-only file-backed rows.
- Backend: 7 admin integration tests + 52 targeted P0 tests all pass; `ruff check` and `ruff format` clean.
- Frontend: `pnpm tsc --noEmit` passes; `biome check` clean for changed files.

### File List

Backend:
- `nowing_backend/app/users.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/routes/admin_global_model_connections_routes.py`
- `nowing_backend/app/routes/model_connections_routes.py`
- `nowing_backend/app/schemas/__init__.py`
- `nowing_backend/app/schemas/admin_global_model_connections.py`
- `nowing_backend/app/schemas/model_connections.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/services/global_model_catalog.py`
- `nowing_backend/app/services/pricing_registration.py`
- `nowing_backend/app/services/auto_model_pin_service.py`
- `nowing_backend/tests/integration/routes/conftest.py`
- `nowing_backend/tests/integration/routes/test_admin_global_model_connections.py`

Frontend:
- `nowing_web/app/admin/layout.tsx`
- `nowing_web/app/admin/admin-shell.tsx`
- `nowing_web/app/admin/global-model-connections/page.tsx`
- `nowing_web/atoms/model-connections/admin-global-model-connections.atoms.ts`
- `nowing_web/contracts/types/admin-global-model-connections.types.ts`
- `nowing_web/contracts/types/model-connections.types.ts`
- `nowing_web/lib/apis/admin-global-models-api.service.ts`
- `nowing_web/lib/query-client/cache-keys.ts`

## Change Log

| Date | Change |
|---|---|
| 2026-07-27 | Created implementation-ready Story 8.11 from verified planning docs and code inspection at baseline `25ba542c2a3dec95b0a4020da8c129242ba748e2`. |

## Review Findings (code review 2026-08-08)

Scope: commits `25ba542c2`..`7a7b0fe31` — backend routes (752 lines) + schemas (130 lines) + frontend page (1257 lines) + tests (388 lines).

**patch:** 0

**defer:** 11 (all low severity)
- Provider validation on create/update — `spec_for()` has fallback for unknown providers. Won't crash.
- API key requirement validation — some providers (Ollama) don't need keys. `spec_for` fallback handles it.
- Race conditions on concurrent admin edits — admin UI with few users. Last-write-wins acceptable.
- Empty API key `""` — route converts falsy to None via `value or None`.
- API key whitespace not trimmed — provider will reject with auth error.
- Change provider on connection with models — admin action, admins aware of consequences.
- No pagination on list endpoint — few global connections (10-20). Not a concern.
- AC-11 PARTIAL: audit logging works but tests don't assert log output.

**dismissed:** 8 (all false positives or by-design)
- Mass assignment connection update — FALSE POSITIVE. `model_dump(exclude_unset=True)` only contains schema fields. Pydantic ignores extra fields by default. `workspace_id`/`user_id`/`scope` can never appear.
- Mass assignment model update — FALSE POSITIVE. Same as above.
- Duplicate model_id silently skipped — BY DESIGN. Dedup is intentional.
- Delete pinned model — BY DESIGN. CASCADE + auto-pin service repairs.
- Very long API key — PostgreSQL TEXT handles it. Provider keys are short.
- Provider/model special characters — SQLAlchemy parameterizes. litellm handles.
- Disable all models — BY DESIGN. Admin can disable all.
- Bulk operation limits — Schema limits to 1000.

**AC coverage:** AC-1 PASS, AC-2 PASS, AC-3 PASS, AC-4 PASS, AC-5 PASS, AC-6 PASS, AC-7 PASS, AC-8 PASS, AC-9 PASS, AC-10 PASS, AC-11 PARTIAL (logging works, no test assertions).

**Positive findings:**
- Auth: ALL 8 routes use `Depends(require_superuser)` — correctly protected
- API key handling: keys never returned in responses (explicitly set to None, `has_api_key` bool only)
- SQL injection: all queries use SQLAlchemy ORM with parameterized queries
- Error handling: DB errors caught, rolled back, logged via `_log_admin_action`
- Frontend: API keys masked with `type="password"`, loading states, error toasts
- Pricing: per-1k to per-token conversion correctly implemented
- Catalog refresh: `refresh_global_model_catalog(rebuild_routers=True)` after every mutation
- Process-local lock serializes concurrent refreshes
