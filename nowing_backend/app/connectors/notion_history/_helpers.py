"""Shared constants, error type, and retry configuration for the Notion history connector."""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.config import config


class NotionAPIError(Exception):
    """Raised when the Notion API returns a non-200 response.

    The message is always user-presentable; callers should surface it directly
    without any additional prefix or wrapping.
    """


# Type variable for generic return type
T = TypeVar("T")

# ============================================================================
# Retry Configuration (per Notion API docs)
# https://developers.notion.com/reference/request-limits
# https://developers.notion.com/reference/status-codes
# ============================================================================
MAX_RETRIES = 5
BASE_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0  # seconds (Notion's max request timeout)
MAX_RATE_LIMIT_WAIT_SECONDS = float(
    getattr(config, "NOTION_MAX_RETRY_AFTER_SECONDS", 30.0)
)
MAX_TOTAL_RETRY_WAIT_SECONDS = float(
    getattr(config, "NOTION_MAX_TOTAL_RETRY_WAIT_SECONDS", 120.0)
)

# Type alias for retry callback function
# Signature: async callback(retry_reason, attempt, max_attempts, wait_seconds) -> None
# retry_reason: 'rate_limit', 'server_error', 'timeout'
# This callback can be used to update notifications during retries
RetryCallbackType = Callable[[str, int, int, float], Awaitable[None]]

# HTTP status codes that should trigger a retry
# 429: rate_limited - Use Retry-After header
# 500: internal_server_error - Unexpected error
# 502: bad_gateway - Failed upstream connection
# 503: service_unavailable - Notion unavailable or timeout
# 504: gateway_timeout - Notion timed out
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Known unsupported block types that Notion API doesn't expose
# These will be skipped gracefully instead of failing the entire sync
UNSUPPORTED_BLOCK_TYPE_ERRORS = [
    "transcription is not supported",
    "ai_block is not supported",
    "is not supported via the API",
]

# Known unsupported block types to check before API calls
UNSUPPORTED_BLOCK_TYPES = ["transcription", "ai_block"]
