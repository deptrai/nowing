# Architecture Improvement Proposals (v2) — 2026-05-01

**Context:** Refined following a Critical Review by Senior System Architect. Focuses on "Boring Technology" and operational stability.
**Status:** Approved / Pending Implementation

---

## 1. [P0] SSE Resilience & Connection Management
- **Risk:** Proxy timeouts and Browser connection limits (max 6 HTTP/1.1 connections per origin) blocking the entire app.
- **Proposal:** 
  - **Heartbeat:** Inject `: heartbeat` comment every 15s in backend SSE streams.
  - **Multiplexing:** Enforce HTTP/2 in the reverse proxy (Traefik/Nginx) to bypass browser connection limits.
  - **Auto-Reconnect:** Implement exponential backoff reconnection logic in the Next.js SSE consumer.

## 2. [P0] Global Circuit Breaker (Redis-First)
- **Risk:** Inconsistent breaker states across workers leading to continued spamming of failing APIs.
- **Proposal:** Use Redis as the **primary** state store for all `_BREAKERS`. Implement a local in-memory fallback **only** if Redis is unreachable (fail-open to local memory, but keep state shared during normal operation).

## 3. [P1] Automated Cache Purge
- **Risk:** Database bloat from orphaned snapshots belonging to deleted workspaces.
- **Proposal:** Implement a weekly Celery task `cleanup_orphaned_snapshots` to delete `crypto_data_snapshots` where `search_space_id` no longer exists.

## 4. [P1] Reliable Concurrency: Per-API Token Buckets
- **Risk:** A global static semaphore (limit=5) is either too slow for fast APIs or too fast for strict ones (e.g., CoinGecko free tier).
- **Proposal:** Replace/Augment global semaphore with per-provider token bucket rate limiters (stored in Redis) based on known provider tiers (e.g., 30/min for CoinGecko).

## 5. [P1] Client-Side Quota Enforcement (Zero-sync)
- **Risk:** Users bypassing subscription limits by reading locally synced data in IndexedDB after expiry.
- **Proposal:** Implement logic in `useQuery` hooks or a high-level Zero wrapper to check `subscription_current_period_end` from the local user record before rendering "Pro" crypto data.

## 6. [P2] Jittered Background Refresh
- **Risk:** Synchronized spikes in external API calls during periodic background refreshes.
- **Proposal:** Introduce random jitter (0-300s) when enqueuing refresh tasks in Celery to flatten the traffic curve.

## 7. [P2] Robust Thundering Herd Protection
- **Risk:** 60s locks causing request pile-up if the lock-holder fails.
- **Proposal:** 
  - Reduce Lock TTL from 60s to **20s**.
  - On lock timeout, **return stale cached data** (if available) with a "stale" metadata flag instead of bypassing the lock and flooding the API.

## 8. [P2] UX Trust: Elapsed Timers
- **Risk:** Heuristic ETA range is fragile and misleading.
- **Proposal:** Remove ETA predictions. Display the actual **Elapsed Time** for each agent and the total query. Focus UI on "moving status" (spinners/summaries) rather than "remaining time."

## 9. [P3] Optimistic Fallback with UI Clarity
- **Risk:** Fallback triggers without user knowledge, leading to perceived data quality issues.
- **Proposal:** Keep 1s fallback threshold. Add a "Data Source" badge in the UI that clearly indicates if a response came from the primary engine (Chainlens) or the fallback (Nowing).

## 10. [P3] Graceful Shutdown Handler
- **Risk:** Dropping long-running (90s) orchestra queries during server deploys/restarts.
- **Proposal:** Implement a SIGTERM handler in FastAPI that allows existing SSE streams up to 30s to finish or emit a "Server restarting, results saved" event before closing.
