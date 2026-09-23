# ADR-002: Exception hierarchy và error handling nhất quán

## Status

Accepted — đã thực hiện (Giai đoạn C)

## Context

Backend có 1.753 lần `except Exception`, trong đó 699 lần ở `routes/` và `services/`. Việc bắt quá rộng làm:
- Che giấu lỗi thực sự, khó debug.
- Trả 500 generic cho client thay vì thông báo lỗi domain rõ ràng.
- Mất dấu `request_id`/`workspace_id`/`user_id` khi log.
- `print()` còn sót trong production.

## Decision

Xây dựng cây exception dựa trên `NowingError` ở `app/exceptions.py`:
- `NotFoundError` (404, NOT_FOUND)
- `PermissionDeniedError` (403, PERMISSION_DENIED)
- `ValidationError` (400, VALIDATION_ERROR)
- `ConnectorError` (502) → `OAuthError`, `IndexingError`, `RateLimitError` (429)
- `DocumentError` (400/422/500) → `UploadError`, `ParseError`, `StorageError`
- `LLMError` (502/503/413) → `ContextOverflowError`, `ModelUnavailableError`
- `ExternalAPIError` (502)
- `ConfigurationError` (500)

Global handler trong `app.py`:
- `NowingError` → status code + envelope `{error: {code, message, status, request_id, timestamp, report_url}, detail}`.
- `HTTPException` → giữ status gốc nếu 4xx/5xx có nghĩa; sanitize 500 để message an toàn.
- `RequestValidationError` → 422 với field errors.
- `Exception` → 500, log `user_id`/`workspace_id`, không leak internal.

Quy tắc `except Exception`:
- Cấm ở route/service trừ khi là entrypoint cuối hoặc có comment giải thích.
- Catch exception cụ thể (`ValueError`, `SQLAlchemyError`, `redis.RedisError`, `OSError`, `RuntimeError`) hoặc domain exception.
- Route-level `SQLAlchemyError` phải `await session.rollback()` trước `raise HTTPException`.
- `print()` thay bằng `logger.*`; ruff rule `T201` bật cho production, per-file-ignores cho CLI/testbench.

## Consequences

- Client nhận lỗi có cấu trúc, dễ hiển thị và trace.
- Log có đủ context để debug.
- Giảm đáng kể `except Exception` trong route/service.
- Cần audit liên tục để không tái phạm.

## Related

- [[ADR-001-split-db-py-into-models]]
- [[ADR-003-split-routes-and-services]]
