---
title: 'Story 6.5: Memory-Driven Automations'
description: ''
createdAt: '2026-07-28T10:28:33.229Z'
updatedAt: '2026-07-28T15:17:33.532Z'
tags:
  - bmad
  - bmad-source-bmad-output-implementation-artifacts-6-5-memory-driven-automations-md
---

---
story_key: 6-5-memory-driven-automations
status: done
---

# Story 6.5: Memory-Driven Automations

Status: done

**Story ID:** 6.5
**Epic:** Epic 6 — Automations
**Priority:** P2 (post-MVP per PRD)
**Source artifacts:**
- PRD: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (FR-35 Memory-Driven Automations — marked `[GAP]`)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Epic 6, Story 6.5)
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (automations + AD-13 research thread)
- Previous stories: `6-4-direct-write-back-actions-new-gap.md` (action pattern), `4-6-research-continuity.md` (continue-research backend), `4-5-agent-memory-tools-via-mcp.md` (memory writes)

---

## Story

As a workspace member,
I want an automation to fire when workspace memory changes (e.g. a new competitor fact) and to be able to continue a saved research thread as an action,
so that research keeps itself up to date without me manually re-running it.

## Acceptance Criteria

Derived from **FR-35**. Everything below is a `[GAP]` — the automation trigger/action registries, the event bus, and the research-continuity backend already exist and are reused.

### AC-1: `memory.changed` event is emitted on memory create/update
**Given** a memory is created or updated in a workspace (via `MemoryRepository.create_memory` / `update_memory` — MCP `nowing_remember`/`nowing_update_fact`, REST, auto-extraction, or markdown bridge)
**When** the write commits
**Then** a `memory.changed` event is published on the event bus with payload `{memory_id, workspace_id, type, tags, change: "created"|"updated", source_type}`
**And** the publish is best-effort (a bus failure must not fail the memory write).

### AC-2: `memory_change` trigger type fires automations
**Given** a `memory_change` trigger is registered and enabled on an automation, optionally filtered by memory `type` and/or `tags`
**When** a `memory.changed` event matches the trigger's workspace and filter
**Then** the automation starts a run (via the existing dispatch/`launch_run` path), with the event payload exposed as runtime inputs for steps.

### AC-3: `continue_research` action returns a thread's memories + citations
**Given** an automation step with `action: "continue_research"` and params `{research_thread_id, top_k?}`
**When** the step runs
**Then** it returns a JSON-serializable dict `{research_thread_id, memories: [...], citations: [...]}` (reusing the Story 4.6 recall + citation aggregation — no divergent ranking)
**And** the result is bound to `steps.<step_id>` (or `output_as`) so later steps can reference `{{ steps.continue.memories }}` / `.citations`
**And** a non-existent thread fails the step with a clear error (no implicit creation, per Story 4.6).

### AC-4: `AutomationRun.research_thread_id` links a run to its thread
**Given** a run is driven by research continuity (a `continue_research` action, or a `memory_change` trigger carrying a thread)
**When** the run is created/executed
**Then** `automation_runs.research_thread_id` (new nullable FK → `research_threads`, `ondelete=SET NULL`) is populated
**And** the column is added by an Alembic migration (head 179 → 180) plus the ORM model.

### AC-5: No self-triggering loop
**Given** a `memory_change`-triggered automation whose steps write memory (e.g. an `agent_task` calling `nowing_remember`)
**When** that write emits its own `memory.changed` event
**Then** it must NOT infinitely re-fire the same automation — memory writes originating from an automation run are excluded from (or filtered out by) `memory_change` triggers (see Risks/Decision for the mechanism).

---

## Technical Context

### Already [BUILT] — reuse, do NOT re-implement

- **Event bus** — `app/event_bus/`: `bus.publish(event_type, payload, workspace_id=...)` (`bus.py`), `EventType` + `EventCatalog.register` (`catalog.py`), event modules under `events/` (example: `events/document_entered_folder.py`). Producers `await bus.publish(...)`.
- **Trigger registry + `event` trigger** — `app/automations/triggers/`: `TriggerDefinition(type, description, params_model)` (`types.py`), `register_trigger` (`store.py`), `builtin/__init__.py` imports each type. The `event` trigger (`builtin/event/{params,source,selector,match,inputs,definition}.py`) already: subscribes to the bus (`source.on_event` → enqueues `automation_event_select`), matches enabled triggers by `params["event_type"]` + `filter` (`selector._eligible` + `match.trigger_matches_event`), and starts a run per match via `dispatch.launch_run` with `event_runtime_inputs(event)`.
- **Action registry + patterns** — `app/automations/actions/`: `ActionDefinition` (`types.py`), `register_action`/`get_action` (`store.py`), packages `builtin/agent_task/` and `builtin/write_back_*/` (`params.py`, `factory.py`, `invoke.py`, `definition.py`, `__init__.py`), imported in `builtin/__init__.py`. Runtime: `runtime/step.py` (`get_action` + retries), `runtime/executor.py:71-72` (binds result to `steps.<output_as|step_id>`), `templating/context.py` (`steps` namespace).
- **Research-continuity backend (Story 4.6)** — `app/services/memory/thread_citations.py::collect_thread_citations`, `MemoryHybridSearch` scoped by `research_thread_id`, and `GET /workspaces/{id}/research-threads/{id}/context` (`routes/research_threads_routes.py`). The `continue_research` action reuses this recall + citation logic directly (in-process), NOT via HTTP.
- **Memory writes** — `app/services/memory/repository.py`: `create_memory` / `update_memory` are the single choke points for all memory mutations (emit the event here).

### The [GAP] this story closes
1. `memory.changed` event type + emission on memory writes (AC-1).
2. `memory_change` trigger type + selector (AC-2).
3. `continue_research` action (AC-3).
4. `AutomationRun.research_thread_id` column + migration (AC-4).
5. A loop guard so memory-writing automations don't self-trigger (AC-5).

---

## Implementation Plan (design)

### Step 1 — `memory.changed` event
- Register `EventType(type="memory.changed", payload_model=MemoryChangedPayload)` in `app/event_bus/events/memory_changed.py` (payload: `memory_id, workspace_id, type, tags, change, source_type`).
- Emit from `MemoryRepository.create_memory` and `update_memory` **after commit** (respect the `commit` flag added in Story 4.5 — emit only once the row is durable; if `commit=False` batch mode, emit after the caller's final commit — simplest: emit inside the methods guarded by `if commit:` and add an explicit emit in the batch caller, OR return the change descriptors and let the service publish). Best-effort: wrap `bus.publish` in try/except + log.

### Step 2 — `memory_change` trigger
- `app/automations/triggers/builtin/memory_change/`: `params.py` (`MemoryChangeTriggerParams`: optional `memory_type: str|None`, `tags: list[str]`), `definition.py` (`register_trigger`), and either a `selector.py` modeled on `builtin/event/selector.py` filtering `memory.changed` events, or (DECISION) reuse the generic `event` trigger. Register in `triggers/builtin/__init__.py`.
- Subscribe the selector to `memory.changed` on the bus the same way `event/source.py` does.

### Step 3 — `continue_research` action
- `app/automations/actions/builtin/continue_research/`: `params.py` (`ContinueResearchActionParams`: `research_thread_id: int`, `top_k: int = 5`, `extra="forbid"`), `factory.py`/`invoke.py`/`definition.py`/`__init__.py` mirroring `agent_task`.
- `invoke` loads the `ResearchThread` (404-equivalent error if missing/not in workspace — reuse the same load+guard as `research_threads_routes`), runs `MemoryHybridSearch` scoped by `research_thread_id` and `collect_thread_citations`, returns `{research_thread_id, memories, citations}`.
- Register in `actions/builtin/__init__.py`.

### Step 4 — `AutomationRun.research_thread_id`
- Alembic migration `180_add_automation_run_research_thread.py`: add nullable `research_thread_id` FK → `research_threads(id)` `ondelete=SET NULL`, indexed.
- Add the column + relationship to `app/automations/persistence/models/run.py`.
- Populate it in `dispatch.launch_run` / the executor when the trigger or a `continue_research` step carries a `research_thread_id`.

### Step 5 — Loop guard (AC-5)
- Resolve the DECISION below; implement the chosen mechanism (recommended: tag automation-origin memory writes and exclude them from `memory.changed` emission or from `memory_change` matching).

### Step 6 — Verification
- `uv run --active python -m pytest nowing_backend/tests/unit/automations nowing_backend/tests/integration/automations nowing_backend/tests/integration/memory -q`
- Registration canary: `memory_change` trigger in `all_triggers()`, `continue_research` in `get_action()` after `import app.automations`.
- `alembic upgrade head` (single head = 180).
- `uv run ruff check` on changed files.

---

## Tasks / Subtasks

- [ ] Event: `MemoryChangedPayload` + register `memory.changed` EventType; emit from `create_memory`/`update_memory` (best-effort, after commit). (AC-1)
- [ ] Trigger: `memory_change` package (params + definition + selector/subscription); register in `triggers/builtin/__init__.py`. (AC-2)
- [ ] Action: `continue_research` package (params/factory/invoke/definition); register in `actions/builtin/__init__.py`; reuse `MemoryHybridSearch` + `collect_thread_citations`; clear error on missing thread. (AC-3)
- [ ] Migration `180_...` + `AutomationRun.research_thread_id` model column + populate on run creation. (AC-4)
- [ ] Loop guard per the resolved decision. (AC-5)
- [ ] Tests: trigger fires on matching `memory.changed` (and not on filtered-out / other-workspace / automation-origin events); action returns memories+citations and errors on missing thread; run row carries `research_thread_id`; registration canaries; migration upgrade/downgrade.
- [ ] Verification: pytest + alembic head + ruff.

## Dev Notes

### Existing patterns to mirror
- **Trigger:** copy the shape of `builtin/event/` (params/source/selector/match/inputs/definition). The generic `event` selector already does workspace + `event_type` + filter matching and `launch_run`; `memory_change` is a memory-typed specialization.
- **Action:** copy `builtin/agent_task/` or any `builtin/write_back_*/` package layout exactly (self-registering `__init__.py` importing `definition`).
- **Recall reuse:** do NOT re-implement recall/citations — call the same `MemoryHybridSearch(session).search(research_thread_id=...)` and `collect_thread_citations(session, thread)` used by `research_threads_routes.py` (Story 4.6).

### Read before modifying
- `app/services/memory/repository.py` (`create_memory`/`update_memory` — the emit points; note the `commit` flag from Story 4.5).
- `app/automations/triggers/builtin/event/{selector,source,match}.py` and `app/event_bus/bus.py` (publish signature, workspace scoping).
- `app/automations/persistence/models/run.py` and `app/automations/dispatch.py` (`launch_run`) for wiring `research_thread_id`.

## Risks & Open Decisions

- **[DECISION] Dedicated `memory_change` trigger vs reuse generic `event` trigger.** FR-35 names a `memory_change` trigger type. The generic `event` trigger already matches arbitrary `event_type` + filter, so a user could subscribe to `event_type="memory.changed"` today. Choose: (a) a thin dedicated `memory_change` trigger with memory-friendly params (`memory_type`, `tags`) that internally maps to `memory.changed` matching — better UX, matches FR-35 wording; or (b) document `event` + `memory.changed` and skip a new trigger type. **Recommend (a).**
- **[DECISION / AC-5] Loop-guard mechanism.** Options: (1) do not emit `memory.changed` for writes whose `source_type`/origin marks them automation-generated; (2) stamp the run/event with an origin and have `memory_change` matching drop automation-origin events; (3) a per-automation cooldown/depth cap. **Recommend (1)+(2)** (origin tagging: skip emission for automation-origin writes) — simplest and robust. Requires threading an "origin" flag into the memory write path used by automation actions.
- **Event timing vs `commit=False` batch writes (Story 4.5).** Auto-extraction commits many facts in one transaction; ensure exactly-one event per durable memory (emit after the final commit, not per flush).
- **Scope guard:** recall quality/eval gate (NFR-8) remains out of scope; this story wires triggers/actions, not ranking quality.

## Guardrails / Anti-patterns
- Reuse `MemoryHybridSearch` + `collect_thread_citations` (no divergent recall) and the existing `launch_run`/event infra (no parallel dispatch path).
- Memory-write event emission must be best-effort — never fail a memory write because the bus is down.
- `continue_research` must not create a `ResearchThread` implicitly (consistent with Story 4.6 AC-2).
- Prevent self-triggering loops (AC-5) — this is a hard requirement, not optional.
- Self-registering packages only (import side-effect); keep `all_triggers()`/`get_action()` canaries green.

## References
- FR-35 — `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:352-363`
- Event bus — `nowing_backend/app/event_bus/{bus.py,catalog.py,__init__.py,events/document_entered_folder.py}`
- Trigger registry — `app/automations/triggers/{types.py,store.py,builtin/__init__.py}`
- `event` trigger — `app/automations/triggers/builtin/event/{params.py,source.py,selector.py,match.py,inputs.py,definition.py}`
- Action registry + patterns — `app/automations/actions/{types.py,store.py,builtin/__init__.py,builtin/agent_task/,builtin/write_back/}`
- Runtime binding — `app/automations/runtime/{step.py,executor.py}`, `app/automations/templating/context.py`
- Dispatch — `app/automations/dispatch.py` (`launch_run`)
- AutomationRun model — `app/automations/persistence/models/run.py` (no `research_thread_id` today)
- Memory writes (emit points) — `app/services/memory/repository.py` (`create_memory`, `update_memory`)
- Research-continuity recall + citations (reuse) — `app/services/memory/thread_citations.py`, `app/services/memory/search.py`, `app/routes/research_threads_routes.py`
- `ResearchThread` model — `app/db.py:1968-2015`

## Dev Agent Record

### Review Findings — Code Review 2026-07-25

Three-layer review of the staged 6.5 diff. **AC-2, AC-3 genuinely Met. AC-1, AC-4 Partial. AC-5 (hard guardrail) NOT met end-to-end.** Tests pass but several assert primitives, masking the gaps.

- [x] [Review][Decision] **AC-5 loop guard not wired end-to-end (BLOCKER, hard requirement).** RESOLVED via approach (a) — thread automation origin end-to-end. Investigated the reachable write path (below): only the **in-process** native `update_memory` tool is reachable from an `agent_task` (external `nowing_mcp`/HTTP is NOT wired into the automation agent). Added a `current_automation_run_id` contextvar (`app/automations/runtime/origin.py`) stamped by the executor for the whole run and read by `create_memory`/`update_memory` (no hand-passed kwarg needed); the explicit `automation_run_id` kwarg still works. `MemoryChangedPayload` now carries `automation_run_id` (mechanism-2 reachable); repo emit-skip + selector drop both use truthiness (0 == no origin). REST `create/update` read an `X-Automation-Run-Id` header for the (currently unreachable) cross-process path. End-to-end test added. [repository.py, runtime/origin.py, executor.py, memory_change/selector.py, event payload, memories_routes.py]
- [x] [Review][Patch] **AC-1: auto-extraction (`commit=False`) never emits `memory.changed`** → RESOLVED. `commit=False` writes now buffer their payload in the repo; `extraction.py` calls `flush_pending_memory_changed()` after its single batch commit, emitting exactly once per durable memory (idempotency guard prevents re-emit on redelivery). [services/memory/extraction.py, repository.py]
- [x] [Review][Patch] **AC-4: `research_thread_id` can't reach a memory-driven run** → RESOLVED. Added `research_thread_id` to `MemoryChangedPayload` (flattened into run inputs by `event_runtime_inputs`) so `launch` populates `run.research_thread_id`; and the executor now populates the run from a `continue_research` step's literal param. [event payload, launch.py, executor.py]
- [x] [Review][Patch] No-op update still emits `change="updated"` → RESOLVED. `update_memory` and the `create_memory` duplicate-overwrite branch gate emission on `content_changed`. [repository.py]
- [x] [Review][Patch] `memory_change` selector doesn't filter automation status → RESOLVED. `_eligible` joins `Automation` and filters `status == ACTIVE`, so paused/archived automations are never selected (no `DispatchError` spam). [memory_change/selector.py]
- [x] [Review][Patch] `launch._research_thread_id_from_inputs` coerces int with no existence/workspace check → RESOLVED. Replaced with async `resolve_research_thread_id` that validates the id EXISTS and belongs to the run's workspace before setting it; a bad/cross-workspace id is dropped silently. [dispatch/launch.py]
- [x] [Review][Patch] Tests assert primitives → RESOLVED. Added an end-to-end AC-5 test (real executor + real `agent_task` action + real repository; only the LLM agent faked) asserting a memory-writing `memory_change` automation emits no `memory.changed` for its own write, plus a control write that does emit. Added tests for the contextvar path, no-op-update gate, payload `research_thread_id`, selector status filter, launch validation, and extraction emission. [tests]

- [x] [Review][Defer] deletions never emit `memory.changed`; Python-side type/tags filter after loading workspace triggers; enum `ADD VALUE` assumes PG12+; migration downgrade drops data. — deferred, low impact

### Review Fixes — 2026-07-25 (dev-story)

**Investigated write path (AC-5).** Traced the memory-write paths reachable from an automation run's `agent_task` action (`run_agent_task` → `create_multi_agent_chat_deep_agent(thread_visibility=PRIVATE, auth=AuthContext.system(source="automation"))` → `agent.ainvoke`):
- **(i) IN-PROCESS native tool — REACHABLE.** The agent's `update_memory` tool → `services/memory/service.py::save_memory` → `MemoryRepository.create_memory`, all `async`/awaited inline in one asyncio task (no thread hop). Under PRIVATE visibility it resolves to the **USER**-scoped tool (writes `workspace_id=None`, which never emits), but the write is still in-process, so a contextvar set by the executor reaches it regardless of scope or which session the tool opens.
- **(ii) Auto-extraction — NOT reachable from `agent_task`.** `agent_task` bypasses `stream_new_chat`/`assistant_finalize`, never persists `NewChatMessage`, and never enqueues `extract_memory_after_chat_turn`. (FIX 2 still makes extraction emit for its real trigger — the chat streaming flow.)
- **(iii) External `nowing_mcp` over HTTP — NOT reachable from `agent_task`.** The in-process agent only loads MCP tools from workspace `SearchSourceConnector` rows (`load_mcp_tools_by_connector`); `nowing_mcp` is a separate process that calls the backend REST API with a user PAT. An automation run carries no PAT and wires no nowing MCP client, so `nowing_remember`/`nowing_update_fact` are unreachable.

**Threading mechanism implemented.**
- **Mechanism 1 (primary, in-process):** `app/automations/runtime/origin.py::current_automation_run_id` contextvar; `executor.execute_run` wraps the whole run in `automation_run_origin(run.id)`. `MemoryRepository._emit_memory_changed` resolves the origin from the explicit kwarg or (lazily, to avoid an import cycle) the contextvar, and **skips emission** for any automation-origin write. ContextVars propagate across `await` and into child tasks, so any in-process write inside the run is covered even if it opens its own session.
- **Mechanism 1 (cross-process, defense-in-depth):** REST `POST /workspaces/{id}/memories` and `PATCH /memories/{id}` read an optional `X-Automation-Run-Id` header → `create_memory/update_memory(automation_run_id=...)`. No automation path sets it today (external MCP is unreachable, per above), so it is dormant but correct if such wiring is ever added.
- **Mechanism 2 (backstop):** `MemoryChangedPayload` now carries `automation_run_id`; the `memory_change` selector drops any event carrying a truthy `automation_run_id`. Repo emit-skip and selector drop both use truthiness so `0` (never a valid serial PK) is treated as "no origin" consistently.
- **AC-5 closure:** the reachable in-process path is fully closed by mechanism 1 (contextvar). The external-MCP path is documented as unreachable from an automation `agent_task`; it is nonetheless covered by the header plumbing (if wired) and the mechanism-2 selector drop. No path is left where a memory-writing automation can re-fire itself.

**Files changed (this review pass).**
- Product:
  - `nowing_backend/app/event_bus/events/memory_changed.py` — `MemoryChangedPayload` gains `research_thread_id` + `automation_run_id`; docstring updated.
  - `nowing_backend/app/automations/runtime/origin.py` — NEW: `current_automation_run_id` contextvar + `automation_run_origin` CM + `get_current_automation_run_id`.
  - `nowing_backend/app/automations/runtime/__init__.py` — export the origin helpers.
  - `nowing_backend/app/automations/runtime/executor.py` — wrap run in `automation_run_origin(run.id)`; populate `run.research_thread_id` from a `continue_research` step param (validated).
  - `nowing_backend/app/services/memory/repository.py` — contextvar-aware origin resolution; truthiness-aligned emit-skip; `commit=False` payload buffer + `flush_pending_memory_changed`; payload carries `research_thread_id`; no-op-update emission gated on `content_changed` (both `update_memory` and the `create_memory` duplicate-overwrite branch).
  - `nowing_backend/app/services/memory/extraction.py` — flush buffered `memory.changed` after the batch commit.
  - `nowing_backend/app/automations/triggers/builtin/memory_change/selector.py` — `_eligible` filters `Automation.status == ACTIVE`; origin-drop uses truthiness.
  - `nowing_backend/app/automations/dispatch/launch.py` — `resolve_research_thread_id` validates existence + workspace (replaces the unchecked int coercion).
  - `nowing_backend/app/automations/dispatch/__init__.py` — export `resolve_research_thread_id`.
  - `nowing_backend/app/routes/memories_routes.py` — read `X-Automation-Run-Id` header on create/update.
- Tests:
  - `nowing_backend/tests/integration/automations/test_memory_change_trigger.py` — added the end-to-end AC-5 no-refire test, selector status-filter test, event-payload/continue-research-step research_thread_id linkage tests, and launch validation (unknown + cross-workspace) tests; `_make_automation_with_trigger` now accepts `plan`/`status`.
  - `nowing_backend/tests/integration/memory/test_memory_changed_event.py` — added no-op-update-no-emit, contextvar-origin-no-emit (no kwarg), and payload-carries-research_thread_id tests.
  - `nowing_backend/tests/integration/memory/test_memory_changed_extraction.py` — NEW: auto-extraction emits after commit + exactly-once on redelivery.

**Verification (all `uv run --active`, run sequentially).**
- `pytest tests/unit/automations tests/integration/automations tests/integration/memory -q` → **243 passed, 11 skipped** (the 11 skips are unrelated Story 8.7 red-phase scaffolds in `test_auto_extract_spend_cap.py`), 0 failed. (Was 231 passed pre-fix; +12 new tests.)
- Regression: `pytest tests/integration/memory/test_research_continuity.py tests/integration/memory/test_memory_extraction.py tests/integration/workspaces/test_memory_routes.py tests/unit/event_bus -q` → **62 passed**.
- Registration canaries: `all_triggers()` keys == `{event, memory_change, schedule}`; `get_action('continue_research')` and `get_action('agent_task')` present; `TriggerType.MEMORY_CHANGE == 'memory_change'`; `catalog.get('memory.changed')` present; `MemoryChangedPayload` accepts `research_thread_id` + `automation_run_id`.
- Alembic: `alembic heads` → single head **180**; full `alembic upgrade head` on a scratch Postgres → `alembic current` = `180`; `180 → 179 → 180` downgrade/upgrade round-trip verified.
- Ruff: `ruff check` **clean** on every changed product and test file (`test_memory_extraction.py` was left untouched — the new extraction-emit tests live in a dedicated `test_memory_changed_extraction.py` to avoid entangling its pre-existing lint debt).

### Agent Model Used

Kiro BMAD dev agent (dev-story workflow).

### Debug Log References

- `uv run --active python -m pytest tests/unit/automations tests/integration/automations tests/integration/memory -q` → **231 passed, 11 skipped** (the 11 skips are unrelated Story 8.7 red-phase scaffolds in `test_auto_extract_spend_cap.py`), 0 failed.
- New-file focus run (3 files) → **15 passed**; unit automations → **195 passed**; unit event_bus → **33 passed**.
- Registration canary: `all_triggers() == {event, memory_change, schedule}`, `get_action('continue_research')` present, `TriggerType.MEMORY_CHANGE == 'memory_change'`, `catalog.get('memory.changed')` present.
- Alembic: `alembic heads` → single head `180`. Migration exercised end-to-end on a scratch Postgres — `179 → 180` (upgrade) adds nullable `research_thread_id` + FK `automation_runs_research_thread_id_fkey` (`ON DELETE SET NULL`, `confdeltype='n'`) + index + enum value `memory_change`; `180 → 179` (downgrade) drops them cleanly; round-trip verified.
- Ruff: `ruff check` clean on every created/modified file.

### Completion Notes List

- **AC-1 `memory.changed` event** — new `app/event_bus/events/memory_changed.py` (`MemoryChangedPayload{memory_id, workspace_id, type, tags, change, source_type}`) registered in the catalog. Emitted best-effort from `MemoryRepository.create_memory` (`change="created"`) and `update_memory` (`change="updated"`) via a shared `_emit_memory_changed` helper. Emission is guarded to fire exactly once per durable memory: only when `commit=True` (batch `commit=False` extraction does not emit per-flush — left for the caller/`automate`), only for workspace-scoped memories, and never on automation-origin writes. A bus failure is swallowed + logged so it can never fail the write.
- **AC-2 `memory_change` trigger** — DECISION (a) implemented: a dedicated `memory_change` trigger type (FR-35), not a reuse of the generic `event` trigger. New self-registering package `app/automations/triggers/builtin/memory_change/` (`params` with optional `memory_type` + `tags`, `match` predicate, `source` bus subscriber, `selector._eligible` + celery task, `definition`) modeled 1:1 on `builtin/event/`. `TriggerType.MEMORY_CHANGE = "memory_change"` added. The selector additionally scopes by the automation's **workspace** (join to `Automation`), which the generic `event` selector does not enforce.
- **AC-3 `continue_research` action** — new self-registering package `app/automations/actions/builtin/continue_research/` (`params{research_thread_id, top_k=5}`, `factory`, `invoke`, `definition`) modeled on `write_back_notion`. `invoke` reuses Story 4.6 **in-process** (no HTTP): loads the `ResearchThread` by id **and** workspace (clear error, no implicit creation on miss), recalls via `MemoryHybridSearch(...).search(research_thread_id=...)` and aggregates citations via `collect_thread_citations` — identical to `research_threads_routes.py`, so recall never diverges. Returns `{research_thread_id, memories, citations}` (JSON-serializable) bound to `steps.<id>`.
- **AC-4 run ↔ thread link** — `AutomationRun.research_thread_id` column + relationship added; `dispatch.launch_run` populates it from the resolved run inputs (a `continue_research` step / research-driven `memory_change` trigger threads it via `static_inputs`/`runtime_inputs`). Migration `180` (down_revision `179`) adds the nullable FK → `research_threads` (`ON DELETE SET NULL`, indexed) plus the `memory_change` enum value (mirroring migration 147's safe `DO`-block pattern). Constraint/index names match `create_all` defaults so bootstrapped and migrated DBs are identical.
- **AC-5 loop guard** — DECISION: origin tagging via a new `automation_run_id` kwarg on `create_memory`/`update_memory`, with **both** recommended mechanisms implemented: (1) the repository **skips emission** for automation-origin writes; (2) the `memory_change` selector **drops** any `memory.changed` event carrying an `automation_run_id`. Together a memory-writing automation cannot re-fire its own trigger. UPDATE (Review Fixes 2026-07-25): end-to-end threading is now COMPLETE via approach (a) — a `current_automation_run_id` contextvar stamped by the run executor and read by the repository closes the reachable in-process write path without a hand-passed kwarg; the external MCP-over-HTTP path was investigated and found NOT reachable from an `agent_task` (no PAT / not wired), and is additionally covered by the `X-Automation-Run-Id` REST header + the mechanism-2 selector drop. See "Review Fixes — 2026-07-25" for the full write-path investigation, mechanism, and verification.
- **Test adjustments** — (1) removed the `@pytest.mark.skip` red-phase markers from all 8 Story-6.5 scaffolds (30 markers); no other scaffold change was needed — the implementation matched every documented green-phase assumption (`automation_run_id` kwarg, `TriggerType.MEMORY_CHANGE`, `_eligible(session, *, event)`, `trigger_matches_event(params, event)`, `build_handler(ctx)→handle(params)→dict`, `MemorySearchHit`-shaped memories). (2) Updated the pre-existing enum canary `tests/unit/automations/test_persistence_enums.py::test_trigger_type_keeps_manual_member_even_though_unregistered` to include the new `memory_change` member (it pins the exact `TriggerType` member set).

### File List

**Created (product):**
- `nowing_backend/app/event_bus/events/memory_changed.py`
- `nowing_backend/app/automations/triggers/builtin/memory_change/__init__.py`
- `nowing_backend/app/automations/triggers/builtin/memory_change/params.py`
- `nowing_backend/app/automations/triggers/builtin/memory_change/match.py`
- `nowing_backend/app/automations/triggers/builtin/memory_change/source.py`
- `nowing_backend/app/automations/triggers/builtin/memory_change/selector.py`
- `nowing_backend/app/automations/triggers/builtin/memory_change/definition.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/__init__.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/params.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/factory.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/invoke.py`
- `nowing_backend/app/automations/actions/builtin/continue_research/definition.py`
- `nowing_backend/alembic/versions/180_add_automation_run_research_thread.py`

**Modified (product):**
- `nowing_backend/app/event_bus/events/__init__.py` (register `memory_changed`)
- `nowing_backend/app/services/memory/repository.py` (`automation_run_id` kwarg + `_emit_memory_changed` on create/update)
- `nowing_backend/app/automations/persistence/enums/trigger_type.py` (`MEMORY_CHANGE` member)
- `nowing_backend/app/automations/triggers/builtin/__init__.py` (import `memory_change`)
- `nowing_backend/app/automations/actions/builtin/__init__.py` (import `continue_research`)
- `nowing_backend/app/automations/persistence/models/run.py` (`research_thread_id` column + relationship)
- `nowing_backend/app/automations/dispatch/launch.py` (populate `research_thread_id` from inputs)
- `nowing_backend/app/celery_app.py` (include `memory_change.selector` task)

**Modified (tests):**
- `nowing_backend/tests/unit/automations/triggers/builtin/memory_change/test_params.py` (un-skip)
- `nowing_backend/tests/unit/automations/triggers/builtin/memory_change/test_definition.py` (un-skip)
- `nowing_backend/tests/unit/automations/triggers/builtin/memory_change/test_match.py` (un-skip)
- `nowing_backend/tests/unit/automations/actions/builtin/continue_research/test_params.py` (un-skip)
- `nowing_backend/tests/unit/automations/actions/builtin/continue_research/test_definition.py` (un-skip)
- `nowing_backend/tests/integration/memory/test_memory_changed_event.py` (un-skip)
- `nowing_backend/tests/integration/automations/test_memory_change_trigger.py` (un-skip)
- `nowing_backend/tests/integration/automations/actions/builtin/continue_research/test_continue_research.py` (un-skip)
- `nowing_backend/tests/unit/automations/test_persistence_enums.py` (add `memory_change` to the pinned `TriggerType` member set)
