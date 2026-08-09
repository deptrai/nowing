# Story 18.4: `AgentConfig` Prompt Injection

Status: done

Baseline commit: 1e5f46b86

## Story

As a chat system,
I want to inject agent-specific system instructions into the chat prompt,
so that each vertical client gets a specialized agent experience.

## Acceptance Criteria

1. **Given** a chat request with `agent_id`, **When** the chat flow starts, **Then** `AgentConfig.system_instructions` is prepended to the default system prompt.
2. **Given** an `agent_id` with `enabled_tools`, **When** the chat agent selects tools, **Then** only tools in the allowlist are available.
3. **Given** no `agent_id`, **When** processed, **Then** the default Nowing chat agent is used (backward compatible).

## Tasks / Subtasks

- [ ] Inject `system_instructions` into prompt (AC: #1)
  - [ ] Update `app/tasks/chat/streaming/flows/new_chat/prompt.py` (or equivalent prompt assembler) to accept an `AgentConfig` parameter
  - [ ] Prepend `AgentConfig.system_instructions` after the base system prompt and before the user context
  - [ ] Add length guard (e.g., max 8,000 chars) and strip/escape any secret-like placeholders
  - [ ] Log which `agent_id`/`client_id` instructions were used for audit; do not store raw instructions in message content
- [ ] Tool allowlist filtering (AC: #2)
  - [ ] Update `app/agents/chat/multi_agent_chat/main_agent/tools/registry.py` to expose `filter_tools_by_agent(tools, agent_config)`
  - [ ] Load the full tool catalog, then remove tools in `disabled_tools` and keep only `enabled_tools` when an allowlist is provided
  - [ ] When `enabled_tools` is empty, treat as no restriction (or fail closed per `AD-30` — decide in kickoff); at minimum log the effective tool set
  - [ ] Ensure tool filtering is applied in the chat turn runtime before the LLM tool-choice call
  - [ ] Apply the same filter to agent tool introspection (`/agent/tools`, `app/routes/new_chat_routes.py:1668-1690`)
- [ ] Backward-compatible default agent (AC: #3)
  - [ ] When `agent_id` is `None` and the request is not from a vertical client, use the existing default Nowing prompt and full workspace-allowed tool set
  - [ ] When `agent_id` is `None` but a PAT scope has a `client_id`, use the default agent for that `client_id` if exactly one active agent exists; otherwise fail with 400 (ambiguous)
- [ ] No raw secret interpolation (security)
  - [ ] Ban `{`/`}` Jinja-like markers in `system_instructions` unless explicitly tested
  - [ ] Treat `platform_metadata` and `external_metadata` as untrusted data; never render them inside `system_instructions`
- [ ] Tests
  - [ ] Unit test prompt builder with and without `AgentConfig`
  - [ ] Unit test tool registry filter with allowlist and denylist
  - [ ] Integration test `POST /new_chat` with `agent_id` returns response using specialized system prompt
  - [ ] Integration test `POST /new_chat` with `agent_id` cannot call a disabled tool
  - [ ] Regression test default chat without `agent_id` is unchanged

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-30` (`ARCHITECTURE-SPINE.md:739-748`) — `AgentConfig.system_instructions` are trusted admin content, but still subject to length limits, audit, and no raw secret interpolation from client metadata; tool allowlists explicit; new connectors not auto-enabled.
  - `AD-29` (`ARCHITECTURE-SPINE.md:727-737`) — `external_metadata` and `platform_metadata` are untrusted and additive; never used in authz or prompt secret interpolation.
  - `epic-18-pat-scope-rls-threat-model.md §5 TM8` — prompt injection via instruction override: system instructions admin-only, length limits, no secret interpolation.
  - `epic-18-pat-scope-rls-threat-model.md §5 TM6` — prompt injection → tool abuse: tool allowlist enforced in runtime not prompt; deny-by-default new connectors.

- Source tree components to touch
  - `nowing_backend/app/tasks/chat/streaming/flows/new_chat/prompt.py` — prompt assembly
  - `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` — orchestrates agent config load and prompt build
  - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py` — tool catalog and filter
  - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/agent.py` — main agent loop
  - `nowing_backend/app/routes/new_chat_routes.py:1668-1690` — `/agent/tools` introspection
  - `nowing_backend/app/services/agent_registry.py` (Story 18.3) — `AgentConfig` lookup
  - `nowing_backend/app/observability/metrics.py` — agent prompt/tool filter telemetry

- Testing standards summary
  - Unit tests in `tests/unit/agents/chat/test_tool_filter.py` and `tests/unit/tasks/chat/test_prompt.py`
  - Integration tests in `tests/integration/routes/test_new_chat_routes.py` and `tests/integration/api/test_agent_chat_pat_matrix.py`
  - Assert specialized system instructions appear in the final prompt sent to the LLM
  - Assert a disabled tool is not present in the tool list passed to the model

### Project Structure Notes

- Alignment with unified project structure
  - Prompt injection stays in the existing streaming flow; no new abstraction.
  - Tool filtering is a function in the existing tool registry, not a new registry.

- Detected conflicts or variances
  - `main_agent` currently builds its tool list from workspace settings + user trust + MCP; `AgentConfig` adds another filter layer. The order must be: full catalog → `AgentConfig` allow/deny → workspace permissions → user trust.
  - System prompt concatenation must not exceed model context; consider truncating instructions if the prompt grows too large.
  - `enabled_tools` may list tool names that no longer exist; validation in Story 18.3 should catch this at write time, but runtime should ignore missing names with a warning.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.4]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-29, AD-30]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §5 TM6, TM8]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-agent-registry.md` §2B System instructions preview]
- [Source: `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py`]
- [Source: `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py`]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List