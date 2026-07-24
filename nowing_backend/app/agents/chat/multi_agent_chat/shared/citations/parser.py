"""Parse persisted ``[citation:<payload>]`` markers back into structured tokens.

This is the inverse of ``normalizer.normalize_citations`` /
``markers.to_frontend_payload``: the normalizer *writes* ``[citation:<payload>]``
into assistant message text at finalize time (see
``app/tasks/chat/streaming/flows/shared/assistant_finalize.py``); this *reads*
those markers back out of persisted content (e.g. to aggregate a research
thread's prior sources for research-continuity recall).

The pattern is the canonical citation regex shared by every surface. Source of
truth: ``nowing_web/lib/citations/citation-parser.ts`` (``CITATION_REGEX``),
also ported verbatim in ``nowing_evals/src/nowing_evals/core/parse/citations.py``.
It is kept byte-for-byte identical here so the web renderer, the evals harness,
and this backend extractor all recognize exactly the same markers.

Never raises on malformed input: a marker that does not match the pattern (an
unterminated ``[citation:`` or an unparseable payload) is simply not yielded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The ZWSP must be spliced in as the literal code point: Python's ``re`` does not
# interpret the ``\u`` escape inside a raw pattern the way the TS regex literal
# does, so we build the pattern with an f-string to stay identical to the source.
_ZWSP = "\u200b"
CITATION_REGEX = re.compile(
    rf"[\[【]{_ZWSP}?citation:\s*("
    rf"https?://[^\]】{_ZWSP}]+|urlcite\d+|(?:doc-)?-?\d+(?:\s*,\s*(?:doc-)?-?\d+)*"
    rf")\s*{_ZWSP}?[\]】]"
)


@dataclass(frozen=True)
class UrlCitationMarker:
    """A citation whose payload is a live URL (web result)."""

    url: str


@dataclass(frozen=True)
class ChunkCitationMarker:
    """A citation whose payload is a knowledge-base chunk id."""

    chunk_id: int
    is_docs_chunk: bool


CitationMarker = UrlCitationMarker | ChunkCitationMarker


def parse_citation_markers(text: str) -> list[CitationMarker]:
    """Return the citation markers found in ``text`` in document order.

    Multi-id payloads like ``[citation:1, doc-2, -3]`` are flattened into one
    ``ChunkCitationMarker`` per id, mirroring the canonical parser. Web-only
    ``urlcite{N}`` placeholders are dropped (their URL lives in a render-time
    map we do not have here), and any payload that fails to parse is skipped.
    """
    if not text:
        return []

    out: list[CitationMarker] = []
    for match in CITATION_REGEX.finditer(text):
        captured = match.group(1)
        if captured.startswith(("http://", "https://")):
            out.append(UrlCitationMarker(url=captured.strip()))
            continue
        if captured.startswith("urlcite"):
            # Web-only placeholder; without the render-time url map we cannot
            # resolve it, so drop it rather than emit a broken citation.
            continue
        for raw_id in (segment.strip() for segment in captured.split(",")):
            is_docs_chunk = raw_id.startswith("doc-")
            number_part = raw_id[4:] if is_docs_chunk else raw_id
            try:
                chunk_id = int(number_part)
            except ValueError:
                continue
            out.append(
                ChunkCitationMarker(chunk_id=chunk_id, is_docs_chunk=is_docs_chunk)
            )
    return out


__all__ = [
    "CITATION_REGEX",
    "ChunkCitationMarker",
    "CitationMarker",
    "UrlCitationMarker",
    "parse_citation_markers",
]
