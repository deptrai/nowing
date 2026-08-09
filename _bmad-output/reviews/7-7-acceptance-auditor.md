# Acceptance Auditor Findings — Story 7.7 MCP Server Tool Expansion

Reviewed: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/reviews/7-7-review-diff.patch`  
Spec: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/7-7-mcp-server-tool-expansion.md`

## AC / Spec Findings

1. **`nowing_workspace_memory_update` exposes `memory_md` instead of the spec-mandated `content` parameter**
   - **Violates:** AC-2, Section 6 API contract.
   - **Evidence:** `nowing_mcp/mcp_server/features/team_memory/__init__.py` (new-file hunk `@@ -0,0 +1,102 @@`), function `workspace_memory_update`, parameter `memory_md: Annotated[str, Field(min_length=1, ...)]` (diff ~l.1592) and `json={"memory_md": memory_md}` (diff ~l.1616). The spec AC-2 and API contract both call the parameter `content (str, required)`.

2. **`nowing_report_list` lacks the `offset` pagination parameter required by AC-6**
   - **Violates:** AC-6 (note: the spec is internally inconsistent — AC-6 lists `offset` while the Section 6 API contract omits it).
   - **Evidence:** `nowing_mcp/mcp_server/features/reports/__init__.py` (hunk `@@ -0,0 +1,155 @@`), function `report_list` signature only has `limit` and `workspace`/`response_format` (diff ~l.1184); the `GET /reports` call uses `params={"workspace_id": ..., "limit": limit}` with no `offset`/`skip` (diff ~l.1198). The backend route accepts `skip`, but the MCP tool does not expose pagination.

3. **`nowing_automation_list` markdown output omits `trigger_type` and `next_run` required by AC-5**
   - **Violates:** AC-5.
   - **Evidence:** `nowing_mcp/mcp_server/features/automations/__init__.py` (hunk `@@ -0,0 +1,128 @@`), `_render_automation_list` builds lines `f"- **{id}**: {name} [{status}, v{version}]"` (diff ~l.691-703) and the tool docstring documents "id, name, status, and version" (diff ~l.643). The backend `AutomationSummary` schema does not expose trigger/next-run either, so the tool cannot meet the AC without backend changes.

4. **`nowing_muaban_bds_scrape` makes `city` optional with a default value, contrary to the API contract**
   - **Violates:** AC-4, Section 6 API contract (`city (str, required)`).
   - **Evidence:** `nowing_mcp/mcp_server/features/scrapers/platforms/muaban_bds.py` (hunk `@@ -0,0 +1,97 @@`), `city: Annotated[str, Field(...)] = "ho-chi-minh"` (diff ~l.1460). Contrast with `chotot_bds_scrape` in the same patch, which has `city` as a required parameter.

5. **`nowing_image_generate` response does not include a `status` field as stated in AC-3**
   - **Violates:** AC-3 ("trả về generation id / status / download").
   - **Evidence:** `nowing_mcp/mcp_server/features/image_generation/__init__.py` (hunk `@@ -0,0 +1,137 @@`), `_render_generation` renders id, model, size, created_at, error, image URLs (diff ~l.1086-1107); no `status` is printed. The backend `ImageGenerationRead` schema also has no `status` field, so the AC cannot be met without adding it.

6. **`nowing_workspace_memory_get` does not provide creation guidance when team memory is empty, as required by AC-2**
   - **Violates:** AC-2 ("render nội dung team memory (hoặc hướng dẫn tạo nếu chưa có)").
   - **Evidence:** `nowing_mcp/mcp_server/features/team_memory/__init__.py` (hunk `@@ -0,0 +1,102 @@`), `_render_memory` returns `"Team memory for '{workspace_name}' is empty."` with no instructions to create (diff ~l.1623-1635).

7. **Selfcheck / backend catalog tool count contradicts the 42/44 counts asserted by AC-7 and the DOD**
   - **Violates:** AC-7, Slice 5, DOD ("selfcheck OK: 44 tools").
   - **Evidence:** `nowing_mcp/mcp_server/selfcheck.py` hunks (diff ~l.2190-2218) add 13 entries; `nowing_backend/app/mcp_tools.py` first hunk (diff ~l.32-55) adds `nowing_cafef_scrape`, `nowing_indeed_scrape`, `nowing_walmart_scrape`, `nowing_walmart_reviews` in addition to the 7.7 tools; the first commit message states "Catalog sync test now passes: 53 = 53". The actual `EXPECTED_TOOLS` and `MCP_TOOL_NAMES` are internally consistent at 53, but the spec's 42/44 figures are stale because of out-of-scope tool additions carried in the same diff.

## Review artifact completeness note (not an AC gap in the product)

- The provided diff file does **not** contain hunks for the backend implementations required by AC-1 / AC-9:
  - `nowing_backend/app/services/memory/repository.py` (`list_memories`)
  - `nowing_backend/app/routes/memories_routes.py` (`GET /workspaces/{id}/memories`)
  - `nowing_backend/app/automations/services/run.py` (`RunService.launch`)
  - **Evidence:** `grep` for `^diff --git.*(repository|memories_routes|services/run).py` in the patch returns nothing; `RunService` is only imported/used in the route/test hunks (e.g. `test_run_service_launch.py` line 432 `from app.automations.services.run import RunService`).
  - **Corroboration:** these files exist in the actual repository and implement the required behavior, so this is a review-diff completeness issue, not a missing product feature. The parent should confirm whether these hunks are in a separate patch/branch or were accidentally omitted from the review artifact.

## Commands / actions

- No commands were run; the review is based on reading the provided diff and spot-checking the working tree for the missing backend hunks.
- **Actions for the parent agent:**
  1. Decide whether to update the spec (`content` → `memory_md`, report-list `offset` clarification, remove `muaban` `city` default, add `trigger_type`/`next_run` to automation list output, add `status` to image-generation output) or update the code to match the spec.
  2. Verify the missing backend hunks are included in the actual merge (memory list route/repository, `RunService.launch`).
  3. Reconcile the selfcheck/catalog count in the spec (42/44 vs actual 53).
