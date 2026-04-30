# Architecture Drift Report & Improvement Proposals

**Date:** 2026-04-29
**Auditor:** Winston (System Architect)
**Method:** Source code audit via SymDex (9248 functions), CRG (1192 communities), Serena + Bash scans

---

## Executive Summary

Code đã vượt xa docs ở nhiều vùng — đặc biệt là crypto sub-agent ecosystem, real-time sync stack, và tool registry. Có **7 drifts đáng kể** (3 critical, 4 moderate) và **5 structural concerns** cần address.

---

## Part 1: Architecture Drift — Code vs Docs

### DRIFT-1 (CRITICAL) — Real-time Sync Stack: Doc nói ElectricSQL, code dùng cả hai

**Doc (`architecture-web.md`):** "Local-First Sync với ElectricSQL"
**Thực tế (`package.json`):**
- `@electric-sql/client: ^1.4.0`, `@electric-sql/pglite: ^0.3.14`, `@electric-sql/react: ^1.0.26`
- `@rocicorp/zero: ^0.26.2`

**Evidence:**
- `nowing_web/components/providers/ZeroProvider.tsx` — active
- `nowing_web/hooks/use-zero-document-type-counts.ts` — active
- `nowing_web/app/api/zero/query/route.ts` — active
- Multiple hooks dùng cả Drizzle + Zero: `use-documents.ts`, `use-connectors-sync.ts`, `use-messages-sync.ts`

**Impact:** Doc không mention Rocicorp/Zero chút nào. Developer mới sẽ hiểu sai toàn bộ data sync architecture.

**Recommendation:** Update `architecture-web.md` Section 3 → mô tả dual-stack (ElectricSQL cho PGlite offline, Zero cho real-time multiplayer sync). Clarify migration path nếu đang transition.

---

### DRIFT-2 (CRITICAL) — Crypto Sub-Agent Ecosystem: Vượt xa plan gấp 2x

**Doc (`crypto-subagents-epics.md`):**
- FR1-FR5: 4 tool files, 11 tools
- FR6-FR9: 6 sub-agents
- FR11-FR16: 6 advanced agents (Epic 4, "batch 2")

**Thực tế (source code):**
| Category | Planned | Actual | Delta |
|----------|---------|--------|-------|
| Tool files | 4 | 10+ (`defillama`, `crypto_sentiment`, `crypto_news`, `contract_analysis`, `certik_skynet`, `nansen_smart_money`, `dune_query`, `tokeninsight_rating`, `crypto_realtime`, `chainlens_research`) | +6 files |
| Sub-agent specs | 6 | 8 (`defillama`, `news`, `sentiment`, `smart_contract`, `tokenomics`, `whale_tracker`, `yield_optimizer` + narration_templates) | +2 agents |
| Middleware | basic gp_middleware | `SubAgentResilienceMiddleware`, `ParallelSpawnDirectiveMiddleware`, `_SubAgentTokenUsageTracker`, `_build_gp_middleware()` per-agent factory | Significantly evolved |

**Impact:** `crypto-subagents-epics.md` đã được mark SUPERSEDED nhưng không có doc thay thế mô tả architecture thực tế. Epic 0 + 9 trong `epics.md` chỉ track stories, không mô tả technical architecture.

**Recommendation:** Tạo `architecture-crypto-orchestra.md` mô tả actual implementation: tool registry pattern, sub-agent spec pattern, middleware stack, parallel spawn directive, resilience + retry, narration templates, citation pipeline.

---

### DRIFT-3 (CRITICAL) — Middleware Stack: Doc không đề cập phần lớn middleware

**Doc (`architecture-backend.md`):** Chỉ nhắc chung "DeepAgents framework" + "LangGraph StateGraph"

**Thực tế (chat_deepagent.py:2478 lines):**
```
Middleware stack thực tế:
├── AnthropicPromptCachingMiddleware (langchain_anthropic)
├── PatchToolCallsMiddleware (deepagents)
├── TodoListMiddleware (langchain)
├── create_summarization_middleware (deepagents)
├── KnowledgeSearchMiddleware (custom — app.agents.new_chat.middleware)
├── MemoryInjectionMiddleware (custom)
├── DedupToolCallsMiddleware (custom)
├── NowingFilesystemMiddleware (custom)
├── SubAgentResilienceMiddleware (custom — retry + circuit-like)
├── ParallelSpawnDirectiveMiddleware (custom — orchestrates crypto agents)
├── _SubAgentTokenUsageTracker (custom — cost tracking)
└── _build_gp_middleware() — per-agent middleware factory
```

**Impact:** Không có doc nào mô tả middleware ordering, dependency, hoặc interaction patterns. Thêm middleware mới mà không hiểu ordering sẽ gây bugs khó debug.

**Recommendation:** Document middleware pipeline diagram + ordering constraints trong `architecture-backend.md` hoặc separate doc.

---

### DRIFT-4 (MODERATE) — Frontend State Management: Doc không nhắc Jotai

**Doc (`architecture-web.md`):** Nhắc "Server Actions" cho mutations, ElectricSQL cho sync — không nhắc client state.
**Thực tế:** Jotai (`^2.15.1`) + `jotai-tanstack-query` (`^0.11.0`), 10+ atom directories:
`agent-tools`, `auth`, `chat`, `chat-comments`, `connector-dialog`, `connectors`, `documents`, `editor`, `image-gen-config`, `inbox`

**Recommendation:** Thêm section "Client State Management" vào architecture-web.md, mô tả Jotai atom organization.

---

### DRIFT-5 (MODERATE) — Tool Registry: Evolved far beyond original spec

**Doc:** Đề cập "ToolDefinition với `requires=[]`" cho crypto tools (FR5)
**Thực tế (`registry.py`):** 40+ ToolDefinitions covering:
- Podcast/Video generation
- Report generation
- Image generation
- Web search/scrape
- 30+ connector CRUD tools (Linear, Notion, Google Drive, Dropbox, OneDrive, Calendar, Gmail, Confluence, Jira, Slack)
- Full crypto suite (DeFiLlama, sentiment, news, contract, CertiK, Nansen, Dune, TokenInsight)

**Recommendation:** registry.py cần grouping/organization (hiện tại là flat list). Tách thành registry sections hoặc module registries.

---

### DRIFT-6 (MODERATE) — ORM Layer: Doc nói Drizzle, thực tế dùng cả SQLAlchemy (BE) + Drizzle (FE)

**Doc (`architecture-web.md`):** "ORM Client: Drizzle ORM — Type-safe queries"
**Thực tế:**
- Backend: SQLAlchemy Async (`db.py:2710 lines`, 42 models)
- Frontend: Drizzle (`drizzle.config.ts`, `app/db/schema.ts`) — nhưng chủ yếu cho PGlite local, không phải primary ORM

**Recommendation:** Clarify: Drizzle dùng cho PGlite client-side, SQLAlchemy Async cho server-side PostgreSQL.

---

### DRIFT-7 (MODERATE) — Authentication: Doc nói JWT/OAuth chung, thực tế phức tạp hơn

**Doc:** "Middleware xác thực JWT/OAuth token"
**Thực tế:** fastapi-users with multi-backend auth:
- JWT (primary)
- OAuth2 (Google, etc.)
- Gift code subscription flow (`GiftCode`, `GiftRequest` models in db.py nhưng **không có** `gift_routes.py`)
- Admin-approval subscription flow (model exists, routes missing)

**Recommendation:** Update auth section + document incomplete gift/admin-approval flows.

---

## Part 2: Structural Concerns (Code Quality)

### SC-1 (HIGH) — God Files: 5 files > 2000 lines

| File | Lines | Concern |
|------|-------|---------|
| `routes/search_source_connectors_routes.py` | 3695 | Router + business logic mixed |
| `services/connector_service.py` | 2942 | Single class, 0 top-level functions |
| `db.py` | 2710 | 42 models in 1 file |
| `tasks/chat/stream_new_chat.py` | 2539 | Streaming orchestration monolith |
| `agents/new_chat/chat_deepagent.py` | 2478 | Agent factory + 8 middleware classes + orchestration |

**Recommendation (prioritized):**
1. **chat_deepagent.py** → Extract middleware classes to `middleware/` (5 custom classes = 5 files). Already have 4 middleware files in `middleware/` dir, but 5 more inline.
2. **db.py** → Split into modules: `models/user.py`, `models/chat.py`, `models/connector.py`, `models/subscription.py`, `models/crypto.py`
3. **connector_service.py** → Break ConnectorService class into per-connector-type services

---

### SC-2 (MEDIUM) — Orphaned/Incomplete Features

| Feature | Model/Code Exists | Routes/UI | Status |
|---------|-------------------|-----------|--------|
| Gift Codes | `GiftCode`, `GiftRequest` in db.py | No routes | Dead code or WIP |
| Admin-approval subscription | Models referenced in stories | Partial | Needs completion or cleanup |

---

### SC-3 (MEDIUM) — Dual Real-time Sync Libraries

Both `@electric-sql/*` and `@rocicorp/zero` in `package.json`. Active code uses both. Nếu đang migrate, cần:
- Document migration plan
- Track which features dùng Electric vs Zero
- Set deadline để remove deprecated library

---

### SC-4 (LOW) — Test Coverage Gaps

Crypto sub-agents có narration_templates.py (test-friendly pure functions) nhưng không thấy unit tests cho:
- Tool factories (defillama, certik, nansen, dune, tokeninsight)
- Middleware classes (SubAgentResilienceMiddleware, ParallelSpawnDirective)
- Registry validation (all 40+ tools instantiate without errors)

---

### SC-5 (LOW) — Frontend Component Size

`markdown-text.tsx` (499 lines) handles: markdown preprocessing, citation parsing, LaTeX normalization, image rendering, table rendering, heading slugification, code blocks, chart embedding. Consider splitting citation logic and image components.

---

## Part 3: Improvement Proposals

### Proposal 1: Architecture Doc Refresh (Priority: HIGH)

**Effort:** 1-2 days
**Action:**
1. Update `architecture-web.md`: add Jotai, correct ElectricSQL→dual-stack, add Zero
2. Update `architecture-backend.md`: add middleware pipeline diagram, tool registry overview
3. Create `architecture-crypto-orchestra.md`: document actual crypto sub-agent system
4. Add "Architecture Decisions Log" section — track when/why major decisions were made

### Proposal 2: chat_deepagent.py Decomposition (Priority: HIGH)

**Effort:** 2-3 days
**Action:**
Extract from 2478-line monolith:
- `middleware/resilience.py` — SubAgentResilienceMiddleware
- `middleware/parallel_spawn.py` — ParallelSpawnDirectiveMiddleware  
- `middleware/token_tracker.py` — _SubAgentTokenUsageTracker
- `middleware/degradation.py` — _track_degradation logic
- `orchestration/crypto_directive.py` — _CRYPTO_ANALYSIS_DIRECTIVE, agent ordering

**Expected:** chat_deepagent.py → ~1200 lines (factory + graph setup only)

### Proposal 3: db.py Model Separation (Priority: MEDIUM)

**Effort:** 1-2 days
**Action:**
```
app/models/
├── __init__.py    (re-export all for backwards compat)
├── base.py        (Base, TimestampMixin)
├── user.py        (User, UserProfile, Team)
├── chat.py        (ChatThread, ChatMessage, ChatRun)
├── document.py    (Document, DocumentChunk)
├── connector.py   (Connector, ConnectorConfig)
├── subscription.py (Subscription, GiftCode, GiftRequest)
└── crypto.py      (crypto-specific models if any)
```

### Proposal 4: Tool Registry Organization (Priority: LOW)

**Effort:** 0.5 day
**Action:** Group BUILTIN_TOOLS by category with section comments, or split into `registry_core.py`, `registry_connectors.py`, `registry_crypto.py`.

### Proposal 5: Orphaned Feature Cleanup (Priority: LOW)

**Effort:** 0.5 day
**Action:** Audit GiftCode/GiftRequest — either implement routes or remove models. Document decision in ADR.

---

## Summary Matrix

| ID | Type | Severity | Effort | Impact |
|----|------|----------|--------|--------|
| DRIFT-1 | Doc drift | CRITICAL | 0.5d | Misleads devs on sync stack |
| DRIFT-2 | Doc drift | CRITICAL | 1d | No doc for crypto architecture |
| DRIFT-3 | Doc drift | CRITICAL | 0.5d | Middleware stack undocumented |
| DRIFT-4 | Doc drift | MODERATE | 0.25d | Client state not documented |
| DRIFT-5 | Doc drift | MODERATE | 0.25d | Registry organization needed |
| DRIFT-6 | Doc drift | MODERATE | 0.25d | ORM layer confusion |
| DRIFT-7 | Doc drift | MODERATE | 0.25d | Auth complexity undocumented |
| SC-1 | Code quality | HIGH | 3d | 5 god files > 2000 LOC |
| SC-2 | Dead code | MEDIUM | 0.5d | Orphaned gift feature |
| SC-3 | Tech debt | MEDIUM | TBD | Dual sync libraries |
| SC-4 | Coverage | LOW | 2d | Missing crypto tool tests |
| SC-5 | Code quality | LOW | 0.5d | FE component size |
| P1 | Doc refresh | HIGH | 2d | Bring docs to reality |
| P2 | Decomposition | HIGH | 3d | Reduce cognitive load |
| P3 | Model split | MEDIUM | 2d | Better navigability |
| P4 | Registry org | LOW | 0.5d | Developer ergonomics |
| P5 | Cleanup | LOW | 0.5d | Remove dead code |
