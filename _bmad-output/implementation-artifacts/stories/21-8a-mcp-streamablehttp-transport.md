---
story_key: 21-8a-mcp-streamablehttp-transport
status: done
epic: 21
story: 8a
---

# Story 21.8a: MCP StreamableHTTP Transport for XActions

**Status:** `done`  
**Epic:** Epic 21 — Lead Gen Intelligence  
**Governed by:** AD-SOC-1, AD-SOC-4, AD-SOC-11, TRINITY-4  
**Split from:** Story 21.8 — Social Ingress via XActions Integration (baseline)

---

## Story

As a Nowing backend engineer,  
I want `XActionsSocialAdapter` and chat agents to connect to XActions via streamable HTTP MCP,  
so that I can reuse sessions, avoid spawning `node` subprocesses, and honor consumer quota.

---

## Acceptance Criteria

1. **MCP StreamableHTTP Client** — **Given** `XACTIONS_MCP_URL`, `XACTIONS_MCP_API_KEY`, `XACTIONS_CONSUMER_ID` are configured, **When** `XActionsMcpClient` connects, **Then** it uses `mcp.client.streamable_http.streamablehttp_client`, reuses the session, and sends `Authorization: Bearer <api_key>` and `X-Consumer-Id` headers.
2. **3-Layer Envelope Parsing** — **Given** a tool call, **When** XActions returns JSON, **Then** the client parses `success`, `data`, `meta`, `summary`, and `datasetArtifactPath` correctly; empty/non-JSON responses degrade safely.
3. **Structured Error Handling** — **Given** `XACT_4291`, `PROXY_EXHAUSTED`, `ACCOUNT_HIBERNATION`, or `XACT_4010`, **When** an error occurs, **Then** `XActionsMcpError` carries `code`, `retry_after`, and `suggested_action` for downstream handling.
4. **Chat Agent Connector** — **Given** a workspace with `XACTIONS_MCP_CONNECTOR` enabled, **When** the main chat agent selects tools, **Then** it sees 3 consolidated meta-tools (`x_search`, `x_scrape`, `x_crawl_post`) and the connector is auto-seeded on startup.
5. **Config & Enum** — **Given** deployment env, **When** `app.config` loads, **Then** `XACTIONS_MCP_URL`, `XACTIONS_MCP_API_KEY`, `XACTIONS_CONSUMER_ID`, and `XACTIONS_FACEBOOK_ACCOUNT_ID` are available and the `SearchSourceConnectorType` enum contains `XACTIONS_MCP_CONNECTOR`.

---

## Tasks / Subtasks

- [x] Task 1: `XActionsMcpClient` session lifecycle (AC: 1, 2, 3)
  - [x] 1.1 Implement `streamablehttp_client` context manager and `ClientSession` lifecycle.
  - [x] 1.2 Add `list_tools()` helper.
  - [x] 1.3 Artifact handling for `datasetArtifactPath`.
  - [x] 1.4 Unit test `test_xactions_mcp_client_lifecycle.py`.
- [x] Task 2: Config and environment (AC: 5)
  - [x] 2.1 Add `XACTIONS_MCP_URL`, `XACTIONS_MCP_API_KEY`, `XACTIONS_CONSUMER_ID`, `XACTIONS_FACEBOOK_ACCOUNT_ID` to `app/config/entities.py` and `.env.local`.
  - [x] 2.2 Wire config in `app/config/__init__.py`.
- [x] Task 3: Connector enum and seed (AC: 4, 5)
  - [x] 3.1 Add `XACTIONS_MCP_CONNECTOR` to `SearchSourceConnectorType` and frontend `EnumConnectorName`.
  - [x] 3.2 Create `xactions_connector_seed.py` to auto-provision XActions connectors per workspace.
  - [x] 3.3 Call seed in `app/lifespan.py` and `workspaces_routes.py`.
  - [x] 3.4 Alembic migration `5bd0001357ae_add_xactions_mcp_connector_enum`.
- [x] Task 4: Chat meta-tools (AC: 4)
  - [x] 4.1 Create `xactions_gateway.py` with 3 meta-tools `x_search`, `x_scrape`, `x_crawl_post`.
  - [x] 4.2 Register in `mcp/tool.py` and `constants.py`.
  - [x] 4.3 Add `connector_searchable_types.py` entry.
  - [x] 4.4 Unit test `test_xactions_gateway.py`.
- [x] Task 5: Adapter v2 wiring (AC: 1, 3)
  - [x] 5.1 Replace `stdio_client` usage in `adapter.py` with `XActionsMcpClient`.
  - [x] 5.2 Update `adapter_v2.py` to use the new client.

---

## Dev Notes

- **Session lifecycle P0:** `XActionsMcpClient` must exit both `ClientSession` and `streamablehttp_client` transport context managers to avoid SSE reader leaks. See `INTEGRATION-PLAN-2026-09-09.md` §4.2.
- **Chat scope:** The 3 meta-tools are read-only, bypass HITL, and map to low-level XActions tools. They live in `app/agents/chat/multi_agent_chat/shared/tools/mcp/xactions_gateway.py`.
- **Do not break:** Existing `SocialEntityExtractor`, Redis producer payload, and `facebook_group`/`twitter_keyword` behavior.
- **PII:** Extracted phone/price/location still goes into `raw_entities`; do not store PII in logs.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-xactions-21-8-correction.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Code: nowing_backend/app/proprietary/platforms/xactions/mcp_client.py]
- [Code: nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/xactions_gateway.py]
- [Code: nowing_backend/app/services/xactions_connector_seed.py]
