"""Notion history connector package (split from notion_history.py)."""

from ._helpers import (
    BASE_RETRY_DELAY,
    MAX_RATE_LIMIT_WAIT_SECONDS,
    MAX_RETRIES,
    MAX_RETRY_DELAY,
    MAX_TOTAL_RETRY_WAIT_SECONDS,
    RETRYABLE_STATUS_CODES,
    UNSUPPORTED_BLOCK_TYPE_ERRORS,
    UNSUPPORTED_BLOCK_TYPES,
    NotionAPIError,
    RetryCallbackType,
)
from .service import NotionHistoryConnector

__all__ = [
    "BASE_RETRY_DELAY",
    "MAX_RATE_LIMIT_WAIT_SECONDS",
    "MAX_RETRIES",
    "MAX_RETRY_DELAY",
    "MAX_TOTAL_RETRY_WAIT_SECONDS",
    "RETRYABLE_STATUS_CODES",
    "UNSUPPORTED_BLOCK_TYPES",
    "UNSUPPORTED_BLOCK_TYPE_ERRORS",
    "NotionAPIError",
    "NotionHistoryConnector",
    "RetryCallbackType",
]
