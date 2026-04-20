"""Unit tests for DexScreener indexer — filtering, LLM fallback, and error handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tasks.connector_indexers.dexscreener_indexer import index_dexscreener_pairs
from app.db import SearchSourceConnectorType

pytestmark = pytest.mark.unit


class TestDexScreenerIndexerFiltering:
    """Tests for token/pair filtering, LLM fallback, and database error handling."""

    @pytest.mark.asyncio
    async def test_index_pairs_skips_invalid_tokens(self, async_session):
        """Test indexer skips tokens with missing chain or address."""
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = {
            "tokens": [
                {"chain": "ethereum"},  # Missing address
                {"address": "0x123"},  # Missing chain
                {"chain": "solana", "address": "So11111111111111111111111111111111111111112", "name": "SOL"},
            ]
        }
        mock_connector.last_indexed_at = None

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.DexScreenerConnector") as mock_dex_client, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.get_user_long_context_llm") as mock_get_llm, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.generate_document_summary") as mock_gen_summary, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.create_document_chunks") as mock_create_chunks, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.update_connector_last_indexed") as mock_update_indexed, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = mock_connector

            mock_pair = {
                "pairAddress": "0xabc",
                "baseToken": {"symbol": "SOL"},
                "quoteToken": {"symbol": "USDC"},
                "dexId": "raydium",
                "priceUsd": "100.0",
                "liquidity": {"usd": 1000000},
                "volume": {"h24": 500000},
                "priceChange": {"h24": 2.5},
            }
            mock_client_instance = MagicMock()
            mock_client_instance.get_token_pairs = AsyncMock(return_value=([mock_pair], None))
            mock_client_instance.format_pair_to_markdown.return_value = "# Mock Markdown"
            mock_dex_client.return_value = mock_client_instance

            mock_get_llm.return_value = MagicMock()
            mock_gen_summary.return_value = ("Mock summary", [0.1] * 384)
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
            assert documents_indexed == 1
            assert mock_client_instance.get_token_pairs.call_count == 1

    @pytest.mark.asyncio
    async def test_index_pairs_skips_pairs_without_address(self, async_session, mock_connector_config, mock_pair_data):
        """Test indexer skips pairs without pairAddress."""
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = mock_connector_config
        mock_connector.last_indexed_at = None

        invalid_pair = mock_pair_data["pairs"][0].copy()
        del invalid_pair["pairAddress"]

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.DexScreenerConnector") as mock_dex_client, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.update_connector_last_indexed") as mock_update_indexed, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = mock_connector

            mock_client_instance = MagicMock()
            mock_client_instance.get_token_pairs = AsyncMock(return_value=([invalid_pair], None))
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

    @pytest.mark.asyncio
    async def test_index_pairs_without_llm(self, async_session, mock_connector_config, mock_pair_data):
        """Test indexer works without LLM service (fallback to basic summary)."""
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = mock_connector_config
        mock_connector.last_indexed_at = None

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.DexScreenerConnector") as mock_dex_client, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.get_user_long_context_llm") as mock_get_llm, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.create_document_chunks") as mock_create_chunks, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.update_connector_last_indexed", new_callable=AsyncMock) as mock_update_indexed, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.config") as mock_config, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.return_value = mock_connector

            mock_client_instance = MagicMock()
            mock_client_instance.get_token_pairs = AsyncMock(return_value=(mock_pair_data["pairs"], None))
            mock_client_instance.format_pair_to_markdown.side_effect = [
                "# Mock Markdown 1",
                "# Mock Markdown 2",
            ]
            mock_dex_client.return_value = mock_client_instance

            mock_get_llm.return_value = None

            mock_embedding_instance = MagicMock()
            mock_embedding_instance.embed.side_effect = [
                [0.1] * 384,
                [0.2] * 384,
            ]
            mock_config.embedding_model_instance = mock_embedding_instance
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
            mock_embedding_instance.embed.assert_called()

    @pytest.mark.asyncio
    async def test_index_pairs_update_last_indexed_false(self, async_session, mock_connector_config, mock_pair_data):
        """Test indexer respects update_last_indexed=False parameter."""
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
                "# Mock Markdown 1",
                "# Mock Markdown 2",
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
                update_last_indexed=False,
            )

            assert error is None
            assert documents_indexed == 2
            mock_update_indexed.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_pairs_database_error(self, async_session, mock_connector_config):
        """Test indexer handles database errors gracefully."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        mock_connector.config = mock_connector_config

        with patch("app.tasks.connector_indexers.dexscreener_indexer.get_connector_by_id") as mock_get_connector, \
             patch("app.tasks.connector_indexers.dexscreener_indexer.TaskLoggingService") as mock_task_logger:

            mock_get_connector.side_effect = SQLAlchemyError("Database connection failed")

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
            assert error is not None
            assert "Database error" in error
            mock_logger_instance.log_task_failure.assert_called_once()
