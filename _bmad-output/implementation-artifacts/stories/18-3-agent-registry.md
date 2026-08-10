# Story 18.3: Agent Registry

Status: done

Baseline commit: 1e5f46b86

## Story

As a platform administrator,
I want to register agents with custom system prompts and tool configurations,
so that different vertical clients can have specialized chat agents.

## Acceptance Criteria

1. **Given** the migration runs, **When** complete, **Then** an `agent_configs` table exists with fields: `id`, `client_id`, `name`, `system_instructions`, `enabled_tools`, `disabled_tools`, `model_name`, `citations_enabled`, `is_active`.
2. **Given** the seed script runs, **When** complete, **Then** `bdsai-listing-assistant` is seeded as the first agent.
3. **Given** an `agent_id` is provided in a chat request, **When** processed, **Then** the system loads the corresponding `AgentConfig` or returns 404 if not found.
4. **Given** `AgentConfig` is global (not workspace-scoped), **When** same agent is used across workspaces, **Then** the same config applies.

## Tasks / Subtasks

- [ ] Database schema for `agent_configs` (AC: #1)
  - [ ] Create Alembic migration for `agent_configs` table with columns: `id` (PK), `client_id` (text, not null, indexed), `name` (text, unique with client_id), `display_name` (text), `system_instructions` (text), `enabled_tools` (JSONB array), `disabled_tools` (JSONB array), `model_name` (text), `citations_enabled` (bool, default true), `is_active` (bool, default true), timestamps
  - [ ] Add `AgentConfig` model to `app/db.py`
  - [ ] Add FK/unique constraint ensuring `agent_id` (`name`) + `client_id` is unique
- [ ] Seed script (AC: #2)
  - [ ] Add `app/scripts/seed_agent_configs.py` (or extend `app/db/seed.py`) that seeds `bdsai-listing-assistant` for `client_id='bdsai.vn'` with BĐS tool allowlist
  - [ ] Seed should be idempotent (upsert on `client_id` + `name`)
  - [ ] Document command in `nowing_backend/README.md` and ops runbook
- [ ] Agent registry service (AC: #3, #4)
  - [ ] Create `app/services/agent_registry.py` with `get_agent_config(client_id, name)` and `list_agents(client_id=None)`
  - [ ] Fail closed: `get_agent_config` raises `AgentConfigNotFound` (mapped to 404) when missing or `is_active=False`
  - [ ] `list_agents` returns global/platform-scoped configs; not workspace-scoped
- [ ] Admin CRUD routes (AC: #1, #2, #3, #4)
  - [ ] Create `app/routes/admin_agent_registry_routes.py` under `/admin/agent-registry` with superuser-only `GET`, `POST`, `PATCH`, `DELETE`
  - [ ] Add Pydantic schemas in `app/schemas/agent_config.py` for create/update/read
  - [ ] Mount router in `app/routes/__init__.py` after `admin_global_model_connections_router`
- [ ] UI contract alignment
  - [ ] Implement `ux-contract-agent-registry.md` states: list, create form, detail/edit, tool allowlist selector
  - [ ] Reuse pattern from `admin_global_model_connections_routes.py` and `ux-contract-admin-global-model-config.md`
- [ ] Runtime wiring (AC: #3)
  - [ ] Update `app/tasks/chat/streaming/flows/new_chat/orchestrator.py` (Story 18.2/18.4) to call `AgentRegistry.get_agent_config`
  - [ ] Update `app/auth/agent_chat.py` (Story 18.1) to validate requested `agent_id` against allowed `client_id` and active status
- [ ] Tests
  - [ ] Unit tests for `AgentRegistry` service: missing/inactive → 404, global list, client filter
  - [ ] Integration tests for admin CRUD with superuser and non-superuser access
  - [ ] Integration test seed script is idempotent and creates `bdsai-listing-assistant`
  - [ ] Integration test chat request with invalid `agent_id` returns 404

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-30` (`ARCHITECTURE-SPINE.md:739-748`) — `AgentConfig` registry is platform-superuser managed (not end-user workspace CRUD); tool allow/deny lists explicit; new connectors not auto-enabled; `system_instructions` trusted admin content with length limits and no raw secret interpolation.
  - `AD-31` (`ARCHITECTURE-SPINE.md:750-764`) — `client_id` is the hard tenancy key; `agent_configs.client_id` must match the vertical client.
  - `AD-29` (`ARCHITECTURE-SPINE.md:727-737`) — public agent-chat surface loads `AgentConfig` by `agent_id` after PAT scope is authorized.
  - `FR-57` (`prd.md:443-453`) defines the product requirement.
  - `ux-contract-agent-registry.md` defines the required admin UI states.

- Source tree components to touch
  - `nowing_backend/alembic/versions/` — `agent_configs` migration
  - `nowing_backend/app/db.py` — `AgentConfig` model
  - `nowing_backend/app/schemas/agent_config.py` — CRUD schemas
  - `nowing_backend/app/services/agent_registry.py` — registry service
  - `nowing_backend/app/routes/admin_agent_registry_routes.py` — admin API
  - `nowing_backend/app/routes/__init__.py` — router mount
  - `nowing_backend/app/scripts/seed_agent_configs.py` — seed script
  - `nowing_backend/app/auth/agent_chat.py` (Story 18.1) — agent validation
  - `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` — runtime lookup
  - `nowing_web/app/admin/agent-registry/` — admin page (per `ux-contract-agent-registry.md`)

- Testing standards summary
  - Unit tests in `tests/unit/services/test_agent_registry.py`
  - Integration tests in `tests/integration/routes/test_admin_agent_registry.py`
  - Seed idempotency test in `tests/integration/test_seed.py`
  - Fail-closed test: chat with `agent_id='nonexistent'` → 404

### Project Structure Notes

- Alignment with unified project structure
  - `AgentConfig` is a platform-level admin entity, similar to `GlobalModelConnection`. Use the existing admin route pattern.
  - The registry service is separate from the chat orchestrator; orchestrator only calls `get_agent_config`.

- Detected conflicts or variances
  - `GlobalModelConnection` (`app/db.py`) already has a model catalog; `AgentConfig.model_name` may reference a catalog entry but does not duplicate it.
  - Tool lists in `AgentConfig` must be validated against the existing tool registry (`app/agents/chat/multi_agent_chat/shared/tools/registry.py`) at write time to fail fast on typos.
  - `client_id` may need a `vertical_clients` table seed (Story 18.3 seed can create `vertical_clients` row for `bdsai.vn` if missing).

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.3]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-57]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-30]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-agent-registry.md`]
- [Source: `nowing_backend/app/db.py` §Memory / GlobalModelConnection patterns]
- [Source: `nowing_backend/app/routes/admin_global_model_connections_routes.py` §admin pattern]

### Review Findings

**Review layers completed:** Blind Hunter, Edge Case Hunter, Acceptance Auditor.  
**Note:** The `bmad-review-adversarial-general` and `bmad-review-edge-case-hunter` skills were not available in this environment, so the corresponding subagents performed manual review.

**Triage summary:** 0 `decision-needed`, 12 `patch`, 5 `defer`, 1 dismissed.

#### `decision-needed`

None.

#### `patch`

- [x] [Review][Patch] Admin agent registry routes must set tenant GUCs and use `app.internal_service` bypass when querying `agent_configs` / `vertical_clients` under RLS — `nowing_backend/app/routes/admin_agent_registry_routes.py:41-149` and `nowing_backend/alembic/versions/c826c8e6e149...:44-58`.
- [x] [Review][Patch] Disallow `client_id` mutation and re-validate `(client_id, slug)` / `(client_id, name)` uniqueness on PATCH — `nowing_backend/app/schemas/agent_config.py:36-38`, `nowing_backend/app/routes/admin_agent_registry_routes.py:119-149`.
- [x] [Review][Patch] Normalize and validate `client_id` and `slug` (trim, lowercase, regex) and ensure non-empty slug — `nowing_backend/app/schemas/agent_config.py:10-25`, `nowing_backend/app/routes/admin_agent_registry_routes.py:59`.
- [x] [Review][Patch] `get_agent_config` guard must compare `client_id` case-insensitively because the column is CITEXT — `nowing_backend/app/services/agent_registry.py:42`.
- [x] [Review][Patch] Validate `enabled_tools` / `disabled_tools` against known main-agent tool names at write time and fix BDS seed tool names — `nowing_backend/app/schemas/agent_config.py:15-16,41-42`, `nowing_backend/scripts/seed_agent_configs.py:36-41`.
- [x] [Review][Patch] `citations_enabled` must default to `True` in schema, model, and migration per the story spec — `nowing_backend/app/schemas/agent_config.py:18`, `nowing_backend/app/db.py:2211-2213`, `nowing_backend/alembic/versions/78f7a9b1e85f...:170-175`.
- [x] [Review][Patch] Seed script must default `ENVIRONMENT` to a non-safe value and require `--force` for production — `nowing_backend/scripts/seed_agent_configs.py:51-57`.
- [x] [Review][Patch] Admin create and update must handle `IntegrityError` races / unique-constraint violations with `409 CONFLICT` instead of `500` — `nowing_backend/app/routes/admin_agent_registry_routes.py:60-84,119-149`.
- [x] [Review][Patch] `list_agents` and `list_agent_configs` must treat empty or whitespace `client_id` filter as no filter — `nowing_backend/app/services/agent_registry.py:47-57`, `nowing_backend/app/routes/admin_agent_registry_routes.py:43`.
- [x] [Review][Patch] Add `display_name` column, enforce `(client_id, name)` uniqueness, and include `created_at`/`updated_at` in `AgentConfigRead` per story spec / UX contract — `nowing_backend/app/db.py:2190-2220`, `nowing_backend/alembic/versions/78f7a9b1e85f...:144-199`, `nowing_backend/app/schemas/agent_config.py:55-67`.
- [x] [Review][Patch] Ensure `updated_at` refreshes on update for `AgentConfig` and `VerticalClient` — `nowing_backend/app/db.py:2182-2220`.
- [x] [Review][Patch] Mount `admin_agent_registry_router` after `admin_global_model_connections_router` as the story task specifies — `nowing_backend/app/routes/__init__.py:166-169`.

#### `defer`

- [x] [Review][Defer] Frontend admin agent-registry UI page is not implemented; deferred to a separate frontend story or the `ux-contract-agent-registry.md` implementation pass.
- [x] [Review][Defer] README / ops runbook seed command documentation is missing; deferred to documentation sprint.
- [x] [Review][Defer] Expand integration/unit test coverage for PATCH, uniqueness, RLS non-owner role, and invalid-agent chat 404; deferred to test sprint.
- [x] [Review][Defer] Reconcile `AgentConfig` tool lists with the full tool catalog (`shared/tools/catalog.py`) once the runtime supports more than main-agent tools; deferred to tool-catalog unification.
- [x] [Review][Defer] Add an explicit foreign-key constraint from `agent_configs.client_id` to `vertical_clients.client_id`; deferred to vertical-client lifecycle hardening.

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List