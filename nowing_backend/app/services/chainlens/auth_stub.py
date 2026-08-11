"""Deprecated re-export for the temporary ChainLens auth stub.

Story 20.4 moved the implementation to ``app.services.chainlens.auth``.
This module remains only for backwards compatibility and will be removed
once all callers are migrated.
"""

from __future__ import annotations

from .auth import get_chainlens_auth_header

__all__ = ["get_chainlens_auth_header"]
