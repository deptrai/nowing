"""Integration tests for Vietstock scraper with real or recorded API."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="red phase — requires Vietstock credentials")]


async def test_real_vietstock_quote() -> None:
    """Pattern 6: real API returns quote with numeric ratios."""
    raise NotImplementedError("red phase — implement with real credentials or VCR")


async def test_vietstock_auth_refresh() -> None:
    """Pattern 6: expired cookie refreshes and persists usage_state in DB."""
    raise NotImplementedError("red phase — implement with real credentials or VCR")


async def test_vietstock_to_chainlens_feed() -> None:
    """Pattern 6: chunks sent to chainlens and ChainLensIngestJob persisted."""
    raise NotImplementedError("red phase — implement with real DB + chainlens mock")
