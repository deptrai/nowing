# Story 18.7: Cost Traceability

Status: ready-for-dev

## Story

As a vertical client,
I want to attribute costs to my users and listings,
so that I can track and bill for Nowing usage.

## Acceptance Criteria

1. **Given** a chat request with `external_metadata` (listing_id, broker_id, user_id), **When** processed, **Then** the `TokenUsage` row stores the metadata.
2. **Given** a `client_id`, **When** querying TokenUsage, **Then** cost reports can be generated per client per day.
3. **Given** an `X-Run-Id` header in the response, **When** the client receives it, **Then** they can correlate costs with their internal records.

## Tasks / Subtasks

- [ ] Add attribution columns to `TokenUsage` and `Run` (AC: #1, #2)
  - [ ] Add Alembic migration for:
    - `token_usage.client_id` (text, nullable, index `(workspace_id, client_id, created_at)`)
    - `token_usage.external_metadata` (JSONB, nullable, default `{}`)
    - `token_usage.run_id` (UUID, nullable, index) — for cost correlation with `Run`
    - `runs.client_id` (text, nullable, index) and `runs.external_metadata` (JSONB, nullable)
  - [ ] Update `TokenUsage` model (`app/db.py:1167-1246`)
  - [ ] Update `Run` model (`app/db.py:3306-3371`)
- [ ] Capture `external_metadata` and `client_id` in chat (AC: #1)
  - [ ] Update `NewChatRequest` / `AgentChatMessageCreate` to accept `external_metadata: dict` (Story 18.1/18.2)
  - [ ] Pass `external_metadata`, `client_id`, and `run_id` to `record_token_usage` (`app/services/token_tracking_service.py:545-620`)
  - [ ] Update `record_token_usage` signature to accept `client_id`, `run_id`, `external_metadata`
  - [ ] Ensure `external_metadata` is stored in `TokenUsage.call_details` or `TokenUsage.external_metadata` JSONB
  - [ ] Validate `external_metadata` keys are not used for authz or RLS (per `epic-18-pat-scope-rls-threat-model.md §2.7` TM9)
- [ ] Return `X-Run-Id` header (AC: #3)
  - [ ] Generate `run_id` at the start of chat turn (reuses `Run.id` UUID)
  - [ ] Add `X-Run-Id` header to `POST .../messages` response headers
  - [ ] Include `run_id` in SSE status/done frames for public agent-chat if using streaming
- [ ] Cost reporting endpoint (AC: #2)
  - [ ] Add `GET /api/v1/workspaces/{workspace_id}/agent-chat/costs?client_id=...&start_date=...&end_date=...` to `app/routes/agent_chat_routes.py`
  - [ ] Aggregate `TokenUsage` by `client_id` / day / `usage_type` with sums of `cost_micros`
  - [ ] Add `CostReport` schema in `app/schemas/agent_chat.py`
  - [ ] Restrict report access to workspace Owner or PAT with `agent_chat:cost:read` scope
  - [ ] Add index `(workspace_id, client_id, created_at)` on `token_usage` for efficient daily rollups
- [ ] Attribution for `Run`/scraper calls (AC: #1)
  - [ ] Update `app/capabilities/core/runs.py` to accept `client_id` and `external_metadata` and store on `Run`
  - [ ] Propagate from agent tool calls so scraper runs triggered by vertical-client chat carry the same attribution
  - [ ] Update `record_token_usage` for tool/capability usage to include `run_id` and `client_id`
- [ ] Tests
  - [ ] Unit test `record_token_usage` stores `external_metadata`, `client_id`, and `run_id`
  - [ ] Integration test public `POST .../messages` returns `X-Run-Id`
  - [ ] Integration test cost report endpoint returns correct daily per-client totals
  - [ ] Integration test `external_metadata` is ignored by authz/RLS (TM9)
  - [ ] Integration test scraper runs triggered from vertical-client chat carry `client_id`

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-29` (`ARCHITECTURE-SPINE.md:727-737`) — `external_metadata` is additive and untrusted for authorization; responses carry `X-Run-Id` for cost/audit correlation.
  - `AD-8` (`ARCHITECTURE-SPINE.md:218-226`) — unified credit wallet; `TokenUsage.cost_micros` is the canonical cost field; external cost (e.g., ChainLens) parsed from `costDollars`.
  - `AD-31` (`ARCHITECTURE-SPINE.md:750-764`) — `client_id` is the hard tenant key; `TokenUsage`/`Run` must carry it for attribution and reports.
  - `epic-18-pat-scope-rls-threat-model.md §2.7` — `external_metadata` is stored for attribution only and **never** used in authz or RLS.
  - `epic-18-pat-scope-rls-threat-model.md §5 TM9` — external_metadata authz confusion: test that metadata never read by authz/RLS.

- Source tree components to touch
  - `nowing_backend/alembic/versions/` — migration for `token_usage`/`runs` attribution columns
  - `nowing_backend/app/db.py:1167-1246` — `TokenUsage`
  - `nowing_backend/app/db.py:3306-3371` — `Run`
  - `nowing_backend/app/services/token_tracking_service.py:545-620` — `record_token_usage`
  - `nowing_backend/app/schemas/agent_chat.py` — `AgentChatMessageCreate`, `CostReport`
  - `nowing_backend/app/schemas/new_chat.py:234-313` — `NewChatRequest` (add `external_metadata`)
  - `nowing_backend/app/routes/agent_chat_routes.py` — public endpoints + cost report
  - `nowing_backend/app/capabilities/core/runs.py` — `Run` creation
  - `nowing_backend/app/capabilities/core/access/rest.py` — capability invocation context
  - `nowing_backend/app/services/wallet_credit.py` — debit call sites
  - `nowing_backend/app/observability/metrics.py` — cost attribution counters

- Testing standards summary
  - Unit tests in `tests/unit/services/test_token_tracking_service.py`
  - Integration tests in `tests/integration/routes/test_agent_chat_costs.py`
  - Assert `X-Run-Id` returned on every public message creation
  - Assert `external_metadata` appears in `TokenUsage.call_details`/`external_metadata`
  - Assert cost report aggregation is correct and scoped to workspace + client

### Project Structure Notes

- Alignment with unified project structure
  - `TokenUsage` is the canonical cost ledger; extend it with attribution JSONB and `client_id` rather than creating a new table.
  - Cost report is a workspace-scoped public agent-chat route.

- Detected conflicts or variances
  - `TokenUsage` has a partial unique index on `message_id` (line 1186-1191); `run_id` and `client_id` are nullable and additive, no conflict.
  - `TokenUsage` currently has no `run_id` column; Story 20.4 also needs `run_id`/`call_details` for `chainlens-research` cost. Coordinate schema with 20.4 to avoid duplicate migrations.
  - `Run.id` is a UUID while `TokenUsage` uses integer `id`; `run_id` on `TokenUsage` must be a UUID type.
  - `external_metadata` may contain PII; log/metrics must not include raw keys/values as labels.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.7]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-29, AD-8, AD-31]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §2.7 Untrusted Fields, §5 TM9]
- [Source: `nowing_backend/app/db.py` §TokenUsage, Run]
- [Source: `nowing_backend/app/services/token_tracking_service.py` §record_token_usage]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List