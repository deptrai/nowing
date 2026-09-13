"""Core Notion history connector: auth, client lifecycle, and retry wrapper."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from notion_client import AsyncClient
from notion_client.errors import APIResponseError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector
from app.schemas.notion_auth_credentials import NotionAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

from ._helpers import (
    BASE_RETRY_DELAY,
    MAX_RATE_LIMIT_WAIT_SECONDS,
    MAX_RETRIES,
    MAX_RETRY_DELAY,
    MAX_TOTAL_RETRY_WAIT_SECONDS,
    RETRYABLE_STATUS_CODES,
    NotionAPIError,
    RetryCallbackType,
    T,
)
from .blocks import NotionBlocksMixin
from .pages import NotionPagesMixin

logger = logging.getLogger(__name__)


class NotionHistoryConnector(NotionBlocksMixin, NotionPagesMixin):
    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: NotionAuthCredentialsBase | None = None,
    ):
        """
        Initialize the NotionHistoryConnector with auto-refresh capability.

        Args:
            session: Database session for updating connector
            connector_id: Connector ID for direct updates
            credentials: Notion OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self._notion_client: AsyncClient | None = None
        # Track pages with skipped unsupported content (for user notifications)
        self._pages_with_skipped_content: list[str] = []
        # Optional callback to notify about retry progress (for user notifications)
        self._on_retry_callback: RetryCallbackType | None = None
        # Track if using legacy integration token (for upgrade notification)
        self._using_legacy_token: bool = False

    def set_retry_callback(self, callback: RetryCallbackType | None) -> None:
        """
        Set a callback function to be called when API calls are retried.

        This allows the indexer to receive notifications about rate limits
        and other transient errors, which can be used to update user-facing
        notifications.

        Args:
            callback: Async function with signature:
                      callback(retry_reason, attempt, max_attempts, wait_seconds) -> None
                      retry_reason: 'rate_limit', 'server_error', or 'timeout'
                      Set to None to disable callbacks.
        """
        self._on_retry_callback = callback

    async def _get_valid_token(self) -> str:
        """
        Get valid Notion access token, refreshing if needed.

        Returns:
            Valid access token

        Raises:
            ValueError: If credentials are missing or invalid
            Exception: If token refresh fails
        """
        # Load credentials from DB if not provided
        if self._credentials is None:
            result = await self._session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == self._connector_id
                )
            )
            connector = result.scalars().first()

            if not connector:
                raise ValueError(f"Connector {self._connector_id} not found")

            config_data = connector.config.copy()

            # Check for legacy integration token format first
            # (for connectors created before OAuth was implemented)
            legacy_token = config_data.get("NOTION_INTEGRATION_TOKEN")
            raw_access_token = config_data.get("access_token")

            # Validate that we have some form of token
            if not raw_access_token and not legacy_token:
                raise ValueError(
                    "Notion integration not properly connected. "
                    "Please remove and re-add the Notion connector."
                )

            # Decrypt credentials if they are encrypted
            token_encrypted = config_data.get("_token_encrypted", False)
            if token_encrypted and config.SECRET_KEY:
                try:
                    token_encryption = TokenEncryption(config.SECRET_KEY)

                    # Decrypt sensitive fields
                    if config_data.get("access_token"):
                        config_data["access_token"] = token_encryption.decrypt_token(
                            config_data["access_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                    logger.info(
                        f"Decrypted Notion credentials for connector {self._connector_id}"
                    )
                except Exception as e:  # per-item sync failure; continue batch
                    logger.error(
                        f"Failed to decrypt Notion credentials for connector {self._connector_id}: {e!s}"
                    )
                    raise ValueError(
                        "Notion credentials could not be decrypted. "
                        "Please remove and re-add the Notion connector."
                    ) from e

            # Handle legacy format: convert NOTION_INTEGRATION_TOKEN to access_token
            if not config_data.get("access_token") and legacy_token:
                config_data["access_token"] = legacy_token
                self._using_legacy_token = True
                logger.info(
                    f"Using legacy NOTION_INTEGRATION_TOKEN for connector {self._connector_id}"
                )

            # Final validation: ensure we have a valid access_token after all processing
            final_token = config_data.get("access_token")
            if not final_token or (
                isinstance(final_token, str) and not final_token.strip()
            ):
                raise ValueError(
                    "Notion access token is invalid or empty. "
                    "Please remove and re-add the Notion connector."
                )

            try:
                self._credentials = NotionAuthCredentialsBase.from_dict(config_data)
            except KeyError as e:
                raise ValueError(
                    f"Notion credentials are incomplete (missing {e}). "
                    "Please reconnect your Notion account."
                ) from e
            except Exception as e:  # per-item sync failure; continue batch
                raise ValueError(
                    f"Notion credentials format error: {e!s}. "
                    "Please reconnect your Notion account."
                ) from e

        # Check if token is expired and refreshable
        if self._credentials.is_expired and self._credentials.is_refreshable:
            try:
                logger.info(
                    f"Notion token expired for connector {self._connector_id}, refreshing..."
                )

                # Get connector for refresh
                result = await self._session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == self._connector_id
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    raise RuntimeError(
                        f"Connector {self._connector_id} not found; cannot refresh token."
                    )

                # Refresh token
                from app.routes.notion_add_connector_route import refresh_notion_token

                connector = await refresh_notion_token(self._session, connector)

                # Reload credentials after refresh
                config_data = connector.config.copy()
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY:
                    token_encryption = TokenEncryption(config.SECRET_KEY)
                    if config_data.get("access_token"):
                        config_data["access_token"] = token_encryption.decrypt_token(
                            config_data["access_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                self._credentials = NotionAuthCredentialsBase.from_dict(config_data)

                # Invalidate cached client so it's recreated with new token
                self._notion_client = None

                logger.info(
                    f"Successfully refreshed Notion token for connector {self._connector_id}"
                )
            except Exception as e:  # per-item sync failure; continue batch
                logger.error(
                    f"Failed to refresh Notion token for connector {self._connector_id}: {e!s}"
                )
                raise NotionAPIError(
                    "Failed to refresh your Notion connection. "
                    "Please try again or reconnect your Notion account."
                ) from e

        return self._credentials.access_token

    async def _get_client(self) -> AsyncClient:
        """
        Get or create Notion AsyncClient with valid token.

        Returns:
            Notion AsyncClient instance
        """
        if self._notion_client is None:
            token = await self._get_valid_token()
            self._notion_client = AsyncClient(auth=token)
        return self._notion_client

    async def _api_call_with_retry(
        self,
        api_func: Callable[..., Awaitable[T]],
        *args: Any,
        on_retry: RetryCallbackType | None = None,
        **kwargs: Any,
    ) -> T:
        """
        Execute Notion API call with retry logic and exponential backoff.

        Handles retryable errors per Notion API documentation:
        - 429 rate_limited: Uses Retry-After header value
        - 500 internal_server_error: Retries with exponential backoff
        - 502 bad_gateway: Retries with exponential backoff
        - 503 service_unavailable: Retries with exponential backoff
        - 504 gateway_timeout: Retries with exponential backoff

        Args:
            api_func: The async Notion API function to call
            *args: Positional arguments to pass to the API function
            on_retry: Optional callback to notify about retry progress.
                      Signature: async callback(retry_reason, attempt, max_attempts, wait_seconds)
                      retry_reason is one of: 'rate_limit', 'server_error', 'timeout'
            **kwargs: Keyword arguments to pass to the API function

        Returns:
            The result from the API call

        Raises:
            APIResponseError: If all retries are exhausted or error is not retryable
        """
        last_exception: APIResponseError | None = None
        retry_delay = BASE_RETRY_DELAY
        total_wait_time = 0.0

        for attempt in range(MAX_RETRIES):
            try:
                return await api_func(*args, **kwargs)

            except APIResponseError as e:
                last_exception = e

                # Check if this error is retryable
                if e.status not in RETRYABLE_STATUS_CODES:
                    # Not retryable (e.g., 400, 401, 403, 404) - raise immediately
                    raise

                # Check if we've exhausted retries
                if attempt == MAX_RETRIES - 1:
                    logger.error(
                        f"Notion API call failed after {MAX_RETRIES} retries. "
                        f"Last error: {e.status} {e.code}"
                    )
                    raise

                # Determine retry reason and wait time based on status code
                if e.status == 429:
                    # Rate limited - use Retry-After header if available
                    retry_reason = "rate_limit"
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                        except (ValueError, TypeError):
                            wait_time = retry_delay
                    else:
                        wait_time = retry_delay

                    # Avoid very long worker sleeps from external Retry-After values.
                    if wait_time > MAX_RATE_LIMIT_WAIT_SECONDS:
                        logger.warning(
                            f"Notion Retry-After ({wait_time}s) exceeds cap "
                            f"({MAX_RATE_LIMIT_WAIT_SECONDS}s). Clamping wait time."
                        )
                        wait_time = MAX_RATE_LIMIT_WAIT_SECONDS

                    logger.warning(
                        f"Notion API rate limited (429). "
                        f"Waiting {wait_time}s. Attempt {attempt + 1}/{MAX_RETRIES}"
                    )
                elif e.status == 504:
                    # Gateway timeout
                    retry_reason = "timeout"
                    wait_time = min(retry_delay, MAX_RETRY_DELAY)
                    logger.warning(
                        f"Notion API timeout ({e.status}). "
                        f"Retrying in {wait_time}s. Attempt {attempt + 1}/{MAX_RETRIES}"
                    )
                else:
                    # Server error (500/502/503) - use exponential backoff
                    retry_reason = "server_error"
                    wait_time = min(retry_delay, MAX_RETRY_DELAY)
                    logger.warning(
                        f"Notion API error {e.status} ({e.code}). "
                        f"Retrying in {wait_time}s. Attempt {attempt + 1}/{MAX_RETRIES}"
                    )

                # Notify about retry via callback (for user notifications)
                # Call before sleeping so user sees the message while we wait
                if total_wait_time + wait_time > MAX_TOTAL_RETRY_WAIT_SECONDS:
                    logger.error(
                        "Notion API retry budget exceeded "
                        f"({total_wait_time + wait_time:.1f}s > "
                        f"{MAX_TOTAL_RETRY_WAIT_SECONDS:.1f}s). Failing fast."
                    )
                    raise

                if on_retry:
                    try:
                        await on_retry(
                            retry_reason,
                            attempt + 1,  # 1-based for display
                            MAX_RETRIES,
                            wait_time,
                        )
                    except Exception as callback_error:  # per-item sync failure; continue batch
                        # Don't let callback errors break the retry logic
                        logger.warning(f"Retry callback failed: {callback_error}")

                # Wait before retrying
                await asyncio.sleep(wait_time)
                total_wait_time += wait_time

                # Exponential backoff for next attempt
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

        # This should not be reached, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state in retry logic")

    async def close(self):
        """Close the async client connection."""
        if self._notion_client:
            await self._notion_client.aclose()
            self._notion_client = None

    def get_pages_with_skipped_content(self) -> list[str]:
        """
        Get list of page titles that had unsupported content skipped.

        Returns:
            List of page titles with skipped content
        """
        return self._pages_with_skipped_content

    def get_skipped_content_count(self) -> int:
        """
        Get count of pages that had unsupported content skipped.

        Returns:
            Number of pages with skipped content
        """
        return len(self._pages_with_skipped_content)

    def is_using_legacy_token(self) -> bool:
        """
        Check if connector is using legacy integration token format.

        Returns:
            True if using legacy NOTION_INTEGRATION_TOKEN, False if using OAuth
        """
        return self._using_legacy_token

    def _record_skipped_content(self, page_title: str):
        """
        Record that a page had unsupported content skipped.

        Args:
            page_title: Title of the page with skipped content
        """
        if page_title not in self._pages_with_skipped_content:
            self._pages_with_skipped_content.append(page_title)

    @staticmethod
    def _api_error_message(error: APIResponseError) -> str:
        """Extract a stable, human-readable message from Notion API errors."""
        body = getattr(error, "body", None)
        if isinstance(body, dict):
            return str(body.get("message", str(error)))
        if body:
            return str(body)
        return str(error)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
