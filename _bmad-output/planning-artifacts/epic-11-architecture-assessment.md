# Epic 11 — User Flow & Architecture Assessment

**Date:** 2026-05-01
**Author:** Winston (System Architect)

---

## 1. User Flow: Crypto Orchestra Query (After Epic 11)

### Sequence Diagram — Full Request Lifecycle

```
┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐     ┌──────────────┐
│  Browser  │     │   Next.js    │     │    FastAPI     │     │   LangGraph  │     │ External API │
│  (User)   │     │   Frontend   │     │    Backend     │     │   DeepAgent  │     │ (DeFiLlama…) │
└─────┬─────┘     └──────┬───────┘     └──────┬────────┘     └──────┬───────┘     └──────┬───────┘
      │                  │                    │                     │                    │
      │ "Phân tích       │                    │                     │                    │
      │  toàn diện $UNI" │                    │                     │                    │
      │─────────────────▶│                    │                     │                    │
      │                  │                    │                     │                    │
      │          ┌───────┴────────┐           │                     │                    │
      │          │ [11.5] CHECK   │           │                     │                    │
      │          │ useSubscription│           │                     │                    │
      │          │ Gate()         │           │                     │                    │
      │          │                │           │                     │                    │
      │          │ expired? ──────┼──▶ REDACT (blur + upgrade CTA)  │                    │
      │          │ active? ───────┼──▶ PROCEED                      │                    │
      │          └───────┬────────┘           │                     │                    │
      │                  │                    │                     │                    │
      │                  │ POST /threads/     │                     │                    │
      │                  │   {id}/runs        │                     │                    │
      │                  │───────────────────▶│                     │                    │
      │                  │                    │                     │                    │
      │                  │ GET /threads/{id}/ │                     │                    │
      │                  │  runs/{id}/stream  │                     │                    │
      │                  │───────────────────▶│                     │                    │
      │                  │                    │                     │                    │
      │                  │ ◀─── SSE stream ───┤                     │                    │
      │                  │   Content-Type:    │                     │                    │
      │                  │   text/event-stream│                     │                    │
      │                  │                    │                     │                    │
      │                  │                    │ create_deepagent()  │                    │
      │                  │                    │────────────────────▶│                    │
      │                  │                    │                     │                    │
      │                  │                    │              ┌──────┴──────┐             │
      │                  │                    │              │  Middleware  │             │
      │                  │                    │              │   Stack     │             │
      │                  │                    │              │             │             │
      │                  │                    │              │ TodoList    │             │
      │                  │                    │              │ Memory      │             │
      │                  │                    │              │ Filesystem  │             │
      │                  │                    │              │ Summarize   │             │
      │                  │                    │              │ PatchTool   │             │
      │                  │                    │              │ PromptCache │             │
      │                  │                    │              │ CryptoCache │             │
      │                  │                    │              │ SourceAttr  │             │
      │                  │                    │              └──────┬──────┘             │
      │                  │                    │                     │                    │
      │                  │                    │              Agent detects intent:       │
      │                  │                    │              Rule C → parallel spawn     │
      │                  │                    │                     │                    │
      │                  │                    │              ┌──────┴──────────────────┐ │
      │                  │                    │              │ SubAgentMiddleware      │ │
      │                  │                    │              │ spawn 6 agents via      │ │
      │                  │                    │              │ task() in 1 ToolNode:   │ │
      │                  │                    │              │                         │ │
      │                  │                    │              │ ┌─ defillama_analyst    │ │
      │                  │                    │              │ ├─ sentiment_analyst    │ │
      │                  │                    │              │ ├─ news_analyst         │ │
      │                  │                    │              │ ├─ tokenomics_analyst   │ │
      │                  │                    │              │ ├─ yield_optimizer      │ │
      │                  │                    │              │ └─ governance_analyst   │ │
      │                  │                    │              └──────┬──────────────────┘ │
      │                  │                    │                     │                    │
      │                  │                    │              Per-agent tool call:        │
      │                  │                    │                     │                    │
      │                  │                    │              ┌──────┴──────┐             │
      │                  │                    │              │ [11.4] TOKEN│             │
      │                  │                    │              │ BUCKET      │             │
      │                  │                    │              │ acquire()   │             │
      │                  │                    │              │             │             │
      │                  │                    │              │ bucket OK?──┼─▶ PROCEED   │
      │                  │                    │              │ bucket empty┼─▶ WAIT 5s   │
      │                  │                    │              │ timeout ────┼─▶ {"error"} │
      │                  │                    │              └──────┬──────┘             │
      │                  │                    │                     │                    │
      │                  │                    │              ┌──────┴──────┐             │
      │                  │                    │              │ [11.2]      │             │
      │                  │                    │              │ CIRCUIT     │             │
      │                  │                    │              │ BREAKER     │             │
      │                  │                    │              │ (Redis)     │             │
      │                  │                    │              │             │             │
      │                  │                    │              │ OPEN? ──────┼─▶ fail-fast │
      │                  │                    │              │ HALF_OPEN?──┼─▶ 1 probe   │
      │                  │                    │              │ CLOSED? ────┼─▶ PROCEED   │
      │                  │                    │              └──────┬──────┘             │
      │                  │                    │                     │                    │
      │                  │                    │              ┌──────┴──────┐             │
      │                  │                    │              │ SEMAPHORE   │             │
      │                  │                    │              │ (5 max)     │             │
      │                  │                    │              └──────┬──────┘             │
      │                  │                    │                     │                    │
      │                  │                    │              ┌──────┴──────┐             │
      │                  │                    │              │ CryptoData  │             │
      │                  │                    │              │ CacheMiddle │             │
      │                  │                    │              │ ware        │             │
      │                  │                    │              │             │             │
      │                  │                    │              │ cache hit?──┼─▶ return DB │
      │                  │                    │              │ cache miss?─┼─▶ ─────────▶│
      │                  │                    │              │             │  API call   │
      │                  │                    │              │ ◀───────────┼─────────────│
      │                  │                    │              │ write snap  │  response   │
      │                  │                    │              │ + herd lock │             │
      │                  │                    │              └──────┬──────┘             │
      │                  │                    │                     │                    │
      │                  │                    │              Agent synthesize            │
      │                  │                    │              response (graceful          │
      │                  │                    │              degradation if errors)      │
      │                  │                    │                     │                    │
      │                  │ ◀─── SSE events ───┤◀────────────────────┤                    │
      │                  │  orchestra.spawn   │                     │                    │
      │                  │  orchestra.done    │                     │                    │
      │                  │  text-delta        │                     │                    │
      │                  │                    │                     │                    │
      │          ┌───────┴────────┐           │                     │                    │
      │          │ [11.1] SSE     │           │                     │                    │
      │          │ RESILIENCE     │           │                     │                    │
      │          │                │           │                     │                    │
      │          │ no data 15s?───┼───── : heartbeat ──────────────▶│                    │
      │          │ stream dies?───┼───── reconnect (exp backoff)    │                    │
      │          │ reconnect OK?──┼───── resume after_seq={n}       │                    │
      │          │ 5x fail? ──────┼───── "Connection lost" banner   │                    │
      │          └───────┬────────┘           │                     │                    │
      │                  │                    │                     │                    │
      │ ◀── render ──────┤                    │                     │                    │
      │   OrchestraStrip │                    │                     │                    │
      │   + Report       │                    │                     │                    │
      │   + Citations    │                    │                     │                    │
      │                  │                    │                     │                    │
```

### Flow Legend — Epic 11 Components

| Layer | Component | Story | Where it acts |
|-------|-----------|-------|---------------|
| **FE Entry** | `useSubscriptionGate()` | 11.5 | Before request — gate/redact |
| **FE SSE** | Heartbeat + auto-reconnect | 11.1 | During streaming — connection resilience |
| **BE Tool** | `TokenBucketRateLimiter` | 11.4 | Before API call — proactive throttle |
| **BE Tool** | `RedisCircuitBreaker` (HALF_OPEN) | 11.2 | Before API call — fail-fast |
| **BE Tool** | `_OUTBOUND_SEMAPHORE(5)` | Existing | Concurrency cap (unchanged) |
| **BE Middleware** | `CryptoDataCacheMiddleware` | Existing (Epic 10) | Cache layer |
| **BE Celery** | `cleanup_orphaned_snapshots` | 11.3 | Background — weekly cleanup |

### Request Protection Stack (per tool call, inner to outer):

```
1. [11.4] Token Bucket    ─── "Can I call this provider right now?"
2. [11.2] Circuit Breaker  ─── "Is this provider alive?"
3. [existing] Semaphore(5) ─── "Am I under global concurrency cap?"
4. [existing] Cache check   ─── "Is there fresh cached data?"
5. [existing] Herd lock     ─── "Is someone already fetching this?"
6. [actual API call]        ─── External HTTP request
```

---

## 2. Architecture Assessment — Post-Epic 11

### 2.1 Strengths (What Epic 11 Fixes Well)

**A. Defense in Depth — 3 layers trước API call**
Hiện tại chỉ có circuit breaker + semaphore. Sau Epic 11, mỗi outbound request qua **5 checkpoints** trước khi hit external API. Đây là pattern "Swiss Cheese Model" — mỗi layer catch lỗi mà layer trước miss.

**B. SSE Reliability — Boring nhưng essential**
Heartbeat 15s + auto-reconnect là industry standard cho SSE. Hiện tại **không có** — bất kỳ proxy timeout nào (Nginx default 60s, Cloudflare 100s) đều kill stream silently. Story 11.1 fix lỗ hổng cơ bản nhất.

**C. Cache hygiene — DB bloat prevention**
Orphaned snapshots sẽ tích tụ vĩnh viễn nếu không cleanup. Weekly purge (Story 11.3) là simple, boring, effective. Đúng triết lý "boring technology".

### 2.2 Risks & Concerns

**A. 🔴 Story 11.5 — Zero Schema Gap (BLOCKING)**

Discovery mới: **Zero schema (`nowing_web/zero/schema/index.ts`) KHÔNG có user table** — không sync `subscription_current_period_end` xuống client. Story 11.5 viết `useSubscriptionGate()` đọc từ "Zero local cache" nhưng **data không tồn tại ở đó**.

**Hiện trạng:**
- Zero schema chỉ sync: `documents`, `folders`, `chatMessages`, `comments`, `notifications`, `connectors`, `orchestraSessions`, `chatSessionState`
- Subscription check hiện tại dùng `use-pro-status.ts` → Clerk metadata / billing state, **KHÔNG qua Zero**

**Impact:** Story 11.5 **KHÔNG implement được** như hiện tại. Cần 1 trong 2 options:
1. **Thêm user table vào Zero schema** — significant change, ảnh hưởng Zero permissions + RLS
2. **Đổi approach**: `useSubscriptionGate()` đọc từ existing `use-pro-status.ts` (Clerk) thay vì Zero. Mất offline capability nhưng simpler.

**Recommendation:** Option 2 cho MVP — dùng existing `use-pro-status.ts`. Offline quota enforcement defer sang khi user table được add vào Zero schema (bigger story).

**B. 🟠 Story 11.4 — Integration Point với `crypto_tool_decorator`**

`utils.py` đã có `crypto_tool_decorator(source)` wrap mọi crypto tool với circuit breaker + semaphore + error handling. Token bucket cần integrate **vào decorator này**, KHÔNG phải vào từng tool file riêng.

**Current decorator flow:**
```python
@crypto_tool_decorator("defillama")
async def get_defillama_protocol(...):
    ...
```

**Expected integration point:**
```python
# Inside crypto_tool_decorator.wrapper():
# 1. Token Bucket acquire  ← NEW (Story 11.4)
# 2. Circuit Breaker check  ← existing
# 3. Semaphore acquire      ← existing
# 4. Execute tool           ← existing
# 5. Record success/failure ← existing
```

Story 11.4 task list nói "thêm `await rate_limiter.acquire()` vào từng tool file" — **SAI**. Phải thêm vào `crypto_tool_decorator` trong `utils.py`. 1 điểm thay đổi thay vì 4 files.

**C. 🟡 Ordering Concern — Token Bucket vs Circuit Breaker**

Thứ tự quan trọng:
- **Token Bucket TRƯỚC Circuit Breaker**: Nếu bucket empty, chờ refill (max 5s). Không cần check circuit vì chưa gọi API.
- **Circuit Breaker TRƯỚC Semaphore**: Nếu circuit open, fail-fast ngay. Không cần acquire semaphore slot.

Flow hiện tại (circuit → semaphore) đúng. Thêm token bucket ở đầu là correct.

**D. 🟡 Semaphore Naming Confusion**

Story 11.4 trước đó nói "không có global semaphore" — đã sửa. Nhưng story dev notes vẫn chưa mention `crypto_tool_decorator` trong `utils.py` là integration point chính. Cần update story file.

### 2.3 Architecture Coherence Matrix

| Epic 11 Story | Coherent với existing? | Conflict? | Notes |
|---------------|----------------------|-----------|-------|
| 11.1 SSE Heartbeat | ✅ | None | `NewStreamingService` có sẵn `_format_sse()`, thêm heartbeat tự nhiên |
| 11.2 Breaker Hardening | ✅ | None | `RedisCircuitBreaker` đã exist, refactor in-place |
| 11.3 Cache Purge | ✅ | None | Clone existing `cleanup_expired_crypto_snapshots` pattern |
| 11.4 Token Bucket | ⚠️ | **Integration point sai** | Phải integrate vào `crypto_tool_decorator` (utils.py), không phải 4 tool files |
| 11.5 Client Quota | 🔴 | **Zero schema gap** | Subscription data không có trong Zero. Cần đổi approach. |

### 2.4 Recommendations

| Priority | Action |
|----------|--------|
| **P0** | Update Story 11.5: đổi từ "Zero local cache" sang "existing `use-pro-status.ts` (Clerk)" approach. Defer offline enforcement. |
| **P0** | Update Story 11.4: integration point là `crypto_tool_decorator` trong `utils.py`, KHÔNG phải 4 tool files riêng. |
| **P1** | Implement order: 11.1 → 11.3 (parallel) → 11.2 → 11.4 → 11.5 |
| **P2** | Future: thêm user table vào Zero schema để enable true offline quota enforcement |

---

## 3. Summary

Epic 11 **tăng cường đáng kể resilience** của hệ thống với 5 layers protection. Tuy nhiên cần **2 fixes quan trọng** trước khi implement:

1. **Story 11.5**: Đổi data source từ Zero (không available) sang existing Clerk-based pro status check
2. **Story 11.4**: Integration point là `crypto_tool_decorator` trong `utils.py`, không phải scatter vào 4 tool files

Sau 2 fixes này, Epic 11 **READY for implementation**.
