"""Vietnam BĐS cross-source aggregator (Apache-2.0)."""

from __future__ import annotations

from .dedupe import deduplicate, fingerprint, merge, merge_group, search_text

__all__ = ["deduplicate", "fingerprint", "merge", "merge_group", "search_text"]
