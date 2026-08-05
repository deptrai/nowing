# Sprint Change Proposal — Chat Mode-Aware Latency/Cost Policy

**Ngày:** 2026-08-05
**Người đề xuất:** Agent / Luisphan
**Được kích hoạt bởi:** `bmad-correct-course` (Batch)
**Liên quan:** Epic 4 (Chat & Agents), FR-42, NFR-10, stories 4.8a–4.8g

---

## 1. Issue Summary

`chat/regression` benchmark với document 21-chunk (run 2026-08-05T08-12-02Z) **fail** tất cả mode:

- p95 e2e: **43,165 ms** (threshold 30,000 ms)
- p95 TTFB: **33,286 ms** (threshold 5,000 ms)
- p95 cost/turn: **259,193 micros** (threshold 200,000 micros)
- Per-mode cost vượt ngưỡng: speed 228k (max 50k), balanced 185k (max 100k), auto 463k (max 100k)

Root cause: multi-agent chat **không sử dụng `mode` (speed/balanced/quality/auto)** để giới hạn tool calls, retrieval depth, hay escalation tới `chainlens.research`. Mọi mode đều chạy như deep research:

- `auto` gọi `google_search_scrape` 8 lần, `search_knowledge_base` 7 lần, `task` 7 lần.
- `speed` vẫn gọi `task` 5 lần, `search_knowledge_base` 6 lần.
- `search_knowledge_base` luôn lấy tối đa 12 passages/doc, gây prompt lớn.

Đây là vấn đề **product behavior**, không phải benchmark telemetry hay gate config.

---

## 2. Impact Analysis

### 2.1 Epic Impact

- **Epic 4: Chat & Agents** hiện ở `in-progress` theo `sprint-status.yaml`. Stories 4.8a–4.8g đã xây benchmark & gate, nhưng **chưa có story nào optimize product để pass gate**.
- Cần thêm story `4-8h` (hoặc re-open 4-8b nếu xem như defect) để implement mode policy.
- Không cần epic mới hoặc thay đổi epic scope.

### 2.2 Story Impact

| Story | Status | Impact |
|---|---|---|
| 4.8a NewChatClient telemetry | done | Không đổi |
| 4.8b Chat Regression Suite | done/review | Có thể coi là fail acceptance với large doc → cần story con hoặc defect |
| 4.8c Production query sampler | done | Không đổi |
| 4.8d Chat quality with LLM judge | ready-for-dev | Cần đảm bảo mode policy không làm regress quality |
| 4.8e CI / deploy gate | done | Không đổi |
| 4.8f Benchmark stability | done | Không đổi |
| 4.8g Mode/tier matrix | done | Không đổi |
| **4.8h (mới)** | backlog → ready-for-dev | Mode-aware tool budget & retrieval caps |

### 2.3 Artifact Conflicts

- **PRD §4.4 / FR-42 / NFR-10:** Đã bao hàm benchmark & gate. Không conflict.
- **Architecture AD-4 (Multi-agent chat runtime):** Mode policy là extension của tool registry/permission middleware — phù hợp.
- **Architecture AD-15 (ChainLens = engine):** Mode policy phải giữ `chainlens.research` chỉ dùng khi thực sự cần web/deep research — phù hợp.
- **Architecture AD-8 (Unified credit wallet):** `search_knowledge_base` cần clamp `top_k`/`max_passages` theo mode để giảm cost — phù hợp.
- **UX contract chat benchmark:** Không cần UI mới; chỉ cần gate pass.
- **Knowns spec `specs/2026-08-05/new-chat-mode-aware-latency-cost-policy`:** Đã viết, có thể dùng làm đầu vào cho story.

### 2.4 Technical Impact

- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py`
- `app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/middleware.py`
- `app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py`
- `app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py`
- New middleware: `app/agents/chat/multi_agent_chat/main_agent/middleware/mode_budget_middleware.py`

Không cần migration, không thay đổi API contract `POST /api/v1/new_chat`.

---

## 3. Recommended Approach

**Option 1 — Direct Adjustment (selected):** Thêm story `4-8h` vào Epic 4 để implement mode policy, sau đó chạy lại `chat/regression` để ratify baseline.

**Không chọn Option 2 (rollback):** 4.8b đã đo được, telemetry tốt; vấn đề là agent behavior, không cần rollback benchmark code.

**Không chọn Option 3 (MVP review):** FR-42/NFR-10 vẫn hợp lệ; chỉ cần fix implementation.

Rationale:
- Scope nhỏ, nằm trong Epic 4.
- Không thay đổi MVP.
- Tận dụng `mode` đã có trong API (`speed/balanced/quality/auto`).
- Rủi ro trung bình: thay đổi multi-agent chat tool surface.

---

## 4. Action Plan

1. **Thêm story `4-8h`** vào `epics.md` và `sprint-status.yaml`.
2. **Chạy `bmad-create-story:create`** cho `4-8h`, lấy Knowns spec làm context.
3. **Chạy `bmad-dev-story`** để implement 3 lớp:
   - system prompt per mode,
   - tool availability filtering,
   - tool-call budget middleware,
   - `search_knowledge_base` `top_k`/`max_passages` clamp.
4. **Chạy `chat/regression` large doc** để verify pass gate.
5. **Nếu pass** → ratify `gate.yaml`; **nếu fail** → quay lại dev.

---

## 5. PRD / MVP Impact

- MVP không thay đổi.
- FR-42, NFR-10 vẫn là mục tiêu; story mới là **implementation gap** để đạt được chúng.

---

## 6. Handoff Plan

- **Product Owner / Dev (bạn):** Approve proposal, quyết định story ID (4-8h hoặc 4-8b defect).
- **Developer agent:** Chạy `bmad-create-story` → `bmad-dev-story` → tests.
- **QA/Eval:** Chạy `nowing_evals run chat regression` + `chat/quality` sau implement.

---

## 7. Next Step

Approve this proposal → em sẽ:
1. Update `sprint-status.yaml` và `epics.md`.
2. Chạy `bmad-create-story:create 4-8h`.
