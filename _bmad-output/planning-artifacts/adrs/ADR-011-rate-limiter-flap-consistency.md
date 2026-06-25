# ADR-011: Rate Limiter Redis-Flap Consistency

**Status:** Proposed
**Date:** 2026-05-02
**Deciders:** Winston (Architect), Developer
**Triggers:** Story 11-4 round-2 review; promoted to Story 11-6 T4

## Context

`TokenBucketRateLimiter` (`nowing_backend/app/agents/new_chat/middleware/rate_limiter.py`) uses Redis as the canonical token bucket store, with an in-memory `_local_tokens` counter as fallback when Redis is unavailable (AC#5 of Story 11-4).

The fallback semantics are: "Redis-down → use local counter; over-counting acceptable, prefer throttle over spam."

**Problem discovered round 2:**
When Redis flaps (up → down → up mid-request), a single `acquire()` call can consume tokens from BOTH stores:

```
t0: Redis up → EVAL succeeds, Redis bucket: 30 → 29
t1: Redis goes down (network blip)
t2: Same request retries (acquire's while-loop iteration 2)
t3: Redis-down branch → _acquire_local() consumes local bucket: 30 → 29
t4: Redis comes back up
```

Net effect: 1 logical request consumed 2 tokens (1 in Redis, 1 local). Across N concurrent requests during a flap, the bucket can drain at 2× the configured rate, defeating the purpose of rate limiting (CoinGecko 30/min → ~60 actual outbound calls).

The original AC#5 wording "over-count acceptable" was meant for the *steady-state* fallback (Redis durably down), not for the flap edge case where the same logical request gets billed twice.

## Decision

**Mirror Redis state to local on every successful EVAL.**

When the Redis EVAL path succeeds (returns 1), additionally update the local bucket atomically:
1. Read the bucket's `tokens` field from the EVAL response (extend the Lua script to return both `acquired` and `tokens`).
2. Inside `acquire()`, after success, set `self._local_tokens = redis_tokens` and `self._local_last_refill = time.monotonic()`.

When the Redis EVAL path fails (exception), the local bucket already reflects the most recent Redis state (within the last successful EVAL), so `_acquire_local()` doesn't double-consume.

Trade-off: 1 extra atomic write to local memory per successful EVAL (~50ns); eliminates double-consume entirely; preserves AC#5 over-count tolerance for steady-state Redis-down (local counter operates from the last-known Redis state, not from a fresh `capacity` reset).

## Consequences

### Positive
- **Eliminates double-consume class of bug** without architectural complexity (no distributed transaction, no 2-phase commit).
- **Preserves AC#5 semantics**: steady-state Redis-down still falls back to local counter; flap edge case becomes safe.
- **Local counter remains a true mirror**, useful for observability (`/metrics` endpoint can read `_local_tokens` to show "current bucket level" even when Redis is down).

### Negative
- Lua script becomes slightly more complex (returns array `[acquired, tokens]` instead of int).
- 1 extra Python-side write per successful EVAL — negligible perf impact.
- Tests must use a custom Lua mock that returns `[1, N]` shape instead of just `1`.

### Neutral
- The `_local_tokens` field is still per-process (not shared across workers). For multi-worker double-consume protection across workers during Redis-down, that's a separate concern (currently accepted as over-count per AC#5).

## Alternatives considered

1. **Distributed lock per acquire** — Too heavy; defeats the purpose of a fast rate limiter.
2. **Compare-and-swap on EVAL** — Lua already provides atomicity; the issue is between Redis and local stores, not within Redis.
3. **Disable local fallback entirely (Redis-required mode)** — Violates AC#5; Redis outage would block all crypto tool calls.
4. **Quorum across local and Redis (require both to consume)** — Overkill; AC#5 explicitly accepts over-count tolerance.

## Implementation pointers

- File: `nowing_backend/app/agents/new_chat/middleware/rate_limiter.py`
- Modify Lua script: return `[acquired, tokens, last_refill]` instead of just `acquired`.
- Modify `acquire()`: on Redis EVAL success, update `self._local_tokens` and `self._local_last_refill` from response.
- Add integration test using `toxiproxy` (or test double) to simulate Redis flap mid-request and assert single-consume.

## Owner

Story 11.6 Task T4 (Developer).
