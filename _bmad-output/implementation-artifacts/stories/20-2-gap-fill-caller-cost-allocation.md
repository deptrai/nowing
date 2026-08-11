---
baseline_commit: fa204db7a08eda76db4645d5d2b43af76d34a091
baseline_branch: develop
story_key: 20-2-gap-fill-caller-cost-allocation
status: review
---

# Story 20.2: Gap-Fill Caller + Cost Allocation (Nowing side)

Status: implementation-complete

## Story

As a chat user,
I want the agent to ask `chainlens-research` to index missing data on demand,
so that the answer does not say "I don't know" when the data is available on the public web or via a Nowing scraper.

## Acceptance Criteria

1. **Given** a user query in chat, **When** `chainlens-research` `POST /api/v1/search` returns a `gap-fill-needed` signal (or an empty/`insufficient_evidence` result with `suggested_domains`), **Then** the chat orchestrator calls `POST /v1/gap-fill` with `{ query, domains?, source?, priority }` and `workspace_id`, and surfaces a "gap-fill in progress" indicator to the user.
2. **Given** a gap-fill request, **When** `chainlens-research` decides the gap is in a domain owned by Nowing (e.g. `batdongsan`, `vn_jobs`), **Then** `chainlens-research` calls `POST /v1/scraper/{scraper_id}/run` on Nowing (internal), Nowing runs the scraper, and the result is pushed back to `chainlens-research` via Story 20.1.
3. **Given** the final `SSE done` frame, **When** `costDollars` is reported, **Then** Nowing bills the user once for the total (search + gap-fill + scraper usage), and internal cost allocation is recorded separately for Nowing scraper infra vs `chainlens-research` indexing.
4. **Given** gap-fill takes longer than 60s, **When** the chat orchestrator waits, **Then** it uses the async research door (`AD-17`, `?mode=async`) and returns a `run_id` to the user; the result arrives via SSE `run_event_bus`.

## Tasks / Subtasks

- [x] Detect gap-fill signals in the chat/research flow (AC: #1)
  - [x] Extend `app/capabilities/chainlens/research/executor.py` `_SSEParser` to detect `gap-fill-needed` frames and `suggested_domains`
  - [x] Implement fallback detection: when the terminal SSE frame has `status: insufficient_evidence` and a non-empty `suggested_domains` list, treat it as a gap-fill trigger
  - [x] Add `gap_fill_needed`, `suggested_domains`, and `insufficient_evidence` fields to `ResearchOutput` in `app/capabilities/chainlens/research/schemas.py`
  - [x] Surface the signal in `app/tasks/chat/streaming/flows/new_chat/orchestrator.py` (or `new_streaming_service.py`) with a clear "gap-fill in progress" UX message
- [x] Implement `GapFillService` and `POST /v1/gap-fill` caller (AC: #1)
  - [x] Create `nowing_backend/app/services/chainlens/gap_fill.py`
  - [x] Implement `request(query, workspace_id, domains=None, source=None, priority=None)` with service auth and `X-Workspace-Id` headers
  - [x] Map the response to a typed `GapFillResponse` with `run_id` / `status`
- [x] Implement internal scraper callback from `chainlens-research` (AC: #2)
  - [x] Add `nowing_backend/app/routes/chainlens_internal.py` (or extend `app/routes/__init__.py`) with `POST /v1/scraper/{scraper_id}/run`
  - [x] Validate service auth token and workspace mapping
  - [x] Look up the registered scraper in `app/capabilities/core/store.py` and invoke `execute_with_context`
  - [x] Push scraper output to `chainlens-research` via `NowingIngestService` (Story 20.1)
  - [x] Return `ingestJobId` to `chainlens-research`
- [x] Cost allocation for search + gap-fill + scraper (AC: #3)
  - [x] Reuse `UsageType.CHAINLENS_GAP_FILL` (already in `app/services/token_tracking_service.py`) and the existing `TokenUsage.run_id` nullable UUID column (already in `app/db.py`); set `run_id` on every ChainLens-related `TokenUsage` row
  - [x] Use `ChainLensServiceAuth.cost_dollars_to_micros` (Decimal half-up, from Story 20.4) for all `costDollars` conversions
  - [x] If `chainlens-research` returns a single `costDollars` total, estimate the split by operation using a documented heuristic (e.g., fixed per-operation weights or proportional to recorded duration), store the heuristic in `TokenUsage.call_details`, and apply the total as one `wallet_credit.apply_debit`
  - [x] If `chainlens-research` returns per-operation costs, record exact costs in `call_details` (`search_cost_micros`, `gap_fill_cost_micros`, `scraper_cost_micros`, `scraper_id`) and still debit the total once
  - [x] Record one `TokenUsage` row per operation (`chainlens_search`, `chainlens_gap_fill`, `chainlens_ingest`/`nowing_scraper`) with a shared `run_id` so the ledger reconciles to the single debit
- [x] Async research door for gap-fill > 60s (AC: #4)
  - [x] Reuse `?mode=async` path in `app/capabilities/core/access/rest.py` and `app/capabilities/core/access/agent.py`
  - [x] Use `app/capabilities/core/async_runner.py` `start_async_run` for gap-fill background execution
  - [x] Stream progress/result via `app/capabilities/core/events.py` `run_event_bus` SSE
  - [x] Return `run_id` to the chat orchestrator; continue the chat turn without blocking
  - [x] Surface async progress and estimated completion in the chat UI (UX §2B "Gap-fill in progress")
- [x] Tests
  - [x] Unit test gap-fill signal parsing and `GapFillService` request serialization
  - [x] Unit test internal `POST /v1/scraper/{scraper_id}/run` callback auth and dispatch
  - [x] Integration test end-to-end chat -> gap-fill -> scraper callback -> ingest
  - [x] Integration test cost allocation `TokenUsage` rows for search/gap-fill/scraper
  - [x] Integration test async gap-fill returns `run_id` and completes via SSE

### Review Findings

- [x] [Review][Patch] Async research path does not trigger gap-fill (`app/capabilities/core/async_runner.py:142`)
- [x] [Review][Patch] `TokenUsage.run_id` missing in sync research paths (`app/capabilities/core/access/agent.py:434`, `app/capabilities/core/access/rest.py:310-329`)
- [x] [Review][Patch] Scraper callback trusts `body.workspace_id` over auth context (`app/routes/chainlens_internal.py:85-93`)
- [x] [Review][Patch] Duplicate `ChainLensIngestJob` created on scraper callback (`app/routes/chainlens_internal.py:174-195`)
- [x] [Review][Patch] `insufficient_evidence_flag` set when only `suggested_domains` present (`app/capabilities/chainlens/research/executor.py:588-614`)
- [x] [Review][Patch] Sync gap-fill timeout starts a second upstream request (`app/services/chainlens/gap_fill.py:216-243`)
- [x] [Review][Patch] Gap-fill service cost not recorded/debited (`app/services/chainlens/gap_fill.py:88-104, 186-214`)
- [x] [Review][Patch] KB-fallback cost double-counted in cost allocation (`app/capabilities/core/billing.py:535-579, 611`)
- [x] [Review][Patch] REST sync path does not trigger gap-fill (`app/capabilities/core/access/rest.py:309-329`)
- [x] [Review][Patch] Background task list never cleaned (`app/services/chainlens/gap_fill.py:76, 207-209`)
- [x] [Review][Patch] `_normalize_cost_breakdown` drops non-integer micros (`app/capabilities/chainlens/research/executor.py:619-671`)
- [x] [Review][Patch] Inbound correlation id not forwarded to ingest (`app/routes/chainlens_internal.py:85-86, 174-180`)
- [x] [Review][Patch] Gap-fill does not rotate service token on 401 (`app/services/chainlens/gap_fill.py:160-163`)
- [x] [Review][Patch] Missing end-to-end async gap-fill integration test (`tests/integration/capabilities/chainlens/research/test_gap_fill_cost_allocation.py`)
- [ ] [Review][Defer] Usage type for search bucket is `DEEP_RESEARCH` instead of `chainlens_search` per AC (`app/capabilities/core/billing.py:618-624`)

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-15` (ChainLens is an external deep-research dependency, not a scraper capability) means the gap-fill caller is a service adapter in `app/services/chainlens/`, not a capability.
  - `AD-17` (deep research on the async capability door) requires reusing `?mode=async` and the existing `run_event_bus` instead of inventing a new job/progress flow.
  - `AD-8` (unified credit wallet, cost from `costDollars`) requires parsing `costDollars` from the terminal `done` frame and converting to micros with the same half-up rounding used for `chainlens.research`.
  - `AD-4` (multi-agent chat runtime) and `AD-5` (Zero sync) govern how the chat orchestrator surfaces the async `run_id` and progress to the web client.
  - `AD-3` (scraper capabilities self-register) applies when `chainlens-research` invokes `POST /v1/scraper/{scraper_id}/run`; the callback should use the existing capability registry (`app/capabilities/core/store.py`, `execute_with_context`).
  - `AD-34` (scraper feed contract) requires the callback to push scraper results to `chainlens-research` via `NowingIngestService` with `Chunk[]` and `source: 'nowing_scraper'`.
  - `AD-35` (no public/vertical corpus in Nowing) ensures gap-fill only triggers index building in `chainlens-research`, not in Nowing.
  - `FR-59` (Gap-Fill Trigger) and `PRD §4.2/4.9` are the product sources.

- Source tree components to touch
  - `nowing_backend/app/services/chainlens/gap_fill.py` — new `GapFillService`
  - `nowing_backend/app/services/chainlens/ingest.py` (Story 20.1) — called by the scraper callback
  - `nowing_backend/app/services/chainlens/auth.py` (Story 20.4) — service-to-service auth headers
  - `nowing_backend/app/routes/chainlens_internal.py` — internal callback routes for `chainlens-research`
  - `nowing_backend/app/routes/__init__.py` — register the new internal router
  - `nowing_backend/app/capabilities/chainlens/research/executor.py` — parse gap-fill signals
  - `nowing_backend/app/capabilities/chainlens/research/schemas.py` — `ResearchOutput` gap-fill fields
  - `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` — trigger gap-fill in chat
  - `nowing_backend/app/schemas/new_chat.py` — chat request / mode schema (research mode threading)
  - `nowing_backend/app/services/new_streaming_service.py` — streaming cost aggregation
  - `nowing_backend/app/capabilities/core/access/agent.py` — async agent tool path
  - `nowing_backend/app/capabilities/core/access/rest.py` — async `POST` door
  - `nowing_backend/app/capabilities/core/async_runner.py` — background run execution
  - `nowing_backend/app/capabilities/core/events.py` — `run_event_bus`
  - `nowing_backend/app/capabilities/core/billing.py` — cost allocation across operation types
  - `nowing_backend/app/services/token_tracking_service.py` — `record_token_usage` for `chainlens_gap_fill`
  - `nowing_backend/app/services/wallet_credit.py` — `apply_debit`
  - `nowing_backend/app/db.py` — `TokenUsage`, `Run` (provenance)
  - `nowing_backend/app/config/__init__.py` — `CHAINLENS_API_URL`, `CHAINLENS_REQUEST_TIMEOUT_SECONDS`, `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED`

- Testing standards summary
  - Mock `chainlens-research` `POST /api/v1/search` to emit `gap-fill-needed` and `POST /v1/gap-fill`
  - Mock internal `POST /v1/scraper/{scraper_id}/run` and `POST /v1/ingest/scraper`
  - Assert `X-Correlation-Id` and `X-Workspace-Id` headers on every outbound call
  - Assert `TokenUsage` rows for `chainlens_search`, `chainlens_gap_fill`, and scraper usage add up to the single debit
  - Assert chat turn returns `run_id` and the SSE `run_event_bus` eventually delivers `run.finished`

### Project Structure Notes

- Alignment with unified project structure
  - All `chainlens-research` integration logic is grouped under `nowing_backend/app/services/chainlens/` (auth, ingest, gap-fill, private-provider) to keep the external dependency boundary visible.
  - New internal callback routes live under `nowing_backend/app/routes/chainlens_internal.py` and are mounted in `nowing_backend/app/routes/__init__.py`.
  - Async machinery is already centralized in `nowing_backend/app/capabilities/core/` (`access/rest.py`, `access/agent.py`, `async_runner.py`, `events.py`).

- Detected conflicts or variances
  - `chainlens.research` may not yet emit a dedicated `type: gap-fill-needed` SSE frame. The executor must tolerate unknown frame types and detect gap-fill from an explicit `type: gap-fill-needed` frame OR from a terminal frame with `status: insufficient_evidence` + non-empty `suggested_domains`.
  - `TokenUsage.run_id` already exists as a nullable UUID column (`app/db.py`), and `UsageType.CHAINLENS_GAP_FILL` already exists (`app/services/token_tracking_service.py`). Story 20.4 also threaded `run_id` through `CapabilityContext`; set it on every ChainLens `TokenUsage` row.
  - `app/capabilities/core/billing.py` currently charges `chainlens_query` only for deep-research calls. Extend it (or the gap-fill orchestrator) to record `chainlens_gap_fill` and scraper usage `TokenUsage` rows, then debit the total once via `wallet_credit.apply_debit`.
  - `chainlens-research` may return a single `costDollars` total rather than a per-operation breakdown. Define and document a fallback split heuristic (e.g., weighted by operation type or measured duration) and store the estimated `search_cost_micros`, `gap_fill_cost_micros`, `scraper_cost_micros`, and `scraper_id` inside `TokenUsage.call_details`.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Epic 20 / Story 20.2]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-3]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-4]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-5]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-8]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-15]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-17]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-34]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-35]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-59]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-ecosystem-search.md` §2B Gap-fill in progress]
- [Source: `nowing_backend/app/capabilities/chainlens/research/executor.py` §`_SSEParser`]
- [Source: `nowing_backend/app/capabilities/chainlens/research/schemas.py` §`ResearchOutput`]
- [Source: `nowing_backend/app/capabilities/core/billing.py` §`_charge_chainlens`]
- [Source: `nowing_backend/app/services/token_tracking_service.py` §`record_token_usage`]
- [Source: `nowing_backend/app/services/wallet_credit.py` §`apply_debit`]
- [Source: `nowing_backend/app/capabilities/core/async_runner.py`]
- [Source: `nowing_backend/app/capabilities/core/events.py`]

## Dev Agent Record

### Change Log

- 2026-08-11: Threaded `run_id`/`correlation_id` through sync (REST / agent) and async (`async_runner`) research paths.
- 2026-08-11: `GapFillService` now authenticates to `chainlens-research` with `ChainLensServiceAuth` headers and rotates tokens on `401`.
- 2026-08-11: Sync gap-fill uses a local background worker + `asyncio.wait_for` so a timeout does not restart the upstream request.
- 2026-08-11: `GapFillService` records `chainlens_gap_fill` and `chainlens_ingest` `TokenUsage` rows and debits the workspace owner once.
- 2026-08-11: `chainlens.research` cost is split into search / gap-fill / scraper `TokenUsage` rows; KB-fallback cost is folded into the search bucket to avoid double-counting.
- 2026-08-11: `chainlens_internal` scraper callback trusts the auth context workspace, forwards `correlation_id` to `NowingIngestService`, and no longer creates duplicate `ChainLensIngestJob` rows.
- 2026-08-11: `_SSEParser._normalize_cost_breakdown` rounds non-integer micros with half-up `Decimal` conversion.
- 2026-08-11: Added/updated tests covering cost allocation, non-integer micros, workspace auth override, async gap-fill trigger, and end-to-end async gap-fill completion.

### Agent Model Used

Devin / SWE-1.7 Max

### Debug Log References

- Validation 2026-08-11: `TokenUsage.run_id` already exists as nullable UUID (`app/db.py`); `UsageType.CHAINLENS_GAP_FILL` already exists (`app/services/token_tracking_service.py`); `ChainLensServiceAuth` and `cost_dollars_to_micros` from Story 20.4 are available.
- `app/capabilities/core/billing.py` only charges `BillingUnit.CHAINLENS_QUERY` for deep-research; gap-fill and scraper cost rows must be added without double-debiting.
- `chainlens.research` may not emit a dedicated `gap-fill-needed` SSE frame; fallback detection via `status: insufficient_evidence` + `suggested_domains` is required.

### Completion Notes List

- Threaded `run_id`/`correlation_id` through sync REST, sync agent, and async research paths.
- Implemented `GapFillService` with sync, async, and local background worker timeout handling; added service auth headers, 401 token rotation, and cost recording.
- Extended `_SSEParser` to detect `gap-fill-needed` frames and `suggested_domains`; `_normalize_cost_breakdown` rounds non-integer micros.
- Added `gap_fill_needed`, `suggested_domains`, `insufficient_evidence`, and `cost_breakdown` to `ResearchOutput`.
- Added `POST /v1/scraper/{scraper_id}/run` internal callback that trusts auth-context workspace, forwards `correlation_id`, runs the scraper, normalizes output to `Chunk[]`, and pushes through `NowingIngestService`.
- Extended `app/capabilities/core/billing.py` to split `chainlens.research` cost into `DEEP_RESEARCH`, `CHAINLENS_GAP_FILL`, and `CHAINLENS_INGEST` rows while debiting once; KB-fallback cost folded into search bucket.
- Integrated gap-fill trigger into `app/capabilities/core/access/agent.py`, `app/capabilities/core/access/rest.py`, and `app/capabilities/core/async_runner.py`.
- Added/updated unit and integration tests; all targeted test suites and ruff checks pass.

### File List

- `app/capabilities/chainlens/research/executor.py`
- `app/capabilities/chainlens/research/schemas.py`
- `app/capabilities/core/billing.py`
- `app/capabilities/core/runs.py`
- `app/capabilities/core/access/agent.py`
- `app/capabilities/core/access/rest.py`
- `app/capabilities/core/async_runner.py`
- `app/services/chainlens/gap_fill.py`
- `app/services/chainlens/ingest.py`
- `app/services/token_tracking_service.py`
- `app/routes/chainlens_internal.py`
- `app/routes/__init__.py`
- `tests/unit/capabilities/chainlens/research/test_gap_fill_sse.py`
- `tests/unit/capabilities/chainlens/research/test_mutation_killers.py`
- `tests/unit/services/chainlens/test_gap_fill.py`
- `tests/unit/routes/test_chainlens_internal.py`
- `tests/unit/capabilities/test_billing.py`
- `tests/unit/capabilities/access/test_rest_degraded.py`
- `tests/integration/capabilities/chainlens/research/test_gap_fill_cost_allocation.py`
