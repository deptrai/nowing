"""Unit tests for Telegram media streaming offload task (Story 22.3 / AC-2 / AD-4).

Validates non-blocking S3/MinIO streaming media offload using aiobotocore, ensuring
no full-file disk buffering on workers and proper database status updates.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# AC-2: Non-Blocking S3/MinIO Streaming Media Offload (AD-4)
# ---------------------------------------------------------------------------


class TestTelegramMediaStreamingTask:
    """Validate streaming media upload behavior without disk buffering."""

    @pytest.mark.asyncio
    async def test_stream_media_single_put_under_5mb(self) -> None:
        """Files < 5MB should stream via single put_object directly to S3/MinIO."""
        from app.tasks.telegram_media_tasks import download_telegram_media_task

        mock_s3_client = AsyncMock()
        mock_s3_client.put_object = AsyncMock(return_value={"ETag": '"test-etag"'})

        async def fake_stream(media_id: int | str) -> AsyncGenerator[bytes, None]:
            yield b"chunk1"
            yield b"chunk2"

        with patch("app.tasks.telegram_media_tasks.get_s3_client", return_value=mock_s3_client), \
             patch("app.tasks.telegram_media_tasks.get_telegram_media_stream", side_effect=fake_stream), \
             patch("app.tasks.telegram_media_tasks.update_media_record", new_callable=AsyncMock) as mock_db:

            result = await download_telegram_media_task(
                message_id=1234,
                media_id=5678,
                file_size=2 * 1024 * 1024,  # 2MB
                mime_type="image/jpeg",
                workspace_id=1,
            )

            mock_s3_client.put_object.assert_awaited_once()
            mock_db.assert_awaited_once()
            assert result["status"] == "uploaded"
            assert "storage_url" in result

    @pytest.mark.asyncio
    async def test_stream_media_multipart_upload_over_5mb(self) -> None:
        """Files >= 5MB must use multipart upload with part size >= 5MB."""
        from app.tasks.telegram_media_tasks import download_telegram_media_task

        mock_s3_client = AsyncMock()
        mock_s3_client.create_multipart_upload = AsyncMock(return_value={"UploadId": "upload-123"})
        mock_s3_client.upload_part = AsyncMock(return_value={"ETag": '"part-etag"'})
        mock_s3_client.complete_multipart_upload = AsyncMock(return_value={"Location": "https://s3.nowing.net/media.mp4"})

        async def fake_large_stream(media_id: int | str) -> AsyncGenerator[bytes, None]:
            # 2 chunks of 6MB each
            yield b"x" * (6 * 1024 * 1024)
            yield b"y" * (6 * 1024 * 1024)

        with patch("app.tasks.telegram_media_tasks.get_s3_client", return_value=mock_s3_client), \
             patch("app.tasks.telegram_media_tasks.get_telegram_media_stream", side_effect=fake_large_stream), \
             patch("app.tasks.telegram_media_tasks.update_media_record", new_callable=AsyncMock):

            result = await download_telegram_media_task(
                message_id=1234,
                media_id=5679,
                file_size=15 * 1024 * 1024,  # 15MB
                mime_type="video/mp4",
                workspace_id=1,
            )

            mock_s3_client.create_multipart_upload.assert_awaited_once()
            mock_s3_client.complete_multipart_upload.assert_awaited_once()
            assert result["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_handles_s3_failure_gracefully(self) -> None:
        """Network/S3 failure should mark record as failed and raise for Celery retry."""
        from app.tasks.telegram_media_tasks import download_telegram_media_task

        mock_s3_client = AsyncMock()
        mock_s3_client.put_object = AsyncMock(side_effect=Exception("S3 Connection Timeout"))

        with patch("app.tasks.telegram_media_tasks.get_s3_client", return_value=mock_s3_client), \
             patch("app.tasks.telegram_media_tasks.update_media_record", new_callable=AsyncMock) as mock_db:

            with pytest.raises(Exception, match="S3 Connection Timeout"):
                await download_telegram_media_task(
                    message_id=1234,
                    media_id=5680,
                    file_size=1024,
                    mime_type="image/png",
                    workspace_id=1,
                )

            mock_db.assert_awaited_with(media_id=5680, status="failed", error="S3 Connection Timeout")
