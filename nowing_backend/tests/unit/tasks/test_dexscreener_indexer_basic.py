"""Unit tests for DexScreener indexer — success and early-exit scenarios."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tasks.connector_indexers.dexscreener_indexer import index_dexscreener_pairs
from app.db import SearchSourceConnectorType

pytestmark = pytest.mark.unit


class TestDexScreenerIndexerBasic:
    """Happy-path and early-exit tests (connector not found, no tokens, API error, no pairs)."""

    @pytest.mark.asyncio
    async def test_index_pairs_success(self, async_session, mock_connector_config, mock_pair_data):
        """Test successful indexing of DexScreener pairs."""
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = mock_connector_config
        mock_connector.last_indexed_at = None

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.DexScreenerConnector") as mock_dex_client, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.get_user_long_context_llm") as mock_get_llm, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.generate_document_summary") as mock_gen_summary, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.create_document_chunks") as mock_create_chunks, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.update_connector_last_indexed", new_callable=AsyncMock) as mock_update_indexed, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = mock_connector

            mock_client_instance = MagicMock()
            mock_client_instance.get_token_pairs = AsyncMock(return_value=(mock_pair_data["pairs"], None))
            mock_client_instance.format_pair_to_markdown.side_effect = [
                "# Mock Markdown Content 1",
                "# Mock Markdown Content 2",
            ]
            mock_dex_client.return_value = mock_client_instance

            mock_get_llm.return_value = MagicMock()
            mock_gen_summary.side_effect = [
                ("Mock summary 1", [0.1] * 384),
                ("Mock summary 2", [0.2] * 384),
            ]
            mock_create_chunks.return_value = []

            mock_logger_instance = MagicMock()
            mock_logger_instance.log_task_start = AsyncMock(return_value=MagicMock(id=1))
            mock_logger_instance.log_task_progress = AsyncMock()
            mock_logger_instance.log_task_success = AsyncMock()
            mock_task_logger.return_value = mock_logger_instance

            documents_indexed, error = await index_dexscreener_pairs(
                session=async_session,
                connector_id=1,
                search_space_id=1,
                user_id="test-user-id",
            )

            assert error is None
            assert documents_indexed == 2
            mock_get_connector.assert_called_once()
            assert mock_client_instance.get_token_pairs.call_count == 2
            mock_update_indexed.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_pairs_connector_not_found(self, async_session):
        """Test indexer when connector is not found."""
        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = None

            mock_logger_instance = MagicMock()
            mock_logger_instance.log_task_start = AsyncMock(return_value=MagicMock(id=1))
            mock_logger_instance.log_task_progress = AsyncMock()
            mock_logger_instance.log_task_failure = AsyncMock()
            mock_task_logger.return_value = mock_logger_instance

            documents_indexed, error = await index_dexscreener_pairs(
                session=async_session,
                connector_id=999,
                search_space_id=1,
                user_id="test-user-id",
            )

            assert documents_indexed == 0
            assert error is not None
            assert "not found" in error.lower()
            mock_logger_instance.log_task_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_pairs_no_tokens_configured(self, async_session):
        """Test indexer when no tokens are configured."""
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = {"tokens": []}

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = mock_connector

            mock_logger_instance = MagicMock()
            mock_logger_instance.log_task_start = AsyncMock(return_value=MagicMock(id=1))
            mock_logger_instance.log_task_progress = AsyncMock()
            mock_logger_instance.log_task_failure = AsyncMock()
            mock_task_logger.return_value = mock_logger_instance

            documents_indexed, error = await index_dexscreener_pairs(
                session=async_session,
                connector_id=1,
                search_space_id=1,
                user_id="test-user-id",
            )

            assert documents_indexed == 0
            assert error == "No tokens configured for connector"
            mock_logger_instance.log_task_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_pairs_api_error(self, async_session, mock_connector_config):
        """Test indexer when API returns an error."""
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = mock_connector_config
        mock_connector.last_indexed_at = None

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.DexScreenerConnector") as mock_dex_client, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.update_connector_last_indexed") as mock_update_indexed, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = mock_connector

            mock_client_instance = MagicMock()
            mock_client_instance.get_token_pairs = AsyncMock(return_value=(None, "API Error: Rate limit exceeded"))
            mock_dex_client.return_value = mock_client_instance

            mock_logger_instance = MagicMock()
            mock_logger_instance.log_task_start = AsyncMock(return_value=MagicMock(id=1))
            mock_logger_instance.log_task_progress = AsyncMock()
            mock_logger_instance.log_task_success = AsyncMock()
            mock_task_logger.return_value = mock_logger_instance

            documents_indexed, error = await index_dexscreener_pairs(
                session=async_session,
                connector_id=1,
                search_space_id=1,
                user_id="test-user-id",
            )

            assert error is None
            assert documents_indexed == 0
            mock_update_indexed.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_pairs_no_pairs_found(self, async_session, mock_connector_config):
        """Test indexer when API returns no pairs."""
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = mock_connector_config
        mock_connector.last_indexed_at = None

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.DexScreenerConnector") as mock_dex_client, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.update_connector_last_indexed") as mock_update_indexed, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = mock_connector

            mock_client_instance = MagicMock()
            mock_client_instance.get_token_pairs = AsyncMock(return_value=([], None))
            mock_dex_client.return_value = mock_client_instance

            mock_logger_instance = MagicMock()
            mock_logger_instance.log_task_start = AsyncMock(return_value=MagicMock(id=1))
            mock_logger_instance.log_task_progress = AsyncMock()
            mock_logger_instance.log_task_success = AsyncMock()
            mock_task_logger.return_value = mock_logger_instance

            documents_indexed, error = await index_dexscreener_pairs(
                session=async_session,
                connector_id=1,
                search_space_id=1,
                user_id="test-user-id",
            )

            assert error is None
            assert documents_indexed == 0
            mock_update_indexed.assert_called_once()
