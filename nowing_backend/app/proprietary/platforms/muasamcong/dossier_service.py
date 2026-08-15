"""Tender Dossier Ingestion & S3 128KB Chunked Streaming Service (Story 16.5 / AD-PROC-2, AD-PROC-3)."""

from __future__ import annotations

import io
import logging
from typing import Any

import httpx
from pypdf import PdfReader

from app.proprietary.platforms.muasamcong.schemas import TextChunk

logger = logging.getLogger(__name__)

# AD-PROC-2 Architecture Invariant constants
CHUNK_SIZE_BYTES = 131072  # 128 KB
MAX_MEMORY_FOOTPRINT_MB = 32
DEFAULT_BUCKET = "nowing-procurement-docs"


class TenderDossierService:
    """Handles streaming download of large E-HSMT dossiers and vector chunking."""

    def __init__(self, bucket_name: str = DEFAULT_BUCKET) -> None:
        self.bucket_name = bucket_name

    async def stream_download_and_upload_s3(
        self,
        dossier_url: str,
        bid_no: str,
        bid_turn_no: str = "00",
        s3_client: Any = None,
    ) -> str:
        """Streams dossier binary directly to S3 in 128KB chunks (AD-PROC-2).

        Ensures peak memory usage remains <= 32MB by never buffering the entire
        file in RAM.
        """
        s3_key = f"{bid_no}_{bid_turn_no}/hsmt.pdf"
        s3_uri = f"s3://{self.bucket_name}/{s3_key}"

        if s3_client is None:
            logger.info("No s3_client provided; simulating S3 upload to %s", s3_uri)
            return s3_uri

        # 1. Initialize Multipart Upload
        multipart = await s3_client.create_multipart_upload(
            Bucket=self.bucket_name,
            Key=s3_key,
        )
        upload_id = multipart["UploadId"]
        parts: list[dict[str, Any]] = []
        part_number = 1

        try:
            async with (
                httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client,
                client.stream("GET", dossier_url) as resp,
            ):
                resp.raise_for_status()

                # Stream in 128KB chunks directly to S3 part upload
                async for chunk in resp.aiter_bytes(chunk_size=CHUNK_SIZE_BYTES):
                    if not chunk:
                        continue
                    part_resp = await s3_client.upload_part(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk,
                    )
                    parts.append({
                        "PartNumber": part_number,
                        "ETag": part_resp["ETag"],
                    })
                    part_number += 1

            # 2. Complete Multipart Upload
            await s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            return s3_uri

        except Exception as exc:
            logger.error(
                "S3 multipart upload failed for bid %s: %s. Aborting upload.",
                bid_no,
                str(exc),
            )
            try:
                if hasattr(s3_client, "abort_multipart_upload"):
                    await s3_client.abort_multipart_upload(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        UploadId=upload_id,
                    )
            except Exception:
                pass
            raise

    def extract_text_from_pdf_stream(self, stream: io.BytesIO | bytes) -> str:
        """Extracts text from PDF document safely."""
        try:
            if isinstance(stream, bytes):
                stream = io.BytesIO(stream)
            reader = PdfReader(stream)
            extracted_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text.append(page_text)
            return "\n\n".join(extracted_text)
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", str(exc))
            return ""

    def split_text_into_chunks(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> list[TextChunk]:
        """Splits document text into overlapping token/character chunks for pgvector."""
        if not text or not text.strip():
            return []

        # Heuristic character chunk size (~3 chars per token)
        char_chunk_size = max(chunk_size * 3, 200)
        char_overlap = min(chunk_overlap * 3, char_chunk_size // 2)
        step_size = char_chunk_size - char_overlap

        # Normalize line endings
        normalized = text.replace("\r\n", "\n")
        raw_lines = [line.strip() for line in normalized.split("\n") if line.strip()]

        chunks: list[TextChunk] = []
        current_lines: list[str] = []
        current_len = 0
        current_section: str | None = None
        chunk_idx = 0

        for line in raw_lines:
            if any(line.startswith(prefix) for prefix in ("Chương", "Mục", "Phần", "Điều", "1.", "2.", "3.", "4.")) and len(line) < 120:
                current_section = line

            # If a single line is excessively long, slice it
            if len(line) > char_chunk_size:
                start = 0
                while start < len(line):
                    sub = line[start : start + char_chunk_size]
                    if current_lines:
                        content_str = "\n".join(current_lines)
                        chunks.append(
                            TextChunk(
                                chunk_index=chunk_idx,
                                content=content_str,
                                section_title=current_section,
                            )
                        )
                        chunk_idx += 1
                        current_lines = []
                        current_len = 0
                    chunks.append(
                        TextChunk(
                            chunk_index=chunk_idx,
                            content=sub,
                            section_title=current_section,
                        )
                    )
                    chunk_idx += 1
                    start += step_size
                continue

            if current_len + len(line) + 1 > char_chunk_size and current_lines:
                content_str = "\n".join(current_lines)
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_idx,
                        content=content_str,
                        section_title=current_section,
                    )
                )
                chunk_idx += 1

                # Retain overlap lines if possible
                overlap_lines: list[str] = []
                overlap_len = 0
                for prev_line in reversed(current_lines):
                    if overlap_len + len(prev_line) + 1 <= char_overlap:
                        overlap_lines.insert(0, prev_line)
                        overlap_len += len(prev_line) + 1
                    else:
                        break

                current_lines = [*overlap_lines, line]
                current_len = sum(len(line_item) + 1 for line_item in current_lines)
            else:
                current_lines.append(line)
                current_len += len(line) + 1


        if current_lines:
            content_str = "\n".join(current_lines)
            chunks.append(
                TextChunk(
                    chunk_index=chunk_idx,
                    content=content_str,
                    section_title=current_section,
                )
            )

        return chunks
