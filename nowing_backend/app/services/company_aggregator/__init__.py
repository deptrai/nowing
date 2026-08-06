"""Vietnamese company directory aggregator (Apache-2.0)."""

from __future__ import annotations

from .dedupe import fingerprint, merge, normalize, search_text

__all__ = ["fingerprint", "merge", "normalize", "search_text"]
