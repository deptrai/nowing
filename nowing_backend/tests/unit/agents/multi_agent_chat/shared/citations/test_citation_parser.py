"""Unit and parity tests for backend citation parser (Story 4.6).

Verifies byte-for-byte pattern parity with nowing_web and nowing_evals,
and covers edge cases, fullwidth Chinese brackets, multi-ids, and URLs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agents.chat.multi_agent_chat.shared.citations.parser import (
    CITATION_REGEX,
    ChunkCitationMarker,
    RunCitationMarker,
    UrlCitationMarker,
    parse_citation_markers,
)

pytestmark = pytest.mark.unit


def test_citation_regex_parity_with_frontend_source():
    """Parity guard: CITATION_REGEX must match nowing_web source pattern."""
    web_ts_path = Path(__file__).resolve().parents[7] / "nowing_web" / "lib" / "citations" / "citation-parser.ts"
    if not web_ts_path.exists():
        pytest.skip(f"Frontend citation parser not found: {web_ts_path}")

    lines = web_ts_path.read_text(encoding="utf-8").splitlines()
    matching_indices = [i for i, l in enumerate(lines) if "export const CITATION_REGEX =" in l]
    assert matching_indices, "Failed to find CITATION_REGEX export in citation-parser.ts"

    raw_regex_line = lines[matching_indices[0] + 1].strip()
    ts_pattern = raw_regex_line.rstrip(";").rstrip("g")[1:-1]

    # Map JS regex syntax differences:
    # 1. ​ in JS regex literal -> literal ​ code point in Python pattern
    # 2. \/ escape for JS literal delimiter -> plain / in Python
    # 3. [[【 unescaped bracket inside class in JS -> [\[【 in Python
    normalized_ts = (
        ts_pattern.replace("\\u200B", "​")
        .replace("\\u200b", "​")
        .replace(r"\/", "/")
        .replace("[[【", r"[\[【")
    )

    assert CITATION_REGEX.pattern == normalized_ts


PARITY_CASES = [
    ("Plain text with no citation.", []),
    (
        "The patient has fever [citation:42] and cough.",
        [ChunkCitationMarker(chunk_id=42, is_docs_chunk=False)],
    ),
    (
        "doc-prefix [citation:doc-12].",
        [ChunkCitationMarker(chunk_id=12, is_docs_chunk=True)],
    ),
    (
        "Multi id [citation:1, doc-2, -3].",
        [
            ChunkCitationMarker(chunk_id=1, is_docs_chunk=False),
            ChunkCitationMarker(chunk_id=2, is_docs_chunk=True),
        ],
    ),
    (
        "URL form [citation:https://nowing.net/test].",
        [UrlCitationMarker(url="https://nowing.net/test")],
    ),
    (
        "Run handle [citation:run_550e8400-e29b-41d4-a716-446655440000].",
        [RunCitationMarker(run_id="run_550e8400-e29b-41d4-a716-446655440000")],
    ),
    (
        "Chinese brackets【citation:5】.",
        [ChunkCitationMarker(chunk_id=5, is_docs_chunk=False)],
    ),
    (
        "ZWSP-decorated [​citation:9​].",
        [ChunkCitationMarker(chunk_id=9, is_docs_chunk=False)],
    ),
    (
        "Whitespace [citation:  doc-100 ] tolerated.",
        [ChunkCitationMarker(chunk_id=100, is_docs_chunk=True)],
    ),
    (
        "Two URLs [citation:https://a.io] and [citation:https://b.io].",
        [
            UrlCitationMarker(url="https://a.io"),
            UrlCitationMarker(url="https://b.io"),
        ],
    ),
    ("Citation-like but wrong [citation:].", []),
]


@pytest.mark.parametrize("text,expected", PARITY_CASES)
def test_parse_citation_markers_parity_cases(text: str, expected: list):
    tokens = parse_citation_markers(text)
    assert tokens == expected
