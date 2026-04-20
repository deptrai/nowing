"""Pure-function tests for PageLimitService.estimate_pages_from_metadata.

These have no mocks — pure input/output, no I/O.
Integration tests (quota gating in connector indexers) are in test_page_limits.py.
"""

import pytest

from app.services.page_limit_service import PageLimitService

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "ext,size_bytes,expected_pages",
    [
        # PDF: ~100 KB/page
        (".pdf", 100 * 1024, 1),
        (".pdf", 500 * 1024, 5),
        (".pdf", 1024 * 1024, 10),
        # DOCX: ~50 KB/page
        (".docx", 50 * 1024, 1),
        (".docx", 200 * 1024, 4),
        # PPTX: ~200 KB/page
        (".pptx", 600 * 1024, 3),
        # XLSX: ~100 KB/page
        (".xlsx", 300 * 1024, 3),
        # TXT: ~3000 bytes/page
        (".txt", 9000, 3),
        # Images: always 1 page regardless of size
        (".jpg", 5_000_000, 1),
        (".png", 5_000_000, 1),
        (".gif", 5_000_000, 1),
        (".webp", 5_000_000, 1),
        # Audio: ~1 MB/page
        (".mp3", 3 * 1024 * 1024, 3),
        # Video: ~5 MB/page
        (".mp4", 15 * 1024 * 1024, 3),
        # Unknown extension: ~80 KB/page
        (".xyz", 160 * 1024, 2),
        # Edge cases: zero/negative/tiny → minimum 1
        (".pdf", 0, 1),
        (".pdf", -500, 1),
        (".pdf", 50, 1),
        # EPUB: ~50 KB/page
        (".epub", 250 * 1024, 5),
    ],
    ids=[
        "pdf_1page", "pdf_5pages", "pdf_10pages",
        "docx_1page", "docx_4pages",
        "pptx_3pages",
        "xlsx_3pages",
        "txt_3pages",
        "jpg_1page", "png_1page", "gif_1page", "webp_1page",
        "mp3_3pages",
        "mp4_3pages",
        "xyz_2pages",
        "pdf_zero", "pdf_negative", "pdf_tiny",
        "epub_5pages",
    ],
)
def test_estimate_pages_from_metadata(ext, size_bytes, expected_pages):
    """PageLimitService.estimate_pages_from_metadata returns correct page count for each file type."""
    assert PageLimitService.estimate_pages_from_metadata(ext, size_bytes) == expected_pages
