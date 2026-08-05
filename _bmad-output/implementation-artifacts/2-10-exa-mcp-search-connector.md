---
baseline_commit: 9f6a4c5942c20a5a6c72144ba03d0d8737cc75a9
---

# Story 2.10: Exa MCP Search Connector

**Status:** done  
**Epic:** 2 — Connectors  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" />  
**Related PRD:** FR-8 MCP connectors in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />  
**Related Architecture:** AD-4 (multi-agent tool registry), AD-7 (MCP stateless server), AD-12 (MCP tool catalog), AD-DEFER-3 (MCP tool toggle) in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />  

## Story

As a workspace user,  
I want to connect the Exa AI MCP server as a first-class search connector,  
So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval.

## Context

This is a retroactive/done story. The implementation was completed on 2026-08-05 to demonstrate and ship a curated, third-party MCP search integration inside Nowing's existing connector framework. It reuses the same patterns as `MCP_CONNECTOR` (generic user-defined MCP servers) but with a known service manifest, whitelisted read-only tools, and an API-key based `server_config` builder.

## Acceptance Criteria

1. **Connector type exists in the database**
   - **Given** the current Alembic history
   - **When** migration `190_add_exa_mcp_connector.py` runs
   - **Then** the `searchsourceconnectortype` enum contains `EXA_MCP_CONNECTOR`

2. **Create Exa connector via API**
   - **Given** a workspace with no existing `EXA_MCP_CONNECTOR`
   - **When** an authenticated user POSTs `/search-source-connectors?workspace_id={id}` with `connector_type: "EXA_MCP_CONNECTOR"`, `name: "Exa"`, and an optional `exa_api_key`
   - **Then** the route builds `config.server_config = { "transport": "streamable-http", "url": "https://mcp.exa.ai/mcp", "headers": { "x-api-key": "<key>" } }` when a key is provided; without a key it omits `headers`
   - **And** the connector is persisted with `is_indexable = false`, `periodic_indexing_enabled = false`

3. **Update Exa connector**
   - **Given** an existing `EXA_MCP_CONNECTOR`
   - **When** the user PUTs `/search-source-connectors/{id}` with a new `exa_api_key`
   - **Then** the backend rebuilds `server_config` from the updated key and preserves the default Exa URL

4. **Agent can discover and call Exa tools**
   - **Given** a workspace with a connected Exa connector
   - **When** the multi-agent chat runtime loads MCP tools
   - **Then** it discovers only `web_search_exa` and `web_fetch_exa`
   - **And** both tools are treated as `readonly`, so they execute without HITL approval

5. **Tool behavior matches Exa server contract**
   - **Given** a chat turn requiring web search
   - **When** `web_search_exa` is called with `query`
   - **Then** it returns clean, ready-to-use text from top web results
   - **Given** a known URL
   - **When** `web_fetch_exa` is called
   - **Then** it returns the page content as clean markdown

6. **Connector removal invalidates tool cache**
   - **Given** a deleted `EXA_MCP_CONNECTOR`
   - **When** the delete route completes
   - **Then** the MCP tools cache for the workspace is invalidated

7. **Existing MCP connector tests keep passing**
   - **When** `pytest tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py` runs
   - **Then** all tests pass (connector must be in `mcp_discovery` route and required-connector maps)

## Implementation Summary

### New / Updated Files

| File | Change |
|------|--------|
| `nowing_backend/alembic/versions/190_add_exa_mcp_connector.py` | New migration adding `EXA_MCP_CONNECTOR` enum value |
| `nowing_backend/app/db.py` | Add `EXA_MCP_CONNECTOR` to `SearchSourceConnectorType` |
| `nowing_backend/app/services/mcp_oauth/registry.py` | Add `exa` service: URL, connector type, `allowed_tools`/`readonly_tools` |
| `nowing_backend/app/routes/search_source_connectors_routes.py` | Build `server_config` on create/update; cache invalidation on delete |
| `nowing_backend/app/utils/validators.py` | Config validation rule for `EXA_MCP_CONNECTOR` |
| `nowing_backend/app/utils/connector_naming.py` | Display name "Exa" |
| `nowing_backend/app/agents/chat/multi_agent_chat/constants.py` | Route to `mcp_discovery`; include in required connector map |
| `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/runtime/connector_searchable_types.py` | Map `EXA_MCP_CONNECTOR` searchable type |
| `nowing_backend/tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py` | Include `EXA_MCP_CONNECTOR` in routed set |

### Key Design Decisions

- **API key embedded as header, not persisted raw.** The create/update route pops `exa_api_key` from `config` and injects it into `server_config.headers["x-api-key"]`. This keeps the key inside the same `server_config` object the generic MCP connector already uses, but avoids leaving a top-level `exa_api_key` field.
- **No indexing.** Exa is a live search tool, not a document source. `is_indexable` and `periodic_indexing_enabled` are forced to `false`.
- **Curated tool allowlist.** `MCPServiceConfig.allowed_tools = ["web_search_exa", "web_fetch_exa"]`; `readonly_tools` is the same set. The agent will not load any future tools Exa advertises until we deliberately expand the allowlist.
- **Reuses `mcp_discovery` subagent.** No new subagent or tool wrapper was created; the existing `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py` handles stdio/HTTP transports, tool loading, and HITL.

### Dev Notes

- **Exa MCP server is remote, HTTP transport.** The `server_config.transport` is `streamable-http` (the Nowing MCP client maps this to the `mcp` package's `streamablehttp_client`).
- **No OAuth.** `supports_dcr=false` in `MCP_SERVICES`. Exa is created through the generic `search-source-connectors` CRUD routes, not `/connectors/mcp/{service}/start`.
- **Uniqueness.** `EXA_MCP_CONNECTOR` is not exempt from the one-per-workspace check, unlike generic `MCP_CONNECTOR`.
- **Migration is reversible only by hand.** PostgreSQL does not support removing enum values directly, so `downgrade()` is a no-op with instructions.

## Verification Commands

```bash
cd nowing_backend

# Syntax
uv run ruff check app/db.py app/services/mcp_oauth/registry.py app/routes/search_source_connectors_routes.py app/utils/validators.py app/utils/connector_naming.py app/agents/chat/multi_agent_chat/constants.py app/agents/chat/multi_agent_chat/main_agent/runtime/connector_searchable_types.py tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py

# Relevant tests
uv run pytest tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py -q
uv run pytest tests/unit/utils/test_validators.py -q

# Migration
uv run alembic current  # should print 190 (head)
```

## Completion Notes

- Migration `190_add_exa_mcp_connector.py` applied successfully to local Postgres (`alembic current` = `190 (head)`).
- `ruff check` passed on all changed files.
- `tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py`: 10 passed.
- `tests/unit/utils/test_validators.py`: 98 passed.
- Manual smoke test with `mcp` SDK connected to `https://mcp.exa.ai/mcp` and called `web_search_exa` successfully.
- Front-end changes are **out of scope** for this story; users currently create the connector by calling the REST API directly. A connector-picking UI is tracked by `7-7-mcp-server-tool-expansion.md` and `7-4-dedicated-connectors-layout.md`.

## File List

- `nowing_backend/alembic/versions/190_add_exa_mcp_connector.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/services/mcp_oauth/registry.py`
- `nowing_backend/app/routes/search_source_connectors_routes.py`
- `nowing_backend/app/utils/validators.py`
- `nowing_backend/app/utils/connector_naming.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/constants.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/runtime/connector_searchable_types.py`
- `nowing_backend/tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py`
- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
