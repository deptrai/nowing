"""``memory`` suite domain — long-term memory quality benchmarks (Story 3.9).

Auto-discovery (``suites/__init__.py:discover_suites``) walks two levels: this
domain package, then each benchmark subpackage under it. The registration
itself lives in ``recall/__init__.py``, so this module stays intentionally
empty of imports — importing the benchmark here would register it twice.
"""

from __future__ import annotations
