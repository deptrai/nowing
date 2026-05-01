import asyncio
import functools
import logging
from typing import Any, Callable

from app.agents.new_chat.middleware.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

# Outbound Pacing: Max 5 concurrent external requests per worker process
# to prevent being IP-banned by data providers during parallel agent execution.
_OUTBOUND_SEMAPHORE = asyncio.Semaphore(5)


def crypto_tool_decorator(source: str):
    """Decorator for crypto tools to enforce resilience and error contracts.

    Features:
    - Circuit Breaker integration (Redis-backed).
    - Outbound Pacing (Concurrency limit).
    - Global exception handling -> returns {"error": "..."} instead of raising.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> dict[str, Any]:
            # 1. Check Circuit Breaker
            if await circuit_breaker.is_open(source):
                return {
                    "status": "error",
                    "error": f"Circuit open for {source}. Please try again later.",
                    "fallback_hint": "use chainlens_deep_research"
                }

            # 2. Apply Pacing (Semaphore)
            async with _OUTBOUND_SEMAPHORE:
                try:
                    result = await func(*args, **kwargs)

                    # 3. Record Success if no logical error in result
                    if isinstance(result, dict) and "error" in result:
                        await circuit_breaker.record_failure(source)
                    else:
                        await circuit_breaker.record_success(source)

                    return result

                except asyncio.TimeoutError:
                    await circuit_breaker.record_failure(source)
                    return {"status": "error", "error": f"{source} request timed out."}

                except Exception as exc:
                    # 4. Global Exception Handling
                    await circuit_breaker.record_failure(source)
                    logger.error("Unhandled exception in crypto tool %s: %s", func.__name__, exc, exc_info=True)
                    return {
                        "status": "error",
                        "error": f"Unexpected error in {source}: {type(exc).__name__}",
                        "details": str(exc) if not isinstance(exc, RuntimeError) else "Internal error"
                    }

        return wrapper

    return decorator
