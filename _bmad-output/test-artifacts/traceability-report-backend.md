---
stepsCompleted: ['step-01-load-context', 'step-02-discover-tests', 'step-03-map-criteria', 'step-04-analyze-gaps', 'step-05-gate-decision']
lastStep: 'step-05-gate-decision'
lastSaved: '2026-04-21'
workflowType: 'testarch-trace'
inputDocuments: ['nowing_backend/tests/**', '_bmad-output/planning-artifacts/epics.md', '_bmad-output/architecture-backend.md']
---

# Traceability Matrix & Gate Decision — Backend (nowing_backend)

**Scope:** nowing_backend · Python FastAPI · Stories 1.2, 2.1–2.2, 3.1–3.2, 3.5, 5.2–5.4, 6.1–6.5, 6.8, 7.1–7.4  
**Date:** 2026-04-21  
**Evaluator:** BMad TEA Agent (Murat)  
**Framework:** pytest 9.x · pytest-asyncio · pytest-mock · pytest-xdist · uv  

---

Note: Workflow does not generate tests. If gaps exist, run `*atdd` or `*automate` to create coverage.

---

## PHASE 1: REQUIREMENTS TRACEABILITY

### Coverage Summary

| Priority  | Total Criteria | FULL Coverage | Coverage % | Status      |
| --------- | -------------- | ------------- | ---------- | ----------- |
| P0        | 2              | 1             | 50%        | ❌ FAIL     |
| P1        | 7              | 5             | 71%        | ❌ FAIL     |
| P2        | 6              | 1             | 17%        | ⚠️ WARN     |
| P3        | 0              | —             | —          | —           |
| **Total** | **15**         | **7**         | **46.7%**  | ❌ **FAIL** |

---

### Detailed Mapping

#### Story 1.2: Backend Auth API & JWT (P0)

- **AC BE-1:** JWT issued on valid credentials, 401 on invalid — **NONE** ❌
- **Tests:** No `test_auth_routes.py` or JWT-specific test file found
- **Heuristics:**
  - Endpoint `/auth/login` → **NOT tested**
  - Auth negative-path (401, invalid token) → **MISSING**
  - Error-path (expired token, malformed JWT) → **MISSING**

---

#### Story 2.1: Celery Worker & PDF Parser (P1)

- **AC BE-2:** Documents chunked, embedded, stored in pgvector — **FULL** ✅
- **Tests:**
  - `tests/unit/indexing_pipeline/test_document_chunker.py` — chunking logic
  - `tests/unit/indexing_pipeline/test_document_hashing.py` — dedup hashing
  - `tests/unit/indexing_pipeline/test_document_summarizer.py` — summarization
  - `tests/unit/indexing_pipeline/test_index_batch.py` — batch indexing
  - `tests/unit/indexing_pipeline/test_index_batch_parallel.py` — parallel indexing
  - `tests/unit/indexing_pipeline/test_create_placeholder_documents.py` — placeholder creation
  - `tests/unit/indexing_pipeline/test_prepare_placeholder_dedup.py` — dedup
  - `tests/integration/indexing_pipeline/test_index_batch.py` — integration
  - `tests/integration/indexing_pipeline/test_index_document.py` — end-to-end indexing
  - `tests/integration/indexing_pipeline/test_prepare_for_indexing.py`
- **Coverage level:** UNIT + INTEGRATION ✅

---

#### Story 2.2: Upload API & Rate Limiting (P1)

- **AC BE-3:** POST upload returns 200, page limits enforced — **PARTIAL** ⚠️
- **Tests:**
  - `tests/integration/document_upload/test_document_upload.py` — happy path + 401
  - `tests/integration/document_upload/test_upload_limits.py` — upload limits
  - `tests/integration/document_upload/test_page_limits.py` — page limit enforcement
  - `tests/unit/connector_indexers/test_page_limits.py` — unit page limits
  - `tests/unit/connector_indexers/test_page_limit_estimation.py`
- **Missing:** Rate limit enforcement (HTTP 429 response) not directly tested at route level
- **Heuristics:** Upload endpoint tested; rate limit negative-path (429) → **PARTIAL**

---

#### Story 3.1: Chat Session API (P1)

- **AC BE-4:** POST /chat/session creates session, returns session_id — **NONE** ❌
- **Tests:** No `test_chat_routes.py` or `test_session` found
- **Heuristics:**
  - `/chat/session` endpoint → **NOT tested** at route level
  - Auth requirement on chat routes → **NOT tested**
- **Note:** `test_knowledge_search.py` (middleware) covers RAG search logic but NOT the route/session API layer

---

#### Story 3.2: RAG Engine & SSE Endpoint (P0)

- **AC BE-5:** SSE stream returns content chunks with citations — **PARTIAL** ⚠️
- **Tests:**
  - `tests/unit/middleware/test_knowledge_search.py` — RAG retrieval middleware (20 tests)
  - `tests/unit/middleware/test_dedup_hitl_tool_calls.py` — HITL dedup middleware
  - `tests/unit/tasks/test_stream_chainlens_tool_start.py` — streaming events (chainlens specific)
  - `tests/unit/tasks/test_stream_chainlens_tool_end_events.py`
  - `tests/integration/retriever/test_optimized_chunk_retriever.py`
  - `tests/integration/retriever/test_optimized_doc_retriever.py`
- **Missing:** SSE endpoint itself (`/chat/stream`) not tested; no test for full RAG→SSE pipeline; citation format not validated
- **Coverage level:** UNIT-ONLY (middleware/retriever covered, route-level SSE NOT covered)

---

#### Story 3.5: Model Selection via Quota (P2)

- **AC:** Subscription tier gates LLM model choices — **NONE** ❌
- **Tests:** No test for model quota enforcement found
- **Heuristics:** Quota enforcement logic not tested

---

#### Story 5.2: Stripe Payment Integration (P1)

- **AC BE-6:** Stripe checkout session created, returns URL — **FULL** ✅
- **Tests:**
  - `tests/integration/document_upload/test_stripe_checkout.py` — checkout creation, 503 on disabled (3 tests)
  - `tests/integration/document_upload/test_stripe_page_purchases.py` — page purchase flow
- **Heuristics:**
  - Checkout endpoint covered ✅
  - Error path (Stripe unavailable → 503) covered ✅

---

#### Story 5.3: Stripe Webhook Sync (P1)

- **AC BE-7:** Webhook receives `payment_intent.succeeded`, grants pages — **FULL** ✅
- **Tests:**
  - `tests/integration/document_upload/test_stripe_webhook.py` — webhook grants pages (idempotency)
  - `tests/integration/document_upload/test_stripe_reconciliation.py` — reconciliation fulfills pending, marks expired failed
- **Heuristics:**
  - Webhook endpoint tested ✅
  - Idempotency (grant once) tested ✅
  - Reconciliation tested ✅

---

#### Story 5.4: Usage Tracking & Rate Limit Enforcement (P2)

- **AC:** Quota exceeded → 429 with upgrade prompt — **NONE** ❌
- **Tests:** No `test_quota_enforcement` or `test_rate_limit_*` found for this story
- **Heuristics:** Quota-exceeded negative path not tested

---

#### Story 6.1–6.5: Gift System Backend (P2)

- **AC:** Gift code creation, webhook fulfillment, redeem, history — **NONE** ❌
- **Tests:** No test files found for gift system (`test_gift_*`, `test_redeem_*`)
- **Heuristics:**
  - Gift checkout endpoint → NOT tested
  - Redeem validation (code expired, already used) → NOT tested
  - Webhook gift fulfillment → NOT tested

---

#### Story 6.8: Admin Gift Requests API (P2)

- **AC:** Admin approve/reject endpoint with row lock — **NONE** ❌
- **Tests:** No admin gift route tests found
- **Heuristics:** Admin authz (non-admin → 403) not tested

---

#### Story 7.1: ChainlensResearchService (P1)

- **AC BE-8:** `is_available()` returns True on 200, False on network error; cache respects TTL — **FULL** ✅
- **Tests:**
  - `tests/unit/services/test_chainlens_research_service.py`
    - `test_is_available_returns_false_without_network`
    - `test_is_available_health_check_returns_true_on_200`
    - `test_is_available_caches_result_within_ttl`
    - `test_is_available_returns_false_during_error_cooldown`
  - `tests/unit/app/test_chainlens_rollback_integration.py` — rollback/availability flow (5 tests)

---

#### Story 7.2: LangGraph Tool — chainlens_deep_research (P1)

- **AC BE-9:** Tool invokes service, fallback returns `{"status": "fallback"}`, no exception raised — **FULL** ✅
- **Tests:**
  - `tests/unit/agents/new_chat/tools/test_chainlens_research_tool.py` (16 tests)
    - Happy path, unavailable fallback, exception fallback, timeout fallback
    - Neutral event dispatch (no vendor name leakage)
    - `switching_event` on unavailable

---

#### Story 7.3: Intent Detection & Streaming Response (P1)

- **AC BE-10:** Agent streams tool_start/tool_end events; neutral messages; timeout handling — **FULL** ✅
- **Tests:**
  - `tests/unit/tasks/test_stream_chainlens_tool_start.py` (4 tests) — query truncation, blank query, neutral emit
  - `tests/unit/tasks/test_stream_chainlens_tool_end_events.py` (9 tests) — success/fallback/zero sources events, vendor leakage prevention
  - `tests/unit/tasks/test_stream_new_chat_chainlens.py` — integration streaming test
  - `tests/unit/agents/new_chat/tools/test_chainlens_intent_routing.py` — intent routing

---

#### Story 7.4: Feature Flag & Config Validation (P2)

- **AC BE-11:** `_validate_chainlens_config()` logs correct warnings on missing vars, never raises — **FULL** ✅
- **Tests:**
  - `tests/unit/app/test_chainlens_config_validation.py` (8 tests)
    - disabled/enabled states, missing vars, whitespace-only vars, consolidated warnings, exception safety

---

## PHASE 1: COVERAGE HEURISTICS

### Endpoints Without Tests

| Endpoint                  | Story  | Tested |
| ------------------------- | ------ | ------ |
| `POST /auth/login`        | 1.2    | ❌     |
| `POST /auth/refresh`      | 1.2    | ❌     |
| `POST /chat/session`      | 3.1    | ❌     |
| `GET /chat/stream` (SSE)  | 3.2    | ❌     |
| `POST /gift/checkout`     | 6.2    | ❌     |
| `POST /gift/redeem`       | 6.4    | ❌     |
| `GET /gift/history`       | 6.5    | ❌     |
| `POST /admin/gift-approve`| 6.8    | ❌     |

### Auth/AuthZ Missing Negative Paths

| Scenario                              | Story | Status   |
| ------------------------------------- | ----- | -------- |
| Invalid JWT → 401                     | 1.2   | ❌ MISS  |
| Expired token → 401                   | 1.2   | ❌ MISS  |
| Non-admin accessing admin route → 403 | 6.8   | ❌ MISS  |
| Unauthenticated upload → 401          | 2.2   | ✅ (partial in integration) |

### Happy-Path-Only Criteria

| Criterion                          | Story | Status            |
| ---------------------------------- | ----- | ----------------- |
| Rate limit (429 response)          | 2.2   | ⚠️ Partial        |
| Quota exceeded (LLM model gate)    | 3.5   | ❌ None           |
| Gift code expired/used → 422       | 6.4   | ❌ None           |
| SSE stream timeout/disconnect      | 3.2   | ❌ None           |

---

## PHASE 2: GATE DECISION

### Gate Criteria

| Criterion                   | Required | Actual | Status      |
| --------------------------- | -------- | ------ | ----------- |
| P0 Coverage                 | 100%     | 50%    | ❌ NOT MET  |
| P1 Coverage                 | ≥ 90%    | 71%    | ❌ NOT MET  |
| Overall Coverage            | ≥ 80%    | 46.7%  | ❌ NOT MET  |

### 🚨 GATE DECISION: FAIL

**Rationale:** P0 coverage is 50% (required: 100%). Story 1.2 Backend Auth API — the JWT authentication layer — has zero test coverage. The `/auth/login` endpoint, token validation, and 401/403 error paths are completely untested. Additionally, P1 coverage is 71% (target: 90%) with critical gaps in Chat Session API (Story 3.1) and the SSE streaming route (Story 3.2 route-level). Overall coverage at 46.7% is well below the 80% minimum.

---

## Recommendations

### 🔴 URGENT — P0 Blocker

| ID    | Action                                                                                    |
| ----- | ----------------------------------------------------------------------------------------- |
| R-001 | Create `tests/unit/routes/test_auth_routes.py` — cover POST /auth/login (200, 401, 422), POST /auth/refresh (200, 401 expired), and JWT decode validation |

### 🟠 HIGH — P1 Gaps

| ID    | Action                                                                                    |
| ----- | ----------------------------------------------------------------------------------------- |
| R-002 | Create `tests/unit/routes/test_chat_routes.py` — POST /chat/session (200 with session_id, 401 unauth, 422 invalid body) |
| R-003 | Create `tests/integration/test_sse_stream.py` — GET /chat/stream SSE endpoint: verify chunks arrive, citations present, stream closes cleanly |
| R-004 | Expand `test_upload_limits.py` — add HTTP 429 assertion when rate limit exceeded |

### 🟡 MEDIUM — P2 Gaps

| ID    | Action                                                                                    |
| ----- | ----------------------------------------------------------------------------------------- |
| R-005 | Create `tests/unit/routes/test_gift_routes.py` — cover checkout creation, redeem (success + expired/used), history endpoint |
| R-006 | Create `tests/unit/routes/test_admin_gift_routes.py` — admin approve/reject, 403 on non-admin |
| R-007 | Add quota enforcement test — model gating returns correct model based on subscription tier |

### 🟢 LOW

| ID    | Action                                                                                    |
| ----- | ----------------------------------------------------------------------------------------- |
| R-008 | Run `bmad-testarch-test-review` on connector indexer tests (208 tests) — validate quality/naming conventions |

---

## Open Items

| ID    | Description                                  | Priority | Status  |
| ----- | -------------------------------------------- | -------- | ------- |
| GAP-1 | Auth API (Story 1.2) — 0% coverage           | P0       | ❌ Open |
| GAP-2 | Chat Session API route (Story 3.1)           | P1       | ❌ Open |
| GAP-3 | SSE Stream route (Story 3.2)                 | P1       | ❌ Open |
| GAP-4 | Gift system backend (Stories 6.1–6.5, 6.8)  | P2       | ❌ Open |
| GAP-5 | Model quota enforcement (Story 3.5/5.4)      | P2       | ❌ Open |

---

## 🚫 GATE: FAIL — Release BLOCKED until P0 + P1 coverage improves

**Next recommended actions:**
1. **[AT]** `bmad-testarch-automate` — generate tests cho GAP-1 (auth routes) ngay, đây là P0 blocker
2. **[AT]** `bmad-testarch-automate` — generate tests cho GAP-2 và GAP-3 (chat session + SSE)
3. **[RV]** `bmad-testarch-test-review` — sau khi tạo xong, verify quality trước khi re-run gate
