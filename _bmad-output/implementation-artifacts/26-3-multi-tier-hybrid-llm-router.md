---
story_key: "26-3"
epic: "epic-26"
story: "26.3"
title: "Bộ định tuyến LLM lai đa tầng (Gemini Flash Free Tier + DeepSeek V4 + Qwen 3.8)"
status: "ready-for-dev"
baseline_commit: "bb548362e"
---

# Story 26.3: Bộ định tuyến LLM lai đa tầng (Gemini Flash Free Tier + DeepSeek V4 + Qwen 3.8)

## CRITICAL DESIGN DECISIONS — Resolve Before Dev

1. **Kiến trúc `HybridLLMRouter`: tầng chính sách (policy) hay mở rộng `LLMRouterService`? (AD-103)**
   - **Quyết định đề xuất:** Tạo một lớp chính sách mới `app/services/hybrid_llm_router.py` (`HybridLLMRouter`) để quyết định tầng trước khi gọi mô hình. Lớp này **không** thay thế `LLMRouterService` đang chạy cho chat Auto, mà **sử dụng** `LLMRouterService` cho các tầng trả phí (DeepSeek V4) và gọi trực tiếp `litellm.acompletion` cho Gemini Free / local vLLM để kiểm soát quota, JSON schema, và fallback.
   - Rationale: AD-103 phân tách rõ 4 tầng ưu tiên (free → local → burst → deep). LiteLLM Router hiện tại dùng `usage-based-routing` trên một pool đồng nhất; nó không hiểu được nguồn free tier, PII, hay peak/off-peak. Tách policy ra giúp tái sử dụng mà không phá hỏng `ChatLiteLLMRouter`/`get_auto_mode_llm`.

2. **Phân loại tác vụ và dữ liệu nhạy cảm (AD-103 Rule 1)**
   - Quyết định API của `HybridLLMRouter.ainvoke()` yêu cầu tham số `task_type` (`fast_extraction`, `tool_dispatch`, `vision_extraction`, `reasoning`) và `sensitivity` (`public`, `business`, `pii`).
   - Nếu `sensitivity == pii` hoặc `business` (dữ liệu khách hàng độc quyền), router **bắt buộc** bỏ qua Tier 1 (Gemini Flash Free) ngay cả khi quota còn. Điều này đảm bảo tuân thủ điều khoản dữ liệu của Google Free Tier.
   - PII được phát hiện bằng helper `has_sensitive_content()`: kết hợp regex phone/email/VN ID và keyword nhạy cảm (tuỳ chọn gọi `app/proprietary/platforms/xactions/phone_extractor.py` hoặc `app/proprietary/platforms/telegram/entity_extractor.py`).

3. **Quản lý quota Free Tier và Redis rate limit (AD-103 Rule 1)**
   - Gemini Flash Free Tier giới hạn 1,500 RPD / 15 RPM / 1M TPM (theo epics.md). Vì `dsh-worker` có thể chạy nhiều replica, **phải** dùng Redis thay vì bộ đếm in-process.
   - Quyết định triển khai sliding window trên `app/redis_client.py:get_redis_client()` với các key:
     - `hybrid:gemini:rpm:{date_hour}` → `INCR` + `EXPIRE` 60s.
     - `hybrid:gemini:tpm:{date_hour}` → `INCRBY` token count + `EXPIRE` 60s.
     - `hybrid:gemini:rpd:{date}` → `INCR` + `EXPIRE` 86400s.
   - Khi vượt quota → tự động fallback đến Tier 1b (local vLLM) nếu khỏe, hoặc Tier 2 (DeepSeek V4-Flash).

4. **Local vLLM với Qwen 3.8-27B AWQ / Outlines guided JSON (AD-103 Rule 2)**
   - Quyết định coi vLLM như một provider OpenAI-compatible: cấu hình trong `global_llm_config.yaml` với `provider: "openai"`, `api_base: "${VLLM_BASE_URL:-http://localhost:8000/v1}"`, `model_name: "Qwen/Qwen3.8-27B"` (hoặc AWQ quantization tuỳ deployment).
   - Để đạt 100% Pydantic JSON schema compliance, truyền `response_format={"type": "json_schema", "json_schema": {...}}` vào `litellm.acompletion`. vLLM/OpenAI server sẽ dùng guided decoding backend (Outlines) nếu được bật.
   - Kiểm tra sức khoẻ bằng `GET {VLLM_BASE_URL}/health` trước khi route. Nếu CPU-only hoặc GPU không active, bỏ qua tầng này.

5. **DeepSeek V4 Pro / Flash, peak/off-peak, và thinking mode (AD-103 Rule 3 & 4)**
   - Quyết định hỗ trợ 2 model trong `global_llm_config.yaml`: `deepseek-v4-pro-0813` và `deepseek-v4-flash`.
   - Giá peak/off-peak theo AD-103: off-peak ~$0.22/$0.66 (Flash) và ~$0.66/$1.98 (Pro); peak ~$0.44/$1.32 (Flash) và ~$1.32/$3.96 (Pro). Thời gian off-peak mặc định 22:00–06:00 UTC+7, cấu hình qua `HYBRID_OFF_PEAK_HOURS`.
   - Khi `task_type=reasoning`, ưu tiên Pro; nếu Pro rate-limit/5xx hoặc `force_budget=true`, burst sang Flash.
   - Để bật “Thinking: High”, truyền tham số `thinking` / `reasoning` trong `litellm_params` (tuỳ adapter DeepSeek của LiteLLM). Capture `reasoning_content` từ response nếu có để lưu vào DSH checkpoint (Glass Box UI).

## Story

Với tư cách là kỹ sư nền tảng AI,
Tôi muốn có `HybridLLMRouter` tự động phân loại mỗi yêu cầu suy luận/trích xuất và định tuyến đến tầng LLM phù hợp nhất (Gemini Flash Free Tier, local vLLM Qwen, DeepSeek V4-Flash/Pro),
Để tối thiểu hóa chi phí token COGS, đảm bảo Pydantic JSON schema compliance 100%, và giữ TTFT < 600ms cho các tác vụ trích xuất, trong khi vẫn đáp ứng deep reasoning cho định giá, đánh giá distress deal, và reverse ICP.

---

## Acceptance Criteria

### AC-1: Tầng 1 — Gemini Flash Free Tier cho trích xuất & tool dispatch (AD-103 Rule 1)

- **Given** `HybridLLMRouter` nhận một yêu cầu `fast_extraction` hoặc `tool_dispatch` với nội dung **không** chứa PII/dữ liệu nhạy cảm,
- **When** quota Free Tier còn trong giới hạn (15 RPM / 1M TPM),
- **Then** request được định tuyến đến Google Gemini Flash với:
  1. Token COGS = **$0.00**.
  2. TTFT < **600ms** (đo bằng `time.perf_counter()` và log vào `app/utils/perf.py`).
  3. Đầu ra là JSON hợp lệ theo Pydantic schema được truyền qua `response_format`.
  4. Token usage được ghi qua `app/services/token_tracking_service.py:record_token_usage` với `cost_micros=0`.

Chi tiết triển khai:
- Thêm cấu hình Gemini Flash Free vào `global_llm_config.yaml` với `billing_tier: "free"`, `provider: "gemini"` (hoặc `vertex_ai` nếu dùng GCP), `model_name: "gemini-2.0-flash-lite"` hoặc tên tương đương.
- Tắt `router_pool_eligible: false` để model này không bị `LLMRouterService` dùng chung cho chat Auto.
- Trước mỗi lời gọi, `HybridLLMRouter` gọi `_check_gemini_quota()` đọc Redis. Nếu vượt quota, tự động chuyển Tier 1b/2 và ghi log `hybrid_router_tier_fallback`.
- Dùng `litellm.acompletion(..., response_format={"type":"json_schema",...})` để ép JSON schema; fallback sang `json_object` nếu provider không hỗ trợ `json_schema`.
- Bắt exception `JSONDecodeError`/validation error và retry 1 lần, sau đó fallback sang Tier 2.

### AC-2: Tầng 1b — Local vLLM Qwen 3.8-27B AWQ (AD-103 Rule 2)

- **Given** môi trường có GPU local và `VLLM_BASE_URL` trỏ đến endpoint vLLM đang healthy,
- **When** `HybridLLMRouter` nhận `fast_extraction` hoặc `tool_dispatch` (bất kể PII hay không, vì dữ liệu không ra ngoài),
- **Then** request được định tuyến đến local vLLM với:
  1. Token COGS = **$0.00** (chỉ có chi phí cơ sở hạ tầng GPU, không tính trong COGS).
  2. `response_format` JSON schema được vLLM decode bằng Outlines/guided decoding.
  3. Nếu vLLm trả lỗi/timeout/quá 600ms, fallback sang Tier 1 (nếu public) hoặc Tier 2.

Chi tiết triển khai:
- Cấu hình vLLM trong `global_llm_config.yaml` với `provider: "openai"`, `api_base: "${VLLM_BASE_URL}"`, `model_name: "Qwen/Qwen3.8-27B"`.
- Healthcheck mặc định mỗi 30s hoặc trước mỗi request: `GET /health` hoặc `GET /v1/models`.
- Với AWQ quantization, đảm bảo model name trong vLLM khớp với AWQ community quantization (ví dụ `barrydeen/Qwen3.8-27B-AWQ-4bit`).
- CPU-only host bỏ qua tầng này: kiểm tra `HYBRID_ENABLE_LOCAL_VLLM` (default `false`) hoặc thử connect; nếu không có, route 100% Tier 1/3.

### AC-3: Tầng 2 & 3 — DeepSeek V4-Flash/Pro cho deep reasoning (AD-103 Rule 3 & 4)

- **Given** các tác vụ phức tạp như định giá đa bước, suy luận distress deal, reverse ICP scoring, hoặc tạo Telegram checkpoint,
- **When** `task_type=reasoning` hoặc `complex_extraction` được gọi,
- **Then** `HybridLLMRouter` định tuyến:
  1. Mặc định đến `deepseek-v4-pro-0813` với `Thinking: High`.
  2. Nếu Pro gặp rate limit / 5xx / cost peak vượt ngưỡng, burst sang `deepseek-v4-flash`.
  3. Cost debit đúng giá off-peak/peak: Pro $0.435 In / $0.87 Out (off-peak) và Flash $0.14/$0.28 (off-peak); gấp đôi ở peak.
  4. Đầu ra JSON Pydantic 100% hợp lệ; nếu model trả `reasoning_content`, lưu riêng vào checkpoint để Glass Box UI hiển thị.

Chi tiết triển khai:
- Khai báo pricing trong `global_llm_config.yaml` dùng `litellm_params.input_cost_per_token` / `output_cost_per_token` để `app/services/pricing_registration.py` đăng ký với LiteLLM.
- `HybridLLMRouter` dùng `is_peak_hour()` (UTC+7) để quyết định ưu tiên Flash trong peak; Pro vẫn được dùng nếu `force_deep_reasoning=true`.
- Gọi qua `LLMRouterService.get_router().acompletion(model="auto", ...)` nếu DeepSeek đã thêm vào `global_llm_config.yaml` với `router_pool_eligible: true`; hoặc gọi trực tiếp `litellm.acompletion` với model string đã chọn.
- `TokenTrackingCallback` tự động tính `response_cost` từ LiteLLM; `record_token_usage` ghi `cost_micros` đúng.
- Lưu `reasoning_content` vào `dsh_missions.checkpoint.subtasks[].reasoning_content` (nếu có) để Story 26.5 Glass Box UI hiển thị CoT.

---

## Tasks / Subtasks

- [ ] **Task 1 — Cấu hình mô hình và tầng (AC-1, AC-2, AC-3)**
  - [ ] 1.1 Thêm 4 block cấu hình vào `nowing_backend/app/config/global_llm_config.example.yaml`: `gemini-flash-free`, `local-vllm-qwen`, `deepseek-v4-flash`, `deepseek-v4-pro`.
  - [ ] 1.2 Thêm `HYBRID_*` defaults vào `app/config/__init__.py:Config` (`HYBRID_ENABLE_LOCAL_VLLM`, `VLLM_BASE_URL`, `HYBRID_GEMINI_RPM_LIMIT`, `HYBRID_OFF_PEAK_HOURS`, `HYBRID_FORCE_DEEP_REASONING`).
  - [ ] 1.3 Đảm bảo `pricing_registration.py` đăng ký giá DeepSeek và Gemini/vLLM với `cost_micros=0`.

- [ ] **Task 2 — Triển khai `HybridLLMRouter` (AC-1, AC-2, AC-3)**
  - [ ] 2.1 Tạo `nowing_backend/app/services/hybrid_llm_router.py` với class `HybridLLMRouter`.
  - [ ] 2.2 Implement `_classify_task(task_type, text)` và `_is_sensitive(text)`.
  - [ ] 2.3 Implement `_select_tier(...)` theo AD-103.
  - [ ] 2.4 Implement `_check_gemini_quota()` và `_consume_gemini_quota()` với Redis.
  - [ ] 2.5 Implement `_vllm_health()` và `_invoke_vllm(...)`.
  - [ ] 2.6 Implement `_invoke_deepseek(...)` với peak/off-peak và fallback Pro→Flash.
  - [ ] 2.7 Implement `ainvoke(...)` chính trả về Pydantic model đã parse.

- [ ] **Task 3 — Schema & route công khai/nội bộ (AC-1, AC-2, AC-3)**
  - [ ] 3.1 Tạo `nowing_backend/app/schemas/hybrid_llm.py`: `HybridLLMRequest`, `HybridLLMResponse`, `HybridTaskType`, `HybridSensitivity`.
  - [ ] 3.2 Tạo `nowing_backend/app/services/hybrid_llm_service.py` để kiểm tra workspace, gọi router, ghi usage.
  - [ ] 3.3 Tạo `nowing_backend/app/routes/hybrid_llm_routes.py`:
    - `POST /api/v1/workspaces/{workspace_id}/hybrid-llm/invoke` (public, auth).
    - `POST /v1/hybrid-llm/invoke` (internal, dsh-worker).
  - [ ] 3.4 Mount router trong `nowing_backend/app/app.py`.

- [ ] **Task 4 — Tích hợp call sites (AC-1, AC-3)**
  - [ ] 4.1 Sửa `nowing_backend/app/lead_intelligence/reverse_icp.py:219-235` để gọi `HybridLLMRouter` thay vì `LLMRouterService.get_router()` trực tiếp.
  - [ ] 4.2 (Tùy chọn 26.2 follow-up) cập nhật `nowing_backend/app/dsh_worker/supervisor.py` để dùng Hybrid Router cho `extraction` và `reasoning` subtasks.
  - [ ] 4.3 Thay thế hoặc bổ sung `app/proprietary/platforms/xactions/phone_extractor.py` để dùng `fast_extraction` tier cho entity extraction nếu dữ liệu public.

- [ ] **Task 5 — Quota, usage, và cost tracking (AC-1, AC-2, AC-3)**
  - [ ] 5.1 Đảm bảo mọi lời gọi `HybridLLMRouter` bọc trong `scoped_turn()` hoặc gọi `record_token_usage` sau completion.
  - [ ] 5.2 Với tầng free/local, truyền `cost_micros=0` rõ ràng.
  - [ ] 5.3 Với DeepSeek, lấy `response_cost` từ `TokenTrackingCallback` hoặc `litellm.completion_cost`.

- [ ] **Task 6 — Kiểm thử (AD-107)**
  - [ ] 6.1 `tests/unit/services/test_hybrid_llm_router.py`: mock Redis, LiteLLM, test tier selection & quota.
  - [ ] 6.2 `tests/integration/services/test_hybrid_llm_router.py`: real Redis + Postgres, fake vLLM server (httpx mock), kiểm tra fallback.
  - [ ] 6.3 `tests/integration/routes/test_hybrid_llm_routes.py`: auth, workspace scoping, cost attribution.
  - [ ] 6.4 Thêm golden cassettes `.sse.jsonl` cho từng tầng để chạy hermetic CI (AD-107).

---

## Dev Notes

### Kiến trúc & ràng buộc

- Tuân thủ AD-103: 4 tầng ưu tiên rõ ràng; không dùng Gemini Free cho PII/proprietary; CPU-only host bỏ qua local vLLM; DeepSeek Pro chỉ dùng cho reasoning; Flash là burst.
- Không tạo microservice mới. Router là một service class nằm trong `nowing_backend` và được gọi bởi `dsh-worker`, `reverse_icp`, hoặc các extractor khác.
- `HybridLLMRouter` **không** thay thế `LLMRouterService`/`ChatLiteLLMRouter` dùng cho chat Auto. Nó là một policy wrapper ở trên.
- Rate limit Free Tier phải **cross-process** qua Redis vì `dsh-worker` có thể chạy nhiều container.
- Mọi lời gọi đều phải ghi `TokenUsage` qua `record_token_usage`. Tầng free/local phải ghi `cost_micros=0` để analytics theo dõi được mà không debit.
- Pydantic JSON schema 100%: luôn dùng `response_format` với `json_schema`; nếu model trả invalid JSON, fallback sang tầng khác hoặc raise `HybridLLMValidationError`.
- Hermetic CI (AD-107): tất cả test phải chạy với `litellm` mock / golden cassettes, không gọi API thật. Không tốn token trong CI.

### Các file/pattern nên tái sử dụng

| Mục đích | File | Dòng | Cách dùng |
|---|---|---|---|
| Router pool & ChatLiteLLMRouter | `nowing_backend/app/services/llm_router_service.py` | 104-420, 500-720 | Dùng `LLMRouterService.get_router()` cho DeepSeek tier; tham khảo singleton pattern. |
| Image Gen Router (mẫu tương tự) | `nowing_backend/app/services/image_gen_router_service.py` | 31-182 | Tham khảo cách wrap `litellm.Router`. |
| Model resolver | `nowing_backend/app/services/model_resolver.py` | 48-107 | `native_connection_from_config` + `to_litellm` để tạo model string. |
| Đăng ký giá | `nowing_backend/app/services/pricing_registration.py` | 1-372 | Đăng ký `input_cost_per_token`/`output_cost_per_token` cho DeepSeek. |
| Token tracking | `nowing_backend/app/services/token_tracking_service.py` | 421-580 | `record_token_usage` và `TokenTrackingCallback`. |
| Catalog ảo | `nowing_backend/app/services/global_model_catalog.py` | 190-260 | `materialize_global_model_catalog` biến YAML thành GLOBAL models. |
| Auto pin / cooldown | `nowing_backend/app/services/auto_model_pin_service.py` | 1-712 | Mẫu runtime cooldown và shared Redis cooldown. |
| Workspace LLM resolution | `nowing_backend/app/services/llm_service.py` | 100-376 | `get_workspace_llm_instance`, `get_global_llm_config`, `get_global_model`. |
| Cấu hình | `nowing_backend/app/config/__init__.py` | 147-275, 1394-1419 | `GLOBAL_LLM_CONFIGS`, `ROUTER_SETTINGS`. |
| YAML mẫu | `nowing_backend/app/config/global_llm_config.example.yaml` | 1-320 | Copy/sửa để thêm 4 block mới. |
| Redis client | `nowing_backend/app/redis_client.py` | 15-41 | `get_redis_client()` async factory. |
| Call site hiện tại | `nowing_backend/app/lead_intelligence/reverse_icp.py` | 219-235 | Gọi LLMRouterService trực tiếp — chuyển sang Hybrid. |
| Call site Zalo | `nowing_backend/app/gateway/zalo/client.py` | 230-270 | Mẫu gọi router + `record_token_usage`. |
| Billable call lifecycle | `nowing_backend/app/services/billable_calls.py` | 1-120 | Nếu cần reserve premium credit trước DeepSeek call. |

### Pattern code cần tuân thủ

- Singleton service với `@classmethod` như `LLMRouterService`.
- Async API chính: `HybridLLMRouter.ainvoke(request: HybridLLMRequest) -> HybridLLMResponse`.
- Dùng `pydantic.BaseModel` cho `response_format` và parse kết quả.
- Dùng `app.utils.perf:get_perf_logger` để log TTFT.
- Dùng `litellm.drop_params = True` để tránh lỗi provider-specific.
- Luôn `try/except` bao quanh `acompletion` và fallback theo thứ tự: local → Gemini → Flash → Pro; hoặc theo AD-103.
- Sử dụng `hmac.compare_digest` nếu có internal route (ít quan trọng hơn 26.2 nhưng giữ nguyên pattern).

---

## GAPs This Story Closes

1. Không có `HybridLLMRouter` hoặc policy định tuyến đa tầng trong codebase.
2. Không có cấu hình/thử nghiệm cho Gemini Flash Free Tier, local vLLM Qwen, DeepSeek V4 trong `global_llm_config.yaml`.
3. Không có quota/rate-limit cross-process cho free tier.
4. Không có cơ chế peak/off-peak và thinking mode cho DeepSeek.
5. Các call site như `reverse_icp.py` gọi thẳng `LLMRouterService` mà không có tối ưu chi phí theo tác vụ.

---

## Source Artifacts & Traceability

| Artifact | Path | Relevant Lines | What it provides |
|----------|------|----------------|------------------|
| Epics & Stories | `_bmad-output/planning-artifacts/epics.md` | 3354-3365 | Story 26.3 text and AC-1/AC-2/AC-3. |
| Architecture Invariants | `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` | 113-121 | AD-103 (4-tier priority, PII, local vLLM, DeepSeek). |
| Implementation Readiness | `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17-epic26.md` | 46 | FR-L4 traceability (4-Tier Hybrid Router). |
| Previous story file pattern | `_bmad-output/implementation-artifacts/26-2-dsh-worker-sidecar-redis-streams-and-task-resumption.md` | 1-623 | Structure, source table, CDD, review findings. |
| LLM Router Service | `nowing_backend/app/services/llm_router_service.py` | 104-420, 500-720 | `LLMRouterService`, `ChatLiteLLMRouter`, context trimming. |
| Image Gen Router | `nowing_backend/app/services/image_gen_router_service.py` | 31-182 | Singleton router pattern tương tự. |
| Model Resolver | `nowing_backend/app/services/model_resolver.py` | 48-107 | `to_litellm`, `native_connection_from_config`. |
| Pricing Registration | `nowing_backend/app/services/pricing_registration.py` | 1-372 | `register_pricing_from_global_configs`, alias cost. |
| Token Tracking | `nowing_backend/app/services/token_tracking_service.py` | 421-580 | `TokenTrackingCallback`, `record_token_usage`. |
| Global Catalog | `nowing_backend/app/services/global_model_catalog.py` | 190-260 | `materialize_global_model_catalog`. |
| Auto Pin Service | `nowing_backend/app/services/auto_model_pin_service.py` | 1-712 | Runtime cooldown and candidate selection pattern. |
| Workspace LLM Service | `nowing_backend/app/services/llm_service.py` | 100-376 | `get_workspace_llm_instance`, global model lookup. |
| Config | `nowing_backend/app/config/__init__.py` | 147-275, 1394-1419 | `GLOBAL_LLM_CONFIGS`, `ROUTER_SETTINGS`. |
| Global LLM Config example | `nowing_backend/app/config/global_llm_config.example.yaml` | 1-320 | YAML schema for static models. |
| Redis client | `nowing_backend/app/redis_client.py` | 15-41 | Async Redis factory. |
| Reverse ICP call site | `nowing_backend/app/lead_intelligence/reverse_icp.py` | 219-235 | Existing direct router call to migrate. |
| Zalo client pattern | `nowing_backend/app/gateway/zalo/client.py` | 230-270 | `record_token_usage` pattern. |
| Billable calls | `nowing_backend/app/services/billable_calls.py` | 1-120 | Quota reserve/audit pattern for premium calls. |

---

## Verification Commands

Từ `nowing_backend/`:

```bash
# Lint new modules
ruff check app/services/hybrid_llm_router.py app/services/hybrid_llm_service.py app/routes/hybrid_llm_routes.py app/schemas/hybrid_llm.py app/config/__init__.py
ruff format app/services/hybrid_llm_router.py app/services/hybrid_llm_service.py app/routes/hybrid_llm_routes.py app/schemas/hybrid_llm.py

echo "---"
# Unit tests
uv run pytest tests/unit/services/test_hybrid_llm_router.py -q

echo "---"
# Integration tests (requires Postgres + Redis, see AGENTS.md)
docker compose -f ../docker/docker-compose.deps-only.yml up -d db redis
uv run alembic upgrade head
uv run pytest tests/integration/services/test_hybrid_llm_router.py tests/integration/routes/test_hybrid_llm_routes.py -m integration -q

echo "---"
# Hermetic golden cassette smoke (nếu có evals)
uv run pytest tests/e2e/eval_hybrid_router.py -q || true

echo "---"
# Mutation gate (optional, see AGENTS.md)
python scripts/mutation-gate.py --services hybrid_llm_router --project-root . --timeout 120.0 || true
```

---

## References

- Architecture contract: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (AD-103)
- Implementation readiness: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17-epic26.md`
- Previous story: `_bmad-output/implementation-artifacts/26-2-dsh-worker-sidecar-redis-streams-and-task-resumption.md`
- AGENTS.md: local test setup, mutation gate, Story 8.11 verification patterns
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml`

---

## Story Completion Status

**Status:** `ready-for-dev`

Created from baseline commit `bb548362e` on 2026-08-18. This story file is the canonical input for the dev agent. Next step is for the dev agent to resolve the five critical design decisions at the top of this file, then proceed to implement `HybridLLMRouter` and tier policy.

## Challenge Log (grill-me)

### Q1 — Already implemented?
- Finding: No `HybridLLMRouter`, `hybrid_llm_router.py`, `hybrid_llm_routes.py`, or dedicated multi-tier policy exists in the repo. A search (`hybrid_llm|HybridLLMRouter`) returns no code matches outside planning files.
- Existing patterns to reuse:
  - LiteLLM Router pool: `nowing_backend/app/services/llm_router_service.py`.
  - Singleton router pattern: `nowing_backend/app/services/image_gen_router_service.py`.
  - YAML model catalog: `nowing_backend/app/config/global_llm_config.example.yaml` + `app/services/global_model_catalog.py`.
  - Cost registration: `app/services/pricing_registration.py`.
  - Token tracking: `app/services/token_tracking_service.py`.
  - Redis client: `app/redis_client.py:15-41`.
  - Workspace scoping / LLM resolution: `app/services/llm_service.py`.
  - Existing direct router call: `app/lead_intelligence/reverse_icp.py:219-235`.
