---
baseline_commit: 6df25e08ef2507670d916168d9d216c2b3391afa
---

# Story 2.5: Workspace MCP Tool Enable/Disable Toggle

**Status:** done
**Epic:** 2 — Connectors & Integrations
**Source:** <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md" />
**Related PRD:** OQ-4, FR-24, FR-29 in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />
**Related Architecture:** AD-7, AD-DEFER-3 in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />

## Story

As a workspace Owner,
I want to enable or disable specific MCP tools for my workspace,
So that I can control which tools MCP clients and agents can see.

## Acceptance Criteria

1. **Tool catalog visible to Owner**
   - **Given** the user is the Owner of a workspace
   - **When** they open the workspace MCP settings
   - **Then** the UI lists all built-in MCP tools (scrapers + knowledge base + run history) with an on/off toggle for each tool

2. **Persist toggle state per workspace**
   - **Given** the Owner toggles a tool off
   - **When** the request is saved
   - **Then** the state is persisted in the database and reflected immediately on reload

3. **Filter MCP `tools/list` per workspace**
   - **Given** a tool is disabled for a workspace
   - **When** an MCP client calls `tools/list` after selecting that workspace
   - **Then** the disabled tool does not appear in the result

4. **Guard `call_tool` for disabled tools**
   - **Given** a tool is disabled for a workspace
   - **When** an MCP client attempts to call it anyway
   - **Then** the server returns a clear error indicating the tool is disabled for that workspace

5. **Defaults keep existing behavior**
   - **Given** no toggle state exists for a tool
   - **When** `tools/list` is requested
   - **Then** the tool is shown (default enabled)

6. **Workspace selector tools are always visible**
   - **Given** any workspace state
   - **When** `tools/list` is requested
   - **Then** `nowing_list_workspaces` and `nowing_select_workspace` are always included

7. **`call_tool` honors explicit `workspace` argument**
   - **Given** an MCP client has selected workspace A but calls a tool with `workspace="B"`
   - **When** the tool is disabled for workspace B
   - **Then** the call is denied using workspace B's settings

8. **Fail-closed when tool state cannot be verified**
   - **Given** the MCP server cannot reach the backend to verify enabled state
   - **When** `call_tool` is invoked for a workspace-scoped tool
   - **Then** the server returns an error and does not execute the tool

## Tasks / Subtasks

- [x] Backend schema & migration (AC 2)
  - [x] Add `WorkspaceMcpToolSetting` model in `app/db.py`
  - [x] Create Alembic migration `175_add_workspace_mcp_tool_settings.py`
- [x] Backend API (AC 1, 2, 4, 7, 8)
  - [x] Define tool catalog constant with groups (`app/mcp_tools.py`)
  - [x] Add `GET /workspaces/{workspace_id}/mcp-tools` endpoint
  - [x] Add `PUT /workspaces/{workspace_id}/mcp-tools/{tool_name}` endpoint (validate tool name, reject system tools, return updated setting)
  - [x] Add Pydantic schemas and export them
- [x] MCP server filter (AC 3, 4, 5, 6)
  - [x] Make `WorkspaceContext` able to fetch workspace tool settings
  - [x] Override `list_tools` to filter by active workspace
  - [x] Guard `call_tool` for disabled tools
  - [x] Keep `nowing_list_workspaces` / `nowing_select_workspace` always enabled
- [x] Web UI (AC 1, 2)
  - [x] Add MCP tool toggles component in `components/settings/`
  - [x] Wire it into `GeneralSettingsManager`
  - [x] Extend `workspaces-api.service.ts` and `workspace.types.ts`
  - [x] Add mutation atom if needed
- [x] Tests
  - [x] Backend integration tests for GET/PUT and permission checks
  - [x] MCP server tests for `tools/list` filtering and disabled `call_tool`
  - [x] Run `uv run ruff check .` and `uv run pytest tests`
- [x] Update docs
  - [x] Update `docs/api-contracts-backend.md` if it exists
  - [x] Update `nowing_mcp/README.md` if behavior changes

## Dev Notes

### Data model

Add a new table `workspace_mcp_tool_settings` in `app/db.py`:

```python
class WorkspaceMcpToolSetting(BaseModel, TimestampMixin):
    __tablename__ = "workspace_mcp_tool_settings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "tool_name", name="uq_workspace_mcp_tool"),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(String(120), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")

    workspace = relationship("Workspace", back_populates="mcp_tool_settings")
```

Add the relationship on `Workspace`:

```python
mcp_tool_settings = relationship(
    "WorkspaceMcpToolSetting",
    back_populates="workspace",
    order_by="WorkspaceMcpToolSetting.tool_name",
    cascade="all, delete-orphan",
)
```

### Migration

Create `nowing_backend/alembic/versions/175_add_workspace_mcp_tool_settings.py` following the pattern of `174_add_llm_setup_completed_at.py` and `124_add_ai_file_sort_enabled.py`:

- Create the table with `workspace_id` FK to `workspaces.id` (`ON DELETE CASCADE`).
- Add unique index on `(workspace_id, tool_name)`.
- No backfill needed; missing rows mean "enabled by default".

### Backend endpoints

Add to `nowing_backend/app/routes/workspaces_routes.py`:

- `GET /workspaces/{workspace_id}/mcp-tools`
  - Permission: `Permission.SETTINGS_VIEW` (Owner/Editor/Viewer can view).
  - Returns: list of all known tools with `name`, `enabled`, `is_system`, `group`.
  - Merge `MCP_TOOL_CATALOG` with `WorkspaceMcpToolSetting` rows: missing rows return `enabled=true`.
- `PUT /workspaces/{workspace_id}/mcp-tools/{tool_name}`
  - Permission: `Permission.SETTINGS_UPDATE` (Owner only by default).
  - Body: `{"enabled": bool}`.
  - Validate `tool_name` exists in `MCP_TOOL_CATALOG`; return 400 for unknown tools.
  - Reject toggling system tools (`nowing_list_workspaces`, `nowing_select_workspace`) with 400.
  - Upsert `WorkspaceMcpToolSetting`.
  - Return `WorkspaceMcpToolRead` of the updated setting.

> **Note on migration numbering:** The suggested migration name `175_*` is based on the current `alembic history` head `174`. The dev agent must run `alembic history` at implementation time and use the actual next revision if another migration has landed first.

Schema additions in `app/schemas/workspace.py` (or new `app/schemas/mcp_tools.py`):

- `WorkspaceMcpToolRead` (name, enabled, is_system, group)
- `WorkspaceMcpToolsListResponse` (list of `WorkspaceMcpToolRead`)
- `WorkspaceMcpToolUpdate` (enabled)

Tool catalog: define `MCP_TOOL_CATALOG` in a new module `app/mcp_tools.py`. It must mirror the tools registered in `nowing_mcp/mcp_server/selfcheck.py` `EXPECTED_TOOLS` plus `nowing_chainlens_research` and any new scrapers. Keep it alphabetized for stable diff reviews.

> **Selfcheck sync:** `nowing_mcp/mcp_server/selfcheck.py` currently lists `EXPECTED_TOOLS` without `nowing_chainlens_research`, while `build_server` registers it. Update `EXPECTED_TOOLS` in the same PR so the offline selfcheck stays green.

Example:

```python
from enum import StrEnum


class McpToolGroup(StrEnum):
    WORKSPACE = "workspace"
    SCRAPER = "scraper"
    RUN_HISTORY = "run_history"
    KNOWLEDGE_BASE = "knowledge_base"


MCP_TOOL_CATALOG: list[dict[str, str]] = [
    {"name": "nowing_list_workspaces", "group": McpToolGroup.WORKSPACE},
    {"name": "nowing_select_workspace", "group": McpToolGroup.WORKSPACE},
    {"name": "nowing_web_crawl", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_google_search", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_reddit_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_youtube_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_youtube_comments", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_comments", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_user_search", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_tiktok_trending", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_google_maps_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_google_maps_reviews", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_amazon_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_instagram_scrape", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_instagram_details", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_list_scraper_runs", "group": McpToolGroup.RUN_HISTORY},
    {"name": "nowing_get_scraper_run", "group": McpToolGroup.RUN_HISTORY},
    {"name": "nowing_chainlens_research", "group": McpToolGroup.SCRAPER},
    {"name": "nowing_search_knowledge_base", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_list_documents", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_get_document", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_add_document", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_upload_file", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_update_document", "group": McpToolGroup.KNOWLEDGE_BASE},
    {"name": "nowing_delete_document", "group": McpToolGroup.KNOWLEDGE_BASE},
]

MCP_TOOL_SYSTEM_TOOLS = {"nowing_list_workspaces", "nowing_select_workspace"}
MCP_TOOL_NAMES = {t["name"] for t in MCP_TOOL_CATALOG}
```

### MCP server filtering

The MCP server uses `mcp.server.fastmcp.FastMCP`. `tools/list` is handled by `FastMCP.list_tools()` and `call_tool` by `FastMCP.call_tool()`.

Recommended approach (ponytail: smallest change that works):

1. Subclass `FastMCP` in `nowing_mcp/mcp_server/server.py` or `nowing_mcp/mcp_server/core/fastmcp_ext.py`:

```python
from typing import Any, Sequence

from mcp.server.fastmcp.exceptions import ToolError as FastMCPError
from mcp.types import ContentBlock, MCPTool

from .core.errors import ToolError as WorkspaceToolError


class WorkspaceAwareFastMCP(FastMCP):
    def __init__(self, *args, context: WorkspaceContext, **kwargs):
        # `context` is a keyword-only argument for our subclass; FastMCP.__init__
        # does not accept it, so it is not passed to super().__init__.
        super().__init__(*args, **kwargs)
        self._workspace_context = context

    async def list_tools(self) -> list[MCPTool]:
        # Get the base manifest first; this keeps the original MCPTool conversion.
        all_tools = await super().list_tools()
        # Outside a real request (selfcheck/offline) or before a workspace is chosen,
        # return the full manifest so clients can still discover selector tools.
        ctx = self.get_context()
        if ctx.request_context is None:
            return all_tools
        try:
            workspace = await self._workspace_context.resolve(None)
        except WorkspaceToolError:
            return all_tools
        try:
            settings = await self._workspace_context.client.request(
                "GET", f"/workspaces/{workspace.id}/mcp-tools"
            )
            enabled = {s["name"] for s in settings if s.get("enabled", True)}
        except Exception:
            # If backend is unreachable, fail-open for discovery only.
            enabled = {t.name for t in all_tools}
        system_tools = {"nowing_list_workspaces", "nowing_select_workspace"}
        return [t for t in all_tools if t.name in enabled or t.name in system_tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Sequence[ContentBlock] | dict[str, Any]:
        # Workspace selector tools must always work.
        system_tools = {"nowing_list_workspaces", "nowing_select_workspace"}
        if name in system_tools:
            return await super().call_tool(name, arguments)

        # Fail-closed: any failure to verify state results in denial.
        try:
            workspace = await self._workspace_context.resolve(
                arguments.get("workspace") if arguments else None
            )
            settings = await self._workspace_context.client.request(
                "GET", f"/workspaces/{workspace.id}/mcp-tools"
            )
            enabled = {s["name"] for s in settings if s.get("enabled", True)}
        except Exception as exc:
            raise FastMCPError(
                f"Could not verify tool '{name}' is enabled for the workspace: {exc}"
            ) from exc

        if name not in enabled:
            raise FastMCPError(
                f"Tool '{name}' is disabled for workspace '{workspace.name}'."
            )

        return await super().call_tool(name, arguments)
```

2. Modify `build_server` in `nowing_mcp/mcp_server/server.py` to pass `context` to the subclass:

```python
mcp = WorkspaceAwareFastMCP(
    "Nowing",
    host=settings.host,
    port=settings.port,
    stateless_http=True,
    json_response=False,
    instructions=(...),
    context=context,
)
```

3. Expose `NowingClient` from `WorkspaceContext` for the subclass. Add a property to `nowing_mcp/mcp_server/core/workspace_context.py`:

```python
@property
def client(self) -> NowingClient:
    return self._client
```

> **Performance note:** Both `list_tools` and `call_tool` make a backend round-trip. If latency matters, add a short TTL cache in `WorkspaceContext` keyed by `(current_identity(), workspace_id)` holding the enabled set for a few seconds. The first implementation can skip caching and optimize later if measured.

### Web UI

Create `nowing_web/components/settings/workspace-mcp-tools-control.tsx` modeled on `workspace-api-access-control.tsx`:

- Fetch `GET /api/v1/workspaces/{id}/mcp-tools` using `workspacesApiService.getWorkspaceMcpTools`.
- Accept `isOwner: boolean` prop. If `false`, render toggles as read-only/disabled and hide the "save" affordance.
- Group tools by `group` (workspace, scraper, run_history, knowledge_base) using collapsible sections or labeled groups.
- Render each non-system tool as a `Switch` row with name + description.
- On toggle, call `PUT /api/v1/workspaces/{id}/mcp-tools/{tool_name}`.
- Disable system tool toggles (`nowing_list_workspaces`, `nowing_select_workspace`) and show a lock icon or "always on" label.
- Show loading skeleton and error retry.

Add to `nowing_web/components/settings/general-settings-manager.tsx` below `<WorkspaceApiAccessControl ... />`:

```tsx
<WorkspaceMcpToolsControl
    workspaceId={workspaceId}
    isOwner={workspace?.is_owner ?? false}
    className="border-t pt-6"
/>
```

Extend:

- `nowing_web/contracts/types/workspace.types.ts`: add schemas for `getWorkspaceMcpToolsResponse`, `updateWorkspaceMcpToolRequest`, `updateWorkspaceMcpToolResponse`.
- `nowing_web/lib/apis/workspaces-api.service.ts`: add `getWorkspaceMcpTools` and `updateWorkspaceMcpTool`.
- `nowing_web/atoms/workspaces/workspace-mutation.atoms.ts`: add `updateWorkspaceMcpToolMutationAtom` (or use a single bulk update mutation if you prefer a "Save" button).

### Tests

Backend tests (add under `nowing_backend/tests/integration/` or unit route tests):

- Owner can list and update MCP tool settings.
- Editor/Viewer can list but cannot update (PUT returns 403).
- Non-member gets 403.
- Disabling a tool persists and is reflected on next GET.
- System tools cannot be disabled (PUT returns 400).
- Unknown `tool_name` in PUT returns 400.
- GET returns `enabled=true` for tools with no stored setting.

MCP server tests (add under `nowing_mcp/tests/`):

- `test_list_tools_filters_disabled`: mock backend returning a disabled tool; assert it is omitted from `tools/list`.
- `test_list_tools_no_workspace_returns_all`: assert `tools/list` returns full catalog when no workspace is selected (selfcheck/initial discovery).
- `test_call_tool_disabled`: assert calling a disabled tool returns an error.
- `test_call_tool_uses_workspace_argument`: assert guard uses `workspace` argument, not active workspace, when present.
- `test_call_tool_fail_closed_on_backend_error`: mock backend raising; assert tool is denied, not executed.
- `test_selfcheck_still_passes`: run `selfcheck.py` (or import `run()`) after updating `EXPECTED_TOOLS` and ensure no problems.

Web tests: optional component test for toggles using React Testing Library or a manual E2E check. Verify non-owner sees read-only UI.

### Consistency & conventions

- Follow AD-7: MCP server remains stateless; per-workspace state comes from the backend on each `tools/list`/`call_tool`.
- Follow AD-9: only Owner can mutate workspace settings. Use `Permission.SETTINGS_UPDATE` for the PUT endpoint.
- Follow existing schema conventions: Pydantic v2 in `app/schemas/workspace.py`, Zod schemas in `nowing_web/contracts/types/workspace.types.ts`.
- Follow existing migration conventions: numeric revision `175`, `down_revision = "174"`.
- Follow `ponytail`: do not add a new abstraction layer for tool catalog beyond one constant module and one model.

### Open questions / risks

- **Catalog duplication:** `app/mcp_tools.py` and `nowing_mcp/mcp_server/selfcheck.py` both list tools. If a tool is added later, both must be updated. Add a test in `nowing_mcp/tests/` that asserts `EXPECTED_TOOLS` matches `MCP_TOOL_NAMES` or a single source of truth.
- **External MCP connector tools:** this story covers only built-in Nowing MCP tools. External MCP connector tools (added via Composio/OAuth) are out of scope; toggling them requires a separate design because their names and availability are dynamic per workspace.
- **`list_tools` backend call:** every `tools/list` will hit the backend. If latency becomes an issue, add a short TTL cache keyed by `(api_key, workspace_id)` in `WorkspaceContext`.
- **`call_tool` guard:** `call_tool` receives `arguments` which may include `workspace`. If `workspace` is omitted, resolve active workspace. If no active workspace and multiple exist, `WorkspaceContext` already raises a clear error; keep that behavior.
- **Bulk reset:** there is no bulk "reset to defaults" endpoint. If Owner wants to re-enable all tools, they must toggle each one. Consider a `POST /workspaces/{id}/mcp-tools/reset` follow-up if requested.
- **Agent chat tools:** this story controls MCP server tools only. It does not affect `main_agent/tools/registry.py` or in-chat agent tools. If the requirement extends to chat agents, split into a separate story.

## References

- Backend workspace routes: <ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/app/routes/workspaces_routes.py" />
- Backend workspace schemas: <ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/app/schemas/workspace.py" />
- Backend workspace model: <ref_snippet file="/Users/luisphan/Documents/nowing/nowing_backend/app/db.py" lines="1702-1840" />
- Backend permission enum: <ref_snippet file="/Users/luisphan/Documents/nowing/nowing_backend/app/db.py" lines="293-388" />
- MCP server composition: <ref_file file="/Users/luisphan/Documents/nowing/nowing_mcp/mcp_server/server.py" />
- MCP workspace context: <ref_file file="/Users/luisphan/Documents/nowing/nowing_mcp/mcp_server/core/workspace_context.py" />
- MCP selfcheck expected tools: <ref_file file="/Users/luisphan/Documents/nowing/nowing_mcp/mcp_server/selfcheck.py" />
- Web workspace API access control (copy pattern): <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/components/settings/workspace-api-access-control.tsx" />
- Web general settings manager: <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/components/settings/general-settings-manager.tsx" />
- Web workspaces API service: <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/lib/apis/workspaces-api.service.ts" />
- Web workspace types: <ref_file file="/Users/luisphan/Documents/nowing/nowing_web/contracts/types/workspace.types.ts" />
- Recent migration example: <ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/alembic/versions/174_add_llm_setup_completed_at.py" />
- Epic 2 context: <ref_snippet file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md" lines="191-261" />

## Dev Agent Record

### Agent Model Used

- SWE-1.7 Max

### Debug Log References

- Backend integration tests passed: 8/8
- MCP server tests passed: 7/7
- Web E2E Playwright tests passed: 4/4
- Web TypeScript/Biome checks passed on touched files

### Completion Notes List

- Added `WorkspaceMcpToolSetting` model and migration `175_add_workspace_mcp_tool_settings.py`.
- Created `app/mcp_tools.py` catalog, backend endpoints `GET/PUT`, schemas, and exports.
- Implemented `WorkspaceAwareFastMCP` with `list_tools` filtering and `call_tool` fail-closed guard.
- Synced `selfcheck.py` `EXPECTED_TOOLS` to include `nowing_chainlens_research`.
- Built web `WorkspaceMcpToolsControl`, wired into `GeneralSettingsManager`, added service/types/mutation/cache-key.
- Updated `docs/api-contracts-backend.md` and `nowing_mcp/README.md`.

### File List

- nowing_backend/app/db.py
- nowing_backend/app/mcp_tools.py
- nowing_backend/app/routes/workspaces_routes.py
- nowing_backend/app/schemas/workspace.py
- nowing_backend/app/schemas/__init__.py
- nowing_backend/alembic/versions/175_add_workspace_mcp_tool_settings.py
- nowing_mcp/mcp_server/server.py
- nowing_mcp/mcp_server/core/workspace_context.py
- nowing_mcp/mcp_server/selfcheck.py
- nowing_web/components/settings/workspace-mcp-tools-control.tsx
- nowing_web/components/settings/general-settings-manager.tsx
- nowing_web/contracts/types/workspace.types.ts
- nowing_web/lib/apis/workspaces-api.service.ts
- nowing_web/atoms/workspaces/workspace-mutation.atoms.ts
- nowing_web/lib/query-client/cache-keys.ts
- nowing_web/tests/workspace-settings/mcp-tools.spec.ts
- nowing_web/tests/helpers/api/auth.ts
- nowing_web/tests/helpers/api/workspaces.ts
- nowing_backend/tests/integration/workspaces/conftest.py
- nowing_backend/tests/integration/workspaces/test_mcp_tools.py
- nowing_mcp/tests/test_mcp_tool_filter.py
- docs/api-contracts-backend.md
- nowing_mcp/README.md

### Review Findings

#### Decision Needed

- [x] [Review][Decision] MCP `list_tools` fail-open when backend is unreachable for an active workspace — Resolved: fail-closed for active workspaces (return only `nowing_list_workspaces` / `nowing_select_workspace`) but keep fail-open for selfcheck/initial discovery when no workspace is active.

#### Patch

- [x] [Review][Patch] Race condition in `PUT /workspaces/{id}/mcp-tools/{tool_name}` — Fixed using `INSERT ... ON CONFLICT ... DO UPDATE` via `sqlalchemy.dialects.postgresql.insert`.
- [x] [Review][Patch] Missing catalog sync test — Added `test_backend_catalog_matches_selfcheck` in `nowing_mcp/tests/test_mcp_tool_filter.py`.
- [x] [Review][Patch] System tools defined in two places — Introduced `_SYSTEM_TOOLS` constant in `nowing_mcp/mcp_server/server.py`; backend already uses `MCP_TOOL_SYSTEM_TOOLS` in `app/mcp_tools.py`.
- [x] [Review][Patch] `update_workspace_mcp_tool` looks up group with unguarded `next()` and linear scan — Replaced with `MCP_TOOL_GROUP_MAP` dict lookup.
- [x] [Review][Patch] Unnecessary `session.refresh` after commit — Removed; response now uses the value returned by the upsert.
- [x] [Review][Patch] Dead/unused `WorkspaceMcpToolsListResponse` schema — Removed from `app/schemas/workspace.py` and `app/schemas/__init__.py`.
- [x] [Review][Patch] `isOwner` flashes `false` while workspaces are loading — `isOwner` now `boolean | undefined`; `WorkspaceMcpToolsControl` shows skeleton until ownership is known.
- [x] [Review][Patch] Non-owner toggle gives no feedback — Added `toast.error` when a non-owner attempts to toggle.
- [x] [Review][Patch] Unknown group label falls back to raw key — Added humanized fallback `group.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())`.
- [x] [Review][Patch] `call_tool` and `list_tools` swallow all exceptions without logging — Added `logger.warning`/`logger.error` before raising `FastMCPError`.
- [x] [Review][Patch] `call_tool` assumes `arguments` is a dict — Guarded with `isinstance(arguments, dict)` before calling `.get`.
- [x] [Review][Patch] Duplicated client fixtures in `conftest.py` — Extracted shared `_client_for_user` helper used by all four client fixtures.

#### Dismissed

- ~15 false positives or handled-elsewhere items from Blind Hunter and Edge Case Hunter, including: `z.boolean()` coercion (Zod `boolean()` is strict), missing `updated_at` (this model uses `TimestampMixin` with only `created_at`), XSS in `title` (React escapes), workspace ID validation returning 403 (matches existing tests), default `enabled=true` when no settings rows (intended), missing `enabled` key in backend response (handled by `.get`), `KeyboardInterrupt` catching (`except Exception` does not catch it), `reference` integer `0` (resolved as a valid workspace id lookup), and test-helper additions (needed for the non-owner E2E scenario).
- _bmad-output/implementation-artifacts/2-5-workspace-mcp-tool-toggle.md
