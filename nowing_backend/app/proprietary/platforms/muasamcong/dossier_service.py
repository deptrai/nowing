"""Tender Dossier Ingestion & S3 128KB Chunked Streaming Service (Story 16.5 / AD-PROC-2, AD-PROC-3)."""

from __future__ import annotations

import asyncio
import io
import ipaddress
import logging
import re
import zipfile
from typing import Any
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader

from app.proprietary.platforms.muasamcong.schemas import TextChunk

logger = logging.getLogger(__name__)

# AD-PROC-2 Architecture Invariant constants
CHUNK_SIZE_BYTES = 131072  # 128 KB HTTP streaming chunks
MIN_S3_PART_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB minimum part size for AWS S3 Multipart Upload
MAX_MEMORY_FOOTPRINT_MB = 32
DEFAULT_BUCKET = "nowing-procurement-docs"

# Trusted hostnames for public procurement dossiers
ALLOWED_PROCUREMENT_HOSTS = {
    "muasamcong.mpi.gov.vn",
    "egp.mpi.gov.vn",
    "dauthau.mpi.gov.vn",
    "localhost",
    "127.0.0.1",
}


def validate_dossier_url(url: str, allow_custom_hosts: bool = False) -> None:
    """Validates dossier URL against SSRF attacks (AD-PROC-2 security invariant)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}': only http/https allowed.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Invalid dossier URL: missing hostname.")

    if (
        not allow_custom_hosts
        and not any(hostname == allowed or hostname.endswith(f".{allowed}") for allowed in ALLOWED_PROCUREMENT_HOSTS)
    ):
        raise ValueError(f"Host '{hostname}' is not in the allowed procurement domain whitelist.")

    # Check for private / loopback IP address SSRF attempts
    try:
        ip = ipaddress.ip_address(hostname)
        if (ip.is_private or ip.is_loopback or ip.is_link_local) and hostname not in ("localhost", "127.0.0.1"):
            raise ValueError(f"Direct access to private/internal IP '{hostname}' is forbidden.")
    except ValueError:
        # Not a raw IP address, which is normal for domain names
        pass


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
        allow_custom_hosts: bool = False,
    ) -> str:
        """Streams dossier binary directly to S3 with 5MB multipart buffers (AD-PROC-2).

        Ensures peak memory usage remains <= 32MB by never buffering the entire
        file in RAM, while satisfying AWS S3 minimum 5MB part size requirement.
        """
        # Validate SSRF safety
        validate_dossier_url(dossier_url, allow_custom_hosts=allow_custom_hosts)

        # Sanitize keys against path traversal
        safe_bid_no = re.sub(r"[^A-Za-z0-9_-]", "_", bid_no) or "UNKNOWN"
        safe_turn_no = re.sub(r"[^A-Za-z0-9_-]", "_", bid_turn_no) or "00"
        s3_key = f"{safe_bid_no}_{safe_turn_no}/hsmt.pdf"
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

                buffer = bytearray()

                # Stream in 128KB chunks, accumulating up to 5MB S3 part threshold
                async for chunk in resp.aiter_bytes(chunk_size=CHUNK_SIZE_BYTES):
                    if not chunk:
                        continue
                    buffer.extend(chunk)

                    if len(buffer) >= MIN_S3_PART_SIZE_BYTES:
                        part_resp = await s3_client.upload_part(
                            Bucket=self.bucket_name,
                            Key=s3_key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=bytes(buffer),
                        )
                        parts.append({
                            "PartNumber": part_number,
                            "ETag": part_resp["ETag"],
                        })
                        part_number += 1
                        buffer.clear()

                # Upload any remaining tail buffer (allowed to be < 5MB for the last part)
                if len(buffer) > 0:
                    part_resp = await s3_client.upload_part(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=bytes(buffer),
                    )
                    parts.append({
                        "PartNumber": part_number,
                        "ETag": part_resp["ETag"],
                    })
                    buffer.clear()

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
        """Extracts text from PDF or ZIP dossier safely."""
        try:
            if isinstance(stream, bytes):
                raw_bytes = stream
            else:
                raw_bytes = stream.getvalue() if hasattr(stream, "getvalue") else stream.read()

            if not raw_bytes:
                return ""

            # Check if this is a ZIP archive
            if raw_bytes.startswith(b"PK\x03\x04"):
                extracted_docs = []
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                        for filename in zf.namelist():
                            if filename.lower().endswith(".pdf"):
                                with zf.open(filename) as pdf_file:
                                    reader = PdfReader(io.BytesIO(pdf_file.read()))
                                    for page in reader.pages:
                                        t = page.extract_text()
                                        if t:
                                            extracted_docs.append(t)
                except Exception as zip_exc:
                    logger.warning("ZIP extraction failed: %s", str(zip_exc))
                return "\n\n".join(extracted_docs)

            reader = PdfReader(io.BytesIO(raw_bytes))
            extracted_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text.append(page_text)
            return "\n\n".join(extracted_text)
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", str(exc))
            return ""

    async def extract_text_from_pdf_stream_async(self, stream: io.BytesIO | bytes) -> str:
        """Asynchronously extracts text in a worker thread without blocking asyncio loop."""
        return await asyncio.to_thread(self.extract_text_from_pdf_stream, stream)

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
        step_size = max(char_chunk_size - char_overlap, 1)

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

