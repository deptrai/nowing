# Kiến Trúc Hệ Thống: Backend (`nowing_backend`)

## 1. Tổng Quan
Backend của Nowing (viết bằng Python 3.12) chịu trách nhiệm chính trong việc xử lý Data Ingestion, Indexing, LLM Orchestration và cung cấp REST APIs cho các Client.

## 2. Công Nghệ Cốt Lõi
- **Môi trường Server**: FastAPI, Uvicorn
- **Database & ORM**: PostgreSQL, SQLAlchemy, Alembic (Migration), pgvector (Vector DB)
- **Task Queue & Background Jobs**: Celery, Redis
- **AI / LLM Framework**: LangChain, LangGraph, LiteLLM
- **Xử lý Dữ liệu**: Unstructured, Docling, Playwright

## 3. Cấu Trúc Mã Nguồn (Directory Structure)
```text
nowing_backend/app/
├── agents/              # Định nghĩa LangGraph agents / chains để xử lý luồng AI
├── api/routes/          # Chứa các endpoint API (users, chat, documents...)
├── connectors/          # Logic kết nối bên thứ 3 (Google Drive, Slack, Composio)
├── db.py                # Điểm khai báo Core Models của SQLAlchemy
├── etl_pipeline/        # Pipeline trích xuất dữ liệu, chunking text, transform
├── indexing_pipeline/   # Chịu trách nhiệm tạo embedding và push vào VectorDB
├── prompts/             # Template lưu trữ prompt chuẩn cho các luồng LLM
├── schemas/             # Pydantic models (validation cho request/response)
├── services/            # Tầng Business Logic (CRUD, gọi API ngoài)
├── tasks/               # Các Celery task (Background jobs xử lý nặng)
└── utils/               # Các hàm tiện ích (helper functions, formats, parsing)
```

## 4. Pipeline Architecture & Search (Deep Dive)

### 4.1 ETL Pipeline (`etl_pipeline/`)
Chịu trách nhiệm trích xuất văn bản từ nhiều định dạng file khác nhau.
- **Entry point**: `EtlPipelineService.extract()` phân loại file (`classify_file`) thành các nhóm (PLAINTEXT, DIRECT_CONVERT, AUDIO, IMAGE, DOCUMENT).
- **Parsers Tích Hợp**:
  - `docling`: Xử lý PDF/tài liệu phức tạp (via `parse_with_docling`).
  - `unstructured`: Parser thay thế cho tài liệu chung.
  - `llamacloud` / `Azure Document Intelligence`: Dùng làm internal accelerator để tối ưu chi phí/tốc độ.
  - `vision_llm`: Fallback parse ảnh nếu model Vision có sẵn.
  - `audio`: Dùng model transcribe.

### 4.2 Indexing Pipeline (`indexing_pipeline/`)
Chịu trách nhiệm chunking, tính toán embedding, chống trùng lặp và lưu trữ vào Vector DB.
- **State Feedback Tức Thì**: `create_placeholder_documents()` tạo ra các Document "Pending" vào DB ngay khi upload, giúp đồng bộ Zero Sync hiển thị UI lập tức.
- **Deduplication**: Dựa vào `compute_content_hash` và `compute_unique_identifier_hash` để chống duplicate khi document đã tồn tại và không đổi.
- **Chunking & Embedding**: Chạy bất đồng bộ (`asyncio.to_thread`) với hàm `chunk_text()` (có hỗ trợ riêng cho code chunking) và `embed_texts()` (chạy qua LiteLLM/OpenAI).
- **Concurrency Control**: Hàm `index_batch_parallel()` dùng `asyncio.Semaphore` để giới hạn số luồng (mặc định 4) tránh rate-limit từ APIs.

### 4.3 Retriever & Hybrid Search (`retriever/`)
Kết hợp sức mạnh Full-text search của Postgres và Vector search của `pgvector`.
- **Hybrid Search Flow (`chunks_hybrid_search.py`)**: 
  - Tính toán tsvector/tsquery (Keyword Search) và L2 Distance / Cosine Similarity `Chunk.embedding.op("<=>")` (Semantic Search).
  - Sử dụng chung RRF (Reciprocal Rank Fusion) ở cấp database (bằng CTE) để cho điểm `1.0 / (k + rank)`.
  - Phân trang & giới hạn: Fetch một số chunk nhất định mỗi document bằng `ROW_NUMBER()` trong subquery, tăng performance khi đọc những file dài/nhiều chunk.

## 4.4 Crypto Orchestra — Rate-limit Degradation Ladder

Epic 9 Crypto Orchestra spawns 6 sub-agents in parallel for comprehensive queries. When the underlying LLM provider has strict RPM limits (e.g., TrollLLM 10 RPM), the system degrades through **3 tiers** automatically. State lives in a module-level `_RateLimitState` in [`chat_deepagent.py`](../nowing_backend/app/agents/new_chat/chat_deepagent.py).

```
            ┌────────── Tier 1: PARALLEL ──────────┐
            │ escalation_level() == 0              │
            │ Emit 6 task() in single LangGraph    │
            │ turn. Target latency: <30s.          │
            └─────┬────────────────────────────────┘
                  │ 1st 429 detected (mark_rate_limited())
                  ▼
            ┌────────── Tier 2: SEQUENTIAL ────────┐
            │ escalation_level() == 1              │
            │ Emit 1 task() per turn, LangGraph    │
            │ loops. No forced sleep. ~15-25s.     │
            └─────┬────────────────────────────────┘
                  │ 3rd consecutive 429 within cooldown window
                  ▼
            ┌────────── Tier 3: PACED + REDUCED ───┐
            │ escalation_level() == 2              │
            │ (A) Cap analysis to 2 critical       │
            │     agents (tokenomics + defillama)  │
            │     instead of full 6                │
            │ (B) asyncio.sleep(PACED_DELAY)       │
            │     before each task() emission      │
            │ (C) Synthesis retries 3× with sleep  │
            │ Target: ~30-45s. Guaranteed partial  │
            │ answer.                              │
            └─────┬────────────────────────────────┘
                  │ cooldown_seconds pass without new 429
                  ▼
            (auto-reset to Tier 1)
```

### Layer 5 (2026-04-25 evening): Synthesis Mode — no respawn loop

Observation from E2E with pacing active: after all 6 sub-agents return (some erroring), the main orchestrator LLM may decide "retry the errored ones" and emit 6 fresh `task()` calls → infinite respawn loop hitting `recursion_limit` with zero final text.

Resolution — in `ParallelSpawnDirectiveMiddleware.awrap_model_call`, when `pending == []` (or on respawn-loop detection):

1. **Remove `task` from `request.tools`** + set `tool_choice="none"` so LLM mechanically cannot emit task() tool_calls.
2. **Replace** the parallel-spawn system directive with `_SYNTHESIS_DIRECTIVE` that explicitly says "Previous 'call 6 task()' instructions are OBSOLETE. Task tool REMOVED. Write final markdown now."
3. **Respawn-loop guard**: track last-emitted batch signature; force synthesis path if identical on consecutive turns.
4. Bump `recursion_limit` default 80 → 200 via `AGENT_RECURSION_LIMIT` env.

Verified: comprehensive queries at 8 RPM produce full markdown analysis rendered to UI (Copy/Download buttons enabled) instead of silent 14-minute timeout.

### Layer 4 (2026-04-25 afternoon): Sub-agent resilience + partial synthesis fallback

Even with Tier 3 pacing, sub-agents can still hit 429 on very strict providers. To **never lose partial work**, two layers sit between the tier ladder and the user:

**Layer 4a — `SubAgentResilienceMiddleware`** (main agent middleware chain) intercepts every `task()` tool invocation:
1. Retry sub-agent 3× with paced backoffs `(5s, 15s, 45s)` on `RateLimitError`
2. On terminal failure, convert the exception to a `ToolMessage(status="error")` with clear "agent unavailable" content
3. Main orchestrator sees the error ToolMessage, synthesizes using the N/6 agents that succeeded + acknowledges the X/6 that didn't

Before: 1 sub-agent hits 429 → raw `RateLimitError` bubbles up → LangGraph `astream_events` dies → all 5 successful sub-agents' outputs are discarded.
After: 1 sub-agent exhausts retries → error ToolMessage → main agent synthesizes 5/6 with transparency note.

**Layer 4b — `_extract_partial_analysis()`** (in `stream_new_chat.py`) — last-resort salvage:
- If the main orchestrator's synthesis LLM call itself gets rate-limited after its own 3× retries
- Reads current state from the LangGraph checkpointer (PostgreSQL-backed)
- Extracts all `ToolMessage` outputs paired to prior `task()` tool_calls
- Yields markdown-formatted partial response via Vercel streaming protocol
- **Guarantees**: user always sees graceful partial output, never the generic "Sorry, there was an error" message

### Orthogonal safety net: Global Provider Rate Gate (min-interval pacing)

A module-level `_global_rate_bucket` enforces a **strict minimum interval between consecutive LLM calls** across ALL agents (main orchestrator, sub-agents, KB planner, synthesis). Installed via monkey-patch on `ChatLiteLLM._agenerate` / `_astream` so every LLM invocation in the process passes through the gate — independent of which middleware chain spawned the call.

**Min-interval math**: `min_interval = window_seconds / max_rpm`
- At 10 RPM / 60s window → 6s between any two calls
- At 1 RPM / 60s window → 60s between any two calls
- At 60 RPM (Anthropic Tier 1) → 1s between any two calls

**Why min-interval, not token-bucket (2026-04-25 fix)**: Previous token-bucket implementation counted N calls per rolling window but allowed bursts (8 calls in 10ms could all pass when bucket was empty). Provider saw burst → 429 cascade despite the cap. Min-interval converts parallel bursts into strict serial pacing — **bursts mathematically impossible**. An `asyncio.Lock` held across the spacing wait serializes parallel callers into a queue.

**Result**: With `PROVIDER_RPM_LIMIT` set correctly for your provider, sub-agents virtually never see 429. The Layer-4 retry middleware becomes a safety net for clock-skew edge cases.

- Disabled by default (`PROVIDER_RPM_LIMIT=0`) — zero overhead
- Set `PROVIDER_RPM_LIMIT=10` for TrollLLM, `=50` for Anthropic Tier 1, `=1000` for Tier 2, etc.
- Combines with Tier 1/2/3: the gate smooths bursts; tiers react if a 429 slips through anyway

Tunables via environment variables:

| Env var | Default | Purpose |
|---------|---------|---------|
| `PROVIDER_RPM_LIMIT` | `0` (disabled) | Hard cap on LLM calls/minute. Set to match provider tier (10 TrollLLM / 50 Anthropic Tier 1 / 1000 Tier 2) |
| `PROVIDER_RATE_WINDOW_SECONDS` | `60` | Rolling window length. `min_interval = WINDOW/LIMIT` — derived automatically |
| `PROVIDER_RATE_MAX_WAIT_SECONDS` | `90` | Max single-call wait in gate (safety ceiling) |
| `SUBAGENT_RETRY_MAX_WALL_SECONDS` | `900` | Absolute cap on unbounded sub-agent retry (15 min). After this, emits error ToolMessage |
| `SUBAGENT_RETRY_BASE_BACKOFF` | `5` | Initial retry delay; doubles each attempt |
| `SUBAGENT_RETRY_MAX_BACKOFF` | `120` | Upper bound on exponential backoff delay |
| `CRYPTO_ORCHESTRA_RATE_LIMIT_COOLDOWN` | `60` | Seconds of 429-silence before escalation resets to Tier 1 |
| `CRYPTO_ORCHESTRA_ESCALATION_THRESHOLD` | `3` | Consecutive 429 events in cooldown window to promote Tier 2 → Tier 3 |
| `CRYPTO_ORCHESTRA_PACED_DELAY_SECONDS` | `7` | Forced sleep between agent emissions in Tier 3 (≈ 1 call per RPM slot at 10 RPM) |

Prometheus metrics:
- `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_degraded"}` — Tier 2 activations
- `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_paced"}` — Tier 3 activations + per-agent sleep events
- `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_reduced_scope"}` — Tier 3 agent-count reduction (6 → 2)
- `GRACEFUL_DEGRADATION_COUNTER{outcome="subagent_retry"}` — Layer 4a retry attempts
- `GRACEFUL_DEGRADATION_COUNTER{outcome="subagent_exhausted"}` — Layer 4a terminal failures (converted to error ToolMessage)
- `AGENT_ERRORS_COUNTER{error_type="rate_limit"}` — raw 429 events per sub-agent
- Log pattern `provider_rate_gate: N/M slots used — waiting X.Ys` — gate throttle events
- Log pattern `[stream_new_chat] yielding partial analysis: N completed, M errored` — Layer 4b salvage

Related stories: [0.6 Error Handling & Fallback](../_bmad-output/planning-artifacts/stories/0-6-error-handling-fallback.md) (Tier 1+2), [0.6b Tier 3 Paced Escalation](../_bmad-output/planning-artifacts/stories/0-6b-rate-limit-paced-escalation.md). Operational runbook: [crypto-orchestra-degradation.md](runbooks/crypto-orchestra-degradation.md).

## 5. Patterns Hiện Có
- **Tiêm Phụ Thuộc (Dependency Injection)**: Backend chia nhỏ logic theo các Service Class (`services/`, `EtlPipelineService`, `IndexingPipelineService`) sau đó inject vào Router thông qua `Depends()`. 
- **Bất Đồng Bộ (Asynchronous Operations)**:
  - Database Call: Sử dụng `asyncpg` và session async từ SQLAlchemy.
  - Xử lý nặng (Compute-Bound): Offload qua `asyncio.to_thread()` (VD: chunking, embedding generation).
- **Tách Biệt Task Queue**: Các thao tác Indexing bulk hoặc crawl dữ liệu qua Playwright đều được push qua Redis để Celery worker processing.

## 6. Deployment Info
Dự án được triển khai bằng Docker (có `docker-compose.yml` đi kèm cho Dev Environment chạy đủ bộ FastAPI, Postgres (pg17 vector), Redis, Celery Worker, Zero-Cache cache sync daemon).
