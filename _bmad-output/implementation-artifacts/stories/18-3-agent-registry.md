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

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List