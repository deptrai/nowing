---
story_key: 21-8g-medirus-mcp-chat-connector
status: done
epic: 21
story: 8g
---

# Story 21.8g: Medirus MCP Chat Connector

**Status:** `done`  
**Epic:** Epic 21 — Lead Gen Intelligence  
**Governed by:** AD-SOC-1, AD-SOC-4, AD-SOC-11, TRINITY-4

---

## Story

As a chat user,  
I want Medirus to be available as an MCP connector inside Nowing chat agents,  
so that I can search, scrape, and crawl social/marketplace data directly from the conversation without leaving chat.

---

## Acceptance Criteria

1. **Connector Type** — **Given** the `SearchSourceConnectorType` enum, **When** the backend loads, **Then** `MEDIRUS_MCP_CONNECTOR` exists and is mirrored in the frontend `EnumConnectorName` and icons.
2. **Auto-Seed** — **Given** a workspace exists, **When** the app starts or a workspace is created, **Then** an Medirus MCP connector is auto-provisioned for that workspace with the correct `server_config` and `trusted_tools`.
3. **Meta-Tools** — **Given** the Medirus MCP connector is enabled, **When** the chat agent lists tools, **Then** it sees 3 consolidated meta-tools (`x_search`, `x_scrape`, `x_crawl_post`) with Pydantic input schemas and bypass HITL.
4. **Tool Dispatch** — **Given** a user asks to search/scrape/crawl in chat, **When** the agent invokes a meta-tool, **Then** `medirus_gateway.py` validates inputs and dispatches to the correct low-level Medirus tool (`x_search_tweets`, `x_facebook_group_posts`, `x_facebook_marketplace`, `x_crawl_post`, etc.).
5. **Health Probe** — **Given** the health check runs, **When** it checks Medirus, **Then** it verifies MCP connectivity and governor/metrics calls and reports status correctly.
6. **Config** — **Given** deployment env, **When** the backend starts, **Then** `MEDIRUS_MCP_URL`, `MEDIRUS_MCP_API_KEY`, `MEDIRUS_CONSUMER_ID`, and `MEDIRUS_FACEBOOK_ACCOUNT_ID` are loaded from `app/config/entities.py` and `.env.local`.
7. **Tests** — **Given** unit tests run, **When** `test_medirus_gateway.py` and `test_medirus_probe.py` execute, **Then** they pass with mocked Medirus responses.

---

## Tasks / Subtasks

- [x] Task 1: Enum and migration (AC: 1)
  - [x] 1.1 Add `MEDIRUS_MCP_CONNECTOR` to `SearchSourceConnectorType` in `app/db/enums.py`.
  - [x] 1.2 Add `MEDIRUS_MCP_CONNECTOR` and `EXA_MCP_CONNECTOR` to frontend `connector.ts` and `connectorIcons.tsx`.
  - [x] 1.3 Alembic migration `5bd0001357ae_add_medirus_mcp_connector_enum`.
- [x] Task 2: Auto-seed and registry (AC: 2)
  - [x] 2.1 Create `medirus_connector_seed.py` to build `server_config` and seed per workspace.
  - [x] 2.2 Call seed from `app/app/lifespan.py` and `workspaces_routes.py`.
  - [x] 2.3 Register connector in `mcp_oauth/registry.py`.
- [x] Task 3: Chat meta-tools (AC: 3, 4)
  - [x] 3.1 Create `medirus_gateway.py` with 3 `StructuredTool` meta-tools and Pydantic schemas.
  - [x] 3.2 Register in `mcp/tool.py` and `constants.py`.
  - [x] 3.3 Add to `connector_searchable_types.py`.
- [x] Task 4: Config (AC: 6)
  - [x] 4.1 Add `MEDIRUS_MCP_URL`, `MEDIRUS_MCP_API_KEY`, `MEDIRUS_CONSUMER_ID`, `MEDIRUS_FACEBOOK_ACCOUNT_ID` to `app/config/entities.py` and `.env.local`.
  - [x] 4.2 Wire in `app/config/__init__.py`.
- [x] Task 5: Health probe (AC: 5)
  - [x] 5.1 Update `medirus_probe.py` to call `x_governor_status` / `x_admin_stream_metrics` / `x_admin_stream_alerts` via `MedirusMcpClient`.
  - [x] 5.2 Update `tests/unit/services/health/test_medirus_probe.py`.
- [x] Task 6: Adapter/client hardening
  - [x] 6.1 Review and merge updates to `mcp_client.py` and `adapter_v2.py`.
  - [x] 6.2 Ensure artifact handling and error paths are covered.
- [x] Task 7: Unit tests
  - [x] 7.1 Create `test_medirus_gateway.py`.
  - [x] 7.2 Add `test_medirus_mcp_client_lifecycle.py` if missing.
- [x] Task 8: Verification
  - [x] 8.1 Run backend unit tests for affected modules.
  - [x] 8.2 Run ruff/biome checks.
  - [x] 8.3 Browser E2E verification & multi-scenario testing completed (Hashtag, User Posts, Groups, Marketplace).

---

## Dev Notes

- **Meta-tools are read-only and bypass HITL.** They wrap low-level Medirus tools so the LLM sees only 3 clean tools instead of 150+.
- **Platform normalization:** `_normalize_platform` handles `x`/`x.com` → `twitter`, `fb`/`fb.com` → `facebook`, and URL-based auto-detection in `_detect_platform_from_url`.
- **Facebook auth:** `MEDIRUS_FACEBOOK_ACCOUNT_ID` is injected as `accountId` for Facebook tools; `authCookie` is built when not present.
- **Error formatting:** `_format_result` returns a clean JSON string for the agent; non-success results include the Medirus error message and code.
- **Do not break:** Existing `MedirusMcpClient` lifecycle, `SocialEntityExtractor`, Redis stream producer, and existing `MEDIRUS_MCP_CONNECTOR` behavior.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-medirus-21-8-correction.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-medirus-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-medirus-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Code: nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py]
- [Code: nowing_backend/app/services/medirus_connector_seed.py]
- [Code: nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py]
- [Code: nowing_backend/app/services/mcp_oauth/registry.py]
- [Code: nowing_backend/app/proprietary/platforms/medirus/mcp_client.py]
- [Code: nowing_backend/app/services/health/probes/medirus_probe.py]


### Review Findings

Generated: 2026-09-09 22:05

#### Decision Needed
- [x] [Review][Decision] `_handle_medirus_scrape` misroutes `posts` action for non-Twitter platforms to `x_get_tweets` — Resolved by routing `tiktok`, `chotot`, `shopee`, `topcv`, `batdongsan`, `masothue`, `b2b_registry`, and `linkedin_company` to the generic `x_scrape` tool; `user_posts`/`tweets`/`user_tweets` only for `x_get_tweets`. [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:335-365]
- [x] [Review][Decision] Main agent routing prompt lacks description for MEDIRUS_MCP_CONNECTOR — Added Medirus to the `mcp_discovery` entry in `routing.md` describing social search, scrape, marketplace, and B2B sources. [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md]

#### Patch

- [x] [Review][Patch] Invalid type annotation `str ^ None` in MedirusSocialAdapterV2.__init__ [nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py:143] — Line 143 uses bitwise XOR (^) instead of union pipe (|) for `default_account_id`. This raises TypeError at import time, breaking the module. Must change to `str | None = None`.
- [x] [Review][Patch] Health probe calls `x_admin_status` instead of unauthenticated `x_governor_status` [nowing_backend/app/services/health/probes/medirus_probe.py:28-31] — medirus_probe.py:28-31 calls x_admin_status which requires admin JWT (MEDIRUS_ADMIN_TOKEN), but default token is empty. This makes health probe return 401/unavailable even when daemon is healthy. Spec AC5 says use x_go
- [x] [Review][Patch] Facebook account ID injected into all Medirus tools, not just Facebook tools [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:190-196] — _execute_medirus_tool injects `accountId` and `authCookie` for any tool whenever MEDIRUS_FACEBOOK_ACCOUNT_ID is set. This leaks credentials to x_search_tweets / x_get_tweets / non-Facebook scrapers and likely causes sc
- [x] [Review][Patch] Hardcoded Medirus MCP fallback port is 3005 but config uses 3001 [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py; nowing_backend/app/services/medirus_connector_seed.py; nowing_backend/app/services/mcp_oauth/registry.py] — medirus_gateway.py, medirus_connector_seed.py, and mcp_oauth/registry.py default to port 3005. app/config/entities.py and mcp_client.py default to port 3001 (http://medirus:3001/mcp per AD-SOC-4). Unify all fallbacks 
- [x] [Review][Patch] `build_medirus_connector_config` omits top-level `consumer_id` [nowing_backend/app/services/medirus_connector_seed.py:build_medirus_connector_config] — Registry lists account_metadata_keys=["consumer_id"], but build_medirus_connector_config only puts consumer_id in headers["X-Consumer-Id"] and does not return top-level "consumer_id". Add "consumer_id": consumer_id to r
- [x] [Review][Patch] ensure_workspace_medirus_connector catches Exception without rollback [nowing_backend/app/services/medirus_connector_seed.py:70-87] — Exception during flush leaves SQLAlchemy session in poisoned state, causing PendingRollbackError on later use. Add `await session.rollback()` before returning None.
- [x] [Review][Patch] MedirusMcpClient.call_tool has no HTTP timeout [nowing_backend/app/proprietary/platforms/medirus/mcp_client.py:call_tool] — Slow scrapes may hang indefinitely. But streamablehttp_client may have default; add explicit timeout to avoid pool exhaustion.
- [x] [Review][Patch] Frontend `getConnectorTypeDisplay` lacks MEDIRUS_MCP_CONNECTOR label [nowing_web/lib/connectors/utils.ts] — AC1 requires frontend enum/icon mirror; icon exists but display name falls back to raw enum. Add MEDIRUS_MCP_CONNECTOR: "Medirus Social" to typeMap.
- [x] [Review][Patch] MCP_SERVICES registry does not include MEDIRUS_MCP_CONNECTOR [nowing_backend/app/services/mcp_oauth/registry.py] — Subagent mcp_discovery uses MCP_SERVICES to look up metadata. Add an entry for Medirus with mcp_url from config, connector_type, allowed_tools, account_metadata_keys.
- [x] [Review][Patch] Alembic migration adds enum value without autocommit_block [nowing_backend/alembic/versions/5bd0001357ae_add_medirus_mcp_connector_enum.py] — PostgreSQL ALTER TYPE ... ADD VALUE cannot run inside a transaction in some versions. Use op.execute with autocommit_block or use IF NOT EXISTS is fine but wrap in autocommit.
- [x] [Review][Patch] Health probe alert-firing routine can crash instead of returning degraded status [nowing_backend/app/services/health/probes/medirus_probe.py] — _fire_alert_rules_for_stream_breach queries AlertRule and emits events; DB/pool failure may escape check_health(). Should catch and return degraded status.
- [x] [Review][Patch] UniversalScrapeTargetMapper.fallback_crawl_post does not validate URL before sending [nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py] — May pass search keyword or handle as URL. Should validate scheme or raise informative adapter error.
- [x] [Review][Patch] _MCP_ROUTED test set missing MEDIRUS_MCP_CONNECTOR [nowing_backend/tests/unit/agents/multi_agent_chat/test_mcp_discovery_migration.py] — test_mcp_discovery_migration.py:46-59 does not include MEDIRUS_MCP_CONNECTOR, causing assertion failure and skipping route test. Update test.
- [x] [Review][Patch] No test covers `_load_http_mcp_tools` branch for MEDIRUS_MCP_CONNECTOR [nowing_backend/tests/unit/agents/multi_agent_chat/test_mcp_allowlist_fallback.py] — Risk of falling through to raw discovery and exposing 150+ tools. Add unit test.
- [x] [Review][Patch] No tests verify Medirus connector auto-provisioning [nowing_backend/tests/integration/routes/test_workspaces.py] — Workspace creation and lifespan seed need integration/unit tests.
- [x] [Review][Patch] test_medirus_gateway.py patches _execute_medirus_tool; auth/dryRun/error paths unverified [nowing_backend/tests/unit/agents/multi_agent_chat/shared/tools/mcp/test_medirus_gateway.py] — Add unmocked tests for _execute_medirus_tool with mocked MedirusMcpClient.
- [x] [Review][Patch] No test verifies MedirusMcpClient injects token for x_admin_* tools [nowing_backend/tests/unit/platforms/test_medirus_mcp_client.py] — Add test in test_medirus_mcp_client.py.
- [x] [Review][Patch] No test verifies MedirusSocialAdapterV2.fetch_posts_for_target sets dryRun=False [nowing_backend/tests/unit/platforms/test_medirus_adapter_v2.py] — Add unit test for adapter_v2 dryRun override.
- [x] [Review][Patch] server_config.get("headers") may be None [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:186-187] — server_config.get("headers", {}) already defaults to empty dict; if value is explicitly None, `headers = server_config.get("headers") or {}` would fix. Code currently uses .get("headers", {}) which returns None if key is
- [x] [Review][Patch] _format_result serializes success=False without error as empty data response [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:228-229] — If result has success=False but no "error" key, _format_result drops the failure and returns json.dumps of data/summary/meta. Should include error or message.
- [x] [Review][Patch] _detect_platform_from_url incorrectly defaults non-HTTP input to facebook [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:161-177] — If url lacks scheme, urlparse.hostname is None or the first path segment, leading to wrong platform detection. Need to prepend https:// when no scheme.
- [x] [Review][Patch] _handle_medirus_crawl_post does not enforce url or post_id [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:372-385] — Pydantic model may already require one; if both missing, x_crawl_post gets empty target. Need explicit guard.
- [x] [Review][Patch] Facebook search without search_type falls through to x_search_tweets [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:254-272] — _handle_medirus_search only routes to x_facebook_search if normalized == "facebook" AND search_type is set. If unset, it uses x_search_tweets. Need default search_type="posts" for facebook.
- [x] [Review][Patch] Facebook group/page scrape allows empty target/query, building generic facebook URL [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:308-323] — Need guard if not target and not query.
- [x] [Review][Patch] _admin_args may overwrite explicit token argument [nowing_backend/app/proprietary/platforms/medirus/mcp_client.py:128-132] — Code: `return {**arguments, "token": self.admin_token}` when admin_token is set. If caller passed token, it gets overwritten. Should only inject if "token" not in arguments.
- [x] [Review][Patch] tool_name_prefix not applied to Medirus meta-tools [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py:643-649] — _load_http_mcp_tools short-circuits to create_medirus_meta_tools and returns without prefixing. If multiple Medirus connectors exist, tool name collision.
- [x] [Review][Patch] medirus_probe alert unwrapping may call .get() on string [nowing_backend/app/services/health/probes/medirus_probe.py:49-54] — If alerts is a list of strings, `alerts[0]` is str, then `alerts.get("alerts")` raises AttributeError, caught by except and resets to []. This hides alerts.
- [x] [Review][Patch] Tasks 6, 7.2, 8 remain unchecked in spec; lifecycle test missing [_bmad-output/implementation-artifacts/stories/21-8g-medirus-mcp-chat-connector.md] — Story spec marks 6.1, 6.2, 7.2, 8 as not done. This is task-tracking/verification finding, not a code defect. Should be addressed by completing tests.

#### Deferred

- [x] [Review][Defer] seed_medirus_connectors performs N+1 query at startup [nowing_backend/app/services/medirus_connector_seed.py:97-137] — For each workspace it does a separate SELECT for existing connector. With many workspaces this slows startup. Should batch or use a single INSERT ... WHERE NOT EXISTS query. However existing pattern is functionally corre
- [x] [Review][Defer] config/__init__.py loads .env.local with override=True [nowing_backend/app/config/__init__.py] — This overwrites env vars from Docker/Kubernetes. But this is pre-existing behavior, not introduced by story.
- [x] [Review][Defer] Medirus meta-tools are built statically and bypass cache invalidation on daemon schema changes [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py] — Tool schema is hard-coded in medirus_gateway.py input models. If daemon changes, only manual update will fix. This is by design for meta-tools but is a long-term maintenance issue.


### Browser E2E Verification Results
- **Date**: 2026-09-10
- **Scenarios Verified**:
  1. Twitter hashtag search (#AI) via Medirus meta-tool `x_search`.
  2. Twitter user posts (@elonmusk) via Medirus meta-tool `x_scrape` (`x_get_tweets` dispatch).
  3. Facebook group posts via Medirus meta-tool `x_search` (`x_facebook_search` dispatch).
  4. Classifieds / Facebook Marketplace for iPhone 15 via Medirus meta-tool `x_scrape` (`x_facebook_marketplace` dispatch), resulting in 15 scraped listings rendered as an interactive Leads table.
- **Protocol Compliance**:
  - Main Agent prioritizes `mcp_discovery` (Medirus) as first choice.
  - Honors negative constraints: strictly executes within Medirus and avoids Nowing scrapers when instructed.
  - Fallback logic intact when unconstrained.
