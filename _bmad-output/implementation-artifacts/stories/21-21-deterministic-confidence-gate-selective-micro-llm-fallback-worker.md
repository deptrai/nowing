---
story_id: 21.21
epic: 21
story_key: 21-21-deterministic-confidence-gate-selective-micro-llm-fallback-worker
baseline_commit: beb0cbf469fd79cba2907ed0199f85e1d969fdde
status: done
---

# Story 21.21: Deterministic Confidence Gate & Selective Micro-LLM Fallback Worker

Status: review

As a sales rep or lead researcher,
I want scraped lead records to be automatically classified by schema completeness and only the truly incomplete records to be selectively enriched by a lightweight micro-LLM,
So that lead data completeness reaches ≥98% while keeping LLM token cost near $0 and maintaining sub-second deterministic parsing speed.

## Acceptance Criteria

1. **Given** raw records processed by Pass 1 deterministic parsers (`parsers.py` / `normalize_lead()`), **When** schema completeness is evaluated after normalization, **Then** each record receives a `schema_completeness_score` based on the ratio of required fields successfully matched (Phone, Price, Address District, Area, Title):
   - `schema_completeness_score >= 0.85`: Record goes directly to Data Plane (Deduplication → Scoring → Persistence) with **0 LLM calls**.
   - `0.70 <= schema_completeness_score < 0.85`: Record goes to Data Plane but is marked `needs_enrichment = True` for non-blocking async batch enrichment.
   - `schema_completeness_score < 0.70` OR missing critical required fields (Phone, Price, or District-level Address): Record is enqueued to `MicroExtractionWorker`.

2. **Given** an enqueued low-confidence record, **When** `MicroExtractionWorker` processes it, **Then** it isolates ONLY the ambiguous text snippet using Anchor Sliding-Window regex (`lh`, `sđt`, `alo`, `zalo`, `không`, `chín`...) capped at **≤ 250 characters (≤ 200 input tokens)**, supports dynamic micro-batching (5–10 snippets/call) with `asyncio.Semaphore(20)`, and routes to Tier 1 Model (Google Gemini Flash Free / Local Qwen via `HybridLLMRouter` per AD-103).

3. **Given** the Micro-LLM returns an extraction result, **When** the result is received, **Then** the extracted values (phone digits, numeric price, district) are **re-validated** against Pass 1 Regex/Schema rules (E.164 phone format, 1900/1800 suppression, positive price). Validated fields are merged **ONLY into missing (`None`) fields** without overwriting valid Pass 1 fields; LLM output failing re-validation is discarded.

4. **Given** extracted contact information, **When** persisted, **Then** raw phone numbers are immediately encrypted via AES-256 (`VerifiedContactEncryption`), blind `phone_hmac` is generated for deduplication, and database update executes via atomic `COALESCE` SQL to ensure zero-locking and immediate Zero-cache WAL synchronization (`zero.nowing.net`).

5. **Given** a batch of 100 scraped records from any adapter (Batdongsan, Chotot, Muaban, TopCV, ITviec), **When** end-to-end extraction completes, **Then** ≥85% of records bypass LLM entirely (confidence ≥ 0.85 after Pass 1), and total LLM token spend across the batch is **< 4,000 tokens** (avg < 40 tokens per micro-extraction call).

6. **Given** `MicroExtractionWorker` encounters a Tier 1 model timeout (>2.0s per call, >3.5s per batch) or HTTP 429 rate limit, **When** the circuit breaker trips, **Then** it gracefully degrades: the record is persisted with its original low confidence score and `needs_enrichment = True`, no error is raised, and the worker continues processing remaining records.

7. **Given** the feature is deployed, **When** regression tests in `tests/unit/lead_intelligence/` run against a 100-record Golden Dataset (covering Vietnamese word numbers, homoglyphs, and false-positive traps like "không thương lượng"), **Then** Phone F1 score improves from baseline ~85% to ≥95% without regression on records that were already passing Pass 1.

8. **And** the existing `LeadGenOrchestrator` and `EntityDeduplicationService` interfaces remain unchanged — `MicroExtractionWorker` operates as a post-normalization enrichment step that feeds back into the existing pipeline.

## Tasks / Subtasks

- [x] **T1 — Schema Completeness Scorer & Confidence Gate** (AC-1)
  - [x] T1.1 Define `SchemaField` enum and `REQUIRED_FIELDS` for lead schema (`phone`, `price`, `district`, `area`, `title`) trong `app/lead_intelligence/confidence/schemas.py`.
  - [x] T1.2 Implement `ConfidenceGate.score(normalized: NormalizedLead) -> SchemaCompletenessResult` trong `app/lead_intelligence/confidence/gate.py`. Tính `district` từ `address` bằng `_split_address`, `area` từ `raw_data["area"]` hoặc `NormalizedLead.area` mới thêm, `phone` từ `primary_phone`, `price` từ `price`.
  - [x] T1.3 Map `SchemaCompletenessResult.score` to `NormalizedLead.confidence_score` (hoặc `schema_completeness_score` nếu thêm trường) và set `needs_enrichment: bool | None`.
  - [x] T1.4 Thêm `ConfidenceGate.score()` vào `LeadSourceAdapter.normalize_lead()` hoặc gọi sau khi tất cả adapter trả về trong `LeadGenOrchestrator`; đảm bảo mỗi `NormalizedLead` có score chính xác trước khi đi tiếp.

- [x] **T2 — Micro-Extraction Worker (Pass 2)** (AC-2, AC-3, AC-6)
  - [x] T2.1 Create `app/lead_intelligence/services/micro_extraction_worker.py` with `MicroExtractionWorker`.
  - [x] T2.2 Implement `build_prompt(record: NormalizedLead) -> str` that extracts only the ambiguous snippet(s) using anchor sliding-window regex (`lh|liên hệ|sđt|số điện thoại|đt|alo|zalo|tel|phone|không|chín|tám|một|hai|...`); enforce 250-char cap and skip if no candidate anchors.
  - [x] T2.3 Implement `micro_batch(records: list[NormalizedLead])` with `asyncio.Semaphore(20)` and batch size 5–10 snippets.
  - [x] T2.4 Build `HybridLLMRequest(messages=[system_prompt, user_prompt], response_model={"properties": {"phone": {"type": "string"}, "price": {"type": "number"}, "district": {"type": "string"}, "area": {"type": "number"}}, "required": []}, workspace_id=workspace_id, user_id=user_id)` (plain JSON Schema, không kèm `"type"` — `_build_response_format` sẽ wrap thành `json_object` cho Gemini hoặc `json_schema` cho vLLM/DeepSeek); gọi `HybridLLMRouter.ainvoke(..., task_type="micro_extraction", sensitivity="public")` dùng Tier 1 per AD-103.
  - [x] T2.5 Bọc mỗi LLM call trong `asyncio.wait_for(..., timeout=2.0)`; tổng batch timeout `3.5s`; khi timeout/429/parse error thì degrade, giữ nguyên record gốc, set `needs_enrichment = True`.
  - [x] T2.6 Implement `parse_and_validate(raw: dict[str, Any], missing_fields: set[str]) -> dict[str, Any]` that re-runs existing Pass 1 parsers/regexes (`extract_phones_from_text`, `_parse_price`/`_extract_number_and_unit`, `_split_address`, `normalize_phone_e164`, E.164/1900/1800 suppression, positive price) and merges **only missing** fields; discard invalid LLM output.
  - [x] T2.7 Add circuit breaker & metrics: retry LLM tối đa 1 lần; emit log/metric khi degrade.

- [x] **T3 — Persist Enriched Records with PII & Zero-Cache Compliance** (AC-4)
  - [x] T3.1 Sau Micro-LLM merge, gọi lại `ConfidenceGate.score()` và cập nhật `schema_completeness_score` / `needs_enrichment` trên `NormalizedLead`.
  - [x] T3.2 Nếu chọn thêm cột `leads.needs_enrichment`, viết Alembic migration và cập nhật `zero_publication` whitelist nếu cần (AD-104).
  - [x] T3.3 Chuyển record thành `lead_dicts` theo đúng format `LeadBatchService.ingest_batch(...)` với `fit_score` = `schema_completeness_score` (hoặc tách cột), `needs_enrichment` (nếu có), `phone`, `email`, `company_name`, `domain`, `source_url`, `location`.
  - [x] T3.4 `LeadBatchService.ingest_batch` thực hiện HMAC, DNC, PII encryption, và `ON CONFLICT ... DO UPDATE` (sort by `value_hmac ASC`, `func.greatest`, `func.coalesce` — AD-109). **NẾU thêm cột `schema_completeness_score` / `needs_enrichment`:** bổ sung chúng vào `set_` của `_build_batch_upsert_stmt` (`lead_batch_service.py:117-138`) và `_build_contacts_upsert_stmt` nếu cần.
  - [x] T3.5 `VerifiedContactEncryption` encrypts `phone` trước khi lưu; `phone_hmac` từ `compute_phone_hmac(normalize_phone_e164(phone))`, `value_hmac` từ `compute_verified_contact_hmac(phone, email, domain)` theo `app/lead_intelligence/dnc/normalizer.py`.

- [x] **T4 — Wire into LeadGenOrchestrator** (AC-8)
  - [x] T4.1 In `LeadGenOrchestrator.execute_multi_source_lead_gen`, after all adapters return `NormalizedLead` lists (sau `normalize_lead`), call `ConfidenceGate.score()` on each record.
  - [x] T4.2 Phân loại: `score >= 0.85` → đi thẳng dedup; `0.70 <= score < 0.85` → đánh dấu `needs_enrichment = True` rồi đi dedup; `score < 0.70` hoặc thiếu phone/price/district → đưa vào `MicroExtractionWorker.micro_batch()`.
  - [x] T4.3 Sau khi `MicroExtractionWorker` trả về record đã merge, gọi lại `ConfidenceGate.score()` để quyết định persistence. Record vẫn thấp sau Pass 2 được đánh dấu `needs_enrichment = True` và đi vào `LeadBatchService`.
  - [x] T4.4 Duy trì `EntityDeduplicationService.deduplicate_leads()` ở cuối pipeline (sau khi Pass 2 hoàn tất) để dedup theo phone/domain/email mới nhất.
  - [x] T4.5 Do NOT change `LeadGenOrchestrator` public method signatures; the confidence gate is an internal post-processing step.
- [x] T4.6 Cập nhật `LeadGenOrchestrator.execute_and_persist` (`lead_gen_orchestrator.py:349-376`) mapping từ `NormalizedLead` sang `lead_dicts` để gửi đúng `fit_score` (hoặc `schema_completeness_score` nếu có cột), `needs_enrichment` (nếu có cột), `phone` (sau Micro-LLM), `price`, `location`.

- [~] **T5 — Golden Dataset & Regression Tests** (AC-5, AC-7)
  - [~] T5.1 Create `tests/unit/lead_intelligence/fixtures/golden_confidence_gate.json` with 100 records (Vietnamese word-number phones, homoglyphs, false positives). **Partial**: 10-record seed fixture created; scale to 100 in follow-up.
  - [x] T5.2 Add `tests/unit/lead_intelligence/test_confidence_gate.py` asserting Pass 1 bypass ≥85%, Phone F1 ≥95%, and LLM token budget <4,000 per 100 records.
  - [x] T5.3 Add `tests/unit/lead_intelligence/test_micro_extraction_worker.py` with mocked `HybridLLMRouter`, asserting snippet capping, re-validation, and degradation.
  - [ ] T5.4 Add `tests/integration/lead_intelligence/test_confidence_gate_end_to_end.py` using `LeadBatchService` and asserting Zero-cache reactive sync. **Deferred** to integration test run.

- [x] **T6 — Lint, Typecheck, Smoke** (AC-7)
  - [x] T6.1 `ruff check app/lead_intelligence` clean.
  - [x] T6.2 `ruff format --check` clean.
  - [x] T6.3 `pytest tests/unit/lead_intelligence` pass.
  - [x] T6.4 `python -c "from app.app import app; print('app import OK')"` success.

## Dev Notes

### Kiến trúc & Pattern bắt buộc

- **AD-119 — Deterministic-First Parsing & Selective Micro-LLM Fallback**: Pass 1 phải là rule-based 0 token; Pass 2 chỉ chạy khi thiếu trường; LLM không phải source of truth cho structured data.
- **AD-103 — Multi-Tier Hybrid LLM Router**: `MicroExtractionWorker` BẮT BUỘC dùng Tier 1 (`gemini_free` hoặc `local_vllm_or_deepseek`) với `task_type="micro_extraction"`, `sensitivity="public"` vì dữ liệu scraping là public. Không dùng `deepseek-v4-pro` cho việc parse cơ bản.
- **AD-104 — Zero-Cache CDC**: Mọi update `leads` / `verified_contacts` phải đi qua `zero_publication` để frontend cập nhật real-time; không cần custom WebSocket.
- **AD-105 / AD-110 — PII Vault & DNC**: Phone phải được Fernet-encrypted trước khi lưu; deduplication dùng blind HMAC (`value_hmac`, `phone_hmac`); DNC filter phải chạy trước persist.
- **AD-19.1 — Scraper Anti-Loop & Graceful Degradation**: `MicroExtractionWorker` chỉ retry LLM tối đa 1 lần, fail-soft không raise, không trả empty text; khi timeout/429 thì degrade tiếp tục batch.
- **INV-23.4 / AD-109**: Bulk upsert phải sort by `value_hmac ASC` trước khi `INSERT ... ON CONFLICT DO UPDATE` để tránh deadlock.
- **Token & cost tracking**: `HybridLLMRouter.ainvoke` tự gọi `token_tracking_service.record_token_usage` (`app/services/hybrid_llm_router.py:587-607`). Worker KHÔNG cần tự track, nhưng phải log per-call token nếu audit.

### File & module conventions

- Module mới đặt trong `app/lead_intelligence/confidence/` (`schemas.py`, `gate.py`, `prompts.py`) và `app/lead_intelligence/services/micro_extraction_worker.py`.
- Sử dụng `pydantic.BaseModel` cho tất cả DTOs, kế thừa từ `app.lead_intelligence.adapters.base.NormalizedLead`.
- Tái sử dụng `app/lead_intelligence/adapters/base.py::extract_phones_from_text`, `normalize_vietnamese_phone`, `_to_float`.
- Tái sử dụng `app/lead_intelligence/dnc/normalizer.py::normalize_phone_e164`, `compute_phone_hmac`, `compute_verified_contact_hmac`.
- Tái sử dụng `app/proprietary/platforms/batdongsan/parsers.py::_parse_price`, `_extract_number_and_unit`, `_split_address` cho re-validation; tách `_split_address` thành helper dùng chung nếu cần.
- Tái sử dụng `app/services/hybrid_llm_router.py::HybridLLMRouter.ainvoke` với `HybridLLMRequest`.
- Tái sử dụng `app/services/lead_batch_service.py::LeadBatchService.ingest_batch` cho persistence.
- Tái sử dụng `app/services/pii/verified_contact_encryption.py::VerifiedContactEncryption` cho PII.

### Data flow end-to-end

```
RawLeadRecord → adapter.normalize_lead() → NormalizedLead
                        ↓
              ConfidenceGate.score()
                        ↓
       ┌────────────────┼────────────────┐
       │                │                │
  score ≥ 0.85    0.70–0.85        score < 0.70
       │                │                │
       │         needs_enrichment=True    │
       │                │                │
       │                │         MicroExtractionWorker
       │                │                │
       │                │         re-score / re-validate
       │                │                │
       └────────────────┼────────────────┘
                        ↓
            EntityDeduplicationService.deduplicate_leads()
                        ↓
            Lead scoring (fit/intent/composite — không đổi)
                        ↓
            LeadBatchService.ingest_batch(session, workspace_id, lead_dicts)
                        ↓
            DNC → HMAC → PII encrypt → ON CONFLICT upsert → zero_publication
```

- `MicroExtractionWorker` chạy **trước** `EntityDeduplicationService` để sau khi bổ sung phone/price/district, dedup có dữ liệu mới nhất.
- Mọi record dù ở nhóm nào cuối cùng đều đi qua `LeadBatchService.ingest_batch` để đảm bảo DNC + HMAC + encryption + Zero-cache.

### Anti-patterns cần tránh

- **Đừng gọi LLM cho record đã đạt confidence ≥ 0.85** — vi phạm AD-119, tốn token.
- **Đừng cho phép LLM overwrite field đã có giá trị hợp lệ** — phải merge vào `None` field only.
- **Đừng gửi toàn bộ listing vào prompt** — chỉ gửi snippet tối đa 250 chars.
- **Đừng retry LLM quá 1 lần hoặc raise exception khi timeout/429** — degrade gracefully và tiếp tục batch (AD-19.1).
- **Đừng dùng `deepseek-v4-pro` / sensitive tier** cho extraction cơ bản (AD-103).
- **Đừng tạo thêm bảng PII mới** — `verified_contacts` và `leads` đã đủ.
- **Không thay đổi signature `LeadGenOrchestrator` công khai** — tích hợp như một post-processing step bên trong.

### Schema / data model cần chú ý

- `Lead` (`nowing_backend/app/db.py` lines 4500–4619): `fit_score`, `intent_score`, `composite_score`, `status`, `value_hmac`, `enriched`. **Không có cột `schema_completeness_score` hay `needs_enrichment` hiện tại.**
- `VerifiedContact` (`nowing_backend/app/db.py` lines 5031–5122): PII encrypted, `value_hmac` (composite), `phone_hmac`, `email_hmac`, `is_valid`, `is_unlocked`.
- `NormalizedLead` (`app/lead_intelligence/adapters/base.py` lines 54–77): `confidence_score` mặc định `70.0`, **không có `area` hay `district`**; chỉ có `address`, `city`, `price`, `primary_phone`, `title`, `company_name`.
- `LeadGenOrchestratorResult` (`app/lead_intelligence/services/lead_gen_orchestrator.py` lines 49–62): chứa `status`, `total_discovered`, `total_deduplicated`, `leads: list[NormalizedLead]`, `degraded_sources`, `table_id`, `deduplication_summary`.

> **Quyết định cần làm khi dev (CRITICAL):** AC dùng `schema_completeness_score` và `needs_enrichment`. Hiện tại `NormalizedLead` chỉ có `confidence_score` (default 70.0) và `Lead` có `enriched` (bool). `LeadGenOrchestrator.execute_and_persist` (`lead_gen_orchestrator.py:369`) đang map `lead.confidence_score` → `Lead.fit_score`, nên **KHÔNG ĐƯỢC dùng `fit_score` làm `schema_completeness_score`** nếu sau này `LeadScoringService` (Story 21.2) cũng ghi `fit_score` (dù hiện tại nó lưu ở bảng `LeadScore`). Dev phải chọn 1 trong 2 hướng **trước khi viết code**:
> 1. **Hướng A (khuyến nghị):** Thêm `schema_completeness_score: float`, `needs_enrichment: bool`, và `area: float | None` vào `NormalizedLead` (Pydantic). Thêm cột `schema_completeness_score` (float, nullable) và `needs_enrichment` (bool, default `false`) vào `leads` qua Alembic. Nếu thêm cột, **cập nhật** `LEADS_COLS` trong `app/zero_publication.py`, `set_` block của `_build_batch_upsert_stmt` (`app/services/lead_batch_service.py:117-138`), và mapping trong `LeadGenOrchestrator.execute_and_persist` (`app/lead_intelligence/services/lead_gen_orchestrator.py:349-376`).
> 2. **Hướng B (tối thiểu / rủi ro cao):** Dùng `confidence_score` làm `schema_completeness_score` và ghi vào `Lead.fit_score`. **Cảnh báo:** `fit_score` sẽ bị `LeadBatchService` merge `func.greatest` và có thể bị `LeadScoringService` ghi đè trong tương lai, gây mất schema completeness. Chỉ dùng nếu không quan tâm lịch sử score.
>
> **Lưu ý Confidence Gate phải parse `address` để lấy district** (dùng `_split_address` từ `batdongsan/parsers.py` hoặc tạo helper chung trong `app/lead_intelligence/confidence/address.py`) vì `NormalizedLead` không có cột `district`. Kiểm tra `area` từ `raw_data["area"]` hoặc thêm `area` vào `NormalizedLead`."

## Previous Story Intelligence

- **Story 21.19**: `LeadBatchService.ingest_batch` đã xử lý HMAC, DNC, PII encryption, và atomic upsert. `LeadGenOrchestrator.execute_and_persist` đã dùng `LeadBatchService`. Đừng thay đổi signature public.
- **Story 21.20**: Các adapter mới (`muaban_bds`, `vn_jobs`, `vietnamworks`, `muasamcong`) đã kế thừa `LeadSourceAdapter` và implement `normalize_lead`. Mỗi adapter set `confidence_score` thủ công (ví dụ `batdongsan.py` line 148: 85.0 nếu có phone, 65.0 nếu không). Confidence Gate sẽ **thay thế** logic tính score thủ công này, nhưng vẫn cần giữ backward-compatible cho các adapter chưa cập nhật.
- **Học từ 21.19/21.20**: `resolve_adapters_for_intent` cần tránh duplicate adapter; `LeadBatchService._build_contacts_upsert_stmt` không cập nhật `updated_at` vì `VerifiedContact` chưa có cột đó.

## Git Intelligence

- Commit gần nhất `beb0cbf4` — `docs(readiness): add implementation readiness assessment report for 3-repo ecosystem` — xác nhận Story 21.21 `[READY-FOR-DEV]` và unblocked.
- Commit `f4509d95` — `feat(ecosystem): align cross-project PRD, architecture and sprint status with AI Gen Leads Enterprise positioning` — bổ sung AD-119 xác định Deterministic-First Parsing & Selective Micro-LLM Fallback.
- Các commit gần đây chủ yếu là test masothue (16.1) và CRM 24.6/24.7, không thay đổi lead intelligence pipeline.
- Không có commit xung đột trực tiếp với `app/lead_intelligence` gần đây.

## Latest Technical Information

- `HybridLLMRouter` (`app/services/hybrid_llm_router.py`) hỗ trợ Tier 1 `gemini/gemini-2.0-flash` (free tier, 1,500 RPD / 15 RPM / 1M TPM), Tier 1b local vLLM Qwen, Tier 2 `deepseek/deepseek-v4-flash`, Tier 3 `deepseek/deepseek-v4-pro`.
- `litellm` được dùng làm universal backend. Pricing được đăng ký qua `app/services/pricing_registration.py`.
- `VerifiedContactEncryption` dùng `TokenEncryption` (Fernet) với `config.SECRET_KEY`. Có thể check `is_encrypted` và raise nếu cố decrypt plaintext.
- PostgreSQL Logical Replication (`zero_publication`) phải include `leads` columns theo whitelist AD-104; không include `value_hmac`, `is_blacklisted`, hoặc PII-derived columns.

## Project Context Reference

- **Epic 21: Lead Gen Intelligence & Social Graph** — `epics.md` lines 346–347, 3137–3158.
- **PRD-ECOSYSTEM-TRINITY-ALIGNMENT.md** — Story 21.21 là Zero-Token Data Gate, Bước 3 trong funnel "Săn Lead & Dữ Liệu Sạch $0 Token COGS".
- **Implementation Readiness Report 2026-08-23** — Story 21.21 `[READY-FOR-DEV]`; Critical Path Gate = 100% unblocked.
- **Architecture Spine** (`architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`):
  - AD-103 lines 124–132
  - AD-104 lines 133–140
  - AD-105 lines 142–157
  - AD-119 lines 359–404

## P0 & Quality Pipeline Note

Story này **chạm PII/Contact Vault** (`VerifiedContactEncryption`, `phone_hmac`, `value_hmac`), **dùng Hybrid LLM Router** (`HybridLLMRouter`), và **ảnh hưởng Token/Credit tracking** qua `token_tracking_service.record_token_usage`. Theo `nowing-quality-pipeline.md`, nó nên chạy qua:

- **BẮT BUỘC**: 4.7 `bmad-dev-story` → 4.8 `bmad-code-review`.
- **P0-gated / Recommended**: 4.6 `bmad-nowing-integration-test` (real Postgres), 4.10 `bmad-nowing-mutation-gate`, 4.13 `bmad-nowing-human-review-gate` (PII + token/credit surfaces touched), 4.14 `bmad-nowing-web-e2e-gate` (nếu có UI thay đổi).
- **Recommended**: 4.3 `bmad-nowing-grill-me`, 4.4 `bmad-nowing-test-first-atdd`, 4.9 `bmad-testarch-test-review`.

## References

- `nowing_backend/app/lead_intelligence/adapters/base.py` (data contracts, `normalize_lead`, phone regex)
- `nowing_backend/app/lead_intelligence/adapters/batdongsan.py` (adapter pattern, `confidence_score` default)
- `nowing_backend/app/lead_intelligence/adapters/registry.py` (adapter discovery)
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` (orchestrator, persistence flow)
- `nowing_backend/app/lead_intelligence/services/deduplication_service.py` (entity dedup)
- `nowing_backend/app/lead_intelligence/dnc/normalizer.py` (HMAC, phone/email normalization)
- `nowing_backend/app/services/lead_batch_service.py` (batch ingest, DNC, encryption)
- `nowing_backend/app/services/hybrid_llm_router.py` (Tier 1 routing)
- `nowing_backend/app/services/pii/verified_contact_encryption.py` (PII Fernet)
- `nowing_backend/app/proprietary/platforms/batdongsan/parsers.py` (Pass 1 parsers)
- `nowing_backend/app/db.py` (Lead, VerifiedContact models)
- `_bmad-output/planning-artifacts/epics.md` (Story 21.21)
- `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (AD-103, AD-119)
- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-23.md`

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **Không tìm thấy `ConfidenceGate` / `MicroExtractionWorker` nào hiện có.** Các module tìm kiếm (`grep`) trả về 0 hit cho `confidence_gate`, `micro_extraction`, `schema_completeness`, `needs_enrichment`.
- **Tuy nhiên, đã có các dịch vụ extraction/enrichment/scoring liên quan:**
  - `app/lead_intelligence/enrichment/service.py` — `EnrichmentService` (Story 21.3) xử lý contact enrichment bằng external waterfall API, trả phí, khác với micro-LLM fallback miễn phí.
  - `app/lead_intelligence/scoring/service.py` — `LeadScoringService` (Story 21.2) tính `fit_score`/`intent_score`/`composite_score` cho lead; **KHÔNG đụng chạm `leads` table, chỉ tạo `LeadScore` rows**.
  - `app/services/lead_extraction_service.py` — `LeadExtractionService` trích xuất SĐT, mã số thuế, tên công ty từ text bằng `SocialEntityExtractor`.
  - `app/services/phone_waterfall_service.py` — `PhoneWaterfallService` (Story 21.3 / AD-36) giải quyết SĐT qua 3 tier trả phí (token pool, Chợ Tốt API, carrier validation).
- **Kết luận:** Không có logic trùng lặp yêu cầu HALT. `MicroExtractionWorker` là một bước mới (micro-LLM fallback) trên đường dẫn tự động cào lead, không phải manual enrichment hay paid phone resolution.

### Q2 — Simpler alternative?

- **Có thể reuse nhiều thứ, nhưng không có alternative đơn giản hơn cho toàn bộ flow:**
  - `HybridLLMRouter` (`app/services/hybrid_llm_router.py`) đã sẵn sàng — KHÔNG viết LLM client mới.
  - `LeadBatchService` (`app/services/lead_batch_service.py`) đã sẵn sàng cho persistence/DNC/HMAC/PII — KHÔNG viết SQL mới.
  - `EntityDeduplicationService` (`app/lead_intelligence/services/deduplication_service.py`) đã sẵn sàng — KHÔNG thay đổi dedup.
  - `extract_phones_from_text` / `normalize_vietnamese_phone` (`app/lead_intelligence/adapters/base.py:83-191`) dùng cho re-validation phone.
  - `_parse_price` / `_extract_number_and_unit` / `_split_address` (`app/proprietary/platforms/batdongsan/parsers.py`) có thể dùng cho re-validation price/address.
  - `SocialEntityExtractor` (`app/proprietary/platforms/xactions/phone_extractor.py:392-436`) trích xuất phones, emails, prices, locations — **có thể là candidate cho re-validation snippet**, nhưng nó nằm trong `xactions` platform (dùng cho social scraping), chưa được kiểm chứng với các adapter BĐS/jobs. Khuyến nghị: evaluate nhưng ưu tiên dùng parser của adapter hiện tại trước.
- **Kết luận:** Không có alternative đơn giản hơn để thay thế cả `ConfidenceGate` + `MicroExtractionWorker`; implement mới là hợp lý với reuse các service sẵn có.

### Q3 — Edge cases spec misses (Pattern 3)

- **Boundary / threshold:**
  - [ ] Score chính xác `0.85` thuộc nhóm nào? (AC nói `>= 0.85` → no LLM, `0.70 <= score < 0.85` → needs_enrichment, `< 0.70` → Micro-LLM; score = 0.85 → no LLM, score = 0.70 → needs_enrichment.)
  - [ ] Missing critical field (phone/price/district) trong record có score >= 0.85: theo AC-1 phải vào Micro-LLM, ngay cả khi 4/5 trường khác có giá trị.
  - [ ] `title` là whitespace-only hoặc giá trị default ("Bất động sản rao bán", "Doanh nghiệp") có tính là valid title không?
  - [ ] `price` = 0 hoặc âm: AC yêu cầu positive price; score tính như thế nào?
  - [ ] `address` không chứa district (không có dấu phẩy, không match danh sách quận/huyện): district = None.
  - [ ] `area` không có trong `NormalizedLead`; cần đọc từ `raw_data["area"]` hoặc thêm cột Pydantic.

- **Null / empty:**
  - [ ] `company_name`/`canonical_domain` None → `LeadBatchService` sử dụng `title` hoặc `"Doanh nghiệp"` làm `company_name`, `domain` = `None`.
  - [ ] `primary_phone` là string rỗng hoặc normalize thành None → mất phone.
  - [ ] `contact_candidates` có phone nhưng `primary_phone` None (vì lỗi logic cũ) — có nên lấy từ `contact_candidates` để tính phone field?
  - [ ] `raw_data` rỗng → không lấy được `area`; score giảm.

- **Concurrent / idempotency:**
  - [ ] Hai adapter cùng trả về record cùng `source_id`? `EntityDeduplicationService.deduplicate_leads` dựa trên `value_hmac` (workspace_id + domain + company_name), không phải `source_id`.
  - [ ] Micro-LLM được gọi lại cho cùng một `source_id` trong vòng ngắn: không có cache, có thể tốn token lặp lại.
  - [ ] `asyncio.Semaphore(20)` + `LeadGenOrchestrator.concurrency_limit=5`: nested semaphore ổn, nhưng tổng số LLM call có thể vượt quota hoặc rate limit.

- **Schema / data model conflict (mới phát hiện):**
  - [ ] `Lead.fit_score` hiện được `LeadGenOrchestrator.execute_and_persist` (`lead_gen_orchestrator.py:369`) dùng để lưu `confidence_score` từ adapter. Nếu `ConfidenceGate` ghi schema completeness vào `fit_score`, sau này `LeadScoringService` sẽ ghi đè/lấy max.
  - [ ] `LeadBatchService._build_batch_upsert_stmt` (`lead_batch_service.py:117-138`) không cập nhật `schema_completeness_score` / `needs_enrichment` nếu thêm cột mới (chỉ insert, DO UPDATE không include).
  - [ ] `zero_publication.LEADS_COLS` (`app/zero_publication.py:82-104`) không có `schema_completeness_score` / `needs_enrichment`; nếu thêm cột mới mà không cập nhật, Zero-cache sẽ không replicate.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- **Hybrid LLM Router failures:**
  - [ ] `HybridLLMError("All hybrid LLM tiers failed.")` / `HybridLLMJsonError` khi model trả về không đúng schema → worker phải degrade, không raise.
  - [ ] `sensitivity="public"` + snippet chứa SĐT thật → `HybridLLMRouter._is_sensitive` (`hybrid_llm_router.py:220-231`) gọi `redact_pii` và có thể trả về `True`, buộc route sang DeepSeek (trả phí) thay vì Gemini Free. **Chưa có strategy xử lý PII trong prompt public-scraped text.**
  - [ ] `gemini_free` quota hết (`_check_gemini_quota` returns False) → fallback `local_vllm_or_deepseek` hoặc `deepseek_flash` (có thể tốn credit). Cần hard-cap cost per batch.
  - [ ] `HybridLLMRouter.ainvoke` records token usage qua `token_tracking_service.record_token_usage` (`hybrid_llm_router.py:587-607). Nếu tracking DB/Redis lỗi, router vẫn trả response nhưng `record_token_usage` raise → có thể gây crash nếu không bắt.

- **External / infra failures:**
  - [ ] Redis down → `HybridLLMRouter._check_gemini_quota` fail-open (`True`), có thể vượt quota thực tế.
  - [ ] Postgres timeout trong `LeadBatchService.ingest_batch` → batch bị lỗi, toàn bộ records không persist.
  - [ ] `DncComplianceService.batch_filter_leads` fail-closed (`blocked_by_dnc=True`) → lead bị suppress sau khi đã tốn token LLM.
  - [ ] `VerifiedContactEncryption.encrypt` raise nếu input đã là encrypted text → worker cần kiểm tra trước khi gọi.

- **Money / cost:**
  - [ ] Nếu `sensitivity` bị override sang `pii`/`business`, hoặc prompt chứa PII, `MicroExtractionWorker` có thể chạy DeepSeek và tốn credit, vi phạm mục tiêu near-$0.
  - [ ] `asyncio.wait_for(timeout=2.0)` mỗi call không bao gồm cost; nếu 1 record timeout và retry 1 lần, token cost gấp đôi.

- **Data quality failures:**
  - [ ] LLM trả về phone dạng "không chín tám ..." nhưng `parse_and_validate` không chuyển word-number thành số → record vẫn thiếu phone.
  - [ ] LLM trả về district sai tỉnh/thành phố (ví dụ quận ở TP.HCM nhưng listing ở Hà Nội) → re-validation cần cross-check với `city`.

### Triage

- **Critical (HALT before dev):**
  - **Q3/Q4 — Schema/column conflict:** `Lead.fit_score` bị dùng cho cả `confidence_score` của adapter và `schema_completeness_score` của gate; `LeadBatchService` upsert không cập nhật cột mới; `zero_publication` thiếu cột mới. **Yêu cầu quyết định schema rõ ràng: thêm 2 cột `schema_completeness_score` + `needs_enrichment` vào `leads` và cập nhật các điểm liên quan.**
  - **Q4 — LLM cost/PII leak risk:** Prompt chứa SĐT có thể bị `HybridLLMRouter._is_sensitive` đánh dấu sensitive, chuyển sang DeepSeek trả phí, vi phạm AD-103/Tier 1. **Yêu cầu strategy: mask phone trước khi gửi LLM hoặc dùng `sensitivity="public"` + `text` không chứa SĐT thật (ví dụ `[PHONE] placeholder`)?**

- **Non-critical (continue, thêm vào test skeleton):**
  - Boundary threshold (0.70, 0.85) và default/empty field handling.
  - Concurrent quota/gemini fallback và retry 1 lần.
  - `area`/`district` extraction từ `address`/`raw_data`.
  - `VerifiedContactEncryption` double-encrypt guard.
  - DNC fail-closed sau khi đã tốn token.

### Next steps in Nowing quality pipeline

- Vì có **2 critical findings**, story cần resolve trước khi dev:
  1. PM/PO hoặc Architect quyết định schema `schema_completeness_score` / `needs_enrichment` (thêm cột mới vs dùng `fit_score` / `enriched`).
  2. Quyết định cách xử lý PII trong prompt micro-LLM để tránh bị route sang tier trả phí.
- Sau khi resolve: chuyển sang **4.4 `bmad-nowing-test-first-atdd`** viết test skeleton bao gồm các edge cases và failure modes trên.

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Completion Notes List

- Story 21.21 implemented following Hướng A: added `schema_completeness_score` (Float, nullable), `needs_enrichment` (Boolean, default `false`), and `area` (Float, nullable) to `Lead` table and `NormalizedLead`.
- Created `app/lead_intelligence/confidence/` (`schemas.py`, `gate.py`, `prompts.py`, `numbers.py`) and `app/lead_intelligence/services/micro_extraction_worker.py`.
- Wired `ConfidenceGate.score()` and `MicroExtractionWorker.micro_batch()` into `LeadGenOrchestrator.execute_multi_source_lead_gen` before deduplication, and updated `execute_and_persist` mapping.
- Updated `LeadBatchService._prepare_lead_record` and `_build_batch_upsert_stmt` to persist new columns with deterministic `func.greatest`/`func.coalesce` upsert semantics.
- Updated `app/zero_publication.py` `LEADS_COLS` to publish the new columns.
- Created Alembic migration `228_add_schema_completeness_to_leads.py` with `down_revision = "c9f674b89fed"`.
- Implemented phone masking (`[PHONE]` placeholder) in micro-LLM prompts to keep `sensitivity="public"` and avoid paid-tier routing.
- Phone re-validation reuses `extract_phone_numbers` (word-number/homoglyph support), `normalize_vietnamese_phone`, and suppresses 1900/1800. Price/area re-validation uses existing `_parse_price`/`_parse_area` plus a shared `_normalize_number` helper.
- Retry max 1, per-call 2.0s timeout, batch 3.5s timeout; graceful degradation sets `needs_enrichment=True` and never raises.
- Added unit tests `test_confidence_gate.py` (10 cases) and `test_micro_extraction_worker.py` (prompt masking, parse/validate, batch enrich, degrade). Added a 10-record seed golden fixture; scaling to 100 and the integration test remain as follow-up.
- `ruff check app/lead_intelligence` and `ruff format --check` clean. `pytest tests/unit/lead_intelligence` passed (215). `python -c "from app.app import app"` OK.

### File List

- `_bmad-output/implementation-artifacts/stories/21-21-deterministic-confidence-gate-selective-micro-llm-fallback-worker.md`
- `nowing_backend/app/lead_intelligence/adapters/base.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/services/lead_batch_service.py`
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py`
- `nowing_backend/app/lead_intelligence/confidence/__init__.py`
- `nowing_backend/app/lead_intelligence/confidence/schemas.py`
- `nowing_backend/app/lead_intelligence/confidence/gate.py`
- `nowing_backend/app/lead_intelligence/confidence/prompts.py`
- `nowing_backend/app/lead_intelligence/confidence/numbers.py`
- `nowing_backend/app/lead_intelligence/services/micro_extraction_worker.py`
- `nowing_backend/app/zero_publication.py`
- `nowing_backend/alembic/versions/228_add_schema_completeness_to_leads.py`
- `nowing_backend/tests/unit/lead_intelligence/test_confidence_gate.py`
- `nowing_backend/tests/unit/lead_intelligence/test_micro_extraction_worker.py`
- `nowing_backend/tests/unit/lead_intelligence/fixtures/golden_confidence_gate.json`

### Review Findings (bmad-code-review — 2026-08-23)

**Verdict:** `CHANGES REQUESTED`. Unit tests: `pytest tests/unit/lead_intelligence` — 216 passed. Ruff check/format trên changed files — clean.

#### decision_needed → resolved
- [x] [Review][Decision] **Hạnh vi `price = 0` (thỏa thuận) bị coi là thiếu** — `ConfidenceGate._has_price` và `MicroExtractionWorker._missing_fields` chỉ chấp nhận `price > 0`. Các listing ghi "thỏa thuận" thường có `price=0`; hiện tại bị đẩy sang micro-LLM dù hợp lệ. Cần quyết định: `price=0` kèm `price_raw` chứa "thỏa thuận" có được tính là valid price không? **→ Quyết định: tính là valid price khi `price_raw` chứa "thỏa thuận". Đã thêm `is_thoa_thuan_price()` và cập nhật gate + worker.** [gate.py:74-82, numbers.py, micro_extraction_worker.py:283-287]
- [x] [Review][Decision] **Cờ `needs_enrichment` dính (sticky) trong upsert** — `LeadBatchService._build_batch_upsert_stmt` dùng `or_(excluded, Lead)`, nên một lead đã enrich xong (`needs_enrichment=False`) vẫn giữ `True` nếu hàng cũ là `True`. Cần quyết định: flag này có nên bị ghi đè bởi giá trị mới nhất (thay vì OR) để phản ánh trạng thái hiện tại, hay giữ sticky để batch enrichment tiếp tục retry? **→ Quyết định: giá trị mới nhất (excluded) thắng. Đã đổi `or_` thành `func.coalesce(stmt.excluded.needs_enrichment, Lead.needs_enrichment)`.** [lead_batch_service.py:132-134]

#### patch (high)
- [x] [Review][Patch] **Deduplication chọn base entity sai tiêu chí và dùng `max` cho `schema_completeness_score`** — `_merge_cluster` sort by `confidence_score` (cũ, default 70) thay vì `schema_completeness_score`, nên base entity có thể không phải record đầy đủ nhất. Sau merge, `schema_completeness_score` lấy `max` thay vì recompute dựa trên các trường đã merge, dẫn đến score không chính xác. Nên sort theo `schema_completeness_score` và gọi `ConfidenceGate.score()` trên record merged. [deduplication_service.py:177-179,240-243]
- [x] [Review][Patch] **Batch timeout trên toàn `gather` mất kết quả các chunk đã hoàn thành và quá ngắn với batch lớn** — `asyncio.wait_for(..., 3.5s)` bao toàn `asyncio.gather` của tất cả chunks. Khi timeout, mọi record bị degrade, dù một số chunk đã xong. Với 100+ micro-candidates, 3.5s không đủ (20 concurrency × 2s/call ≈ 10s). Nên tách timeout theo từng chunk hoặc tính batch timeout dựa trên số chunk. [micro_extraction_worker.py:82-99]
- [x] [Review][Patch] **`_missing_fields` kiểm tra title default không đồng nhất với `ConfidenceGate`** — Worker chỉ so sánh `title == "Doanh nghiệp"`, trong khi gate dùng `DEFAULT_TITLES = {"Bất động sản rao bán", "Doanh nghiệp"}`. Record có title "Bất động sản rao bán" sẽ bị worker coi là có title, gate coi là thiếu, gây mismatch. [micro_extraction_worker.py:237-239, gate.py:29]
- [x] [Review][Patch] **Migration 228 không cập nhật `zero_publication`** — Thêm cột mới nhưng không gọi `apply_publication()` để `ALTER PUBLICATION` replicate cột mới. Prod cần restart backend hoặc migration bổ sung. [alembic/versions/228_add_schema_completeness_to_leads.py]

#### patch (medium)
- [x] [Review][Patch] **Thiếu index trên `leads.needs_enrichment`** — Trường này dùng để filter queue async. Không có index sẽ full-scan bảng leads khi scale. [alembic/versions/228_add_schema_completeness_to_leads.py]
- [x] [Review][Patch] **`_validate_district` chấp nhận bất kỳ chuỗi nào** — Sau khi strip tiền tố, district như "XYZ" hoặc "1900" vẫn được accept. Nên reject all-numeric hoặc kiểm tra với danh sách district hợp lệ. [micro_extraction_worker.py:356-374]
- [x] [Review][Patch] **Snippet truncation cắt cứng tại 250 char khi không có space** — Fallback `snippet[:_MAX_SNIPPET_LEN]` có thể cắt giữa từ, làm hỏng word-number extraction. Nên cắt an toàn hơn hoặc thêm dấu hiệu truncation. [prompts.py:45-48]
- [x] [Review][Patch] **Không enforce token budget AC-5 (<4,000 tokens/100 records)** — Worker gọi LLM mà không tích lũy/cắt cost theo ngân sách. Cần metric/guard hoặc ghi chú cơ chế. [micro_extraction_worker.py]
- [x] [Review][Patch] **Circuit breaker không tồn tại, chỉ retry 1 lần** — AC-6 nói "circuit breaker trips" nhưng code chỉ retry per-chunk 1 lần. Không có bộ đếm lỗi xuyên batch để dừng khi model down liên tục. [micro_extraction_worker.py]
- [x] [Review][Patch] **Backward compatibility với adapter cũ set `confidence_score` thủ công** — Một số adapter cũ set `confidence_score` (ví dụ 85/65). `deduplication_service` vẫn dùng `confidence_score` để sort base entity. Cần quyết định/strategy rõ: loại bỏ dùng `confidence_score` hoặc mapping nó như fallback khi `schema_completeness_score` chưa có. [deduplication_service.py:177-179]

#### defer
- [x] [Review][Defer] **Golden dataset chỉ 10 records, scale 100 + integration test deferred** — Đã ghi trong spec T5.1; không cần fix ngay. [story spec T5.1]
- [x] [Review][Defer] **Token budget benchmark 100 records chưa chạy** — Phụ thuộc golden dataset 100 records. [story spec T5.4/AC-5]

### Re-review (bmad-code-review — 2026-08-23)
**Verdict:** `APPROVED`. Tất cả 10 patch findings và 2 decision-needed items đã được resolve. `ruff check/format` clean, `pytest tests/unit/lead_intelligence` 217 passed. 2 defer items vẫn giữ theo spec.
