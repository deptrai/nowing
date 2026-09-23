---
title: NowingError & Exception Narrowing — Batch 2 (LLM & Model Routing Services)
type: refactor
created: '2026-09-13'
status: done
baseline_commit: e1ad20daa4eb5cb52467d58309dfca07ba5ff825
review_loop_iteration: 0
context:
  - nowing_backend/app/exceptions.py
  - nowing_backend/app/services/hybrid_llm_router.py
  - nowing_backend/app/services/openrouter_integration_service.py
  - nowing_backend/app/services/auto_model_pin_service.py
  - nowing_backend/app/services/llm_service.py
  - nowing_backend/app/services/llm_error_adapter.py
  - nowing_backend/app/services/model_list_service.py
  - nowing_backend/app/services/global_model_catalog.py
  - nowing_backend/app/services/model_connection_service.py
  - nowing_backend/app/services/llm_router/model_resolver.py
  - nowing_backend/app/services/llm_router/service.py
  - nowing_backend/app/services/llm_router/config_builder.py
  - nowing_backend/app/services/llm_router/chat_model.py
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Có 40 vị trí `except Exception` trong các dịch vụ LLM, Model Routing và Model Connections. Nhiều khối nuốt lỗi hoặc che giấu các lỗi kết nối upstream (OpenRouter, LiteLLM, Redis model pin, context overflow).

**Approach:** Refactor Batch 2 gồm 40 call-sites `except Exception` trên 12 files thuộc nhóm LLM & Model Routing:
1. Narrow sang typed exceptions (`LLMError`, `ModelUnavailableError`, `ExternalServiceError`, `SQLAlchemyError`, `redis.RedisError`, `ValueError`, `KeyError`, `httpx.HTTPError`).
2. Với các fallback an toàn (OpenRouter model catalog cache, fallback provider routing, metadata extraction): annotate rõ ràng `# <lý do: fallback/best-effort vs re-raise on critical invocation>`.
3. Với critical path (invoke LLM chat model, stream chunk processing): re-raise typed exception `ModelUnavailableError` / `LLMError` để router xử lý fallback hoặc trả lỗi chuẩn.

## Boundaries & Constraints

**Always:**
- Giữ nguyên routing behavior và fallback logic giữa các LLM providers.
- Với caching / metrics / pin status: log warning/debug và không làm gián đoạn inference.
- Chạy toàn bộ test suites liên quan sau khi sửa.

**Never:**
- Không nuốt lỗi trong hàm gọi inference chính mà không có fallback provider.
- Không thay đổi interface và signatures của LLM router / chat model.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Upstream LLM call timeout / 5xx | Provider fail | Thử fallback model / provider nếu có, hoặc raise ModelUnavailableError | Error code rõ ràng |
| Redis model pin fail | Redis connection drop | Log warning, dùng unpinned model catalog | Best-effort, không chặn inference |
| Token / Context overflow | Prompt quá dài | Raise ContextOverflowError | Client nhận 400 chuẩn |
| Catalog sync fail | OpenRouter API down | Dùng stale cached catalog hoặc local static catalog | Log warning, không crash app boot |

</frozen-after-approval>

## Code Map

- `app/exceptions.py` — `LLMError`, `ContextOverflowError`, `ModelUnavailableError`, `ExternalServiceError`.
- `app/services/hybrid_llm_router.py` (10 sites): Hybrid local/cloud routing, fallback chains.
- `app/services/openrouter_integration_service.py` (8 sites): Sync catalog, fetch models, healthcheck.
- `app/services/auto_model_pin_service.py` (4 sites): Pin model version per workspace in Redis.
- `app/services/llm_service.py` (3 sites): Core LLM invocation helper.
- `app/services/llm_error_adapter.py` (2 sites): Map litellm / provider errors to NowingError.
- `app/services/model_list_service.py` (2 sites): Lấy danh sách models available cho user/workspace.
- `app/services/global_model_catalog.py` (1 site): Quản lý catalog toàn cục.
- `app/services/model_connection_service.py` (1 site): Test connection credentials.
- `app/services/llm_router/model_resolver.py` (1 site): Resolve connection ID to litellm model string.
- `app/services/llm_router/service.py` (1 site): High-level LLM router service.
- `app/services/llm_router/config_builder.py` (2 sites): Build litellm params from connection config.
- `app/services/llm_router/chat_model.py` (5 sites): LangChain ChatModel wrapper with routing & fallback.

## Tasks & Acceptance

**Execution:**
- [x] `hybrid_llm_router.py` (10 sites)
- [x] `openrouter_integration_service.py` (8 sites)
- [x] `auto_model_pin_service.py` (4 sites)
- [x] `llm_service.py` (3 sites)
- [x] `llm_error_adapter.py` (2 sites)
- [x] `model_list_service.py` (2 sites)
- [x] `global_model_catalog.py` (1 site), `model_connection_service.py` (1 site)
- [x] `app/services/llm_router/` (9 sites: chat_model 5, config_builder 2, model_resolver 1, service 1)
- [x] Verify tests & ruff check

**Acceptance Criteria:**
- 100% các call-sites `except Exception` được narrow hoặc annotate rationale chuẩn.
- Các unit & integration tests liên quan đến LLM routing pass 100%.
- `ruff check` pass không có lỗi.
