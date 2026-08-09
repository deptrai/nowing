# Story 20.2: Gap-Fill Caller + Cost Allocation (Nowing side)

Status: ready-for-dev

## Story

As a chat user,
I want the agent to ask `chainlens-research` to index missing data on demand,
so that the answer does not say "I don't know" when the data is available on the public web or via a Nowing scraper.

## Acceptance Criteria

1. **Given** a user query in chat, **When** `chainlens-research` `POST /api/v1/search` returns a `gap-fill-needed` signal (or empty result with `suggested_domains`), **Then** the chat orchestrator calls `POST /v1/gap-fill` with `{ query, domains?, source?, priority }` and `workspace_id`.
2. **Given** a gap-fill request, **When** `chainlens-research` decides the gap is in a domain owned by Nowing (e.g. `batdongsan`, `vn_jobs`), **Then** `chainlens-research` calls `POST /v1/scraper/{scraper_id}/run` on Nowing (internal), Nowing runs the scraper, and the result is pushed back to `chainlens-research` via Story 20.1.
3. **Given** the final `SSE done` frame, **When** `costDollars` is reported, **Then** Nowing bills the user once for the total (search + gap-fill + scraper usage), and internal cost allocation is recorded separately for Nowing scraper infra vs `chainlens-research` indexing.
4. **Given** gap-fill takes longer than 60s, **When** the chat orchestrator waits, **Then** it uses the async research door (`AD-17`, `?mode=async`) and returns a `run_id` to the user; the result arrives via SSE `run_event_bus`.

## Tasks / Subtasks

- [ ] Detect gap-fill signals in the chat/research flow (AC: #1)
  - [ ] Extend `app/capabilities/chainlens/research/executor.py` `_SSEParser` to detect `gap-fill-needed` and `suggested_domains` frames
  - [ ] Add `gap_fill_needed`, `suggested_domains` fields to `ResearchOutput` in `app/capabilities/chainlens/research/schemas.py`
  - [ ] Surface the signal in `app/tasks/chat/streaming/flows/new_chat/orchestrator.py` (or `new_streaming_service.py`)
- [ ] Implement `GapFillService` and `POST /v1/gap-fill` caller (AC: #1)
  - [ ] Create `nowing_backend/app/services/chainlens/gap_fill.py`
  - [ ] Implement `request(query, workspace_id, domains=None, source=None, priority=None)` with service auth and `X-Workspace-Id` headers
  - [ ] Map the response to a typed `GapFillResponse` with `run_id` / `status`
- [ ] Implement internal scraper callback from `chainlens-research` (AC: #2)
  - [ ] Add `nowing_backend/app/routes/chainlens_internal.py` (or extend `app/routes/__init__.py`) with `POST /v1/scraper/{scraper_id}/run`
  - [ ] Validate service auth token and workspace mapping
  - [ ] Look up the registered scraper in `app/capabilities/core/store.py` and invoke `execute_with_context`
  - [ ] Push scraper output to `chainlens-research` via `NowingIngestService` (Story 20.1)
  - [ ] Return `ingestJobId` to `chainlens-research`
- [ ] Cost allocation for search + gap-fill + scraper (AC: #3)
  - [ ] Add `chainlens_gap_fill` usage type support in `app/services/token_tracking_service.py` and `app/db.py`
  - [ ] Extend `app/capabilities/core/billing.py` to allocate total `cost_micros` across `chainlens_search`, `chainlens_gap_fill`, and scraper usage in `call_details`
  - [ ] Ensure single `wallet_credit.apply_debit` for the total and one `TokenUsage` row per operation
  - [ ] Store breakdown in `TokenUsage.call_details` (`search_cost_micros`, `gap_fill_cost_micros`, `scraper_cost_micros`, `scraper_id`)
- [ ] Async research door for gap-fill > 60s (AC: #4)
  - [ ] Reuse `?mode=async` path in `app/capabilities/core/access/rest.py` and `app/capabilities/core/access/agent.py`
  - [ ] Use `app/capabilities/core/async_runner.py` `start_async_run` for gap-fill background execution
  - [ ] Stream progress/result via `app/capabilities/core/events.py` `run_event_bus` SSE
  - [ ] Return `run_id` to the chat orchestrator; continue the chat turn without blocking
- [ ] Tests
  - [ ] Unit test gap-fill signal parsing and `GapFillService` request serialization
  - [ ] Unit test internal `POST /v1/scraper/{scraper_id}/run` callback auth and dispatch
  - [ ] Integration test end-to-end chat -> gap-fill -> scraper callback -> ingest
  - [ ] Integration test cost allocation `TokenUsage` rows for search/gap-fill/scraper
  - [ ] Integration test async gap-fill returns `run_id` and completes via SSE

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
  - `chainlens.research` currently has no `gap-fill-needed` SSE frame type. The executor will need to tolerate unknown frame types and detect gap-fill either from an explicit `type: gap-fill-needed` frame or from `status: insufficient_evidence` + `suggested_domains`.
  - `TokenUsage` does not have a `run_id` column; run attribution must be stored in `call_details` or a new nullable FK must be added.
  - `app/capabilities/core/billing.py` currently only charges `chainlens_query` for `chainlens.research`. It needs to be extended to support `chainlens_gap_fill` and combined scraper costs.
  - Cost allocation between search, gap-fill, and scraper may not be broken down by `chainlens-research`; Nowing may need to estimate the split when only a total `costDollars` is provided.

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

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List
