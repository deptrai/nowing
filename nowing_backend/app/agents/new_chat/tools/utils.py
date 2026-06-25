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
            # 1. Check Circuit Breaker FIRST — short-circuit before consuming a
            # rate-limit token. (Round 2 review fix: previously the limiter was
            # consulted first; if the breaker was OPEN every short-circuited
            # request still drained one token, exhausting the bucket during a
            # provider outage.)
            if await circuit_breaker.is_open(source):
                return {
                    "status": "error",
                    "error": f"Circuit open for {source}. Please try again later.",
                    "fallback_hint": "use chainlens_deep_research"
                }

            # 2. Rate Limiter (Token Bucket) - AC#1, AC#3
            from app.agents.new_chat.middleware.rate_limiter import get_limiter

            limiter = get_limiter(source)
            if not await limiter.acquire(timeout_s=5.0):
                return {
                    "status": "error",
                    "error": f"Rate limit exceeded for {source}. Provider quota exhausted.",
                    "event": "rate_limited"
                }

            # Story 11.7 T1 / token-waste fix: track whether the tool actually
            # made a billable outbound call. Acquired tokens are returned to
            # the bucket on internal failures (TimeoutError, unhandled
            # exceptions) so we don't double-penalise our local quota for
            # work that never reached the provider.
            token_consumed = True
            try:
                # 3. Apply Pacing (Semaphore)
                async with _OUTBOUND_SEMAPHORE:
                    try:
                        result = await func(*args, **kwargs)

                        # 4. Record Success if no logical error in result
                        if isinstance(result, dict) and "error" in result:
                            await circuit_breaker.record_failure(source)
                        else:
                            await circuit_breaker.record_success(source)

                        return result

                    except asyncio.TimeoutError:
                        # Provider didn't respond — request likely never billable.
                        # Return the token; the circuit breaker still counts the
                        # failure so repeated timeouts trip the breaker.
                        await circuit_breaker.record_failure(source)
                        token_consumed = False
                        return {"status": "error", "error": f"{source} request timed out."}

                    except Exception as exc:
                        # 5. Global Exception Handling — internal failure
                        # (network, parsing, programming bug). Token returned
                        # by best practice; provider not actually charged.
                        await circuit_breaker.record_failure(source)
                        token_consumed = False
                        logger.error("Unhandled exception in crypto tool %s: %s", func.__name__, exc, exc_info=True)
                        return {
                            "status": "error",
                            "error": f"Unexpected error in {source}: {type(exc).__name__}",
                            "details": str(exc) if not isinstance(exc, RuntimeError) else "Internal error"
                        }
            finally:
                if not token_consumed:
                    # Best-effort release; never raises — release() swallows
                    # Redis errors internally so the response path stays clean.
                    try:
                        await limiter.release()
                    except Exception:
                        logger.exception("rate-limiter release failed for %s", source)

        return wrapper

    return decorator
