# Architecture Improvement Proposals — Nowing

**Date:** 2026-04-29
**Author:** Winston (System Architect)
**Scope:** Full stack — Agent/LLM, Data/Infra, Frontend
**Constraint:** Greenfield OK — breaking changes acceptable for long-term gains

---

## Overview

Đề xuất 12 cải tiến chia 3 tiers: Quick Wins (1-3 ngày), Strategic (1-2 tuần), Transformational (1+ tháng). Mỗi đề xuất bao gồm: vấn đề hiện tại, giải pháp đề xuất, trade-offs, và estimated effort.

---

## Tier 1: Quick Wins (ship trong 1-3 ngày, zero risk)

### QW-1: Extract Inline Middleware from chat_deepagent.py

**Vấn đề:** `chat_deepagent.py` chứa 5 middleware classes inline (2478 LOC). Khi cần sửa `SubAgentResilienceMiddleware`, dev phải scroll qua agent factory code. Cognitive load cao, merge conflicts thường xuyên.

**Đề xuất:**
```
middleware/
├── __init__.py                   (re-export tất cả)
├── knowledge_search.py           (existing)
├── memory_injection.py           (existing)
├── dedup_tool_calls.py           (existing)
├── filesystem.py                 (existing)
├── source_attribution.py         ← EXTRACT
├── provider_rate_limit.py        ← EXTRACT
├── sub_agent_resilience.py       ← EXTRACT
├── parallel_spawn_directive.py   ← EXTRACT
├── parallelism_telemetry.py      ← EXTRACT
└── token_usage_tracker.py        ← EXTRACT
```

**Impact:** `chat_deepagent.py` giảm ~1200 LOC → chỉ còn agent factory + graph setup.
**Risk:** Zero — pure refactor, no behavior change.
**Effort:** 1 ngày.

---

### QW-2: Split db.py into Model Modules

**Vấn đề:** 42 models trong 1 file (2710 LOC). `git blame` chậm, IDE navigation khó, mọi Alembic migration đều touch `db.py`.

**Đề xuất:**
```python
# app/models/__init__.py — backwards-compatible re-export
from app.models.base import Base, TimestampMixin
from app.models.user import User, UserProfile
from app.models.chat import ChatThread, ChatMessage, ChatRun, ChatRunEvent
from app.models.document import Document, DocumentChunk
from app.models.connector import SearchSourceConnector, SearchSourceConnectorType
from app.models.subscription import Subscription, GiftCode, GiftRequest
# ... etc

# Alembic env.py chỉ cần import Base từ models/__init__.py
```

**Trick:** Giữ `from app.db import *` hoạt động bằng cách biến `db.py` thành thin re-export module. Zero breaking changes cho existing code.
**Effort:** 1-2 ngày.

---

### QW-3: Tool Registry Grouping + Validation

**Vấn đề:** 56 ToolDefinitions trong flat list. Thêm tool mới phải scroll hàng trăm dòng. Không có startup validation — tool factory failure chỉ phát hiện khi user trigger.

**Đề xuất:**
```python
# registry.py
CRYPTO_TOOLS: list[ToolDefinition] = [...]      # 21 tools
CONNECTOR_TOOLS: list[ToolDefinition] = [...]    # ~30 tools
CONTENT_TOOLS: list[ToolDefinition] = [...]      # 4 tools
WEB_TOOLS: list[ToolDefinition] = [...]          # 2 tools
AGENT_INTERNAL_TOOLS: list[ToolDefinition] = [...]

BUILTIN_TOOLS = CRYPTO_TOOLS + CONNECTOR_TOOLS + CONTENT_TOOLS + WEB_TOOLS + AGENT_INTERNAL_TOOLS

# Startup validation
def validate_registry():
    """Call during app startup — fail fast if any factory is broken."""
    for td in BUILTIN_TOOLS:
        assert callable(td.factory), f"Tool {td.name} factory is not callable"
```

**Effort:** 0.5 ngày.

---

## Tier 2: Strategic Improvements (1-2 tuần, moderate risk)

### S-1: Migrate Crypto Tools → MCP Servers

**Vấn đề:** 21 crypto tools dùng custom factory pattern. Mỗi tool là Python function wrap HTTP call. Không reusable ngoài Nowing, không standardized, khó test isolation.

**Đề xuất:** Migrate sang **MCP (Model Context Protocol)** servers — đang trở thành industry standard cho tool integration.

```
nowing_backend/
├── mcp_servers/
│   ├── crypto_defi/          # DeFiLlama + yields
│   │   ├── server.py         # FastMCP server
│   │   └── tools.py          # 5 DeFiLlama tools
│   ├── crypto_security/      # GoPlus + CertiK + Etherscan
│   │   ├── server.py
│   │   └── tools.py          # 4 security tools
│   ├── crypto_intelligence/  # Nansen + Dune + TokenInsight
│   │   ├── server.py
│   │   └── tools.py          # 7 on-chain tools
│   └── crypto_sentiment/     # CryptoPanic + Reddit + CMC
│       ├── server.py
│       └── tools.py          # 4 sentiment tools
```

**Lợi ích:**
- **Reusability**: MCP servers chạy standalone, dùng được với Claude Desktop, Cursor, bất kỳ MCP client
- **Isolation**: Mỗi server có process riêng → crash isolation, independent scaling
- **Testing**: Test từng MCP server independent mà không cần full agent stack
- **Ecosystem**: Chia sẻ với community nếu muốn open-source

**Trade-off:** Thêm inter-process communication overhead (stdio/HTTP). Cho crypto tools (external API calls), overhead này negligible so với network latency.

**Migration path:** Giữ factory pattern cho internal tools (knowledge_base, filesystem). Chỉ migrate stateless external-API tools.
**Effort:** 1-2 tuần.

---

### S-2: Middleware Pipeline → Composable Middleware Graph

**Vấn đề:** Linear middleware chain (13 layers) có ordering constraints phức tạp. Thêm middleware mới phải hiểu đúng vị trí insert. Một số middleware chỉ cần cho main agent, không cần cho sub-agents — nhưng hiện tại phải dùng if/else trong `_build_gp_middleware()`.

**Đề xuất:** Chuyển sang **composable middleware profiles**:

```python
# Thay vì list ordering:
MAIN_AGENT_PROFILE = MiddlewareProfile(
    pre_model=[
        PromptCachingMiddleware,
        PatchToolCallsMiddleware,
        KnowledgeSearchMiddleware,
        MemoryInjectionMiddleware,
    ],
    post_model=[
        SourceAttributionMiddleware,
        ParallelismTelemetryMiddleware,
    ],
    wrap_model=[
        ProviderRateLimitMiddleware,
        SummarizationMiddleware,
    ],
    orchestration=[
        ParallelSpawnDirectiveMiddleware,  # main-only
    ],
)

SUB_AGENT_PROFILE = MiddlewareProfile(
    pre_model=[PromptCachingMiddleware, PatchToolCallsMiddleware, KnowledgeSearchMiddleware],
    post_model=[SourceAttributionMiddleware],
    wrap_model=[SubAgentResilienceMiddleware],
)
```

**Lợi ích:** Declarative, dễ hiểu, dễ test từng profile. Type-safe (IDEs hiểu middleware thuộc phase nào).
**Trade-off:** Refactor cost. Nhưng đây là foundation cho mọi agent behavior — worth investing.
**Effort:** 1 tuần.

---

### S-3: ConnectorService Decomposition (Strategy Pattern)

**Vấn đề:** `ConnectorService` — 2942 LOC, single class xử lý 30+ connector types. Thêm connector mới = thêm if/else vào monolith.

**Đề xuất:** Strategy Pattern — mỗi connector type là 1 class implement `ConnectorStrategy` interface:

```python
class ConnectorStrategy(Protocol):
    async def connect(self, config: ConnectorConfig) -> Connection: ...
    async def fetch_data(self, connection: Connection, params: FetchParams) -> list[Document]: ...
    async def disconnect(self, connection: Connection) -> None: ...
    def get_searchable_type(self) -> str: ...  # Fix DRIFT mà ko cần manual mapping

class GoogleDriveStrategy(ConnectorStrategy): ...
class SlackStrategy(ConnectorStrategy): ...
class DexScreenerStrategy(ConnectorStrategy): ...

# Registry auto-discovers strategies
CONNECTOR_STRATEGIES: dict[str, type[ConnectorStrategy]] = {
    cls.connector_type: cls
    for cls in ConnectorStrategy.__subclasses__()
}
```

**Killer feature:** `get_searchable_type()` method trên mỗi strategy → **eliminates** `_CONNECTOR_TYPE_TO_SEARCHABLE` manual mapping. Bug class từ DexScreener incident sẽ không bao giờ xảy ra nữa.
**Effort:** 1.5 tuần (incremental, 1 connector tại 1 thời điểm).

---

### S-4: Structured Output cho Sub-Agent Responses

**Vấn đề:** Sub-agents trả về free-text markdown → main agent phải parse/understand text để synthesis. Token-expensive, error-prone (main agent đôi khi hallucinate data từ sub-agent output).

**Đề xuất:** Sub-agents trả về **structured JSON** thay vì markdown:

```python
class CryptoAnalysisResult(TypedDict):
    agent_name: str
    status: Literal["success", "partial", "failed"]
    facts: list[DataFact]       # machine-readable facts
    narrative: str              # 2-3 sentence summary
    confidence: float           # 0-1
    sources: list[SourceRef]    # citation references

class DataFact(TypedDict):
    metric: str                 # "tvl_usd", "price_usd", "risk_level"
    value: Any
    unit: str
    source: str                 # "defillama", "coingecko"
    timestamp: str              # ISO 8601
```

**Lợi ích:**
- Main agent synthesis chỉ cần read `facts[]` → giảm 40-60% synthesis prompt tokens
- Citation generation trở thành deterministic (mỗi fact có source + value)
- Dễ detect conflicts (2 agents report different TVL values)
- FE có thể render structured data trực tiếp (tables, charts) mà không cần LLM formatting

**Trade-off:** Sub-agent output prompts cần thêm JSON schema instruction. Nhưng narration_templates.py đã extract facts → pattern đã proven.
**Effort:** 1 tuần.

---

### S-5: Consolidate Real-time Sync Stack

**Vấn đề:** Dual-stack (Zero + ElectricSQL/PGlite) tăng bundle size, maintenance burden, và developer confusion. 2 cách đọc data = 2 caching strategies = inconsistency potential.

**Đề xuất:** Evaluate consolidation:

**Option A — All-in on Zero:**
- Zero đã handle multiplayer sync, auth, và real-time updates
- PGlite/Drizzle chỉ cần cho offline — nhưng Zero có offline support đang improve
- Remove ElectricSQL deps, dùng Zero cho mọi thứ

**Option B — All-in on ElectricSQL:**
- ElectricSQL mới hơn, local-first strong, nhưng multiplayer sync yếu hơn Zero

**Recommendation:** Option A (consolidate trên Zero) vì:
- Zero đã là primary sync cho critical features (messages, comments, connectors, documents)
- ElectricSQL chỉ dùng cho PGlite offline queries — ít critical hơn
- Giảm 3 packages + simplify provider tree

**Phải verify:** Zero offline support đủ cho use case hiện tại không? Nếu không, giữ PGlite cho offline nhưng remove `@electric-sql/client` và `@electric-sql/react` (chỉ giữ `@electric-sql/pglite`).
**Effort:** 1 tuần evaluation + 1 tuần migration.

---

## Tier 3: Transformational (1+ tháng, high impact)

### T-1: Agent Observability Platform

**Vấn đề:** Debugging multi-agent systems rất khó. Khi 7 sub-agents chạy song song, biết agent nào slow/fail/hallucinate cần dig through logs.

**Đề xuất:** Tích hợp **LangSmith** hoặc **Langfuse** (open-source) cho:
- Per-agent trace visualization (latency, tokens, tool calls)
- Cost attribution per sub-agent per request
- Prompt versioning + A/B testing
- Automatic quality scoring (detect hallucination, incomplete analysis)

```python
# Trong mỗi middleware:
with langfuse.trace(name="tokenomics_analyst", metadata={"query": q}):
    result = await handler(request)
    langfuse.score(name="completeness", value=len(result.facts)/expected_facts)
```

**Lợi ích:** Visibility → optimization. Biết chính xác agent nào tốn nhiều token nhất, API nào slow nhất, prompt nào cần tune.
**Effort:** 1-2 tuần integration + ongoing tuning.

---

### T-2: Modular Monolith Architecture

**Vấn đề:** Backend hiện tại là flat-structure monolith — `routes/`, `services/`, `tasks/` ở cùng level, không có domain boundaries. 50 route files, 30+ services, mọi thứ import mọi thứ.

**Đề xuất:** Chuyển sang **modular monolith** với DDD-inspired boundaries:

```
nowing_backend/app/
├── modules/
│   ├── auth/
│   │   ├── routes.py
│   │   ├── services.py
│   │   ├── models.py
│   │   └── events.py        # domain events
│   ├── chat/
│   │   ├── routes.py
│   │   ├── services/
│   │   │   ├── streaming.py
│   │   │   └── session.py
│   │   ├── models.py
│   │   └── agents/           # agent code lives WITH its domain
│   │       ├── deepagent.py
│   │       ├── middleware/
│   │       ├── subagents/
│   │       └── tools/
│   ├── connectors/
│   │   ├── routes.py         # 1 file thay vì 15 *_add_connector_route.py
│   │   ├── strategies/       # per-connector-type
│   │   ├── models.py
│   │   └── tasks/            # indexing tasks
│   ├── documents/
│   │   ├── routes.py
│   │   ├── services.py
│   │   ├── models.py
│   │   └── tasks/            # processing tasks
│   ├── subscription/
│   │   ├── routes.py
│   │   ├── services.py
│   │   ├── models.py
│   │   └── stripe_webhooks.py
│   └── notifications/
│       ├── routes.py
│       ├── services.py
│       └── models.py
├── shared/
│   ├── db.py                 # Base, engine, session factory only
│   ├── config.py
│   ├── auth_deps.py          # shared auth dependencies
│   └── events.py             # event bus
└── main.py                   # app factory, mount module routers
```

**Module Rules:**
1. Modules communicate qua **events** hoặc **public interfaces** — không import internal services của module khác
2. Mỗi module có riêng models, routes, services
3. Shared code chỉ ở `shared/` — db engine, config, auth deps

**Lợi ích:**
- Clear domain boundaries → dễ onboard dev mới ("bạn work trên module connectors")
- Prep cho microservice extraction nếu cần scale riêng (chat module scale riêng connector module)
- Import cycle impossible (modules không import nhau trực tiếp)

**Trade-off:** Lớn — cần migration plan, feature flags, incremental move.
**Effort:** 2-3 tháng incremental. Bắt đầu với module nhỏ nhất (notifications), learn patterns, rồi move lớn hơn.

---

### T-3: RAG Pipeline v2 — Hybrid Search + Reranking

**Vấn đề:** RAG hiện tại dùng pgvector similarity search thuần túy. Không có reranking, không có hybrid (BM25 + vector), document chunking strategy cố định.

**Đề xuất:**
1. **Hybrid Search**: pgvector similarity + pg_trgm BM25 → combined score (RRF fusion)
2. **Reranking**: Cohere Rerank hoặc cross-encoder model cho top-k results
3. **Adaptive Chunking**: chunk by semantic boundaries (paragraph, section) thay vì fixed token count
4. **Query Decomposition**: Complex queries → sub-queries → parallel search → merge results

```python
# Hybrid search pipeline
async def hybrid_search(query: str, search_space_id: int, top_k: int = 20):
    vector_results = await pgvector_search(query, search_space_id, top_k * 2)
    bm25_results = await bm25_search(query, search_space_id, top_k * 2)
    fused = reciprocal_rank_fusion(vector_results, bm25_results)
    reranked = await rerank(query, fused[:top_k * 2])
    return reranked[:top_k]
```

**Lợi ích:** Recall tăng 20-40% (hybrid), precision tăng 15-25% (reranking). Đặc biệt quan trọng cho crypto data (specific numbers, ticker symbols mà pure vector search miss).
**Effort:** 2-3 tuần.

---

### T-4: Frontend — React Compiler + RSC Streaming

**Vấn đề:** `markdown-text.tsx` (499 LOC) dùng manual `memo()`, `memoizeMarkdownComponents`. 25+ atom modules with manual subscription management.

**Đề xuất:**
1. **React Compiler (React Forget)**: Bật auto-memoization → remove manual `memo()`, `useMemo()`, `useCallback()`. React 19 Compiler tự optimize re-renders.
2. **RSC for Chat History**: Chat messages đã rendered (non-streaming) → Server Components. Chỉ active streaming message cần Client Component. Giảm client bundle và hydration cost.
3. **Streaming với RSC**: Dùng React `<Suspense>` boundaries cho progressive loading thay vì SSE manual parsing cho initial load.

**Trade-off:** React Compiler vẫn experimental — cần test kỹ. RSC cho chat cần architectural change (message list split server/client).
**Effort:** 2-4 tuần.

---

## Priority Matrix

| ID | Category | Impact | Effort | Risk | Recommended Order |
|----|----------|--------|--------|------|-------------------|
| QW-1 | Agent | HIGH | 1d | ZERO | 1st — immediate |
| QW-2 | Data | HIGH | 2d | ZERO | 1st — immediate |
| QW-3 | Agent | MEDIUM | 0.5d | ZERO | 1st — immediate |
| S-4 | Agent/Cost | HIGH | 1w | LOW | 2nd — structured outputs reduce cost |
| S-1 | Agent | HIGH | 2w | LOW | 3rd — MCP standardization |
| S-2 | Agent | MEDIUM | 1w | MEDIUM | 4th — after S-1 |
| S-3 | Data | HIGH | 1.5w | LOW | 5th — eliminates bug class |
| S-5 | Frontend | MEDIUM | 2w | MEDIUM | 6th — needs evaluation |
| T-1 | Agent | HIGH | 2w | LOW | 7th — observability unlocks everything |
| T-3 | Data | HIGH | 3w | MEDIUM | 8th — RAG quality leap |
| T-4 | Frontend | MEDIUM | 4w | MEDIUM | 9th — performance polish |
| T-2 | Infra | TRANSFORMATIONAL | 3mo | HIGH | 10th — long-term foundation |

---

## ROI Summary

| Tier | Total Effort | Expected Outcome |
|------|-------------|------------------|
| **Quick Wins** | 3.5 days | God files eliminated, cognitive load -50% |
| **Strategic** | 6-7 weeks | LLM cost -40%, tool standardization, bug class elimination, sync simplification |
| **Transformational** | 3-4 months | Modular architecture, RAG quality leap, full observability |

**Recommended next step:** Ship QW-1 + QW-2 + QW-3 trong sprint này (3.5 ngày), sau đó start S-4 (structured outputs) vì nó có ROI cao nhất — giảm LLM cost 40-60% cho synthesis phase.
