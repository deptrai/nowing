"""App errors helpers."""
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address  # noqa: F401 — kept for reference

from app.exceptions import GENERIC_5XX_MESSAGE, ISSUES_URL, NowingError
from app.observability import metrics as ot_metrics

_error_logger = logging.getLogger("nowing.errors")

rate_limit_logger = logging.getLogger("nowing.rate_limit")


# ============================================================================
# Rate Limiting Configuration (SlowAPI + Redis)
# ============================================================================
# Uses the same Redis instance as Celery for zero additional infrastructure.
# Protects auth endpoints from brute force and user enumeration attacks.

# limiter is imported from app.rate_limiter (shared module to avoid circular imports)


# ============================================================================
# Rate Limiting Configuration (SlowAPI + Redis)
# ============================================================================
# Uses the same Redis instance as Celery for zero additional infrastructure.
# Protects auth endpoints from brute force and user enumeration attacks.

# limiter is imported from app.rate_limiter (shared module to avoid circular imports)


def _get_request_id(request: Request) -> str:
    """Return the request ID from state, header, or generate a new one."""
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    return request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")


def _build_error_response(
    status_code: int,
    message: str,
    *,
    code: str = "INTERNAL_ERROR",
    request_id: str = "",
    extra_headers: dict[str, str] | None = None,
    fields: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Build the standardized error envelope (new ``error`` + legacy ``detail``)."""
    error = {
        "code": code,
        "message": message,
        "status": status_code,
        "request_id": request_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "report_url": ISSUES_URL,
    }
    if fields:
        error["fields"] = fields
    body = {
        "error": error,
        "detail": message,
    }
    headers = {"X-Request-ID": request_id}
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(status_code=status_code, content=body, headers=headers)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


def _nowing_error_handler(request: Request, exc: NowingError) -> JSONResponse:
    """Handle our own structured exceptions."""
    rid = _get_request_id(request)
    user_id = getattr(request.state, "user_id", None)
    workspace_id = getattr(request.state, "workspace_id", None)
    if exc.status_code >= 500:
        _error_logger.error(
            "[%s] user=%s workspace=%s path=%s - %s: %s",
            rid,
            user_id,
            workspace_id,
            request.url.path,
            exc.code,
            exc,
            exc_info=True,
        )
    elif exc.status_code >= 400:
        _error_logger.warning(
            "[%s] user=%s workspace=%s path=%s - %s: %s",
            rid,
            user_id,
            workspace_id,
            request.url.path,
            exc.code,
            exc,
        )
    message = exc.message if exc.safe_for_client else GENERIC_5XX_MESSAGE
    return _build_error_response(
        exc.status_code, message, code=exc.code, request_id=rid
    )


def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Wrap FastAPI/Starlette HTTPExceptions into the standard envelope.

    5xx sanitization policy:
    - 500 responses are sanitized (replaced with ``GENERIC_5XX_MESSAGE``) because
      they usually wrap raw internal errors and may leak sensitive info.
    - Other 5xx statuses (501, 502, 503, 504, ...) are raised explicitly by
      route code to communicate a specific, user-safe operational state
      (e.g. 503 "Page purchases are temporarily unavailable."). Those details
      are preserved so the frontend can render them, but the error is still
      logged server-side.
    """
    rid = _get_request_id(request)
    if exc.status_code in {401, 403} and request.url.path.startswith("/auth"):
        ot_metrics.record_auth_failure(reason=_status_to_code(exc.status_code))
    should_sanitize = exc.status_code == 500

    # Structured dict details (e.g. {"code": "CAPTCHA_REQUIRED", "message": "..."})
    # are preserved so the frontend can parse them.
    if isinstance(exc.detail, dict):
        err_code = exc.detail.get("code", _status_to_code(exc.status_code))
        message = exc.detail.get("message", str(exc.detail))
        if exc.status_code >= 500:
            _error_logger.error(
                "[%s] %s - HTTPException %d: %s",
                rid,
                request.url.path,
                exc.status_code,
                message,
            )
        elif exc.status_code >= 400:
            _error_logger.warning(
                "[%s] %s %s - HTTPException %d: %s",
                rid,
                request.method,
                request.url.path,
                exc.status_code,
                message,
            )
        if should_sanitize:
            message = GENERIC_5XX_MESSAGE
            err_code = "INTERNAL_ERROR"
        body = {
            "error": {
                "code": err_code,
                "message": message,
                "status": exc.status_code,
                "request_id": rid,
                "timestamp": datetime.now(UTC).isoformat(),
                "report_url": ISSUES_URL,
            },
            "detail": exc.detail,
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers={"X-Request-ID": rid},
        )

    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    if exc.status_code >= 500:
        _error_logger.error(
            "[%s] %s - HTTPException %d: %s",
            rid,
            request.url.path,
            exc.status_code,
            detail,
        )
    elif exc.status_code >= 400:
        _error_logger.warning(
            "[%s] %s %s - HTTPException %d: %s",
            rid,
            request.method,
            request.url.path,
            exc.status_code,
            detail,
        )
    if should_sanitize:
        detail = GENERIC_5XX_MESSAGE
    code = _status_to_code(exc.status_code, detail)
    return _build_error_response(exc.status_code, detail, code=code, request_id=rid)


def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 with field-level detail in the standard envelope."""
    rid = _get_request_id(request)
    fields: list[dict[str, Any]] = []
    summaries: list[str] = []
    for err in exc.errors():
        # Drop the "body" root from loc paths: clients map fields relative to
        # the request body, and the message summary must not leak the prefix.
        loc = list(err.get("loc", []))
        if loc and loc[0] == "body":
            loc = loc[1:]
        fields.append({"loc": loc, "msg": err.get("msg", "invalid")})
        if loc:
            path = " -> ".join(str(part) for part in loc)
            summaries.append(f"{path}: {err.get('msg', 'invalid')}")
    message = (
        f"Validation failed: {'; '.join(summaries)}"
        if summaries
        else "Validation failed."
    )
    return _build_error_response(
        422,
        message,
        code="VALIDATION_ERROR",
        request_id=rid,
        fields=fields,
    )


def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log full traceback, return sanitized 500."""
    rid = _get_request_id(request)
    user_id = getattr(request.state, "user_id", None)
    workspace_id = getattr(request.state, "workspace_id", None)
    ot_metrics.record_auth_failure(reason="unhandled_exception")
    _error_logger.error(
        "[%s] user=%s workspace=%s Unhandled exception on %s %s",
        rid,
        user_id,
        workspace_id,
        request.method,
        request.url.path,
        exc_info=True,
    )
    return _build_error_response(
        500, GENERIC_5XX_MESSAGE, code="INTERNAL_ERROR", request_id=rid
    )


def _status_to_code(status_code: int, detail: str = "") -> str:
    if detail == "RATE_LIMIT_EXCEEDED":
        return "RATE_LIMIT_EXCEEDED"
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
    }
    return mapping.get(
        status_code, "INTERNAL_ERROR" if status_code >= 500 else "CLIENT_ERROR"
    )


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom 429 handler that returns JSON matching our error envelope."""
    rid = _get_request_id(request)
    ot_metrics.record_rate_limit_rejection(scope="slowapi")
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str):
        retry_after = detail.split("per")[-1].strip() or "60"
    else:
        retry_after = "60"
    return _build_error_response(
        429,
        "Too many requests. Please slow down and try again.",
        code="RATE_LIMIT_EXCEEDED",
        request_id=rid,
        extra_headers={"Retry-After": retry_after},
    )
