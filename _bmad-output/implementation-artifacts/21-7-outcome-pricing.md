---
story_key: 21-7-outcome-pricing
status: ready-for-dev
epic: 21
story: 7
---

# Story 21.7: Outcome-Based Pricing & Transparent Credit Ledger ($0 Chat & Credit Pay-as-you-go)

Status: ready-for-dev

<!-- Note: Governed by FR-69, AD-8, AD-10, AD-31, AD-42, AD-48 and Epic 21 Lead Gen Architecture -->

## Story

As a sales team founder or growth operator,
I want a transparent economic model with $0 cost for AI Chat & Sequencer and pay-as-you-go credits for verified leads and booked meetings, along with a real-time service breakdown ledger and promo code redemption,
So that software costs directly reflect business value generated and team usage is completely transparent.

## Acceptance Criteria

### AC-1 — $0 Chat & Sequencer Zero-Cost Invariants
**Given** an authenticated workspace on any pricing tier,
**When** users perform standard chat turns, prompt engineering, multi-table tab filtering/transforms, email sequence creation/enrollment, and CSV exports,
**Then** the cost recorded is 0 credits ($0.00 / 0 `cost_micros`).
**And** `TokenUsage` records generated during standard chat turns are marked with zero customer debit (`cost_micros = 0` when in $0 Chat policy), ensuring that token consumption is tracked for internal LLM observability without debiting the customer's wallet balance.

### AC-2 — Pay-As-You-Go Credit Rates & `BillingEvent` Debit Ledger
**Given** value-generating business actions or outcome events,
**When** recorded,
**Then** the system writes a `BillingEvent` row and debits `User.credit_micros_balance` via `wallet_credit.apply_debit` using the following exact tariff matrix:
- **Verified Phone Unlock (`phone_waterfall`):** 1.5 credits ($0.06 / 60,000 `cost_micros` / 1,500đ).
- **Deep Research Dossier (`deep_research`):** 5.0 credits ($0.20 / 200,000 `cost_micros` / 5,000đ).
- **Qualified Meeting Booked (`outcome_meeting_booked`):** 50.0 credits ($2.00 / 2,000,000 `cost_micros` / 50,000đ).
- **Enriched Lead Profile (`outcome_lead_enriched`):** 1.0 credits ($0.04 / 40,000 `cost_micros` / 1,000đ).
- **Custom Outcome Rate:** As defined in workspace active `PricingPlan.outcome_rates_json`.

**And** `BillingEvent` strictly complies with the AD-42 / AD-48 allowed matrix:
- `signal_event` → `signal_scan`
- `enrichment_request` → `contact_enrichment`
- `lead_score` → `lead_scoring`
- `sequence_event` → `email_send` (only for `SequenceEvent.event_type == 'sent'`)
- `outcome_event` → `outcome_meeting_booked` | `outcome_lead_enriched`

**And** `TokenUsage` remains strictly LLM-only. Business events must **never** write to `TokenUsage`.

### AC-3 — Data Models & Database Relationships (AD-42 / AD-31)
**Given** the database schema in `app/db.py`,
**When** migration 191 is applied,
**Then** the following models and constraints are created:
1. `OutcomeEvent`:
   - `id: UUID` (PK, default uuid4)
   - `workspace_id: Integer` (FK `workspaces.id`, ondelete CASCADE, index)
   - `client_id: CITEXT | None` (nullable, index)
   - `event_type: String(50)` (`outcome_meeting_booked` | `outcome_lead_enriched`)
   - `lead_id: UUID` (FK `leads.id`, ondelete CASCADE, index)
   - `sequence_id: UUID | None` (FK `sequences.id` if exists, ondelete SET NULL, index)
   - `attribution: String(100)` (e.g. `first_touch:seq_123`, `direct_chat`, `zalo_inbound`)
   - `cost_micros: BigInteger` (default 0)
   - `outcome_metadata: JSONB` (default `{}`)
   - `created_at: TIMESTAMP(timezone=True)` (default UTC now)
2. `PricingPlan`:
   - `id: UUID` (PK, default uuid4)
   - `workspace_id: Integer` (FK `workspaces.id`, ondelete CASCADE, index, unique per workspace)
   - `client_id: CITEXT | None` (nullable, index)
   - `plan_type: String(50)` (`seat` | `outcome` | `hybrid`, default `outcome`)
   - `seat_price: BigInteger | None` (micros per seat/month)
   - `outcome_rates_json: JSONB` (e.g. `{"meeting_booked": 2000000, "phone_unlock": 60000}`)
   - `billing_period: String(20) | None` (`monthly` | `annual`)
   - `is_active: Boolean` (default True)
3. `BillingEvent` Linkage:
   - Partial unique index: `ix_billing_events_outcome_unique` on `(event_id)` where `event_entity_type = 'outcome_event'`.
   - `cost_basis` in (`actual`, `estimated`, `refunded`).
4. `PromoCode` & `PromoCodeRedemption`:
   - `PromoCode`: `id: UUID`, `code: String(50)` (unique, uppercase index), `credit_micros_granted: BigInteger`, `max_uses: Integer | None`, `uses_count: Integer` (default 0), `expires_at: TIMESTAMP | None`, `is_active: Boolean` (default True).
   - `PromoCodeRedemption`: `id: UUID`, `user_id: UUID` (FK `user.id`), `promo_code_id: UUID` (FK `promo_codes.id`), `credit_micros_granted: BigInteger`, `redeemed_at: TIMESTAMP`, unique constraint on `(user_id, promo_code_id)`.

### AC-4 — First-Touch Outcome Attribution Engine
**Given** an outcome trigger (calendar meeting booked or webhook confirmation),
**When** `OutcomePricingService.record_meeting_booked(workspace_id, lead_id, ...)` is called,
**Then** the service queries previous interactions for `lead_id` (sequences enrolled, inbound chats, scraper origin), resolves the first-touch attribution identifier, inserts `OutcomeEvent`, writes matching `BillingEvent`, and debits `User.credit_micros_balance` atomically in a single DB transaction.

### AC-5 — Promo Code Claim & Anti-Abuse Engine
**Given** a user submitting a promo code via `POST /api/v1/credits/promo-code/claim`,
**When** the endpoint processes the claim:
- It normalizes the code string (`strip()`, `upper()`).
- Performs a row-level lock (`SELECT FOR UPDATE`) on the `PromoCode` record.
- Validates: `is_active == True`, `expires_at` is in the future (or None), and `uses_count < max_uses` (if `max_uses` is not None).
- Checks `PromoCodeRedemption` to guarantee the current user has not redeemed this specific promo code before (1-time per user).
- Increments `PromoCode.uses_count += 1`.
- Inserts `PromoCodeRedemption` record.
- Increments `User.credit_micros_balance += promo_code.credit_micros_granted`.
- Returns `200 OK` with `new_balance_micros` and `credit_micros_granted`.

### AC-6 — Unified Usage & Service Breakdown Ledger (`UsageService`)
**Given** the usage summary and breakdown endpoints,
**When** `UsageService.get_summary(...)` and `UsageService.get_service_breakdown(...)` are called,
**Then** the query combines both `TokenUsage` (LLM turns) and `BillingEvent` (business events) into 5 standardized service buckets:
1. `AI Generation` (LLM tokens, synthesis, prompt transforms — $0 on standard, metered if custom plan)
2. `Web Search` (SERP queries, crawl gap-fills, Exa/Chainlens search)
3. `Social Media` (XActions Facebook/Twitter ingestion & post extractions)
4. `Phone Waterfall` (Batdongsan/Chotot/BetterContact phone number decodes)
5. `Outcome Meetings` (Qualified booked meetings & outcome bonuses)

**And** `UsageTransactionsResponse` includes:
- `credit_purchase` (Stripe payments / Auto-reload)
- `incentive` (Onboarding tasks)
- `promo_code` (Redeemed gift codes)
- `outcome_debit` (Outcome meeting & enrichment debits)

### AC-7 — REST Endpoints
**Given** authenticated requests with proper workspace permissions,
**Then** the following REST endpoints operate as specified:
- `GET /api/v1/workspaces/{workspace_id}/pricing-plan` — Returns current plan and rate card (`PricingPlanRead`).
- `PUT /api/v1/workspaces/{workspace_id}/pricing-plan` — Updates pricing plan options (Admin/Owner only).
- `POST /api/v1/workspaces/{workspace_id}/outcomes/meeting-booked` — Records meeting outcome, executes attribution and debit.
- `POST /api/v1/credits/promo-code/claim` — Validates and claims promo code, crediting user wallet.
- `POST /api/v1/admin/promo-codes` — Admin creates new promo code campaigns (SuperAdmin only).
- `GET /api/v1/workspaces/{workspace_id}/usage/service-breakdown` — Returns categorized breakdown for charts.

### AC-8 — Frontend Usage Dashboard Overhaul
**Given** the `/dashboard/[workspace_id]/usage` page in `nowing_web`,
**When** rendered:
- **Donut & Bar Breakdown Charts:** Visual breakdown by the 5 service categories (`AI Generation`, `Web Search`, `Social Media`, `Phone Waterfall`, `Outcome Meetings`).
- **[ 🎁 Claim Promo Code ] Card:** Interactive input field with instant validation, loading spinner, celebratory toast feedback, and immediate React Query invalidation of wallet balance.
- **Outcome ROI Metrics:** Renders KPI summary cards for *Total Meetings Booked*, *Cost per Meeting*, and *Estimated ROI Multiplier*.

### AC-9 — Zero-Cache Sync & Real-Time Balance Reactivity
**Given** a promo code redemption or outcome billing debit,
**When** the transaction commits,
**Then** `user.credit_micros_balance` is replicated via Zero-cache (`zero.nowing.net`) so all open browser tabs and split-view action pills reflect updated credit balance with sub-100ms latency.

### AC-10 — Concurrency, Degradation & Error Handling
**Given** concurrent requests or insufficient wallet balance,
**When** an outcome or enrichment event occurs:
- If balance is insufficient, returns `degraded=true` / `402 Payment Required` with `degradation_reason="insufficient_wallet"` without creating orphaned DB records.
- If promo code is invalid, expired, or already claimed, returns clean `400 Bad Request` / `409 Conflict` with clear localized error message (`PROMO_CODE_EXPIRED`, `PROMO_CODE_ALREADY_USED`, `PROMO_CODE_INVALID`).

---

## Tasks / Subtasks

- [ ] Task 1: Database Models & Alembic Migration 191 (AC: 2, 3)
  - [ ] 1.1 Thêm model `OutcomeEvent`, `PricingPlan`, `PromoCode`, `PromoCodeRedemption` vào `nowing_backend/app/db.py`.
  - [ ] 1.2 Cập nhật `BillingEvent` indexes (Partial unique index `ix_billing_events_outcome_unique`).
  - [ ] 1.3 Tạo migration script `nowing_backend/alembic/versions/191_add_outcome_pricing_and_promo_codes.py`.
  - [ ] 1.4 Thêm các bảng mới vào `app/zero_publication.py` (`ensure_publication`).

- [ ] Task 2: Pydantic Schemas (AC: 3, 5, 6, 7)
  - [ ] 2.1 Tạo `nowing_backend/app/schemas/outcome_pricing.py` (`OutcomeEventCreate`, `OutcomeEventRead`, `PricingPlanRead`, `PricingPlanUpdate`, `ServiceBreakdownResponse`, `ServiceBreakdownItem`).
  - [ ] 2.2 Tạo `nowing_backend/app/schemas/promo_code.py` (`PromoCodeClaimRequest`, `PromoCodeClaimResponse`, `PromoCodeCreateRequest`, `PromoCodeAdminRead`).
  - [ ] 2.3 Cập nhật `nowing_backend/app/schemas/usage.py` hỗ trợ `UsageTransactionItem` phân loại `promo_code` và `outcome_debit`.

- [ ] Task 3: Outcome Pricing & Attribution Service (AC: 2, 4)
  - [ ] 3.1 Tạo `nowing_backend/app/services/outcome_pricing_service.py`.
  - [ ] 3.2 Triển khai hàm `resolve_first_touch_attribution(lead_id: UUID) -> str`.
  - [ ] 3.3 Triển khai hàm `record_meeting_outcome(...)` xử lý atomic transaction: check balance -> insert `OutcomeEvent` -> insert `BillingEvent` -> apply debit.
  - [ ] 3.4 Triển khai `get_or_create_workspace_plan(...)` và `update_workspace_plan(...)`.

- [ ] Task 4: Promo Code Engine & Anti-Abuse Service (AC: 5)
  - [ ] 4.1 Tạo `nowing_backend/app/services/promo_code_service.py`.
  - [ ] 4.2 Triển khai `claim_promo_code(user_id: UUID, code: str)` với `SELECT FOR UPDATE` locking và validation chặt chẽ.
  - [ ] 4.3 Triển khai `create_promo_code(...)` cho Admin portal.

- [ ] Task 5: Unified Ledger & Aggregation Engine Upgrade (AC: 1, 6)
  - [ ] 5.1 Cập nhật `nowing_backend/app/services/usage_service.py` thực hiện SQL Union / Aggregation kết hợp `TokenUsage` và `BillingEvent`.
  - [ ] 5.2 Phân bổ chi phí và lượt dùng thành 5 nhóm service chuẩn: `AI Generation`, `Web Search`, `Social Media`, `Phone Waterfall`, `Outcome Meetings`.
  - [ ] 5.3 Bổ sung `get_service_breakdown(...)` và cập nhật `get_transactions(...)` để hiển thị lịch sử nạp promo code và trừ outcome debits.

- [ ] Task 6: REST API Endpoints & RBAC Security (AC: 7)
  - [ ] 6.1 Tạo `nowing_backend/app/routes/outcome_pricing_routes.py`.
  - [ ] 6.2 Tạo `nowing_backend/app/routes/promo_code_routes.py`.
  - [ ] 6.3 Cập nhật `nowing_backend/app/routes/usage_routes.py` với endpoint `/service-breakdown`.
  - [ ] 6.4 Đăng ký routers vào `nowing_backend/app/app.py`.

- [ ] Task 7: Frontend Contracts & API Services (AC: 8)
  - [ ] 7.1 Tạo `nowing_web/contracts/types/outcome-pricing.types.ts` và `nowing_web/contracts/types/promo-code.types.ts`.
  - [ ] 7.2 Cập nhật `nowing_web/contracts/types/usage.types.ts` với kiểu dữ liệu `ServiceBreakdownItem`.
  - [ ] 7.3 Tạo `nowing_web/lib/apis/outcome-pricing-api.service.ts` và `nowing_web/lib/apis/promo-code-api.service.ts`.
  - [ ] 7.4 Cập nhật `nowing_web/lib/apis/usage-api.service.ts`.

- [ ] Task 8: Frontend UI Components for Usage Dashboard (AC: 8, 9)
  - [ ] 8.1 Xây dựng `nowing_web/components/usage/usage-service-donut-chart.tsx` (Recharts Pie/Donut breakdown theo 5 services).
  - [ ] 8.2 Xây dựng `nowing_web/components/usage/usage-service-bar-chart.tsx` (Recharts Bar breakdown theo ngày/tuần/tháng).
  - [ ] 8.3 Xây dựng `nowing_web/components/usage/promo-code-claim-card.tsx` (`[ 🎁 Nhập mã quà tặng / Claim Promo Code ]`, state loading, confetti/toast feedback).
  - [ ] 8.4 Xây dựng `nowing_web/components/usage/outcome-roi-metrics-cards.tsx` (KPI cards: Meetings Booked, Cost/Meeting, ROI multiplier).
  - [ ] 8.5 Cập nhật `nowing_web/components/usage/usage-content.tsx` tích hợp các component mới vào layout dashboard.
  - [ ] 8.6 Thêm chuỗi bản dịch song ngữ `en.json` và `vi.json` cho phần Outcome Pricing và Promo Code.

- [ ] Task 9: Unit & Integration Testing Suite (AC: 1-10)
  - [ ] 9.1 `tests/unit/services/test_outcome_pricing_service.py` (Test first-touch attribution, outcome debit calculations, pricing plan defaults).
  - [ ] 9.2 `tests/unit/services/test_promo_code_service.py` (Test code normalization, expiry validation, max uses exhaustion, duplicate claim block).
  - [ ] 9.3 `tests/unit/services/test_usage_service_unified.py` (Test SQL aggregation across TokenUsage and BillingEvent, service buckets mapping).
  - [ ] 9.4 `tests/integration/routes/test_outcome_pricing_routes.py` (Test REST API RBAC permissions, meeting booking flow, debit consistency).
  - [ ] 9.5 `tests/integration/routes/test_promo_code_routes.py` (Test concurrent claim locking, wallet balance increment, invalid code responses).
  - [ ] 9.6 Frontend testing / typecheck verification (`pnpm tsc --noEmit` & `pnpm exec biome check`).

---

## Dev Notes

### Architecture Decisions & Cross References
- **AD-42 (Outcome-based Pricing & BillingEvent Canonical Ledger):** `TokenUsage` remains LLM-only. All business events use `BillingEvent` with `event_entity_type` + `event_type` matrix. `OutcomeEvent` links to `BillingEvent` via `BillingEvent.event_id = OutcomeEvent.id`.
- **AD-48 (`SequenceEvent` vs `OutcomeEvent` Matrix):** Clarifies that sequence email sends use `sequence_event -> email_send` while booked meetings use `outcome_event -> outcome_meeting_booked`.
- **AD-8 / AD-10 (Unified Credit Wallet):** Single balance column `User.credit_micros_balance` in USD micro-units ($1.00 = 1,000,000 micros).
- **AD-31 (Tenant & Client Isolation):** All new tables MUST declare `workspace_id: Integer` and `client_id: CITEXT | None`.
- **FR-69 ($0 Chat & Transparent Credit Ledger):** Standard chat operations are free ($0); software revenue is aligned with qualified outcomes and enrichment value.

### Tariff Matrix & Conversions
| Business Action | Credits | USD Equiv. | Micros (`cost_micros`) | VND Equiv. |
| :--- | :--- | :--- | :--- | :--- |
| **Standard AI Chat & Turns** | **0.0** | **$0.00** | **0** | **0đ** |
| **Email Sequence Creation / Run** | **0.0** | **$0.00** | **0** | **0đ** |
| **Verified Phone Unlock** | 1.5 | $0.06 | 60,000 | 1,500đ |
| **Deep Research Dossier** | 5.0 | $0.20 | 200,000 | 5,000đ |
| **Verified Contact Enrichment** | 1.0 | $0.04 | 40,000 | 1,000đ |
| **Qualified Meeting Booked** | 50.0 | $2.00 | 2,000,000 | 50,000đ |

### Source Tree Components to Touch
- `nowing_backend/app/db.py` (Models: `OutcomeEvent`, `PricingPlan`, `PromoCode`, `PromoCodeRedemption`)
- `nowing_backend/alembic/versions/191_add_outcome_pricing_and_promo_codes.py` (Migration)
- `nowing_backend/app/schemas/outcome_pricing.py` (New Schemas)
- `nowing_backend/app/schemas/promo_code.py` (New Schemas)
- `nowing_backend/app/services/outcome_pricing_service.py` (New Service)
- `nowing_backend/app/services/promo_code_service.py` (New Service)
- `nowing_backend/app/services/usage_service.py` (Upgrade Aggregation)
- `nowing_backend/app/routes/outcome_pricing_routes.py` (New Routes)
- `nowing_backend/app/routes/promo_code_routes.py` (New Routes)
- `nowing_backend/app/routes/usage_routes.py` (Update Routes)
- `nowing_backend/app/zero_publication.py` (Replication config)
- `nowing_web/components/usage/*` (Donut chart, Bar chart, Promo code card, ROI metrics)
- `nowing_web/lib/apis/*` (Outcome pricing and Promo code API clients)

### Verification Commands
```bash
# Backend lint & tests
cd nowing_backend
ruff check app/db.py app/schemas/outcome_pricing.py app/schemas/promo_code.py app/services/outcome_pricing_service.py app/services/promo_code_service.py app/services/usage_service.py app/routes/outcome_pricing_routes.py app/routes/promo_code_routes.py
pytest tests/unit/services/test_outcome_pricing_service.py tests/unit/services/test_promo_code_service.py tests/unit/services/test_usage_service_unified.py -q
pytest tests/integration/routes/test_outcome_pricing_routes.py tests/integration/routes/test_promo_code_routes.py -q

# Frontend typecheck & lint
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/usage/ lib/apis/ contracts/types/
```

---

## Dev Agent Record

### Agent Model Used
Gemini 3.7 Flash (High)

### File List
- `nowing_backend/app/db.py`
- `nowing_backend/alembic/versions/191_add_outcome_pricing_and_promo_codes.py`
- `nowing_backend/app/schemas/outcome_pricing.py`
- `nowing_backend/app/schemas/promo_code.py`
- `nowing_backend/app/services/outcome_pricing_service.py`
- `nowing_backend/app/services/promo_code_service.py`
- `nowing_backend/app/services/usage_service.py`
- `nowing_backend/app/routes/outcome_pricing_routes.py`
- `nowing_backend/app/routes/promo_code_routes.py`
- `nowing_backend/app/routes/usage_routes.py`
- `nowing_backend/app/zero_publication.py`
- `nowing_web/contracts/types/outcome-pricing.types.ts`
- `nowing_web/contracts/types/promo-code.types.ts`
- `nowing_web/lib/apis/outcome-pricing-api.service.ts`
- `nowing_web/lib/apis/promo-code-api.service.ts`
- `nowing_web/components/usage/usage-service-donut-chart.tsx`
- `nowing_web/components/usage/usage-service-bar-chart.tsx`
- `nowing_web/components/usage/promo-code-claim-card.tsx`
- `nowing_web/components/usage/outcome-roi-metrics-cards.tsx`
- `nowing_web/components/usage/usage-content.tsx`
- `messages/en.json`
- `messages/vi.json`
- `tests/unit/services/test_outcome_pricing_service.py`
- `tests/unit/services/test_promo_code_service.py`
- `tests/unit/services/test_usage_service_unified.py`
- `tests/integration/routes/test_outcome_pricing_routes.py`
- `tests/integration/routes/test_promo_code_routes.py`
