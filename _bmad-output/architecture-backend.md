# Kiến Trúc Backend

## Tổng Quan
Backend của Nowing là một ứng dụng **Python FastAPI** mạnh mẽ, được thiết kế cho các quy trình làm việc agentic hiệu suất cao. Nó đóng vai trò là hệ thống thần kinh trung ương, điều phối RAG (Retrieval-Augmented Generation), quản lý bộ nhớ của agent (agent memory), và xử lý tương tác với các mô hình ngôn ngữ lớn (LLMs).

## Các Thành Phần Cốt Lõi

### 1. Framework AI Agent (DeepAgents & LangGraph)
- **DeepAgents**: Framework tùy chỉnh để xây dựng các AI agents tự chủ (autonomous agents), cung cấp `SubAgent`, `SubAgentMiddleware`, và middleware primitives.
- **LangGraph**: Quản lý StateGraph (đồ thị trạng thái) và quy trình điều phối cho các suy luận phức tạp, nhiều bước.
- **Workflow**: Người dùng gửi truy vấn → LangGraph chạy main agent → main agent spawn crypto sub-agents song song qua `task()` tool → tổng hợp kết quả → stream về client.
- **Crypto Orchestra**: 7 sub-agents chuyên biệt (defillama, sentiment, news, smart_contract, tokenomics, yield_optimizer, whale_tracker) chạy parallel với scoped tool lists. Chi tiết xem [architecture-crypto-orchestra.md](./architecture-crypto-orchestra.md).

### 2. Dịch Vụ Dữ Liệu (Data Services)
- **Primary Database**: **Postgres** (với extension `pgvector`) lưu trữ:
    - Dữ liệu người dùng & ứng dụng.
    - Vector Embeddings cho tìm kiếm ngữ nghĩa (semantic search).
    - Lịch sử chat và phiên làm việc.
- **ORM**: **SQLAlchemy (Async)** dùng cho các tương tác cơ sở dữ liệu quan hệ. Models định nghĩa tại `app/db.py` (42 models, 2710 lines).
- **Caching/Queue**: **Redis** dùng cho hàng đợi tác vụ (Celery broker), pubsub cho live SSE stream, và caching phản hồi ngắn hạn.
- **Authentication**: fastapi-users với JWT (primary) + OAuth2 (Google). Gift code subscription flow có models (`GiftCode`, `GiftRequest`) nhưng routes chưa implement.

### 3. Hệ Thống Tìm Kiếm & RAG
- **Vector Store**: Sử dụng `pgvector` để lưu trữ embeddings của tài liệu.
- **Retriever**: Logic tùy chỉnh trong `app/retriever/` để lấy ngữ cảnh (fetches context) dựa trên sự tương đồng (similarity) và metadata filtering.
- **Ingestion Pipeline**: Celery workers xử lý việc tải tài liệu từ nguồn bên ngoài, chia nhỏ văn bản (chunking), tạo embedding, và lưu trữ.

### 4. Kết Nối Ứng Dụng Ngoài (Connectors)
- **Kiến Trúc**: Modular adapter pattern.
- **Hỗ trợ**: Slack, Google Drive, Notion, GitHub, v.v. (30+ integrations).
- **Cơ chế**: Webhooks hoặc định kỳ polling (thực hiện bởi Celery beats).

## Luồng Dữ Liệu (Data Flow)

1. **Request**: Client (Web/Extension) gửi REST request tới FastAPI Endpoints.
2. **Auth**: Middleware xác thực JWT/OAuth token.
3. **Controller**: Route handler (`app/routes/`) nhận request, gọi Service layer.
4. **Processing**:
    - Nếu là tác vụ nhanh (CRUD): Xử lý trực tiếp với DB.
    - Nếu là tác vụ AI: Đẩy vào LangGraph runner để streaming phản hồi.
    - Nếu là tác vụ dài (Ingestion): Đẩy job vào Redis queue cho Celery.
5. **Response**: Trả về JSON hoặc Streaming Response (SSE).

## Critical RAG Pipeline Fix (Feb 2026)

### DexScreener Connector Integration

**Issue Discovered**: DexScreener connector was successfully implemented and indexed data into `search_space_id = 7`, but the LLM could not retrieve this data when users asked about crypto prices.

**Root Cause**: Missing connector mapping in `_CONNECTOR_TYPE_TO_SEARCHABLE` dictionary.

**File**: `nowing_backend/app/agents/new_chat/chat_deepagent.py`

**The Problem**:
```python
# BEFORE (Missing mapping)
_CONNECTOR_TYPE_TO_SEARCHABLE = {
    "GMAIL": "GMAIL",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE",
    "SLACK_CONNECTOR": "SLACK",
    # ... other connectors ...
    # ❌ DEXSCREENER_CONNECTOR was MISSING
}
```

**Impact**:
1. `connector_service.get_available_connectors()` returned DexScreener connector type
2. `_map_connectors_to_searchable_types()` could not find mapping → ignored DexScreener
3. LLM's tool description didn't mention DexScreener as available
4. LLM never searched DexScreener data, responded "can't see price data"

**The Fix**:
```python
# AFTER (Fixed)
_CONNECTOR_TYPE_TO_SEARCHABLE = {
    "GMAIL": "GMAIL",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE",
    "SLACK_CONNECTOR": "SLACK",
    # ... other connectors ...
    "DEXSCREENER_CONNECTOR": "DEXSCREENER_CONNECTOR",  # ✅ Added
}
```

**Verification**:
- User query: *"What's the current price of WETH?"*
- LLM successfully retrieved: ~$2,442 USD with DexScreener citations
- Citations linked to indexed trading pairs with metadata (chain, DEX, liquidity, volume)

**Lesson Learned**: When adding new connectors, **ALWAYS** update the `_CONNECTOR_TYPE_TO_SEARCHABLE` mapping to enable RAG retrieval. This is a critical step that's easy to miss during implementation.

---

## Connector Architecture Pattern

### Adding New Connectors (Best Practices)

Khi thêm connector mới, cần update **4 locations**:

1. **Connector Class** (`app/connectors/`)
   - Implement data fetching logic
   - Format data to markdown for indexing

2. **Database Enum** (`app/db.py`)
   - Add to `SearchSourceConnectorType` enum

3. **API Routes** (`app/routes/`)
   - Create add/delete/test endpoints

4. **RAG Mapping** (`app/agents/new_chat/chat_deepagent.py`) ⚠️ **CRITICAL**
   - Add to `_CONNECTOR_TYPE_TO_SEARCHABLE` dictionary
   - **Failure to do this = LLM cannot access connector data**

---

## Hybrid Crypto Data Architecture (Feb 2026)

### Vấn Đề: Data Freshness cho Crypto

Kiến trúc Connector ban đầu sử dụng **periodic indexing** (5-60 phút) để index data từ DexScreener vào database. Điều này phù hợp cho:
- ✅ Phân tích lịch sử, xu hướng
- ✅ Research & context
- ❌ **KHÔNG** phù hợp cho real-time price queries

### Giải Pháp: Hybrid Approach (RAG + Real-time)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER QUERY                                      │
│                    "Phân tích BULLA cho tôi"                            │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI AGENT (LangGraph)                               │
│                                                                         │
│   Quyết định dùng tool nào dựa trên intent:                             │
│                                                                         │
│   ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│   │  RAG Tools              │    │  Real-time Tools                │   │
│   │  (Indexed Data)         │    │  (Live API Calls)               │   │
│   ├─────────────────────────┤    ├─────────────────────────────────┤   │
│   │ search_knowledge_base   │    │ get_live_token_price            │   │
│   │                         │    │ get_live_token_data             │   │
│   │ • Xu hướng lịch sử      │    │ • Giá hiện tại                  │   │
│   │ • Phân tích quá khứ     │    │ • Volume live                   │   │
│   │ • Context & tin tức     │    │ • Giao dịch real-time           │   │
│   └─────────────────────────┘    └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Real-time Tools Implementation

**File**: `nowing_backend/app/agents/new_chat/tools/crypto_realtime.py`

| Tool | Mô tả | Use Case |
|------|-------|----------|
| `get_live_token_price` | Lấy giá real-time từ DexScreener API | "Giá SOL bây giờ?" |
| `get_live_token_data` | Lấy full market data (price, volume, txns) | "Volume giao dịch BULLA?" |

**Đặc điểm**:
- Gọi trực tiếp DexScreener API (không qua indexed data)
- Không cần dependencies (`requires=[]`)
- Trả về data với `data_source: "DexScreener API (Real-time)"`

### Khi Nào AI Dùng Tool Nào?

| Query Type | Tool | Ví dụ |
|------------|------|-------|
| Giá hiện tại | `get_live_token_price` | "Giá BULLA bây giờ là bao nhiêu?" |
| Market data live | `get_live_token_data` | "Volume giao dịch SOL thế nào?" |
| Phân tích lịch sử | `search_knowledge_base` | "BULLA tuần này như thế nào?" |
| Phân tích tổng hợp | **Cả hai** | "Phân tích BULLA cho tôi" |

### Frontend Tool-UI Components

**Files**:
- `nowing_web/components/tool-ui/crypto/live-token-price.tsx`
- `nowing_web/components/tool-ui/crypto/live-token-data.tsx`

Các components này render kết quả từ real-time tools trong chat interface với:
- Badge "Real-time" để phân biệt với RAG data
- Price change indicators (5m, 1h, 6h, 24h)
- Transaction activity bar (buys vs sells)
- Link đến DexScreener chart

---

## Background Agent Execution (Story 9-UX-1b)

Agent execution sống độc lập với HTTP request lifetime, cho phép FE disconnect / browser refresh / tab close mà không mất progress.

### Tables
- `chat_runs` — mỗi agent execution có 1 row (UUID PK, status: running/completed/failed/cancelled/abandoned)
- `chat_run_events` — toàn bộ SSE events được persist (seq monotonic per run, ON CONFLICT DO NOTHING cho idempotency)

### Key Components
| Component | File | Responsibility |
|---|---|---|
| `RunEventWriter` | `app/services/run_event_writer.py` | Sync write() + async flush: INSERT → PUBLISH (C6) |
| `run_manager` | `app/tasks/chat/run_manager.py` | start_run / cancel_run / resume_run / mark_abandoned_on_startup |
| `stream_new_chat_detached` | `app/tasks/chat/stream_new_chat.py` | Async function consuming agent SSE, writing to RunEventWriter |
| REST endpoints | `app/routes/new_chat_routes.py` | POST /runs, GET /runs/active, GET /runs/{id}/stream, POST /runs/{id}/cancel, POST /runs/{id}/resume |

### Constraints
- **M1 Single-worker**: `_active_runs` dict là module-level → `UVICORN_WORKERS=1` bắt buộc
- **M2 Migration race**: `mark_abandoned_runs_on_startup` wrapped in try/except
- **M5 Reload protection**: skip orphan cleanup khi `UVICORN_RELOAD=true`
- **C1 LangGraph isolation**: detached run dùng `langgraph_thread_id = "run-{uuid}"` (không phải `thread_id`) để tránh checkpoint collision
- **C6 INSERT before PUBLISH**: DB luôn là source of truth; Redis pubsub chỉ là live-tail

### Feature Flag
`RESUMABLE_RUNS_ENABLED=true` (default) — khi false, POST /runs trả 503, FE fallback về /regenerate.

---

## Architectural Contracts (Story 9-UX-1c)

### T1 — SSE Wire Format (Vercel UI Stream)
Tất cả SSE events từ `/runs/{id}/stream` dùng bare `data:` format — không có `event:` header.

```
data: {"type":"orchestra-spawn","data":{...}}\n\n
data: {"_marker":"replay-end","status":"completed"}\n\n
```

- **`_parse_vercel_envelope(line)`** (`stream_new_chat.py`) — parse raw SSE line về `(event_type, payload)` tuple. Hỗ trợ text-delta prefix (`0:"text"\n`, `a:...\n`) + full JSON envelope.
- **`_rebuild_vercel_wire(event_type, payload)`** (`new_chat_routes.py`) — tái tạo `data: {json}\n\n` line để emit. Nếu payload có `_vercel` key → emit raw. Legacy `_raw` passthrough còn hỗ trợ.
- **Round-trip contract**: `_parse_vercel_envelope(_rebuild_vercel_wire(t, p))` → `(t, p)` (không mất thông tin).

### T2 — Sentinels / Replay Markers
| Sentinel | Khi nào emit |
|---|---|
| `{"_marker":"replay-start"}` | Trước khi yield event đầu tiên từ DB |
| `{"_marker":"replay-end","status":"<running_status>"}` | Sau SELECT drain xong; status = `"live"` \| `"completed"` \| `"abandoned"` \| ... |
| `{"_marker":"run-end"}` | Sau khi pubsub tail kết thúc (run terminal) |

FE dùng `replay-end.status` để quyết định chế độ UI:
- `"live"` → tiếp tục tail stream
- `"completed"` / `"failed"` / `"cancelled"` → đóng stream, show kết quả
- `"abandoned"` → show Resume button trong strip header

### T3 — SUBSCRIBE-First Replay Protocol
Để tránh event loss khi event publish trong khoảng SELECT đang chạy:

```
1. SUBSCRIBE pubsub channel trước
2. Emit _marker: replay-start
3. SELECT * FROM chat_run_events ORDER BY seq → yield tất cả
4. Emit _marker: replay-end (status = run.status)
5. Drain buffer từ pubsub (dedup by seq vs max_replayed_seq)
6. Tail pubsub live cho đến khi run terminal
7. Emit _marker: run-end
```

Gap scan: mỗi 1s poll DB cho seq > last_seen để catch missed pubsub messages.

### T5 — RunEventWriter: deque + coalescing
- `_deque: collections.deque(maxlen=10_000)` — thay thế `asyncio.Queue` (không blocking, overflow drop oldest)
- `_pending_delta: dict[str, tuple[str, dict]]` — per-agentId coalescing cho `text-delta`: chỉ giữ latest chunk trước khi flush. Tuple là `(event_type, payload)`.
- Flush loop: drain `_pending_delta` vào batch trước khi process `_deque`.

### T6 — Advisory Lock + Seq Re-seeding (T16)
Khi hai writers race (không xảy ra trong production single-worker, nhưng cần idempotent):

```sql
SELECT pg_advisory_xact_lock(hashtext(:run_id));
SELECT COALESCE(MAX(seq), -1) + 1 FROM chat_run_events WHERE run_id = :run_id;
```

Nếu DB seq > writer._next_seq → writer tự offset để dùng DB seq. Sau flush `_next_seq = db_seq + batch_size`.

### T8 — Heartbeat Fence
`RunEventWriter.run_flush_loop()` emit `{"type":"heartbeat"}` mỗi 30s nếu không có event nào. Serving endpoint timeout > 30s → client không bị disconnect do silence.

`chat_runs.last_heartbeat_at` (TIMESTAMPTZ) được update sau mỗi heartbeat. `mark_abandoned_runs_on_startup()` dùng `last_heartbeat_at` thay vì `started_at` để phân biệt truly-stalled runs (> 90 giây không heartbeat).

### C4 — Dedup trên Resume
Khi runner restart và resume từ checkpoint:
- `_seed_seen_events()` đọc `chat_run_events` để populate `_seen_spawn_agents`, `_seen_source_keys`, `_seen_attribution_agents`
- `_should_dedup(event_type, payload)` → True nếu event đã persist (skip INSERT + PUBLISH)
- Dedup chỉ áp dụng cho: `orchestra-spawn` (by agentId), `data-orchestra-source-fetched` (by agentId:domain), `data-orchestra-model-attribution` (by agentId)

---

## Middleware Pipeline (chat_deepagent.py)

Main agent và sub-agents đều đi qua middleware stack. Ordering quan trọng — middleware chạy tuần tự, mỗi layer wrap layer tiếp theo.

### Pipeline cho Main Agent

```
Request → AnthropicPromptCachingMiddleware
        → PatchToolCallsMiddleware
        → TodoListMiddleware
        → create_summarization_middleware()
        → KnowledgeBaseSearchMiddleware    ← custom (middleware/)
        → MemoryInjectionMiddleware        ← custom (middleware/)
        → DedupHITLToolCallsMiddleware     ← custom (middleware/)
        → NowingFilesystemMiddleware       ← custom (middleware/)
        → SourceAttributionMiddleware      ← custom (chat_deepagent.py)
        → ProviderRateLimitMiddleware      ← custom (chat_deepagent.py)
        → ParallelSpawnDirectiveMiddleware ← custom (chat_deepagent.py)
        → ParallelismTelemetryMiddleware   ← custom (chat_deepagent.py)
        → LangGraph StateGraph execution
```

### Pipeline cho Sub-Agents (via `_build_gp_middleware()`)

Mỗi sub-agent nhận **fresh middleware instances** (NFR-CS4) để tránh state leaking:

```
Sub-agent request → AnthropicPromptCachingMiddleware
                  → PatchToolCallsMiddleware
                  → TodoListMiddleware
                  → create_summarization_middleware()
                  → KnowledgeBaseSearchMiddleware
                  → MemoryInjectionMiddleware
                  → NowingFilesystemMiddleware
                  → SourceAttributionMiddleware
                  → SubAgentResilienceMiddleware    ← retry + exponential backoff
                  → LangGraph execution
```

### Middleware Descriptions

| Middleware | File | Chức năng |
|-----------|------|-----------|
| `AnthropicPromptCachingMiddleware` | langchain_anthropic | Cache prompt prefixes (system + few-shot) để giảm latency + cost |
| `PatchToolCallsMiddleware` | deepagents | Fix malformed tool_call JSON từ LLM (incomplete args, missing fields) |
| `TodoListMiddleware` | langchain | Manage agent's internal task list (plan, execute, track progress) |
| `create_summarization_middleware()` | deepagents | Auto-summarize conversation khi vượt context window |
| `KnowledgeBaseSearchMiddleware` | middleware/knowledge_search.py | Pre-search KB trước mỗi LLM call, inject relevant chunks vào context |
| `MemoryInjectionMiddleware` | middleware/memory_injection.py | Inject team memory document vào system prompt |
| `DedupHITLToolCallsMiddleware` | middleware/dedup_tool_calls.py | Dedup human-in-the-loop tool calls (prevent double-execution) |
| `NowingFilesystemMiddleware` | middleware/filesystem.py | Virtual filesystem cho agent (read/write/list files trong search space) |
| `SourceAttributionMiddleware` | chat_deepagent.py | Track data sources (CoinGecko, DeFiLlama, etc.) cho citation pipeline |
| `ProviderRateLimitMiddleware` | chat_deepagent.py | Global rate bucket — min interval giữa LLM calls, prevent burst |
| `SubAgentResilienceMiddleware` | chat_deepagent.py | Retry with exponential backoff cho sub-agent failures (rate limit, timeout). Max 5 attempts, max backoff 120s |
| `ParallelSpawnDirectiveMiddleware` | chat_deepagent.py | Orchestrate crypto sub-agents: inject parallel task() directives vào system prompt, quản lý spawn order, handle synthesis phase |
| `ParallelismTelemetryMiddleware` | chat_deepagent.py | Track task() calls per model step — log warning nếu agents spawned sequentially thay vì parallel |

### Ordering Constraints

1. **PromptCaching PHẢI đứng đầu** — nó cần thấy raw messages trước khi các middleware khác modify
2. **PatchToolCalls PHẢI trước TodoList** — fix JSON trước khi TodoList parse tool results
3. **KnowledgeSearch PHẢI trước SourceAttribution** — search results cần được attribute
4. **ParallelSpawnDirective PHẢI sau SourceAttribution** — cần source data để build synthesis directive
5. **Resilience CHỈ cho sub-agents** — main agent không retry (user đang chờ stream)

---

## Tool Registry (`app/agents/new_chat/tools/registry.py`)

56 tools registered, sử dụng factory pattern với dependency injection:

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    factory: Callable[[dict[str, Any]], BaseTool]
    requires: list[str] = field(default_factory=list)  # DB deps needed
```

### Tool Categories

| Category | Count | Tools | Requires |
|----------|-------|-------|----------|
| **Content Generation** | 4 | podcast, video_presentation, report, generate_image | db_session, search_space_id, user_id |
| **Web** | 2 | web_search, scrape_webpage | (none) |
| **Knowledge Base** | 2 | chainlens_research, search_nowing_docs | search_space_id |
| **Crypto — Real-time** | 2 | get_live_token_price, get_live_token_data | (none) |
| **Crypto — DeFiLlama** | 5 | protocol, tvl_overview, yields, stablecoins, bridges | (none) |
| **Crypto — Sentiment/News** | 4 | cmc_sentiment, reddit_sentiment, crypto_news, coingecko_info | (none) |
| **Crypto — Security** | 4 | contract_info, token_security, certik_audit_score, certik_incident_history | (none) |
| **Crypto — On-chain** | 4 | nansen_smart_money, nansen_wallet_label, nansen_token_god_mode, run_dune_query | (none) |
| **Crypto — Research** | 2 | tokeninsight_rating, tokeninsight_research_snippet | (none) |
| **Connector CRUD** | ~30 | Linear (3), Notion (3), Google Drive (2), Dropbox (2), OneDrive (2), Calendar (3), Gmail (2), Confluence (3), Jira (3), Slack (3), Teams (2) | db_session, connector_id |
| **Agent Internal** | 3 | update_memory, update_team_memory, scenario_resynthesis | db_session, search_space_id |

### Tool Scoping cho Sub-Agents

Mỗi sub-agent chỉ nhận subset tools liên quan (NFR-CS4), định nghĩa tại `subagents/crypto/*_spec.py`:

```python
# Ví dụ: defillama_spec.py
DEFILLAMA_ALLOWED_TOOLS: tuple[str, ...] = (
    "get_defillama_protocol",
    "get_defillama_tvl_overview",
    "get_defillama_yields",
    "get_defillama_stablecoins",
    "get_defillama_bridges",
    "get_live_token_data",
    "get_live_token_price",
    "chainlens_deep_research",
)
```

---

## Cấu Trúc Thư Mục Chính

```
nowing_backend/app/
├── agents/new_chat/
│   ├── chat_deepagent.py      — Main agent factory + inline middleware (2478 LOC)
│   ├── middleware/
│   │   ├── knowledge_search.py — KB pre-search middleware
│   │   ├── memory_injection.py — Team memory injection
│   │   ├── dedup_tool_calls.py — HITL dedup
│   │   └── filesystem.py       — Virtual filesystem
│   ├── subagents/crypto/
│   │   ├── defillama_spec.py   — DeFiLlama analyst spec
│   │   ├── sentiment_spec.py   — Sentiment analyst spec
│   │   ├── news_spec.py        — News analyst spec
│   │   ├── smart_contract_spec.py
│   │   ├── tokenomics_spec.py
│   │   ├── whale_tracker_spec.py
│   │   ├── yield_optimizer_spec.py
│   │   └── narration_templates.py — Post-call narration for orchestra events
│   └── tools/
│       ├── registry.py         — 56 ToolDefinitions
│       ├── defillama.py        — 5 DeFiLlama tools
│       ├── crypto_sentiment.py — CMC + Reddit sentiment
│       ├── crypto_news.py      — CryptoPanic news
│       ├── crypto_realtime.py  — DexScreener live price/data
│       ├── contract_analysis.py — Etherscan + GoPlus security
│       ├── certik_skynet.py    — CertiK audit score + incidents
│       ├── nansen_smart_money.py — Nansen whale tracking
│       ├── dune_query.py       — Dune Analytics queries
│       ├── tokeninsight_rating.py — TokenInsight ratings
│       ├── _rate_limiter.py    — Shared rate limiting utilities
│       └── ... (web_search, scrape, generate_image, etc.)
├── routes/                     — 50 route files (REST endpoints)
├── services/                   — Business logic layer
│   ├── connector_service.py    — ConnectorService class (2942 LOC)
│   ├── llm_router_service.py   — LLM model routing (1173 LOC)
│   ├── new_streaming_service.py
│   ├── notification_service.py
│   └── ... (30+ services)
├── tasks/
│   ├── chat/                   — Agent execution (stream_new_chat, run_manager)
│   ├── celery_tasks/           — Background jobs
│   └── connector_indexers/     — Periodic connector data indexing
├── retriever/                  — RAG retrieval logic
│   ├── chunks_hybrid_search.py
│   └── documents_hybrid_search.py
├── connectors/                 — Connector adapters (google_drive, dropbox, onedrive)
└── db.py                       — SQLAlchemy models (42 models, 2710 LOC)
```

---

## Crypto Data Persistence Layer (Epic 10)

**Added:** 2026-04-29 | **ADR:** [ADR-001-crypto-data-layer.md](./planning-artifacts/adrs/ADR-001-crypto-data-layer.md)

### Vấn Đề

Mỗi crypto analysis spawn 7 sub-agents × 2-5 external API calls = ~15-35 API calls. 100 concurrent users query ETH → ~3500 API calls/hr cho identical data. Epic 10 giảm xuống còn ~1 API call set per TTL window per token.

### Kiến Trúc

```
Sub-agent tool call
       │
       ▼
SourceAttributionMiddleware    ← fires narration/events always
       │
       ▼
CryptoDataCacheMiddleware      ← NEW (Epic 10)
  ├── TOOL_CATEGORY_MAP check  → not crypto tool? pass through
  ├── CryptoProjectResolver    → resolve args to canonical project_id
  ├── DB fresh snapshot check  → HIT? return cached data
  ├── Redis lock acquire       → thundering herd protection
  ├── Double-check DB          → someone else filled cache?
  ├── Call handler()           → actual API call
  ├── CryptoDataStore.write()  → persist snapshot
  └── Error? → graceful degradation → call handler() directly
       │
       ▼
External API (DeFiLlama, CoinGecko, GoPlus, etc.)
```

### DB Schema (3 tables mới)

```python
# app/models/crypto.py

class CryptoProject(Base):
    id               SERIAL PK
    project_id       VARCHAR(128) UNIQUE   # "uniswap", "ethereum"
    symbol           VARCHAR(32)           # "UNI", "ETH"
    name             VARCHAR(256)
    chain            VARCHAR(64)
    contract_address VARCHAR(128)
    coingecko_id     VARCHAR(128)
    defillama_slug   VARCHAR(128)
    metadata         JSONB
    created_at, updated_at

class CryptoDataSnapshot(Base):
    id           BIGSERIAL PK
    project_id   FK → crypto_projects
    data_category VARCHAR(64)     # "defi_tvl", "price_realtime", etc.
    tool_name    VARCHAR(128)
    tool_args    JSONB
    data         JSONB NOT NULL   # full tool return dict
    data_hash    VARCHAR(64)      # SHA-256 for dedup
    fetched_at   TIMESTAMPTZ
    ttl_seconds  INTEGER
    expires_at   TIMESTAMPTZ      # fetched_at + interval ttl_seconds
    is_error     BOOLEAN DEFAULT FALSE
    api_source   VARCHAR(64)
    # Indexes: (project_id, data_category, fetched_at DESC), (expires_at)

class SearchSpaceCryptoWatchlist(Base):
    search_space_id FK → searchspaces
    project_id      FK → crypto_projects
    added_at, added_by_id, pin_order
    UNIQUE(search_space_id, project_id)
```

### Data Categories & TTL

| Category | TTL | Tools |
|----------|-----|-------|
| `price_realtime` | 5 min | get_live_token_price, get_live_token_data |
| `sentiment_index` | 15 min | get_cmc_sentiment, get_reddit_crypto_sentiment |
| `defi_tvl` | 1 hour | get_defillama_protocol |
| `defi_yields` | 2 hours | get_defillama_yields |
| `defi_overview` | 2 hours | get_defillama_tvl_overview, get_defillama_stablecoins |
| `news` | 1 hour | get_crypto_news |
| `token_fundamentals` | 1 hour | get_coingecko_token_info |
| `smart_money` | 2 hours | get_nansen_smart_money, get_nansen_wallet_label |
| `dune_onchain` | 2 hours | run_dune_query |
| `security_audit` | 24 hours | check_token_security, get_certik_audit_score |
| `contract_info` | 24 hours | get_contract_info |
| `tokeninsight` | 24 hours | get_tokeninsight_rating, get_tokeninsight_research_snippet |
| `certik_incidents` | 24 hours | get_certik_incident_history |

### New Files (Epic 10)

```
nowing_backend/app/
├── models/
│   └── crypto.py                          — 3 SQLAlchemy models
├── agents/new_chat/
│   ├── tools/
│   │   └── crypto_data_categories.py      — Enum, TTL config, TOOL_CATEGORY_MAP
│   └── middleware/
│       └── crypto_data_cache.py           — CryptoDataCacheMiddleware
├── services/
│   ├── crypto_project_resolver.py         — Multi-field project resolution
│   ├── crypto_data_store.py               — Snapshot CRUD (read/write)
│   └── crypto_cache_lock.py               — Redis distributed lock
├── tasks/celery_tasks/
│   └── crypto_refresh_tasks.py            — Background refresh + cleanup
└── routes/
    └── crypto_data_routes.py              — Watchlist + timeline REST API
```

### Feature Flag

`CRYPTO_DATA_CACHE_ENABLED` (default: `false`) — safe rollout toggle. `false` = zero behavior change (pass-through middleware).

### Middleware Stack Integration

```python
# chat_deepagent.py — _build_gp_middleware() after Epic 10
def _build_gp_middleware(agent_name: str):
    return [
        AnthropicPromptCachingMiddleware(...),
        PatchToolCallsMiddleware(...),
        KnowledgeSearchMiddleware(...),
        MemoryInjectionMiddleware(...),
        DedupToolCallsMiddleware(...),
        NowingFilesystemMiddleware(...),
        SourceAttributionMiddleware(agent_name),   # narration always
        CryptoDataCacheMiddleware(db, redis),       # ← NEW: cache interception
        SubAgentResilienceMiddleware(...),
        ...
    ]
```
