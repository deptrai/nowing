---
adrId: ADR-001
title: Persistent Shared Crypto Data Layer
status: accepted
date: '2026-04-29'
deciders: [Winston (Architect), Mary (BA)]
relatedEpic: epic-10-crypto-data-layer
relatedFRs: [FR36, FR37, FR38, FR39, FR40]
---

# ADR-001: Persistent Shared Crypto Data Layer

## Tóm Tắt

Thay vì mỗi lần user hỏi về token thì 7 sub-agents gọi lại tất cả external APIs từ đầu, hệ thống sẽ lưu kết quả tool calls vào PostgreSQL theo project + data category + timeline. Lần sau query cùng token trong TTL window → serve từ DB, không gọi API.

## Bối Cảnh

Crypto Orchestra hiện tại spawn 7 sub-agents song song, mỗi agent gọi 2-5 external APIs. Với 100 users hỏi về ETH trong 1 giờ = ~700 API calls lặp lại cho cùng dữ liệu. Vấn đề:
- Chi phí API tăng tuyến tính theo số users
- Rate limit risk cao (CoinGecko 30 req/min, GoPlus 2000 req/day)
- Latency không cải thiện dù data đã được fetch gần đây
- Không có audit trail về data đã được dùng để tạo reports

## Các Phương Án Đã Xem Xét

### Option A: Redis Cache (per-query, in-memory)
- Pros: đơn giản, fast reads
- Cons: volatile (restart mất hết), không có history, không shared nếu nhiều BE instances, max TTL 24h với Redis basic setup

### Option B: Modify Tool Files (cache trong từng tool)
- Pros: isolated per tool
- Cons: 22 tool files phải sửa, inconsistent invalidation, không có global data timeline

### Option C: Middleware Interception + PostgreSQL (CHỌN) ✅
- Pros: zero changes to tool files, global shared pool, append-only history, queryable timeline, graceful degradation if DB down
- Cons: thêm DB roundtrip per tool call (mitigated bằng index trên expires_at), phức tạp hơn Option A

### Option D: External Cache Service (Upstash Redis, Momento)
- Pros: fully managed
- Cons: vendor lock-in, thêm billing, không có long-term history

## Quyết Định

**Chọn Option C** — Middleware Interception + PostgreSQL append-only snapshots.

### Lý Do

1. **Zero tool file changes** — 22+ existing tool files không cần sửa. Middleware intercept tại `awrap_tool_call` layer (follow pattern của `SourceAttributionMiddleware`).
2. **Global pool** — 1 snapshot phục vụ N concurrent users cùng query token X trong TTL window.
3. **Append-only history** — audit trail đầy đủ: mỗi fetch = 1 row mới. Có thể query "TVL của ETH qua các tháng" trực tiếp từ DB mà không cần API call.
4. **Graceful degradation** — nếu DB down hoặc middleware fail → catch exception → fallback to direct API call. Agent không bao giờ biết cache đang hoặc không hoạt động.
5. **Hybrid TTL** — data categories có TTL khác nhau: price (5 min), sentiment (15 min), TVL/news (1-2h), security audit (24h). Redis cache không flexible theo category.

## Kiến Trúc

### DB Tables (3 bảng mới)

```
crypto_projects          — entity registry (token metadata)
crypto_data_snapshots    — append-only tool results timeline
search_space_crypto_watchlist — workspace → project link
```

### Middleware Stack

```
_build_gp_middleware(agent_name):
  ProviderRateLimitMiddleware()
  SourceAttributionMiddleware(agent_name)   ← fires events regardless
  CryptoDataCacheMiddleware(db, redis)      ← NEW
  ... (existing middleware)
```

### Flow (per tool call)

```
tool_name in TOOL_CATEGORY_MAP?  No → pass through
↓
SELECT fresh snapshot (expires_at > NOW())  → HIT → return cached
↓ MISS
Acquire Redis distributed lock (thundering herd)
↓
Double-check DB (parallel request may have filled cache)
↓
Call handler() → real API call
↓
Write snapshot → release lock → return result
↓ (ANY error above)
Graceful degradation → call handler() directly
```

### Data Categories & TTL

| Category | TTL | Coverage |
|----------|-----|----------|
| `price_realtime` | 5 min | get_live_token_price, get_live_token_data |
| `sentiment_index` | 15 min | get_cmc_sentiment, get_reddit_crypto_sentiment |
| `defi_tvl` | 1 hour | get_defillama_protocol |
| `defi_yields` | 2 hours | get_defillama_yields |
| `news` | 1 hour | get_crypto_news |
| `token_fundamentals` | 1 hour | get_coingecko_token_info |
| `smart_money` | 2 hours | Nansen tools |
| `security_audit` | 24 hours | GoPlus, CertiK tools |
| `contract_info` | 24 hours | get_contract_info |
| `tokeninsight` | 24 hours | TokenInsight tools |

## Hệ Quả

### Dương

- **Cost reduction ~70-90%** cho high-volume tokens (ETH, BTC, SOL) sau warmup period
- **Latency reduction** — cached responses bypass network round-trip
- **Rate limit safety** — multiple concurrent users không trigger multiple API calls
- **Historical data foundation** — enables future "timeline analysis" features (giá ETH qua 30 ngày, TVL trend)
- **Audit trail** — mọi data point trong report có thể trace về specific API call

### Âm

- **Schema complexity** — 3 new tables + Alembic migration
- **CryptoProjectResolver** cần logic để map heterogeneous tool args (symbol vs slug vs address) → canonical project_id
- **DB roundtrip overhead** — ~1-3ms per tool call cho cache lookup (acceptable vs API latency 200-2000ms)
- **Redis dependency** — distributed lock cần Redis; fallback to asyncio.Lock nếu Redis unavailable

## Feature Flag

`CRYPTO_DATA_CACHE_ENABLED` (default: `false`) cho phép safe rollout:
- `false` → middleware pass-through (zero behavior change)
- `true` → full cache interception

## Implementation Plan

Xem [Epic 10](../epics.md#epic-10) và stories [10-1](../stories/10-1-crypto-data-schema.md) → [10-5](../stories/10-5-workspace-watchlist-api.md).

## References

- Architecture plan: `/Users/luisphan/.claude/plans/partitioned-crafting-phoenix.md`
- Middleware pattern: `nowing_backend/app/agents/new_chat/chat_deepagent.py` (SourceAttributionMiddleware)
- Tool factory pattern: `nowing_backend/app/agents/new_chat/tools/defillama.py`
