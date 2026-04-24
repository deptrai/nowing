"""Fault injection utilities for graceful degradation testing (Story 0.6)."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import respx

# Base URL patterns for each external service
_SERVICE_PATTERNS: dict[str, str] = {
    "coingecko": "https://api.coingecko.com/",
    "defillama": "https://api.llama.fi/",
    "goplus": "https://api.gopluslabs.io/",
    "cryptopanic": "https://cryptopanic.com/",
    "etherscan": "https://api.etherscan.io/",
    "reddit": "https://www.reddit.com/",
    "chainlens": "https://api.chainlens.ai/",
}


@asynccontextmanager
async def inject_api_failure(
    service: str,
    failure_type: str,
) -> AsyncIterator[respx.MockRouter]:
    """Inject an HTTP failure for a single external API service.

    Args:
        service: One of 'coingecko', 'defillama', 'goplus', 'cryptopanic',
                 'etherscan', 'reddit', 'chainlens'
        failure_type: '429' | '500' | 'timeout' | 'network_error'

    Yields:
        The active respx MockRouter for additional customisation.
    """
    base_url = _SERVICE_PATTERNS.get(service)
    if base_url is None:
        raise ValueError(f"Unknown service {service!r}. Known: {sorted(_SERVICE_PATTERNS)}")

    with respx.mock(assert_all_called=False) as router:
        if failure_type == "429":
            router.route(url__startswith=base_url).mock(
                return_value=httpx.Response(429, json={"error": "Rate limited"})
            )
        elif failure_type == "500":
            router.route(url__startswith=base_url).mock(
                return_value=httpx.Response(500)
            )
        elif failure_type == "timeout":
            router.route(url__startswith=base_url).mock(
                side_effect=httpx.TimeoutException("Injected timeout")
            )
        elif failure_type == "network_error":
            router.route(url__startswith=base_url).mock(
                side_effect=httpx.NetworkError("Injected network error")
            )
        else:
            raise ValueError(f"Unknown failure_type {failure_type!r}")

        # Pass through all other services
        router.route().pass_through()
        yield router


@asynccontextmanager
async def inject_all_failures(
    failure_type: str = "500",
) -> AsyncIterator[respx.MockRouter]:
    """Inject failures for ALL known external services simultaneously.

    Used to simulate catastrophic failure (AC9). Any request outside the known
    service list (e.g., the LLM proxy) is passed through so real-LLM-guarded
    tests don't trip respx's `AllMockedAssertionError`.
    """
    with respx.mock(assert_all_called=False) as router:
        for base_url in _SERVICE_PATTERNS.values():
            if failure_type == "timeout":
                router.route(url__startswith=base_url).mock(
                    side_effect=httpx.TimeoutException("Injected timeout")
                )
            else:
                router.route(url__startswith=base_url).mock(
                    return_value=httpx.Response(500)
                )
        # Pass through anything that isn't one of the injected services (e.g., LLM)
        router.route().pass_through()
        yield router
