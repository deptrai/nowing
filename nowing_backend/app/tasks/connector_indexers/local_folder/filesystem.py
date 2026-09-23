"""Local filesystem scanning and content hashing helpers."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path


async def _read_file_content(
    file_path: str, filename: str, *, vision_llm=None, processing_mode: str = "basic"
) -> str:
    """Read file content via the unified ETL pipeline.

    All file types (plaintext, audio, direct-convert, document, image) are
    handled by ``EtlPipelineService``.
    """
    from app.etl_pipeline.cache import extract_with_cache
    from app.etl_pipeline.etl_document import EtlRequest, ProcessingMode

    mode = ProcessingMode.coerce(processing_mode)
    result = await extract_with_cache(
        EtlRequest(file_path=file_path, filename=filename, processing_mode=mode),
        vision_llm=vision_llm,
    )
    return result.markdown_content


def _content_hash(content: str, workspace_id: int) -> str:
    """SHA-256 hash of content scoped to a workspace.

    Matches the format used by ``compute_content_hash`` in the unified
    pipeline so that dedup checks are consistent.
    """
    return hashlib.sha256(f"{workspace_id}:{content}".encode()).hexdigest()


def _compute_raw_file_hash(file_path: str) -> str:
    """SHA-256 hash of the raw file bytes.

    Much cheaper than ETL/OCR extraction -- only performs sequential I/O.
    Used as a pre-filter to skip expensive content extraction when the
    underlying file hasn't changed at all.
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def _compute_file_content_hash(
    file_path: str,
    filename: str,
    workspace_id: int,
    *,
    vision_llm=None,
    processing_mode: str = "basic",
) -> tuple[str, str]:
    """Read a file (via ETL if needed) and compute its content hash.

    Returns (content_text, content_hash).
    """
    content = await _read_file_content(
        file_path, filename, vision_llm=vision_llm, processing_mode=processing_mode
    )
    return content, _content_hash(content, workspace_id)


def scan_folder(
    folder_path: str,
    file_extensions: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[dict]:
    """Walk a directory and return a list of file entries.

    Args:
        folder_path: Absolute path to the folder to scan.
        file_extensions: If provided, only include files with these extensions
            (e.g. [".md", ".txt"]). ``None`` means include all files.
        exclude_patterns: Directory/file names to exclude.  Any path component
            matching one of these strings is skipped.

    Returns:
        List of dicts with keys: path, relative_path, name, modified_at, size.
    """
    root = Path(folder_path)
    if not root.exists():
        raise ValueError(f"Folder path does not exist: {folder_path}")

    if exclude_patterns is None:
        exclude_patterns = []

    files: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)

        dirnames[:] = [d for d in dirnames if d not in exclude_patterns]

        if any(part in exclude_patterns for part in rel_dir.parts):
            continue

        for fname in filenames:
            if fname in exclude_patterns:
                continue

            full = Path(dirpath) / fname

            if (
                file_extensions is not None
                and full.suffix.lower() not in file_extensions
            ):
                continue

            try:
                stat = full.stat()
                rel_path = full.relative_to(root)
                files.append(
                    {
                        "path": str(full),
                        "relative_path": str(rel_path),
                        "name": full.name,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                        "size": stat.st_size,
                    }
                )
            except OSError as e:
                from app.tasks.connector_indexers.base import logger

                logger.warning(f"Could not stat file {full}: {e}")

    return files
