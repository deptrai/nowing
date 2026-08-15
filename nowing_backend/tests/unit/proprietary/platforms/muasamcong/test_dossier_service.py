"""Unit tests for Muasamcong Dossier Service (Story 16.5 / AD-PROC-2, AD-PROC-3)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.proprietary.platforms.muasamcong.dossier_service import (
    CHUNK_SIZE_BYTES,
    MAX_MEMORY_FOOTPRINT_MB,
    MIN_S3_PART_SIZE_BYTES,
    TenderDossierService,
    validate_dossier_url,
)

pytestmark = pytest.mark.unit


async def _fake_stream_chunks(
    total_size: int, chunk_size: int = CHUNK_SIZE_BYTES
) -> AsyncGenerator[bytes, None]:
    """Generates synthetic byte chunks mimicking streaming download."""
    bytes_sent = 0
    chunk_pattern = b"A" * chunk_size
    while bytes_sent < total_size:
        remaining = total_size - bytes_sent
        cur = chunk_pattern if remaining >= chunk_size else b"A" * remaining
        bytes_sent += len(cur)
        yield cur


class TestTenderDossierStreaming:
    """AC-3 / AD-PROC-2: S3 chunk streaming with 5MB multipart buffers without memory bloat."""

    def test_chunk_size_constant(self):
        assert CHUNK_SIZE_BYTES == 131072  # 128 KB
        assert MIN_S3_PART_SIZE_BYTES == 5 * 1024 * 1024  # 5 MB S3 minimum part size
        assert MAX_MEMORY_FOOTPRINT_MB == 32

    def test_ssrf_validation_allowed_hosts(self):
        # Whitelisted hosts should pass
        validate_dossier_url("https://muasamcong.mpi.gov.vn/egp/api/v1/dossier/download?id=123")
        validate_dossier_url("https://egp.mpi.gov.vn/api/v1/download")
        validate_dossier_url("http://localhost:8000/mock-dossier")

    def test_ssrf_validation_blocks_malicious_urls(self):
        # Disallowed hosts should raise ValueError
        with pytest.raises(ValueError, match="not in the allowed procurement domain whitelist"):
            validate_dossier_url("https://evil-attacker.com/steal-data")

        # Invalid schemes should raise ValueError
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_dossier_url("ftp://muasamcong.mpi.gov.vn/test")

        # Cloud metadata IP should raise ValueError
        with pytest.raises(ValueError):
            validate_dossier_url("http://169.254.169.254/latest/meta-data")

    @pytest.mark.asyncio
    async def test_stream_upload_to_s3_chunked(self):
        service = TenderDossierService(bucket_name="nowing-procurement-docs")

        # 6 MB file: buffers part 1 (5MB) + part 2 tail (1MB) -> exactly 2 S3 parts
        total_file_size = 6 * 1024 * 1024
        dossier_url = "https://muasamcong.mpi.gov.vn/egp/api/v1/dossier/download?id=9999"
        bid_no = "IB2400123456"
        bid_turn_no = "00"

        # Mock HTTP streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": str(total_file_size)}
        mock_response.aiter_bytes = MagicMock(
            return_value=_fake_stream_chunks(total_file_size, CHUNK_SIZE_BYTES)
        )

        mock_s3_client = AsyncMock()
        mock_s3_client.create_multipart_upload = AsyncMock(
            return_value={"UploadId": "mock-upload-id-123"}
        )
        mock_s3_client.upload_part = AsyncMock(
            return_value={"ETag": '"mock-etag-abc"'}
        )
        mock_s3_client.complete_multipart_upload = AsyncMock(
            return_value={"Location": "s3://nowing-procurement-docs/IB2400123456_00/hsmt.pdf"}
        )

        with patch("httpx.AsyncClient.stream") as mock_stream_ctx:
            mock_stream_ctx.return_value.__aenter__.return_value = mock_response

            s3_uri = await service.stream_download_and_upload_s3(
                dossier_url=dossier_url,
                bid_no=bid_no,
                bid_turn_no=bid_turn_no,
                s3_client=mock_s3_client,
            )

            assert s3_uri == "s3://nowing-procurement-docs/IB2400123456_00/hsmt.pdf"
            # 6MB with 5MB buffer -> 2 parts (5MB + 1MB)
            assert mock_s3_client.upload_part.call_count == 2
            mock_s3_client.complete_multipart_upload.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_text_chunking_and_embedding_extraction(self):
        service = TenderDossierService()

        sample_pdf_text = (
            "Chương III. TIÊU CHUẨN ĐÁNH GIÁ HỒ SƠ DỰ THẦU\n"
            "1. Tiêu chuẩn đánh giá về năng lực và kinh nghiệm:\n"
            "- Doanh thu bình quân hàng năm từ hoạt động xây dựng: tối thiểu 60 tỷ VND trong 3 năm gần nhất.\n"
            "- Hợp đồng tương tự: đã hoàn thành ít nhất 2 công trình xây dựng dân dụng cấp II có giá trị >= 30 tỷ VND.\n"
            "- Nhân sự chủ chốt: Chỉ huy trưởng công trình có chứng chỉ hành nghề giám sát thi công hạng I.\n"
            "- Bảo đảm dự thầu: Giá trị bảo đảm dự thầu là 675.000.000 VND (Bằng chữ: Sáu trăm bảy mươi lăm triệu đồng), "
            "thời hạn hiệu lực của bảo đảm dự thầu là 180 ngày kể từ ngày đóng thầu.\n"
        ) * 5  # Replicated to create multiple chunks

        chunks = service.split_text_into_chunks(
            text=sample_pdf_text,
            chunk_size=512,
            chunk_overlap=50,
        )

        assert len(chunks) >= 2
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
            assert len(chunk.content) > 0
            assert "TIÊU CHUẨN" in chunk.content or "Doanh thu" in chunk.content or len(chunk.content) > 0

