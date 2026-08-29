"""Structured error hierarchy for Nowing.

Every error response follows a backward-compatible contract:

    {
      "error": {
        "code": "SOME_ERROR_CODE",
        "message": "Human-readable, client-safe message.",
        "status": 422,
        "request_id": "req_...",
        "timestamp": "2026-04-14T12:00:00Z",
        "report_url": "https://github.com/nowing/Nowing/issues"
      },
      "detail": "Human-readable, client-safe message."   # legacy compat
    }
"""

from __future__ import annotations

ISSUES_URL = "https://github.com/nowing/Nowing/issues"

GENERIC_5XX_MESSAGE = (
    "An internal error occurred. Please try again or report this issue if it persists."
)


class NowingError(Exception):
    """Base exception that global handlers translate into the structured envelope."""

    def __init__(
        self,
        message: str = GENERIC_5XX_MESSAGE,
        *,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        safe_for_client: bool = True,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.safe_for_client = safe_for_client


class ConnectorError(NowingError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "CONNECTOR_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code)


class DatabaseError(NowingError):
    def __init__(
        self,
        message: str = "A database error occurred.",
        *,
        code: str = "DATABASE_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=500)


class ConfigurationError(NowingError):
    def __init__(
        self,
        message: str = "A configuration error occurred.",
        *,
        code: str = "CONFIGURATION_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=500)


class ExternalServiceError(NowingError):
    def __init__(
        self,
        message: str = "An external service is unavailable.",
        *,
        code: str = "EXTERNAL_SERVICE_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=502)


class NotFoundError(NowingError):
    def __init__(
        self,
        message: str = "The requested resource was not found.",
        *,
        code: str = "NOT_FOUND",
    ) -> None:
        super().__init__(message, code=code, status_code=404)


class ForbiddenError(NowingError):
    def __init__(
        self,
        message: str = "You don't have permission to access this resource.",
        *,
        code: str = "FORBIDDEN",
    ) -> None:
        super().__init__(message, code=code, status_code=403)


class ValidationError(NowingError):
    def __init__(
        self, message: str = "Validation failed.", *, code: str = "VALIDATION_ERROR"
    ) -> None:
        super().__init__(message, code=code, status_code=422)


class PermissionDeniedError(NowingError):
    """Explicit permission denial (user lacks a required permission)."""

    def __init__(
        self,
        message: str = "You don't have permission to perform this action.",
        *,
        code: str = "PERMISSION_DENIED",
    ) -> None:
        super().__init__(message, code=code, status_code=403)


# -----------------------------------------------------------------------------
# Connector domain
# -----------------------------------------------------------------------------


class OAuthError(ConnectorError):
    def __init__(
        self,
        message: str = "OAuth authentication failed.",
        *,
        code: str = "OAUTH_ERROR",
    ) -> None:
        super().__init__(message, code=code)


class IndexingError(ConnectorError):
    def __init__(
        self,
        message: str = "Connector indexing failed.",
        *,
        code: str = "INDEXING_ERROR",
    ) -> None:
        super().__init__(message, code=code)


class RateLimitError(ConnectorError):
    def __init__(
        self,
        message: str = "Rate limit exceeded.",
        *,
        code: str = "RATE_LIMITED",
    ) -> None:
        super().__init__(message, code=code, status_code=429)


# -----------------------------------------------------------------------------
# Document domain
# -----------------------------------------------------------------------------


class DocumentError(NowingError):
    def __init__(
        self,
        message: str = "A document operation failed.",
        *,
        code: str = "DOCUMENT_ERROR",
        status_code: int = 500,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code)


class UploadError(DocumentError):
    def __init__(
        self,
        message: str = "File upload failed.",
        *,
        code: str = "UPLOAD_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=400)


class ParseError(DocumentError):
    def __init__(
        self,
        message: str = "Document parsing failed.",
        *,
        code: str = "PARSE_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=422)


class StorageError(DocumentError):
    def __init__(
        self,
        message: str = "Document storage failed.",
        *,
        code: str = "STORAGE_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=500)


# -----------------------------------------------------------------------------
# LLM / model domain
# -----------------------------------------------------------------------------


class LLMError(NowingError):
    def __init__(
        self,
        message: str = "An LLM request failed.",
        *,
        code: str = "LLM_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code)


class ContextOverflowError(LLMError):
    def __init__(
        self,
        message: str = "Prompt context exceeds the model's context window.",
        *,
        code: str = "CONTEXT_OVERFLOW",
    ) -> None:
        super().__init__(message, code=code, status_code=413)


class ModelUnavailableError(LLMError):
    def __init__(
        self,
        message: str = "The requested model is unavailable.",
        *,
        code: str = "MODEL_UNAVAILABLE",
    ) -> None:
        super().__init__(message, code=code, status_code=503)


# -----------------------------------------------------------------------------
# External API domain
# -----------------------------------------------------------------------------


class ExternalAPIError(NowingError):
    def __init__(
        self,
        message: str = "An external API request failed.",
        *,
        code: str = "EXTERNAL_API_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code)
