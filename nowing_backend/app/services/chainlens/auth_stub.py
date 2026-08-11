"""Temporary ChainLens service auth stub until Story 20.4 lands.

Story 20.4 will replace this with a rotating ``ChainLensServiceAuth`` provider
that caches tokens and handles token exchange.
"""

from __future__ import annotations

from typing import Any


def get_chainlens_auth_header(config: Any | None = None) -> dict[str, str]:
    """Return the Authorization header for chainlens-research requests."""
    if config is None:
        from app.config import config
    token = getattr(config, "CHAINLENS_SERVICE_TOKEN", "") or getattr(
        config, "CHAINLENS_API_KEY", ""
    )
    return {"Authorization": f"Bearer {token}"}
