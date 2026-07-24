"""Citation registry: maps model-facing ``[n]`` labels to real sources.

Server-side only; the model sees only the bare ``[n]``.
"""

from __future__ import annotations

from .markers import to_frontend_payload
from .models import CitationEntry, CitationSourceType
from .normalizer import normalize_citations
from .parser import (
    ChunkCitationMarker,
    CitationMarker,
    UrlCitationMarker,
    parse_citation_markers,
)
from .registry import CitationRegistry, make_key
from .state import load_registry

__all__ = [
    "ChunkCitationMarker",
    "CitationEntry",
    "CitationMarker",
    "CitationRegistry",
    "CitationSourceType",
    "UrlCitationMarker",
    "load_registry",
    "make_key",
    "normalize_citations",
    "parse_citation_markers",
    "to_frontend_payload",
]
