import asyncio

import pytest


@pytest.fixture(autouse=True)
async def api_retry_delay():
    """Small delay between tests to avoid rate limits."""
    yield
    await asyncio.sleep(0.5)
