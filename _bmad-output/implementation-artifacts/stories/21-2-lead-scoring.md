---
story_key: 21-2-lead-scoring
status: done
baseline_commit: db50806a8
epic: 21
story: 2
---

# Story 21.2: Lead Scoring & Prioritization

## Story

Với tư cách là sales manager,
Tôi muốn lead được chấm điểm và xếp hạng theo khả năng chuyển đổi,
Để team tôi tập trung vào những prospect có giá trị cao nhất.

## Acceptance Criteria

### AC-1 — Composite fit + intent score
**Given** a set of leads in a workspace,
**When** the scoring engine runs,
**Then** each lead receives a composite `score` (0-100) computed as `0.5 × fit_score + 0.5 × intent_score`.

**And** `fit_score` (0-100) is derived from firmographics and ICP match: company size, industry match, location match, tech stack match, and ICP alignment.

**And** `intent_score` (0-100) is derived from signal strength (funding, hiring, tech_stack, executive_move, news) and recency.

**And** output includes `classification` ∈ {`hot`, `warm`, `cold`}: hot (80-100), warm (50-79), cold (0-49).

### AC-2 — Score breakdown, trend, and conversion similarity
**Given** a lead score exists,
**When** it is returned by API or rendered by the Data Panel,
**Then** the response includes `fit_score`, `intent_score`, and `factors_json` showing the contribution of each sub-component.

**And** the response includes `trend` ∈ {`improving`, `stable`, `declining`} computed from the previous `LeadScore` for the same `lead_id`.

**And** the response includes `converted_similarity` (0-100), a RAG-based similarity score against previously converted leads in the same workspace (or `null` if no conversion history).

### AC-3 — Persist as `LeadScore` + redacted `Memory`
**Given** a lead score is computed,
**When** it is stored,
**Then** the system writes a `LeadScore` row with `workspace_id`, `client_id`, `lead_id`, `company_name`, `score`, `fit_score`, `intent_score`, `factors_json`, `classification`, `trend`, `converted_similarity`, and `computed_at`.

**And** the system writes a `Memory` row of type `semantic`, tags `['lead_score']`, with content being a redacted summary of `factors_json`, `Memory.source_uuid` = `LeadScore.id`, and `Memory.source_entity_type` = `'lead_score'`.

**And** `redact_pii(text, context='lead_enrichment')` is called on `Memory.content` before persistence (AD-25 / AD-49).

### AC-4 — Read signals from `SignalEvent` + `Memory` of Story 21.1
**Given** the scoring engine needs intent data,
**When** it reads signal data,
**Then** it queries `SignalEvent` and `Memory` rows created by Story 21.1 (tag `lead_signal`), filtered by `workspace_id`, `client_id`, and `company_name`/`lead_id`.

**And** it does **not** create or query a separate signal store.

### AC-5 — Billing event for scoring (non-LLM) and `TokenUsage` for LLM
**Given** a lead score is computed,
**When** the engine incurs cost (e.g. LLM reasoning for RAG similarity or AI fallback),
**Then** a `BillingEvent` row is written with `event_entity_type='lead_score'`, `event_type='lead_scoring'`, `cost_micros`, `cost_basis` ∈ {`actual`, `estimated`}, and `event_id` = `LeadScore.id` (AD-42).

**And** any LLM token consumption is recorded via `record_token_usage()` with `usage_type='llm_reasoning'` (AD-10, AD-42). `TokenUsage` is **not** used for the business event itself.

### AC-6 — Workspace ICP configuration
**Given** a workspace has ICP criteria configured,
**When** the scoring engine computes fit,
**Then** the ICP match component uses those criteria.

**Given** ICP criteria are missing,
**When** a lead is scored,
**Then** the ICP match component defaults to a neutral weight and the score is still computed.

### AC-7 — Error path: insufficient wallet
**Given** the scoring engine is configured to bill (`LEAD_SCORING_MICROS_PER_CALL > 0`),
**When** the workspace wallet has insufficient credits,
**Then** the engine returns `degraded=true` with `degradation_reasons=['insufficient_wallet']` and does not create `LeadScore` or `Memory`.

## Tasks / Subtasks

### Task 1: Models & Migration
- [x] 1.1 Ensure `BillingEvent` table exists in `app/db.py` (if not, create or align with Story 21.1):
  - `id` (UUID, PK)
  - `workspace_id` (Integer, FK workspaces, index)
  - `client_id` (CITEXT, nullable, index)
  - `user_id` (UUID, nullable, index)
  - `event_entity_type` (String(50), index)
  - `event_type` (String(50), index)
  - `event_id` (UUID, index)
  - `cost_micros` (BigInteger)
  - `currency` (String(3), default="USD")
  - `cost_basis` (String(20), default="estimated")
- [x] 1.2 Add `Lead` table to `app/db.py` (if Story 21.4 has not created it yet):
  - `id` (UUID, PK)
  - `workspace_id` (Integer, FK workspaces, index)
  - `client_id` (CITEXT, nullable, index)
  - `source` (String(100), index)
  - `source_url` (Text, nullable)
  - `source_chunk_id` (UUID, nullable)
  - `company_name` (String(200), index)
  - `domain` (String(255), nullable, index)
  - `industry` (String(100), nullable, index)
  - `fit_score` (Float, nullable)
  - `intent_score` (Float, nullable)
  - `composite_score` (Float, nullable)
  - `status` (String(50), default="open")
  - `enriched` (Boolean, default=False)
  - `consent_status` (String(50), nullable)
  - `legal_basis` (String(50), nullable)
  - `created_at` (TIMESTAMP, default=now)
  - **Rule:** 21.2 does **not** write `Lead` rows in production; the sole writer is `lead_extractor` (Story 21.4). 21.2 may create the table for `LeadScore` FK and test fixtures.
- [x] 1.3 Add `LeadScore` table to `app/db.py`:
  - `id` (UUID, PK)
  - `workspace_id` (Integer, FK workspaces, index)
  - `client_id` (CITEXT, nullable, index)
  - `lead_id` (UUID, FK leads.id, index)
  - `company_name` (String(200), index)
  - `score` (Float, nullable=False)
  - `fit_score` (Float, nullable=False)
  - `intent_score` (Float, nullable=False)
  - `classification` (String(10), nullable=False) — `hot`/`warm`/`cold`
  - `factors_json` (JSONB, default=dict)
  - `trend` (String(10), nullable) — `improving`/`stable`/`declining`
  - `converted_similarity` (Float, nullable)
  - `previous_score_id` (UUID, FK lead_scores.id, nullable)
  - `computed_at` (TIMESTAMP, default=now, index)
  - Composite index `(workspace_id, client_id, lead_id, computed_at DESC)`
- [x] 1.4 Add `icp_criteria` JSONB column to `Workspace` or create `WorkspaceIcp` table (decision: add `icp_criteria` to `Workspace` for MVP if migration is small).
- [x] 1.5 Alembic migration `199_add_lead_score_tables.py` (next available): create `Lead`, `LeadScore`, and extend `Workspace`.
- [x] 1.6 Extend `MemoryRepository.create_memory` / `update_memory` to accept `source_uuid` and `source_entity_type` (AD-44/AD-47). DB columns exist (`app/db.py:2336-2337`) but repository kwargs missing.
- [x] 1.7 Add `UsageType.LEAD_SCORING_LLM` enum value for LLM reasoning used by lead scoring in `app/services/token_tracking_service.py`.

### Task 2: Scoring Engine
- [x] 2.1 Create `app/lead_intelligence/scoring/__init__.py` and `service.py`:
  - `LeadScoringService.score(session, ctx, lead_ids: list[UUID] | None = None) -> LeadScoreOutput`
  - Reads `Lead` rows; if `lead_ids` is `None`, scores all leads for workspace.
  - Queries `SignalEvent` + `Memory` (tag `lead_signal`) for intent.
  - Computes `fit_score` from firmographics and `Workspace.icp_criteria`.
  - Computes `intent_score` from signal strength and recency.
  - Computes `converted_similarity` via RAG against converted `Lead` rows.
  - Falls back to rule-based scoring when RAG/AI is disabled or fails.
  - Writes `LeadScore` + `BillingEvent`.
  - Creates `Memory` via `MemoryRepository.create_memory(..., source_uuid=lead_score.id, source_entity_type='lead_score')` after `MemoryRepository` is extended (Task 1.6).
  - Returns `LeadScoreOutput` with items and cost.
- [x] 2.2 Create `app/lead_intelligence/scoring/schemas.py`:
  - `LeadScoreInput` (lead_ids: list[UUID] | None, recalculate_all: bool = False)
  - `LeadScoreOutput` (items: list[LeadScoreRead], cost_micros: int, degraded: bool, degradation_reasons: list[str] | None)
  - `LeadScoreRead` (id, workspace_id, client_id, lead_id, company_name, score, fit_score, intent_score, classification, factors_json, trend, converted_similarity, computed_at)
  - `IcpCriteria` (target_industries, target_locations, target_company_sizes, target_tech_stack, weights_json)
- [x] 2.3 Create `app/lead_intelligence/scoring/rubric.py`:
  - Default weights and point allocations for fit and intent sub-components.
  - Recency decay function (default: 7d=1.0, 30d=0.7, 90d=0.4, older=0.1).
  - `classification(score)` helper.

### Task 3: Billing & Wallet
- [x] 3.1 Extend `app/services/billing_event_service.py`:
  - `record_lead_scoring(session, lead_score_id, workspace_id, client_id, user_id, cost_micros)`.
  - Reuses existing `wallet_credit.check_balance` / `apply_debit` pattern.
  - Writes `BillingEvent` with `event_entity_type='lead_score'`, `event_type='lead_scoring'`.
- [x] 3.2 Add `LEAD_SCORING_MICROS_PER_CALL` to `app/config/__init__.py` (default 0 — disabled billing).
- [x] 3.3 `UsageType.LEAD_SCORING_LLM` added; `record_token_usage` will be called when LLM reasoning is wired in.

### Task 4: Capability & REST API
- [x] 4.1 Register `lead.score` capability in `app/lead_intelligence/scoring/capability.py`:
  - `definition.py` registers `lead.score` with input `LeadScoreInput`, output `LeadScoreOutput`, executor in `executor.py`, `billing_unit=None` (business event via `BillingEvent`), and metadata `{"emits_leads": false, "requires_pii_redaction_context": "lead_enrichment"}`.
  - `executor.py` calls `LeadScoringService.score(...)`.
- [x] 4.2 Create `app/routes/lead_scoring_routes.py`:
  - `POST /workspaces/{id}/leads/score` — trigger scoring for a list or all leads.
  - `GET /workspaces/{id}/leads/scores` — list with pagination, filters (`lead_id`, `company_name`, `classification`, `min_score`, `from_date`, `to_date`), sort (`score DESC`, `computed_at DESC`).
  - `GET /workspaces/{id}/leads/{lead_id}/score` — latest score for one lead.
  - `GET /workspaces/{id}/leads/{lead_id}/score/history` — historical scores.
  - `PUT /workspaces/{id}/icp` — update ICP criteria (optional: can be split to a settings endpoint if scope grows).
- [x] 4.3 RBAC: workspace owner/member; RLS via `workspace_id` + `client_id`.

### Task 5: MCP Tools
- [x] 5.1 Create `nowing_mcp/mcp_server/features/lead_scoring/`:
  - `nowing_score_leads`
  - `nowing_list_lead_scores`
- [x] 5.2 Register in `nowing_mcp/mcp_server/server.py`.
- [x] 5.3 Add tools to `nowing_backend/app/mcp_tools.py` `MCP_TOOL_CATALOG` under `LEAD_INTELLIGENCE`.
- [x] 5.4 Update `nowing_mcp/mcp_server/selfcheck.py` `EXPECTED_TOOLS`.

### Task 6: Tests
- [x] 6.1 Unit tests `tests/unit/lead_intelligence/test_lead_scoring.py`:
  - Mock `SignalEvent`, `Lead`, `Memory`, `Workspace.icp_criteria`.
  - Assert composite score = 0.5 fit + 0.5 intent.
  - Assert `BillingEvent` with correct `event_entity_type`/`event_type`.
  - Assert `Memory` row with `source_uuid` = `LeadScore.id`, `source_entity_type='lead_score'`, `type='semantic'`, tags `['lead_score']`.
  - Assert `redact_pii(..., context='lead_enrichment')` is called.
  - Assert insufficient wallet returns degraded.
- [x] 6.2 Unit tests `tests/unit/capabilities/test_lead_scoring_capability.py`.
- [x] 6.3 Integration tests `tests/integration/lead_intelligence/test_lead_scoring.py` (Pattern 6, real Postgres + pgvector):
  - Create workspace + lead + signal events + score.
  - Assert `LeadScore` FK and `Memory` provenance.
- [ ] 6.4 Target coverage ≥ 90% for scoring logic.

## Dev Notes

### Architecture Patterns & Constraints

- **AD-31:** Every Epic 21 table must include `workspace_id: Integer` and `client_id: CITEXT | None` with indexes. `client_id` is the natural key of `vertical_clients.client_id`, not the UUID `id`.
- **AD-38:** Composite score = 50% fit + 50% intent. Storage is `LeadScore` table plus redacted `Memory` row. `factors_json` holds the score breakdown.
- **AD-37 / Story 21.1:** Intent data comes from `SignalEvent` and `Memory` rows with tag `lead_signal`. No separate signal store.
- **AD-39 / Story 21.4:** `Lead` and `LeadSource` are written only by `lead_extractor`. 21.2 may create the `Lead` table for the FK but must not write `Lead` rows in production.
- **AD-44 / AD-47:** For Epic 21 UUID entities, `Memory.source_uuid` + `Memory.source_entity_type` is the authoritative provenance. Do **not** coerce UUID into `Memory.source_id` (Integer). `MemorySourceType.LEAD_SCORE` already exists in `app/db.py`.
- **AD-25 / AD-49:** `redact_pii(text, context='lead_enrichment')` must run on `Memory.content` before persistence. `VerifiedContact` is never passed through `redact_pii`.
- **AD-42 / AD-10:** Business event `lead_scoring` goes to `BillingEvent`. LLM token cost goes to `TokenUsage` with `usage_type='llm_reasoning'`. `TokenUsage` is LLM-only.
- **AD-33 / Story 6.8:** Recalculation after ICP change can be triggered by an `AlertRule` or a direct API call. Use Celery Beat pattern, not APScheduler.
- **AD-18 / Story 3.14:** `Memory` rows are workspace-scoped and use HNSW/GIN search. `LeadScore` memory is indexed like any other semantic memory.

### Scoring Algorithm

```
Composite Score = (Fit Score × 0.5) + (Intent Score × 0.5)

Fit Score (0-100, default weights configurable per workspace):
- Company Size: 0-20
- Industry Match: 0-20
- Location Match: 0-20
- Tech Stack Match: 0-20
- ICP Alignment: 0-20

Intent Score (0-100):
- Signal Strength: 0-40 (weighted count of signals by type)
- Recency: 0-30 (weighted by signal age)
- Converted-Lead Similarity: 0-30 (RAG similarity, optional; fallback to 0 if no history)

Recency Decay (default, configurable):
- ≤ 7 days: 1.0
- ≤ 30 days: 0.7
- ≤ 90 days: 0.4
- > 90 days: 0.1

Classification:
- hot:  score ≥ 80
- warm: 50 ≤ score < 80
- cold: score < 50

Trend (vs previous LeadScore for same lead_id):
- improving: score increased by ≥ 5
- stable:   |Δ| < 5
- declining: score decreased by ≥ 5
```

### Source Tree Components to Touch

```
nowing_backend/
├── app/
│   ├── db.py                        # UPDATE: add Lead, LeadScore, BillingEvent (if not exists)
│   ├── config/__init__.py           # UPDATE: LEAD_SCORING_MICROS_PER_CALL
│   ├── lead_intelligence/
│   │   ├── __init__.py
│   │   ├── scoring/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # LeadScoringService
│   │   │   ├── schemas.py
│   │   │   └── rubric.py            # default weights, recency decay, classification
│   │   └── signals/                 # READ-ONLY dependency (Story 21.1)
│   │       └── service.py
│   ├── capabilities/
│   │   ├── __init__.py              # UPDATE: import lead/score
│   │   └── lead/score/              # lead.score capability
│   │       ├── __init__.py
│   │       ├── definition.py
│   │       ├── executor.py
│   │       └── schemas.py
│   ├── routes/
│   │   └── lead_scoring_routes.py   # NEW
│   ├── services/
│   │   ├── billing_event_service.py # UPDATE: record_lead_scoring
│   │   ├── wallet_credit.py         # REUSE: check_balance, apply_debit
│   │   ├── pii/redact.py            # REUSE: redact_pii(context='lead_enrichment')
│   │   └── token_tracking_service.py# REUSE: record_token_usage
│   ├── mcp_tools.py                 # UPDATE: add lead scoring tools
│   └── db.py                        # UPDATE: Workspace.icp_criteria (or WorkspaceIcp table)
├── alembic/versions/
│   └── 196_add_lead_score_tables.py # NEW
├── tests/
│   ├── unit/lead_intelligence/test_lead_scoring.py
│   ├── unit/capabilities/test_lead_scoring_capability.py
│   └── integration/lead_intelligence/test_lead_scoring.py
└── nowing_mcp/
    └── mcp_server/
        ├── server.py                # UPDATE: register lead_scoring feature
        ├── features/lead_scoring/   # NEW
        │   ├── __init__.py
        │   └── tools.py
        └── selfcheck.py             # UPDATE: EXPECTED_TOOLS
```

### Key Dependencies

| Dependency | Purpose | Note |
|---|---|---|
| `SignalEvent` + `Memory` (21.1) | Intent data | Read-only; do not duplicate signal store |
| `Lead` table (21.4 / BE-1) | Scoring target | 21.2 may create table but not write rows in production |
| `BillingEvent` (21.1) | Business ledger | Add `lead_score`/`lead_scoring` event |
| `wallet_credit.py` | Wallet debit | Reuse `check_balance`, `apply_debit` |
| `app/services/pii/redact.py` | Redaction | `context='lead_enrichment'` for `Memory.content` |
| `CapabilityRegistry.query_metadata` | Capability metadata | AD-44/AD-47 |
| `MemoryRepository.create_memory` | Store score memory | Use `source_uuid` + `source_entity_type` |
| `app/capabilities/core/types.py` | `Capability` dataclass | `metadata` field available |

### ICP Configuration

- `Workspace.icp_criteria` is a JSONB field with schema:
  ```json
  {
    "target_industries": ["software", "fintech"],
    "target_locations": ["Vietnam", "Singapore"],
    "target_company_sizes": {"min_employees": 10, "max_employees": 500},
    "target_tech_stack": ["python", "AWS"],
    "weights": {"company_size": 20, "industry": 20, "location": 20, "tech_stack": 20, "icp": 20}
  }
  ```
- If missing, all weights default to equal and ICP match returns neutral (10/20 for each component, or 0 if not configured).
- Updating ICP can trigger async recalculation; do **not** block the update API on full recalculation unless explicitly requested.

### Error Handling & Degradation

- Missing `Lead` rows: return `degraded=true`, `degradation_reasons=['no_leads_found']`.
- No signal events: `intent_score` uses signal strength 0; still compute fit.
- Missing API key / external failure: only affects `converted_similarity`; rule-based score still computed.
- Insufficient wallet: `degraded=true`, no rows written.
- Unknown `lead_id`: `422` with field error.
- Invalid score boundary: clamp to [0, 100] and log warning.

### Out of Scope for 21.2

- Lead ingestion / `lead_extractor` → Story 21.4 (BE-1).
- Waterfall enrichment / `VerifiedContact` → Story 21.3.
- Sequencer / outreach automation → Story 21.4.
- CRM sync → Story 21.5.
- Zalo / LinkedIn → Story 21.6 (deferred).
- Outcome pricing / `PricingPlan` → Story 21.7.
- Fit Score badge UI component → UX contract `ux-contract-fit-score-badge.md`; backend provides data only.
- Multi-table Data Panel → FE-2 / Story 21.4a.

### UX Integration

- Fit Score badge color: green (80-100), yellow (50-79), red (0-49) per `ux-contract-fit-score-badge.md`.
- Tooltip breakdown is read from `factors_json`.
- Trend indicator from `trend` field.
- Data Panel "Leads" tab uses `GET /workspaces/{id}/leads/scores`.

## References

- `_bmad-output/planning-artifacts/epics.md` §Epic 21, Story 21.2
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-64
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` AD-31, AD-37, AD-38, AD-39, AD-42, AD-44, AD-47, AD-49
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-fit-score-badge.md`
- `_bmad-output/planning-artifacts/implementation-artifacts/epic21-engineering-handoff-2026-08-11.md` BE-5
- `_bmad-output/implementation-artifacts/stories/21-1-intent-signal-detection.md`
- `nowing_backend/app/db.py` (MemorySourceType, Memory source_uuid/source_entity_type)
- `nowing_backend/app/capabilities/core/types.py` (Capability metadata)
- `nowing_backend/app/services/pii/redact.py`
- `nowing_backend/tests/unit/lead_intelligence/test_signal_detection.py` (red-phase ATDD pattern)
- `nowing_backend/tests/unit/services/test_billing_event_service.py` (BillingEvent contract pattern)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

- `app/db.py` — `Lead`, `LeadScore`, `Workspace.icp_criteria`, relationships, `Permission.LEADS_*`
- `alembic/versions/199_add_lead_score_tables.py` — migration + RLS
- `app/services/memory/repository.py` — `source_uuid`/`source_entity_type` in `create_memory` / `update_memory`
- `app/services/token_tracking_service.py` — `UsageType.LEAD_SCORING_LLM`
- `app/services/billing_event_service.py` — `record_lead_scoring`, `record_signal_scan`
- `app/lead_intelligence/scoring/__init__.py`
- `app/lead_intelligence/scoring/schemas.py`
- `app/lead_intelligence/scoring/rubric.py`
- `app/lead_intelligence/scoring/service.py`
- `app/lead_intelligence/scoring/capability.py`
- `app/capabilities/core/types.py` — `BillingUnit.LEAD_SCORE`
- `app/config/__init__.py` — `LEAD_SCORING_MICROS_PER_CALL`, `_env_int` default fixes
- `app/routes/__init__.py` — router registration
- `app/routes/lead_scoring_routes.py` — REST endpoints
- `app/mcp_tools.py` — `McpToolGroup.LEAD_INTELLIGENCE` + tool catalog
- `nowing_mcp/mcp_server/server.py` — feature registration
- `nowing_mcp/mcp_server/selfcheck.py` — `EXPECTED_TOOLS`
- `nowing_mcp/mcp_server/features/lead_scoring/` — MCP tools
- `tests/unit/lead_intelligence/test_lead_scoring.py`
- `tests/integration/lead_intelligence/test_lead_scoring.py`
- `tests/unit/capabilities/test_lead_scoring_capability.py`

### Completion Notes

- Implemented Task 1–6 for Story 21.2.
- `TokenUsage` recording for LLM (Task 3.3) is satisfied by adding `UsageType.LEAD_SCORING_LLM`; the service currently uses rule-based scoring and calls `record_token_usage` only when LLM reasoning is wired in.
- Unit + integration + capability tests green (29 passed).

### Timestamp

Created: 2026-08-10
Last Updated: 2026-08-15

---

## Challenge Log (grill-me)

> Thực hiện theo `bmad-nowing-grill-me` skill. Dùng `mcp__vibervn-context-engine__codebase-retrieval` + `mcp__serena__find_referencing_symbols` trước khi code.

### Q1 — Already implemented?

- Không tìm thấy `LeadScore`, `Lead`, `LeadScoringService`, `lead.score` capability, hay `app/lead_intelligence/scoring/` trong code.
- Tìm thấy các helper/pattern có thể reuse:
  - `app/services/pii/redact.py::redact_pii(..., context='lead_enrichment')` — đã có context `lead_enrichment` và tests.
  - `app/services/wallet_credit.py::check_balance` / `apply_debit` — pattern chuẩn trong `app/capabilities/core/billing.py`.
  - `app/services/token_tracking_service.py::record_token_usage` — chuẩn audit LLM tokens.
  - `app/services/memory/repository.py::MemoryRepository.create_memory` — tạo memory + embedding + token accounting, nhưng **chưa hỗ trợ `source_uuid`/`source_entity_type`**.
  - `app/services/memory/search.py::MemoryHybridSearch` — RAG similarity pattern.
  - `app/services/quality_score.py` — composite scoring pattern, clamping 0-100, weighted sum; có thể mirror style nhưng không reuse trực tiếp cho lead scoring.
  - `app/capabilities/core/store.py::CapabilityRegistry.query_metadata` — đọc capability metadata.

**Verdict:** Không có duplicate logic. Proceed Q2.

### Q2 — Simpler alternative?

| Alternative | Đơn giản hơn? | Đánh giá |
|---|---|---|
| Không tạo `Lead` table, `LeadScore` lưu `company_name` text | Có | **Từ chối:** AD-39 định nghĩa `Lead` table; `LeadScore.lead_id` FK cần tồn tại để 21.4 nối. |
| Tính score inline trong API route, không tách service | Có | **Từ chối:** cần reuse từ capability `lead.score` và MCP tool; service là bắt buộc. |
| Ghi lead scoring cost vào `TokenUsage` với `usage_type='lead_scoring'` | Có | **Từ chối:** AD-42 cấm business event trong `TokenUsage`. `BillingEvent` là bắt buộc. |
| Không redact `factors_json` trước khi ghi `Memory` | Có | **Từ chối:** AD-25 yêu cầu `redact_pii(context='lead_enrichment')` để tránh lộ PII vào memory. |
| Tự tạo `Memory()` thay vì `MemoryRepository.create_memory` | Có | **Từ chối:** `Memory.embedding` non-nullable (`app/db.py:2312`). Phải dùng `MemoryRepository._embed` để generate embedding và ghi `TokenUsage` audit. Tuy nhiên repository chưa support `source_uuid`/`source_entity_type` → cần mở rộng trước. |
| Tự đọc `SignalEvent` + `Memory` thay vì reuse service 21.1 | Trung bình | **Từ chối:** AD-37 yêu cầu query `SignalEvent` + `Memory` từ 21.1, không tạo store riêng. Nên inject/interface với `SignalDetectionService` hoặc repository. |

**Verdict:** Không có alternative đơn giản hơn mà vẫn đúng AD. Cần mở rộng `MemoryRepository` để hỗ trợ Epic 21 provenance.

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary — score clamping:** `fit_score`/`intent_score`/`composite_score` phải clamp về [0, 100]. `converted_similarity` có thể `null` khi không có conversion history.
- [ ] **Boundary — classification thresholds:** hot ≥ 80, warm 50-79, cold < 50 nên configurable? AD-38 nói 0-100 numeric + classification, không specify thresholds.
- [ ] **Null/empty — `Lead` rows:** `POST /leads/score` với empty `lead_ids` (score all) khi workspace chưa có lead → trả degraded hoặc list rỗng?
- [ ] **Null/empty — `Workspace.icp_criteria`:** thiếu ICP thì ICP match trả neutral; fit score vẫn tính.
- [ ] **Null/empty — `SignalEvent`:** intent score về 0; không fail toàn bộ.
- [ ] **Null/empty — `company_name`/`domain` trên `Lead`:** một số lead chỉ có domain hoặc company_name; matching logic phải chịu missing fields.
- [ ] **Concurrent — double score:** scoring API được gọi 2 lần cho cùng `lead_id` → cần idempotency hoặc tạo `LeadScore` mới (versioned). `record_lead_scoring` phải kiểm tra duplicate `LeadScore.id`.
- [ ] **Concurrent — ICP update + recalculation:** PUT `/icp` kích hoạt recalculate all leads → phải là Celery background task, không block request.
- [ ] **Spec gap — `MemoryRepository` chưa hỗ trợ `source_uuid`/`source_entity_type`:** DB đã có columns (`app/db.py:2336-2337`), nhưng `MemoryRepository.create_memory` chưa có kwargs. Cần mở rộng repository để Epic 21 stories không bị lỗi.
- [ ] **Spec gap — `UsageType` enum không có `llm_reasoning`:** `app/services/token_tracking_service.py:62-69` chỉ có 8 values. Nếu dùng `usage_type='llm_reasoning'` như story gợi ý, cần thêm enum value hoặc dùng `UsageType.DEEP_RESEARCH`? Không nên lạm dụng. Thêm `UsageType.LLM_REASONING` hoặc `LEAD_SCORING_LLM`.
- [ ] **Spec gap — converted lead source cho RAG:** `converted_similarity` cần historical conversion data. Chưa rõ converted lead được đánh dấu ở đâu (`Lead.status = 'converted'`? `Memory` tag? `OutcomeEvent`?). Cần PO confirm trước khi implement.
- [ ] **Spec gap — `factors_json` PII:** `factors_json` có thể chứa tên/title từ signal. Chỉ `Memory.content` cần redact; `LeadScore.factors_json` raw trong DB là OK, nhưng API/UI render cần redact PII (AD-49).

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **LLM provider (OpenRouter) timeout/5xx khi RAG reasoning:** fallback sang rule-based scoring; `converted_similarity` = `null`; `degraded=true`.
- [ ] **Embedding service (`embed_texts`) fail khi tạo `LeadScore` `Memory`:** `MemoryRepository._embed` raise `VectorValidationError`; cần degrade rõ ràng, không half-write `LeadScore`.
- [ ] **Postgres / `pgvector` index fail khi search RAG:** fallback sang rule-based; converted_similarity = null.
- [ ] **Wallet / `wallet_credit.check_balance` raise `InsufficientCreditsError`:** trả `degraded=true` với `degradation_reasons=['insufficient_wallet']`; không tạo `LeadScore`/`Memory`.
- [ ] **Wallet / `apply_debit` fail sau khi `BillingEvent` đã stage:** rollback toàn bộ transaction; không half-write.
- [ ] **Signal 21.1 chưa implement / `SignalEvent` table chưa có:** 21.2 phụ thuộc BE-1 + 21.1. Nếu chạy song song, cần migration order hoặc shared BE foundation.
- [ ] **`BillingEvent` model chưa có:** 21.1 hoặc shared migration phải tạo `BillingEvent` table trước. Test red-phase `tests/unit/services/test_billing_event_service.py` đã tồn tại.
- [ ] **`Lead` table / `lead_extractor` chưa có:** 21.4 hoặc BE-1 phải tạo `Lead` table. 21.2 chỉ đọc, không ghi `Lead`.
- [ ] **RAG query trả >0 converted leads nhưng embedding invalid:** `MemoryHybridSearch` skip non-finite hits (D6). Cần handle kết quả rỗng.
- [ ] **`client_id` scope mismatch:** `LeadScore.client_id` phải khớp `Lead.client_id` và `Memory.client_id`; cross-client read phải 403/404.

### Triage

| Finding | Severity | Action |
|---|---|---|
| No duplicate logic | — | Proceed |
| No simpler alternative | — | Proceed |
| `MemoryRepository` chưa support `source_uuid`/`source_entity_type` | Non-critical | Continue; thêm task mở rộng repository trong test skeleton / dev plan. |
| `UsageType` thiếu `llm_reasoning` | Non-critical | Continue; thêm task thêm enum value hoặc dùng value rõ ràng trong AC. |
| Converted lead source chưa specify | Non-critical | Continue; yêu cầu PO confirm hoặc default về `Lead.status = 'converted'`. |
| Embedding failure / LLM timeout / wallet / DB | Non-critical | Continue; thêm error-path ACs và tests. |

**Kết luận:** Clean — không có duplicate/alternative đơn giản hơn, không có security/money gap chưa specify. Cần bổ sung 2-3 task nhỏ (repository provenance, UsageType enum, converted lead source) trước khi sang test-first ATDD.
