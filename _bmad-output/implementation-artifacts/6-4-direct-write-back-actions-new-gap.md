# Story 6.4: Direct Write-Back Actions

Status: done

## Story

As a workspace member,
I want automation actions to write directly to Notion, Slack, Linear, or Jira,
so that research outputs land in the tools my team already uses.

## Acceptance Criteria

1. **Action registry accepts new types**
   - `write_back_notion`, `write_back_linear`, `write_back_jira`, `write_back_slack` are registered as `ActionDefinition` entries.
   - Each has its own `params_model` and handler package under `app/automations/actions/builtin/`.

2. **Each action writes through the connected MCP connector**
   - Given a workspace has a connected Notion/Slack/Linear/Jira MCP connector (with `config["server_config"]`), the handler discovers the matching write tool via `load_mcp_tools(..., bypass_internal_hitl=True)`.
   - The handler invokes the tool and writes the page/message/issue.
   - Multi-account connectors are disambiguated by `connector_name` (optional when only one connector exists; required when multiple connectors of the same type exist).
   - If the connector has `auth_expired` or OAuth token decryption fails, the step fails with a clear re-authenticate message instead of silently skipping.

3. **Run output captures the created object reference and is usable in later steps**
   - Handler returns a JSON-serializable dict containing at minimum `provider`, `connector_id`, `connector_name`, `object_id`, and `url` when available.
   - The result is stored in `AutomationRun.step_results[].result` by the executor and exposed as `steps.<step_id>` (or `steps.<output_as>`) in the Jinja template context, so subsequent steps can reference `{{ steps.create_page.url }}`.

4. **Idempotency/update mode for recurring automations**
   - Each `write_back_*` action accepts an optional `object_id`/`page_id`/`issue_key` param.
   - When provided, the handler calls the provider's update tool (`notion-update-page`, `save_issue` with `id`, `editJiraIssue`, Slack `update_message` if available) instead of creating a duplicate.
   - When omitted, the handler creates a new object. v1 may default to create-only for Slack if update tool is not exposed.

5. **Frontend builder can author write-back steps**
   - `builderTaskSchema` supports an `action` field and a discriminated `writeBackParams` union per provider.
   - `buildPlan` emits `action: "write_back_..."` with the correct params.
   - `hydrateForm` does not reject write-back steps.
   - `task-item.tsx` lets the user pick the action type and enter provider-specific params, including a connector-name dropdown.
   - `plan-step-card.tsx` already renders arbitrary actions generically; no change needed.
   - `automation-builder-form.tsx` `mapFormErrors` maps per-action field errors correctly, not only `tasks.${index}.query`.

6. **Automation drafter catalog is updated**
   - `app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py` lists the new action types and their param schemas so the chat drafter can build write-back automations.
   - Include at least one few-shot example combining `agent_task` + `write_back_slack` referencing `{{ steps.<step_id>.url }}`.

7. **Slack write path is enabled at the connector registry**
   - `app/services/mcp_oauth/registry.py` adds `send_message` and `slack_send_message` to `MCP_SERVICES["slack"].allowed_tools`, removes them from `readonly_tools`, and adds `chat:write` (and `chat:write:user` if needed) to `scopes` so the tool is discovered and allowed to write.

## Tasks / Subtasks

- [x] Backend: create shared write-back helper module
  - [x] `app/automations/actions/builtin/write_back/shared.py` — MCP tool discovery, connector selection, multi-account prefix resolution, `cloudId` resolution for Jira, result parsing.
- [x] Backend: create four action packages
  - [x] `app/automations/actions/builtin/write_back_notion/`: `params.py`, `factory.py`, `invoke.py`, `definition.py`, `__init__.py`.
  - [x] `app/automations/actions/builtin/write_back_linear/`: same.
  - [x] `app/automations/actions/builtin/write_back_jira/`: same.
  - [x] `app/automations/actions/builtin/write_back_slack/`: same.
- [x] Backend: register new actions
  - [x] Update `app/automations/actions/builtin/__init__.py` to import the four packages.
- [x] Backend: enable Slack write tool discovery
  - [x] Update `app/services/mcp_oauth/registry.py` Slack `allowed_tools`, `readonly_tools`, and `scopes`.
- [x] Backend: update drafter prompt catalog
  - [x] Update `app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py` catalog and add few-shot.
- [x] Frontend: extend automation builder
  - [x] Update `nowing_web/lib/automations/builder-schema.ts`: `builderTaskSchema` (add `action` + discriminated `writeBackParams`), `emptyTask`, `buildPlan`, `hydrateForm`.
  - [x] Update `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`: action selector + provider-specific param UI.
  - [x] Update `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/automation-builder-form.tsx`: `mapFormErrors` to handle `tasks.${index}.writeBackParams.*` errors.
  - [x] `plan-step-card.tsx` needs no change.
- [x] Tests
  - [x] Unit tests for each handler using a fake `StructuredTool` (mock MCP tool) with `metadata["mcp_connector_id"]` and `metadata["mcp_original_tool_name"]`.
  - [x] Unit test for shared connector selection / multi-account prefix resolution.
  - [x] Test Jira `cloudId` fallback (`connector.config["cloud_id"]` missing → call `getAccessibleAtlassianResources`).
  - [x] Test update vs create path (`object_id` provided vs omitted).
  - [x] Update/import registration canary `tests/unit/automations/test_import_registrations.py` (or add new test) asserting `write_back_*` actions are registered after `import app.automations`.
  - [x] Frontend tests for builder schema round-trip if test suite supports it.

## Dev Notes

### ATDD Artifacts

- Checklist: `/Users/luisphan/Documents/nowing/_bmad-output/test-artifacts/atdd-checklist-6-4-direct-write-back-actions-new-gap.md`
- Backend unit tests:
  - `nowing_backend/tests/unit/automations/actions/builtin/write_back/test_shared.py`
  - `nowing_backend/tests/unit/automations/actions/builtin/write_back/test_action_scaffolds.py`
  - `nowing_backend/tests/unit/automations/test_import_registrations.py` (registration canary)
- Frontend E2E tests: `nowing_web/tests/automations/write-back-builder.spec.ts`

### Existing pattern to mirror

The only existing action is `agent_task`:

- `app/automations/actions/types.py:35-41` defines `ActionContext` and `ActionDefinition` (`type`, `name`, `description`, `params_model`, `build_handler`).
- `app/automations/actions/store.py:10-18` is the registry (`register_action`, `get_action`, `all_actions`).
- `app/automations/actions/builtin/agent_task/definition.py:10-16` creates an `ActionDefinition` and calls `register_action`.
- `app/automations/actions/builtin/agent_task/factory.py:12-27` returns a closure that validates `AgentTaskActionParams` and calls `run_agent_task`.
- `app/automations/actions/builtin/agent_task/__init__.py:15` imports `definition` for its side-effect.
- `app/automations/actions/builtin/__init__.py:5` imports `agent_task` so the registry is populated at startup.
- `app/automations/runtime/step.py:46-78` calls `get_action(step.action)`, builds the handler, runs it with retries.
- `app/automations/runtime/executor.py:71-72` binds the step result to `step_outputs[step.output_as or step.step_id]`.
- `app/automations/templating/context.py:25-41` exposes `steps` to Jinja templates.

Reuse this exact package layout for each write-back action.

### Backend design

Each write-back handler follows this flow:

1. Validate `params` with a Pydantic `*ActionParams` model (use `ConfigDict(extra="forbid")`).
2. Resolve the target connector:
   - Query `SearchSourceConnector` for the workspace where `connector_type` matches the action's provider (e.g. `SearchSourceConnectorType.NOTION_CONNECTOR`) and `config` contains `"server_config"` (`app/db.py:1936` JSONB `config` column).
   - If `connector_name` is supplied, filter by `name` (`uq_workspace_user_connector_type_name` unique constraint, `app/db.py:1898-1904`).
   - If zero matches → fail with `No {provider} MCP connector configured`.
   - If multiple matches and no `connector_name` → fail with `Multiple {provider} connectors found; provide connector_name`.
3. Load MCP tools:
   ```python
   from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import load_mcp_tools
   tools = await load_mcp_tools(session, workspace_id, bypass_internal_hitl=True)
   ```
   `bypass_internal_hitl=True` is required because an automation cannot prompt a human for approval (`app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py:348-349`).
4. Pick the write tool:
   - Look for a tool whose `metadata["mcp_connector_id"]` equals the resolved connector id (`tool.py:424-436`).
   - Match `metadata["mcp_original_tool_name"]` or the unprefixed `tool.name` against the known write tool names.
   - Known base names (primary + fallback):
     - Notion: `notion-create-pages`, `create-pages`, `notion-update-page`, `update-page`.
     - Linear: `save_issue`.
     - Jira: `createJiraIssue`, `editJiraIssue`.
     - Slack: `send_message`, `slack_send_message`.
5. Build tool arguments from `*ActionParams`:
   - Inspect `tool.metadata["mcp_input_schema"]` and map the typed params model to the actual schema.
   - For Jira `createJiraIssue`, resolve `cloudId`:
     - First try `connector.config["cloud_id"]`.
     - If missing, call `getAccessibleAtlassianResources` MCP tool and cache the first `id`.
   - For update mode:
     - Notion `notion-update-page`: pass `page_id` and `properties` / `data`.
     - Linear `save_issue`: include `id` in args.
     - Jira `editJiraIssue`: pass `issueIdOrKey` and updated fields.
     - Slack: if `send_message` does not support `thread_ts` update, fallback to create-only.
6. Invoke:
   ```python
   result_str = await tool.coroutine(**args)
   ```
   `tool.coroutine` runs the MCP call directly, bypassing LangChain invoke wrapping.
7. Parse `result_str`:
   - If it starts with `"Error:"` or `"Tool call rejected"` → raise `RuntimeError` so the step fails.
   - Try `json.loads(result_str)`. If the parsed object has an `error` field, raise.
   - Extract reference fields (`id`, `url`, `key`, `ts`, `channel`, `permalink`, `page_url`, `issue_url`, etc.).
   - Return a normalized dict:
     ```python
     {
       "provider": "notion",
       "connector_id": connector_id,
       "connector_name": connector_name,
       "object_id": "<page-id>",
       "url": "https://...",
       "raw": parsed_json,
     }
     ```
8. `runtime/step.py:67-72` handles retries and timeout via `with_retries`. `executor.py:71-72` binds `result` to `steps.<step_id>` in the template context.

### Multi-account prefixing

`load_mcp_tools` auto-prefixes tool names when a workspace has more than one connector of the same service type (`tool.py:1159-1230`):

- Pattern: `{service_key}_{connector_id}_{original_name}` (e.g. `linear_3_save_issue`).
- `metadata["mcp_original_tool_name"]` preserves the base name (`tool.py:434`).
- Single-account tools keep their original name.

Therefore, match on `metadata["mcp_connector_id"]` first, then `metadata["mcp_original_tool_name"]`; do not rely on `tool.name` alone.

### Connector type constants

`SearchSourceConnectorType` enum values (`app/db.py:85-117`):

- `NOTION_CONNECTOR`
- `SLACK_CONNECTOR`
- `LINEAR_CONNECTOR`
- `JIRA_CONNECTOR`
- `MCP_CONNECTOR` (generic user-defined MCP servers; not used for these dedicated actions)

### MCP service registry

`app/services/mcp_oauth/registry.py:137-181` `MCP_SERVICES["slack"]` controls Slack tool discovery:

- Add `send_message` and `slack_send_message` to `allowed_tools`.
- Remove them from `readonly_tools`.
- Add `chat:write` and `chat:write:user` to `scopes`.
- Notion write tools (`notion-create-pages`, `create-pages`, `notion-update-page`, `update-page`), Linear `save_issue`, and Jira `createJiraIssue`/`editJiraIssue` are already allowed.

### Known MCP tool parameters (starting point)

These are expected shapes; the handler must still inspect `mcp_input_schema` because MCP servers evolve and Notion has v1/v2 naming.

- **Notion `notion-create-pages`**: `pages` (array of `{title, content}`), optional `parent` (object with `page_id` or `database_id`). Minimum viable: `{"pages": [{"title": "...", "content": "..."}]}`.
- **Notion `notion-update-page`**: `page_id` (string), `properties` or `data` (object/string depending on MCP server version).
- **Linear `save_issue`**: `title` (string), `team` (string/identifier), `description` (string, optional), `state` (string, optional), `assignee` (string, optional), `labels` (array, optional). Include `id` to update.
- **Jira `createJiraIssue`**: `cloudId` (string), `projectKey` (string), `summary` (string), `issueTypeName` (string), `description` (string, optional), `additional_fields` (object, optional).
- **Jira `editJiraIssue`**: `cloudId` (string), `issueIdOrKey` (string), `summary`/`description`/`additional_fields`.
- **Slack `send_message`**: `channel` (string, ID or name), `text` (string), optional `thread_ts` and `blocks`.

### Frontend builder changes

`nowing_web/lib/automations/builder-schema.ts:33-46` `builderTaskSchema` currently has `query`, `mentions`, `maxRetries`, `timeoutSeconds`. Refactor to:

```typescript
export const builderTaskSchema = z.object({
  id: z.string(),
  action: z.enum(["agent_task", "write_back_notion", "write_back_linear", "write_back_jira", "write_back_slack"]).default("agent_task"),
  // agent_task fields
  query: z.string().trim().min(1, "Describe what the agent should do").optional(),
  mentions: z.array(z.custom<MentionedDocumentInfo>()).default([]),
  // write-back fields, discriminated by provider
  writeBackParams: z.discriminatedUnion("provider", [
    z.object({ provider: z.literal("notion"), title: z.string().min(1), content: z.string(), parent_page_id: z.string().nullable().default(null), connector_name: z.string().nullable().default(null), object_id: z.string().nullable().default(null) }),
    z.object({ provider: z.literal("linear"), title: z.string().min(1), description: z.string().nullable().default(null), team_id: z.string().nullable().default(null), state: z.string().nullable().default(null), connector_name: z.string().nullable().default(null), object_id: z.string().nullable().default(null) }),
    z.object({ provider: z.literal("jira"), project_key: z.string().min(1), summary: z.string().min(1), description: z.string().nullable().default(null), issue_type: z.string().default("Task"), connector_name: z.string().nullable().default(null), object_id: z.string().nullable().default(null) }),
    z.object({ provider: z.literal("slack"), channel: z.string().min(1), text: z.string().min(1), thread_ts: z.string().nullable().default(null), connector_name: z.string().nullable().default(null), object_id: z.string().nullable().default(null) }),
  ]).nullable().default(null),
  maxRetries: z.number().int().min(0).max(10).nullable(),
  timeoutSeconds: z.number().int().positive().max(86_400).nullable(),
});
```

Adjust so that `query` is required when `action === "agent_task"` and `writeBackParams` is required when `action` is a write-back action. Then update:

- `emptyTask()` (`builder-schema.ts:130`) to set `action: "agent_task"` and `writeBackParams: null`.
- `buildPlan()` (`builder-schema.ts:203-218`) to branch on `task.action`.
- `hydrateForm()` (`builder-schema.ts:390-442`) to stop rejecting non-`agent_task` actions and parse `writeBackParams` back into `BuilderTask`.

`nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx:87-128` currently renders only `MentionTaskInput`. Refactor into sub-components:

- `AgentTaskFields` for `query` + `mentions`.
- `WriteBackFields` for provider-specific inputs and a connector-name dropdown.
- Add an `action` selector at the top of the card.

`nowing_web/app/dashboard/[workspace_id]/automations/components/builder/automation-builder-form.tsx:66-77` `mapFormErrors` hardcodes `tasks.${index}.query`. Update to derive the key from the Zod path:

```typescript
if (path[0] === "tasks" && typeof path[1] === "number") {
  key = path.slice(0, 3).join("."); // e.g. tasks.0.writeBackParams.provider
} else if (path[0] === "schedule") {
  key = "schedule";
} else {
  key = String(path[0] ?? "_root");
}
```

`nowing_web/contracts/types/automation.types.ts:29` already defines `planStep.action` as `z.string()`; no contract change is required.
`plan-step-card.tsx:47-76` already generically renders unknown actions; no change needed.

### Drafter prompt update

`app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py:72-75` currently lists only `agent_task`. Add catalog entries:

```
- write_back_notion — params: title (string, Jinja), content (string, Jinja), parent_page_id (string, optional), object_id/page_id (string, optional), connector_name (string, optional).
- write_back_linear — params: title, description, team_id, state, object_id/issue_key (optional), connector_name.
- write_back_jira — params: project_key, summary, description, issue_type (default "Task"), object_id/issue_key (optional), connector_name.
- write_back_slack — params: channel (string, Jinja), text (string, Jinja), thread_ts (optional), object_id/message_ts (optional), connector_name.
```

Add a few-shot example in `prompt.py` showing an `agent_task` step summarizing folder docs, followed by `write_back_slack` posting `{{ steps.summarize.final_message }}` to channel `#daily-digest`.

### Files to create / modify

Create:

- `nowing_backend/app/automations/actions/builtin/write_back/__init__.py`
- `nowing_backend/app/automations/actions/builtin/write_back/shared.py`
- `nowing_backend/app/automations/actions/builtin/write_back_notion/{__init__.py,params.py,factory.py,invoke.py,definition.py}`
- `nowing_backend/app/automations/actions/builtin/write_back_linear/{__init__.py,params.py,factory.py,invoke.py,definition.py}`
- `nowing_backend/app/automations/actions/builtin/write_back_jira/{__init__.py,params.py,factory.py,invoke.py,definition.py}`
- `nowing_backend/app/automations/actions/builtin/write_back_slack/{__init__.py,params.py,factory.py,invoke.py,definition.py}`
- `nowing_backend/tests/unit/automations/actions/builtin/write_back_*/test_*.py`

Modify:

- `nowing_backend/app/automations/actions/builtin/__init__.py` (import new packages)
- `nowing_backend/app/services/mcp_oauth/registry.py` (Slack allowed tools, readonly tools, scopes)
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py` (catalog + few-shot)
- `nowing_web/lib/automations/builder-schema.ts` (schema, buildPlan, hydrateForm, emptyTask)
- `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx` (action selector + param UI)
- `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/automation-builder-form.tsx` (mapFormErrors)

### Testing approach

- Backend unit tests should mock `load_mcp_tools` returning a list of fake `StructuredTool` objects with the expected metadata (`mcp_connector_id`, `mcp_original_tool_name`) and `coroutine`.
- Use `isolated_action_registry` fixture (`tests/unit/automations/conftest.py:20-28`) for any test that imports write-back action packages.
- Test cases:
  - Zero/multiple connectors without `connector_name`.
  - Multi-account prefix resolution (`linear_3_save_issue`).
  - `bypass_internal_hitl=True` is passed to `load_mcp_tools`.
  - Error strings and JSON `{"error": ...}` are converted to raised exceptions.
  - Jira `cloudId` fallback path.
  - Update vs create (`object_id` present vs absent).
  - Connector with `auth_expired` / missing `server_config` fails with clear message.
- Add canary test asserting all four `write_back_*` action types are present in `get_action()` after `import app.automations`.
- Frontend tests: if `builder-schema.ts` has tests, ensure `formFromAutomation` round-trips write-back steps and `buildPlan` produces correct `action`/`params`.

### Guardrails / anti-patterns

- Do **not** call external APIs directly. Always route through `load_mcp_tools` so OAuth tokens, scopes, and allowed-tools filtering are respected.
- Do **not** prompt for HITL inside an action handler. Use `bypass_internal_hitl=True`.
- Do **not** hardcode tool arguments. Inspect `mcp_input_schema` and map from the typed params model.
- Do **not** expose secrets or raw tokens in the returned `raw` dict.
- Do **not** rely on agent tools (`create_notion_page`, etc.) in the `agent_task` path for this story; this story is the dedicated action path.
- Do **not** silently skip connectors with missing `server_config` or `auth_expired`; fail the step so the run record shows the real reason.

## Project Structure Notes

- Action packages live side-by-side under `app/automations/actions/builtin/` — one package per action type, exactly like `agent_task/`.
- Shared helpers live in `app/automations/actions/builtin/write_back/shared.py` (not an action, so `write_back/__init__.py` should not import `definition`).
- Frontend builder code is colocated under `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/`.
- The MCP connector registry (`app/services/mcp_oauth/registry.py`) is the single source of truth for which write tools are exposed.

## References

- `app/automations/actions/types.py:35-41` — `ActionContext`, `ActionDefinition`.
- `app/automations/actions/store.py:10-18` — `register_action`, `get_action`.
- `app/automations/actions/builtin/agent_task/definition.py:10-16` — `ActionDefinition` registration pattern.
- `app/automations/actions/builtin/agent_task/factory.py:12-27` — handler closure pattern.
- `app/automations/actions/builtin/__init__.py:5` — startup imports.
- `app/automations/runtime/step.py:46-78` — step execution and retries.
- `app/automations/runtime/executor.py:71-72` — `step_outputs` binding.
- `app/automations/templating/context.py:25-41` — Jinja `steps` namespace.
- `app/automations/schemas/definition/plan_step.py:25-28` — `output_as` field.
- `app/automations/schemas/definition/envelope.py:29-41` — `AutomationDefinition`.
- `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py:419-436` — `StructuredTool` metadata.
- `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py:1117-1245` — `load_mcp_tools`, `server_config` filtering, multi-account prefix logic.
- `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py:979-1017` — `_mark_connector_auth_expired`.
- `app/services/mcp_oauth/registry.py:137-181` — Slack `MCPServiceConfig`.
- `app/db.py:85-117` — `SearchSourceConnectorType` enum.
- `app/db.py:1895-1936` — `SearchSourceConnector` model and `config` JSONB column.
- `nowing_web/lib/automations/builder-schema.ts:33-46` — `builderTaskSchema`.
- `nowing_web/lib/automations/builder-schema.ts:130-132` — `emptyTask`.
- `nowing_web/lib/automations/builder-schema.ts:203-218` — `buildPlan`.
- `nowing_web/lib/automations/builder-schema.ts:390-442` — `hydrateForm`.
- `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/automation-builder-form.tsx:66-77` — `mapFormErrors`.
- `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx:87-128` — task editor UI.
- `nowing_web/contracts/types/automation.types.ts:29` — `planStep.action` is `z.string()`.
- `app/agents/chat/multi_agent_chat/main_agent/tools/automation/prompt.py:72-75` — drafter action catalog.
- PRD gap: `FR-18` / `OQ-5` in `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`.
- Architecture deferred decision: `AD-DEFER-2` in `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`.
- Epic source: `Epic 6` / `Story 6.4` in `_bmad-output/planning-artifacts/epics.md`.

## Dev Agent Record

### Review Findings — Code Review 2026-07-24

Reviewed the Story-6.4 diff within checkpoint `1bd12a1d4` (31 files, +1784/−57) with three layers (Blind Hunter + Edge Case Hunter + Acceptance Auditor). **Acceptance Auditor verdict: AC-1, AC-3, AC-4, AC-7 Met; AC-2, AC-5, AC-6 Partial.** Findings verified against `write_back/shared.py`.

- [x] [Review][Decision] (RESOLVED — accept free-text) AC-5: connector-name is a free-text `<Input>`, not the required **dropdown** of the workspace's connectors of that type. Accept free-text (functional — user types the name `resolve_connector` matches) or implement a real connector dropdown (fetch + Select)? [nowing_web/.../builder/task-item.tsx] (MEDIUM)

- [x] [Review][Patch] (FIXED) `resolve_connector` raises on `auth_expired` **before** applying the type/`connector_name` filter, so an unrelated expired same-type connector aborts a write-back to a healthy, explicitly-named connector. Check `auth_expired` only on the selected match. [nowing_backend/app/automations/actions/builtin/write_back/shared.py:110-119] (MEDIUM)
- [x] [Review][Patch] (FIXED) `resolve_jira_cloud_id` returns the literal string `"None"` when the first Atlassian resource lacks both `id` and `cloudId` (`str(first.get("id") or first.get("cloudId"))`). Guard and raise a clear error. [shared.py:430] (MEDIUM)
- [x] [Review][Patch] (FIXED) Update requested (`object_id` set) but only a create tool is advertised → `build_tool_args` notion `"pages"` branch (and general fallthrough) silently **creates a duplicate** instead of updating. Raise a clear "update unsupported for {provider}" error. [shared.py:264-269 + select_write_tool] (MEDIUM)
- [x] [Review][Patch] (FIXED) `builderTaskSchema.refine` only checks `writeBackParams !== null`, not that `writeBackParams.provider` matches `action` → a mismatched provider payload can reach the backend. Enforce action↔provider. [nowing_web/lib/automations/builder-schema.ts:109] (LOW)

- [x] [Review][Defer] `parse_mcp_result` assumes JSON; MCP tools that return plain-text success land as `{"text": ...}` → `object_id`/`url` become `""`, breaking `steps.<id>.url` chaining and update-by-id (false success). Needs real MCP payload samples per provider for robust extraction. [shared.py:332-380] (MEDIUM) — deferred
- [x] [Review][Defer] AC-2: OAuth token-**decryption** failure does not surface a clear re-authenticate message on the failing run (only the persisted `auth_expired` flag catches it on a later run); `select_write_tool` raises the generic "No MCP write tool found". Root cause is in `load_mcp_tools` (outside this diff). (MEDIUM) — deferred, pre-existing infra
- [x] [Review][Defer] Non-idempotent create on retry/timeout: `with_retries` re-invokes the handler → duplicate objects. Broader runtime concern shared by all actions, not write-back-specific. (MEDIUM) — deferred
- [x] [Review][Defer] `select_write_tool` single-tool fallback returns the lone connector tool even if it is read-only. Prod-low risk (would error at invocation); tighten to write-tool names later. [shared.py:210-214] (LOW) — deferred
- [x] [Review][Defer] Full `raw` MCP payload is persisted verbatim in the step result (`raw` key) — potential over-exposure / unbounded size. [shared.py:378] (LOW) — deferred

_Dismissed (note): AC-6 few-shot references `{{ steps.summarize.final_message }}` not the AC-literal `{{ steps.<step_id>.url }}` — the implementation is semantically **correct** (an `agent_task` step exposes `final_message`, not `url`) and matches the story's own Dev Notes; the AC-6 wording is the inconsistency and should be corrected, not the code. Also: unused-ish `MCP_SERVICES` import and `WriteBackAction` type name including `agent_task` (naming nits)._

### Agent Model Used Version

_TBD by implementer_

### Debug Log References

_TBD by implementer_

### Completion Notes List

_TBD by implementer_

### File List

_TBD by implementer (capture all created/modified files before code-review)_
