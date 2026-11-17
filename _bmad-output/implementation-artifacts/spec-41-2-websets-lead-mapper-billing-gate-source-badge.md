---
title: 'Story 41.2 — Websets→Lead Mapper, Billing Gate & Source Badge'
type: 'feature'
created: '2026-10-10'
status: 'in-review'
baseline_revision: 'e85d74dee1a6de12b49e8da63279ff0f07d43033'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings:
  - oversized
deferred: []
---

<intent-contract>

## Intent

**Problem:** Story 41.1 đã drain được entities `ready`/`verified` nhưng `map_webset_entity` chỉ map tối thiểu (bỏ qua `enrichments` theo colKey), chưa trừ credit nào cho lead import, và UI chưa nhận diện nguồn `websets` (chip filter, badge, trạng thái `pending` không bị coi là lỗi). Phát hiện thêm bug contract: `DEFAULT_WEBSET_COLUMNS` gửi `name` nhưng ChainLens `WebsetColumnDto` yêu cầu `key` → `POST /v1/websets` sẽ 400 trên môi trường thật.

**Approach:** Mở rộng `map_webset_entity` map `enrichments` (Record&lt;colKey,{value,status,groundingUrl}&gt;) → Lead fields + cột JSONB `metadata` mới trên `leads` chứa cột chưa map; thêm billing gate (reserve→commit/release 1.5 credits/lead, `BillingEvent` idempotent theo uuid5(webset:entity), `quota_exceeded` khi thiếu số dư); bổ sung chip/badge/pending-state trên 3 UI surface; sửa `name`→`key` trong `DEFAULT_WEBSET_COLUMNS`.

## Boundaries & Constraints

**Always:**
- Billing theo convention `phone_waterfall_service.py`: `wallet_credit.reserve_credit` (soft-lock) trước mỗi flush batch → `commit_reserved_credit` cho lead `accepted=True` → `release_credit` cho lead DNC/đã-bill. `1.5 credits = 1_500_000` micros (`PHONE_RESOLUTION_COST_MICROS` cùng rate Epic 40).
- Idempotent debit: `BillingEvent` với `event_id = uuid5(NAMESPACE_URL, f"{webset_id}:{entity_id}")` — dedup `(event_entity_type, event_type, event_id)` như `_record_business_event` (`billing_event_service.py:763`); BillingEvent tồn tại → release (không debit lại). `InsufficientCreditsError` → `webset_campaigns.status = "quota_exceeded"`, giữ `imported_count` đã có, dừng drain nhẹ nhàng (không raise).
- `leads.metadata` = cột JSONB mới (migration 247, head hiện 246), attr model `extra_metadata = Column("metadata", JSONB, server_default "'{}'::jsonb")` — convention `app/models/scraper.py:246` (`escalation_metadata = Column("metadata", ...)`). `_prepare_lead_record` phải forward key `extra_metadata` (upsert filter theo `Lead.__table__.columns.keys()` tự nhận).
- Mapper chỉ xử lý `item["enrichments"]` (colKey→{value,status,groundingUrl}); `source_url` = `canonical_url`/`url` hoặc groundingUrl đầu tiên; giữ `item["id"]` làm khóa billing (không ghi vào cột Lead — `_entity_id` nội bộ, `ingest_batch` discard key lạ).
- `costDollars` webhook → `cost_dollars_to_micros` (`chainlens/auth.py:320`) ghi vào `campaign.stats["cost_micros"]` — telemetry, KHÔNG bill lại.
- Owner credit = `_resolve_workspace_owner(session, workspace_id)` (`app/capabilities/core/billing.py:933`); không resolve được → skip billing + log warning (như phone_waterfall `user_id is not None` guard).
- UI: `status='pending'` render riêng (spinner/pulse), KHÔNG vào nhánh `degraded`; mọi text qua `t()` + keys mới trong `messages/{en,vi}.json` namespace `leads`.

**Never:**
- Không re-scrape/re-enrich entity; không webset dashboard/CRUD UI trong Nowing (TRINITY-4/5).
- Không dùng `_record_business_event` cho debit (hàm đó tự `apply_debit` — gọi kèm reserve sẽ debit kép); viết `BillingEvent` trực tiếp + `commit_reserved_credit` như phone_waterfall.
- Không thêm cột `metadata` bằng raw SQL — bắt buộc Alembic migration; không đổi `value_hmac`/`ON CONFLICT` semantics.
- Không coi `pending` là degraded; không block `execute` chờ webset.
- Không forward `limit` sang `POST /v1/websets` — contract `create-webset.dto.ts` không có field limit (settle defer 41.1: no-op, đóng).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| MAP_FULL | enrichments `{company_name,phone,email,title,website}` + canonical_url | lead dict đầy đủ fields, `extra_metadata.websets={}` (hoặc chỉ cột lạ) | — |
| MAP_UNMAPPED | enrichments có colKey lạ (vd `opening_hours`) | cột lạ → `extra_metadata.websets[colKey]={value,status,groundingUrl}` | — |
| MAP_URL_FALLBACK | không `canonical_url`, có groundingUrl | `source_url` = groundingUrl đầu tiên | — |
| BILL_OK | buffer 3 lead, đủ credit | reserve 4.5M→commit 3×1.5M, 3 BillingEvent mới | — |
| BILL_DNC | 1 trong 3 bị `accepted=False` | commit 2×1.5M + release 1×1.5M | — |
| BILL_INSUFFICIENT | reserve raise `InsufficientCreditsError` | `campaign.status="quota_exceeded"`, stats cập nhật, giữ imported_count, dừng | graceful return |
| BILL_RERUN | chạy lại cùng webset, BillingEvent đã có | release thay vì commit → không double-debit | — |
| UI_PENDING | alloc `status="pending"`, source `websets` | badge spinner "Đang xây dataset qua ChainLens…", không màu amber/degraded | — |
| UI_FILTER | chọn chip `websets` | chỉ lead `source` chứa "websets" | — |

</intent-contract>

## Code Map

- `nowing_backend/app/services/websets_import.py:19` — `map_webset_entity(entity, webset_id)` mở rộng enrichments→Lead; `:88` `import_webset` + flush loop `:130-163` là hook billing.
- `nowing_backend/app/services/lead_batch_service.py:51` — `_prepare_lead_record` thêm `extra_metadata`; `:212` `ingest_batch` trả `{ingested_count, accepted_lead_ids, accepted[]}` (parallel list → biết lead nào bill).
- `nowing_backend/app/models/leads/main.py` — `Lead` model, thêm `extra_metadata` attr; KHÔNG có sẵn cột metadata.
- `nowing_backend/app/services/wallet_credit.py:195/223/202` — `reserve_credit`/`commit_reserved_credit`/`release_credit`; `InsufficientCreditsError` từ `app.services.etl_credit_service`.
- `nowing_backend/app/services/phone_waterfall_service.py:746-751,970-987` — golden pattern reserve→commit/release + BillingEvent.
- `nowing_backend/app/services/billing_event_service.py:763` — `_record_business_event` dedup convention `(event_entity_type, event_type, event_id)`; `app/models/billing.py:242` BillingEvent.
- `nowing_backend/app/capabilities/core/billing.py:933` — `_resolve_workspace_owner`.
- `nowing_backend/app/services/chainlens/auth.py:320` — `cost_dollars_to_micros`.
- `nowing_backend/app/lead_intelligence/adapters/websets.py:24` — `DEFAULT_WEBSET_COLUMNS` fix `name`→`key`; colKey mapper contract: `company_name, phone, email, title, website`.
- `nowing_backend/app/services/chainlens/websets.py:121` — `iter_ready_items` item shape: `id`, `status`, `canonical_url`/`url`, `enrichments`, `data`/`raw_data`/`properties`.
- `nowing_backend/alembic/versions/` — migration 247 (`down_revision=246`) thêm `leads.metadata` JSONB.
- `nowing_web/components/leads/NowingLeadMatrix.tsx:63-72` — `SOURCE_OPTIONS` (AC gọi SOURCE_FILTERS); `:159-173` filter predicate; `:768-785` hiển thị `rowLead.source`.
- `nowing_web/components/leads/PlanSummaryCard.tsx:367-375` — degraded badge markup `data-testid=badge-degraded-{src}`; thêm pending badge ngay sau.
- `nowing_web/components/leads/SourceStatusPanel.tsx:211,243-251` — panel trạng thái nguồn, cũng cần nhánh pending.
- `nowing_web/components/leads/LeadCard.tsx:78-92` — `getSourceIcon(source)` badge helper.
- `nowing_web/contracts/types/campaign.types.ts:123-135` — `SourcePlanAllocation.status` đã có `"pending"` trong union — không cần sửa type.
- `nowing_web/messages/{en,vi}.json` ns `leads` — thêm `src_websets` + `status_building_dataset` (`status_pending` đã chiếm ở ns khác, `status_degraded` ở `leads`).
- `nowing_web/tests/leads/plan-summary-schema.test.ts`, `plan-summary-contract.test.ts`, `plan-summary-e2e.spec.ts`, `split-canvas.spec.ts` — specs cần extend.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/alembic/versions/247_*.py` + `app/models/leads/main.py` — migration+model `extra_metadata` (`metadata` JSONB) — cần trước mapper test.
- `nowing_backend/app/services/lead_batch_service.py` — `_prepare_lead_record` forward `extra_metadata`.
- `nowing_backend/app/services/websets_import.py` — mở rộng `map_webset_entity` (enrichments→fields + unmapped→`extra_metadata.websets` + `_entity_id`); billing gate trong flush (reserve/ingest/commit|release, uuid5 BillingEvent dedup, `quota_exceeded` graceful); `costDollars`→stats `cost_micros`.
- `nowing_backend/app/lead_intelligence/adapters/websets.py` — `DEFAULT_WEBSET_COLUMNS` `name`→`key`.
- `nowing_backend/tests/unit/` — tests: mapper (mapped/unmapped/url-fallback/`_entity_id`), billing (commit/release math, insufficient→quota_exceeded, rerun no-double-debit, owner-None skip), integration migration 247 roundtrip.
- `nowing_web/components/leads/NowingLeadMatrix.tsx` — `SOURCE_OPTIONS` + predicate `websets`.
- `nowing_web/components/leads/PlanSummaryCard.tsx` + `SourceStatusPanel.tsx` — pending badge `data-testid=badge-pending-{src}` (Loader2 spin, `t("status_building_dataset")`).
- `nowing_web/components/leads/LeadCard.tsx` — `getSourceIcon` case `websets`.
- `nowing_web/messages/{en,vi}.json` — `leads.src_websets` + `leads.status_building_dataset`.
- `nowing_web/tests/leads/` — extend schema/contract tests cho `status:"pending"` + e2e `badge-pending-websets` + split-canvas websets filter.

**Acceptance Criteria:**
- Given webset idle webhook đã enqueue import, when items `ready`/`verified` drain, then enrichments map đúng: `source='websets'`, `source_url`=canonical/grounding URL, company/contact từ colKey đã biết, cột lạ trong `leads.metadata.websets`.
- Given buffer flush N lead và owner đủ credit, when ingest xong, then debit đúng `accepted_count × 1_500_000` micros, DNC/skipped release, mỗi lead có `BillingEvent` idempotent `uuid5(webset_id:entity_id)`; re-run không double-debit.
- Given balance < N×1.5 credits, when reserve raise, then `webset_campaigns.status="quota_exceeded"`, imported_count giữ nguyên, không raise ra ngoài task.
- Given colKey `name` gửi sang ChainLens trước đây, when adapter build payload, then columns dùng `key` khớp `WebsetColumnDto` (fix bug contract).
- Given campaign có allocation `websets` status `pending`, when PlanSummaryCard/SourceStatusPanel render, then badge spinner "Đang xây dataset qua ChainLens…" (không amber/degraded); chip `websets` trong SOURCE_OPTIONS lọc đúng; `getSourceIcon` trả badge websets.

## Spec Change Log

## Review Triage Log

## Design Notes

- **Billing per-flush, không per-drain:** số lead chưa biết trước → `reserve_credit` theo từng batch 100 (khớp flush hiện có), commit/release theo `accepted[]` song song. Re-run an toàn: BillingEvent `uuid5` tồn tại → release, và `ingest_batch` `ON CONFLICT value_hmac` vẫn dedup lead.
- **Pending ≠ degraded (giữ nguyên từ 41.1):** `SourcePlanAllocation.status` union đã chứa `"pending"` (`campaign.types.ts:123`) → UI chỉ cần render nhánh mới, không đổi contract.
- **`extra_metadata` attr ↔ cột `metadata`:** tránh đụng `Base.metadata` của SQLAlchemy (convention `escalation_metadata` ở scraper.py:246); payload `{"websets": {...}}` thỏa AC "metadata.websets".

## Verification

**Commands:**
- `cd nowing_backend && ruff check app/services/websets_import.py app/services/lead_batch_service.py app/models/leads/main.py app/lead_intelligence/adapters/websets.py` -- expected: clean
- `cd nowing_backend && uv run alembic upgrade head` -- expected: migration 247 apply OK, `leads.metadata` JSONB tồn tại
- `cd nowing_backend && uv run pytest tests/unit -k "webset" -q` -- expected: unit tests mới+cũ pass
- `cd nowing_backend && uv run pytest tests/integration/db -k 247 -q` -- expected: migration roundtrip pass
- `cd nowing_web && pnpm tsc --noEmit` -- expected: clean
- `cd nowing_web && pnpm exec biome check components/leads/NowingLeadMatrix.tsx components/leads/PlanSummaryCard.tsx components/leads/SourceStatusPanel.tsx components/leads/LeadCard.tsx` -- expected: clean
- `cd nowing_web && pnpm exec playwright test tests/leads/plan-summary-e2e.spec.ts tests/leads/split-canvas.spec.ts` -- expected: pass (env E2E :4445/:4848)

## Step-04 Review Triage Log

Reviewed: 4 layers (blind / edge-case / verif-gap / intent-alignment) in parallel.

### Fixed
- F1 `LeadRead` + `_map_lead_to_read` thêm `extra_metadata` — API giờ trả metadata (drawer live end-to-end).
- F2 `_build_batch_upsert_stmt` `set_` thêm `extra_metadata = coalesce(excluded.metadata, leads.metadata)`.
- F3 `websets_import.flush()` bọc try/except — exception → `release_credit(reserve - committed)` rồi re-raise (không còn credit leak).
- F4 N+1 BillingEvent select → 1 query `select(BillingEvent.event_id).where(event_id.in_(candidates))` + `seen` set.
- F5 entity_id fallback `lead.get("source_url") or f"idx:{idx}"` — tránh collision uuid5.
- F6/F8/F10 i18n: drawer 2 chuỗi hardcode → `t("websets_enrichments_title"/"source_link_label")`; SourceStatusPanel pending badge → `t("status_building_dataset")`; LeadSourceBadge label → `t("sourceBadgeLabel.{key}")` với fallback.
- F7 `String(val)` → `JSON.stringify` cho object; websetsMetadata guard non-object/array.
- F9 `sourceBadge.ecommerce` key đã thêm en+vi.
- F12 `lead.source.includes` → `(lead.source || "").toLowerCase()` trong NowingLeadMatrix predicate.
- Tests mới: `test_billing_owner_none_skips_billing` (AC-mandated), `test_upsert_set_includes_extra_metadata`, e2e `websets-enrichments-section` assert trong split-canvas spec.

### Deferred / Won't fix
- F11 multi-commit sequence: theo convention build-auto (commit mỗi phase), triển khai ở step-05.
- Intent divergence "backend planner không emit pending": spec ghi UI badge cho trạng thái websets pending — planner emit pending thuộc story backend khác (story contract chỉ định UI render); mock e2e cover.
- pi-lens `window.open` (NowingLeadMatrix:252,258): FALSE POSITIVE — URL hardcode `open.larksuite.com`/`sheets.google.com` đã bọc `isAllowedUrl`; rule ast-grep không có suppress mechanism.

### Verification
- Backend: `pytest` 51 passed (websets_import + lead_batch + webhooks + adapters + migration roundtrip).
- Frontend: `tsc --noEmit` clean; `biome check` 14 files clean; `tsx` schema/contract tests pass; Playwright split-canvas 7/7 + plan-summary-e2e 2/2 pass.
