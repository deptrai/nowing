import asyncio
import time
import logging

import httpx

from app.config import config  # lowercase singleton

logger = logging.getLogger(__name__)

VALID_SOURCES = frozenset({"web", "discussions", "academic"})
ERROR_COOLDOWN_SECONDS = 5.0
MAX_RETRIES = 1
RETRY_BACKOFF_SECONDS = 1.0


# NOTE: Startup config validation lives in `app/app.py::_validate_chainlens_config()`
# (called from FastAPI lifespan). Don't re-emit warnings at import time here —
# (1) logging may not be configured yet at import time → unreliable output,
# (2) duplicate warnings confuse operators, (3) module-import side effects are
# an antipattern. Single source of truth: the lifespan validator.


class ChainlensUnavailableError(Exception):
    """Raised when Chainlens API is unreachable or returns non-success response."""

    pass


class ChainlensResearchService:
    """Proxy service calling Chainlens Research B2B API with cached health check."""

    # Updated only from /health probes — isolated from per-request research failures
    _health_cache: tuple[bool, float] = (False, 0.0)  # (is_live, checked_at monotonic)
    # Short availability suppression after a research failure — avoids amplifying flaky upstream
    _error_cooldown_until: float = 0.0
    _health_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def is_available(cls) -> bool:
        """Health check with in-process TTL cache. Timeout 3s to avoid blocking."""
        # Mirror validator: treat whitespace-only URL as missing (operator typos)
        url = (config.CHAINLENS_RESEARCH_API_URL or "").strip()
        if not config.CHAINLENS_RESEARCH_ENABLED or not url:
            return False

        now = time.monotonic()
        if now < cls._error_cooldown_until:
            return False

        is_live, checked_at = cls._health_cache
        if now - checked_at < config.CHAINLENS_HEALTH_CACHE_TTL:
            return is_live

        # Serialize the fresh probe to prevent thundering herd under concurrent callers
        async with cls._health_lock:
            now = time.monotonic()
            is_live, checked_at = cls._health_cache
            if now - checked_at < config.CHAINLENS_HEALTH_CACHE_TTL:
                return is_live

            try:
                # Adversarial Review Fix: Reduced timeout to 0.5s for optimistic fallback.
                # Meets TTFT < 1.5s NFR by not blocking on slow health checks.
                async with httpx.AsyncClient(timeout=0.5) as client:
                    resp = await client.get(
                        f"{url}/api/v1/b2b/health"
                    )
                    live = resp.status_code == 200
                    cls._health_cache = (live, time.monotonic())
                    return live
            except httpx.HTTPError:
                logger.warning("[Chainlens] Health check failed", exc_info=True)
                cls._health_cache = (False, time.monotonic())
                return False

    @classmethod
    async def research(cls, query: str, sources: list[str] | None = None) -> dict:
        """Call Chainlens B2B research endpoint. Raises ChainlensUnavailableError on failure."""
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if sources is not None:
            invalid = set(sources) - VALID_SOURCES
            if invalid:
                raise ValueError(
                    f"Invalid sources: {sorted(invalid)}. Valid: {sorted(VALID_SOURCES)}"
                )

        if not await cls.is_available():
            raise ChainlensUnavailableError("Chainlens API not available or disabled")
        # Mirror validator: treat whitespace-only KEY as missing
        api_key = (config.CHAINLENS_RESEARCH_API_KEY or "").strip()
        if not api_key:
            raise ChainlensUnavailableError("CHAINLENS_RESEARCH_API_KEY not configured")

        url = f"{(config.CHAINLENS_RESEARCH_API_URL or '').strip()}/api/v1/b2b/research"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {"query": query, "sources": sources or ["web"], "stream": False}

        last_error: ChainlensUnavailableError | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=125.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as e:
                        # Parse error is a data bug, not availability — do NOT trigger cooldown
                        logger.warning(
                            "[Chainlens] Response JSON parse error", exc_info=True
                        )
                        raise ChainlensUnavailableError(
                            f"Chainlens response parse error: {type(e).__name__}"
                        ) from e

                logger.warning(
                    "[Chainlens] Research returned HTTP %s (attempt %d/%d)",
                    resp.status_code,
                    attempt + 1,
                    MAX_RETRIES + 1,
                )
                last_error = ChainlensUnavailableError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
                if 500 <= resp.status_code < 600 and attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                break
            except httpx.TimeoutException:
                logger.warning(
                    "[Chainlens] Research timed out after 125s (attempt %d/%d)",
                    attempt + 1,
                    MAX_RETRIES + 1,
                )
                last_error = ChainlensUnavailableError(
                    "Chainlens API request timed out (>125s)"
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                break
            except httpx.HTTPError as e:
                logger.warning(
                    "[Chainlens] Research request failed: %s (attempt %d/%d)",
                    type(e).__name__,
                    attempt + 1,
                    MAX_RETRIES + 1,
                    exc_info=True,
                )
                last_error = ChainlensUnavailableError(
                    f"Chainlens request failed: {type(e).__name__}"
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                break

        cls._error_cooldown_until = time.monotonic() + ERROR_COOLDOWN_SECONDS
        raise last_error or ChainlensUnavailableError("Chainlens request failed")
