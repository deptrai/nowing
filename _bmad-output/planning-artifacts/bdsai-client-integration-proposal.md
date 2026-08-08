---
title: "Nowing → bdsai.vn: First Vertical Client Integration Proposal"
project: Nowing
client: bdsai.vn
status: approved
version: 1.1
created: 2026-08-08
updated: 2026-08-08
---

# Nowing → bdsai.vn: First Vertical Client Integration Proposal

> bdsai.vn là **vertical client đầu tiên** của Nowing. Tài liệu này là góc nhìn từ Nowing, định nghĩa các thay đổi cần thiết trên nền tảng để hỗ trợ bdsai và các vertical tương lai. **Trạng thái: APPROVED với architectural guardrails.**

---

## 1. Context

- **Client:** `bdsai.vn` — sàn/workspace BĐS Việt Nam.
- **Vertical agent:** `bdsai-listing-assistant`.
- **Client ID:** `bdsai.vn`.
- **Workspace:** bdsai dùng shared workspace (`bdsai-prod`) với service account PAT.
- **Mục tiêu Nowing:** Mở rộng nền tảng thành multi-vertical AI engine; mọi thay đổi cho bdsai phải reusable.

---

## 2. Nowing Changes Required (Approved)

### 2.1 Public `agent-chat` endpoints for service account

Expose workspace-scoped, **generic** endpoints cho mọi vertical client:

```
POST /api/v1/workspaces/{workspace_id}/agent-chat/threads
GET  /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}
POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages
```

- Auth: PAT + workspace membership.
- Sync response Phase 1; SSE Phase 2.
- `client_id` + `agent_id` trong body.
- Thread list query có thể filter by `client_id` để tránh cross-client data leak.

### 2.2 `NewChatRequest` schema extension

```python
class NewChatRequest(BaseModel):
    chat_id: int
    workspace_id: int
    user_query: str
    agent_id: str | None = None          # NEW
    client_id: str | None = None         # NEW
    platform_metadata: dict | None = None # NEW
    mode: str = "balanced"
    disabled_tools: list[str] | None = None
    mentioned_document_ids: list[str] | None = None
```

- `agent_id`: route to Agent Registry.
- `client_id`: tag TokenUsage, Memory, Run (hard filter in RAG).
- `platform_metadata`: forward context (e.g. `listing_context`) into prompt.

### 2.3 Agent Registry (minimum viable — global table)

```python
class AgentConfig(BaseModel):
    __tablename__ = "agent_configs"

    id: str                         # PK, e.g. "bdsai-listing-assistant"
    client_id: str                  # "bdsai.vn"
    name: str                       # Display name
    system_instructions: str        # Domain prompt
    enabled_tools: list[str]        # Tool allowlist
    citations_enabled: bool = True
    is_active: bool = True
    created_at: datetime
```

- **Global table** (not workspace-scoped); same agent config across workspaces.
- **Seed** `bdsai-listing-assistant` as first agent.
- **Admin UI deferred** to Phase 2.

### 2.4 ResearchThread auto-creation/linkage

- `POST /agent-chat/threads` with `agent_id` auto-creates a `ResearchThread`.
- Return `research_thread_id` in thread response.
- All memories extracted from that chat get tagged with `research_thread_id`.

### 2.5 Memory tagging (hard RAG filter)

`Memory` metadata:

```json
{
  "client_id": "bdsai.vn",
  "agent_id": "bdsai-listing-assistant",
  "source": "bdsai",
  "listing_id": "...",
  "broker_id": "...",
  "user_id": "..."
}
```

- **`client_id` is a hard filter** in RAG recall — not soft boost.
- Prevents BĐS memory contaminating HR/e-com/agent-builder contexts.

### 2.6 Cost traceability

`TokenUsage` / `Run` includes:

```json
{
  "external_metadata": {
    "client_id": "bdsai.vn",
    "agent_id": "bdsai-listing-assistant",
    "listing_id": "...",
    "broker_id": "...",
    "user_id": "..."
  }
}
```

- bdsai uses `X-Run-Id` for cost attribution.

---

## 3. Nowing-side Stories (Revised)

| Story | Description | Priority | Epic |
|---|---|---|---|
| **N.1** | Public `agent-chat` endpoints (threads + messages) | P0 | Epic 13 |
| **N.2** | Extend `NewChatRequest` with `agent_id`/`client_id`/`platform_metadata` | P0 | Epic 13 |
| **N.3** | Agent Registry minimal (seed `bdsai-listing-assistant`) | P0 | Epic 13 |
| **N.4** | Use `AgentConfig.system_instructions` in chat prompt | P0 | Epic 13 |
| **N.5** | Auto-create/link `ResearchThread` on chat thread creation | P0 | Epic 13 |
| **N.6** | Tag `Memory` with `client_id`/`agent_id` + hard RAG filter | P1 | Epic 13 |
| **N.7** | Add `external_metadata` to `TokenUsage`/`Run` | P1 | Epic 13 |
| **N.8** | Admin UI for Agent Registry | P2 | Future |

---

## 4. bdsai Responsibilities

- Lưu `nowing_thread_id` + `nowing_research_thread_id`.
- Mask phone raw trước khi gửi.
- Enforce cost cap per user/day.
- Send public listing fields (no PII) to Nowing memory.

---

## 5. Co-Evolution Checkpoints (Revised)

| Checkpoint | Nowing Deliverable | bdsai Deliverable | Go/No-Go |
|---|---|---|---|
| C0 | Contract review + sign-off | Scope lock | **GO** (approved) |
| C1 | `/agent-chat/threads` + `/messages` (N.1, N.2) | `AssistantModule` scaffold + drawer | First E2E message |
| C2 | Agent Registry + prompt (N.3, N.4) | `AiGatewayService` chat client | BĐS domain response |
| C3 | `ResearchThread` linkage (N.5) | `assistant_threads.research_thread_id` | Follow-up memory |
| C4 | Memory tags + hard RAG filter (N.6) | Listing feed pipeline | bdsai listing in recall |
| C5 | Cost attribution (N.7) | Cost cap per user/day | Billing integration |

---

## 6. Guardrails

1. **Generic endpoints:** `/agent-chat/...` for any vertical client, not BDS-specific.
2. **Hard memory isolation:** `client_id` mandatory in RAG recall.
3. **Minimal Agent Registry:** Phase 1 = global seeded table; Admin UI Phase 2.
4. **BDS owns UI:** Nowing never builds BĐS UI.
5. **PII masking at source:** bdsai masks phone raw before sending.
6. **No multi-agent per client Phase 1:** single `bdsai-listing-assistant`.
7. **No streaming Phase 1:** sync response only; SSE Phase 2.

---

## 7. Non-Goals

- bdsai does NOT build its own LLM engine.
- Nowing does NOT build BĐS UI.
- Nowing does NOT become BĐS-only.
- Admin UI Agent Registry, multi-agent orchestration, SSE streaming, custom model per agent — **Phase 2**.

---

## 8. Open Questions (Resolved)

1. ✅ `AgentConfig` lives in a **global DB table** `agent_configs`, seeded for Phase 1.
2. ✅ `POST /agent-chat/threads` auto-creates `ResearchThread` when `agent_id` is present.
3. ✅ `agent_id` not found: fail closed (return 4xx).
4. ✅ `Memory.client_id` is a hard filter for RAG recall.
5. ✅ Prompt iteration co-owned by bdsai PM and Nowing team.

---

## 9. Links

- bdsai co-evolution contract: `/Users/luisphan/Documents/GitHub/bdsai-vn/docs/bdsai/planning/nowing-bdsai-co-evolution-contract.md`
- bdsai AI assistant architecture: `/Users/luisphan/Documents/GitHub/bdsai-vn/docs/bdsai/architecture/ARCHITECTURE-SPINE-ai-assistant.md`
- bdsai product brief: `/Users/luisphan/Documents/GitHub/bdsai-vn/docs/bdsai/planning/product-brief-ai-assistant.md`
