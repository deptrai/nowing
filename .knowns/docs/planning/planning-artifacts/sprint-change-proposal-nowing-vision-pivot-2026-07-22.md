---
title: Sprint Change Proposal — Nowing Vision Pivot (2026-07-22)
description: ''
createdAt: '2026-07-28T12:47:48.116Z'
updatedAt: '2026-07-28T15:17:33.263Z'
tags:
  - bmad
  - bmad-source-bmad-output-planning-artifacts-sprint-change-proposal-2026-07-22-vision-pivot-md
---

# Sprint Change Proposal — Nowing Vision Pivot (2026-07-22)

**Workflow:** `bmad-correct-course`  
**Project:** Nowing  
**Date:** 2026-07-22  
**Author:** AI-assisted planning  
**Affected artifacts:**
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md`
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`

---

## 1. Issue Summary

PRD Vision của Nowing vừa được cập nhật từ:

> *Open-source NotebookLM alternative cho AI agents — nền tảng nghiên cứu web mở với live data connectors.*

sang:

> *Open-source long-term research memory cho AI agents và team — bộ lưu trữ dữ liệu nghiên cứu lâu dài với live data connectors và MCP server.*

Đây là **strategic pivot** từ “nền tảng nghiên cứ web / chatbot” sang “bộ nhớ nghiên cứu lâu dài / data layer cho AI agents”. Pivot này ảnh hưởng đến target user, user journeys, functional requirements, epics, architecture, và success metrics.

### Ngữ cảnh phát hiện
- User research cho thấy Claude/ChatGPT/OpenCode thiếu persistent memory, project context bị mất giữa các session, và việc đọc toàn bộ file tốn token rất đắt.
- Các startup memory layer (Mem0 $24M, Cognee $7.5M, Supermemory $2.6M) và hàng loạt open-source MCP memory servers xuất hiện, chứng minh nhu cầu thị trường.
- Nowing đã có đủ building blocks (KB, connectors, MCP, citations, automations) để trở thành long-term research memory, nhưng chưa có memory model và MCP memory tools.

---

## 2. Impact Analysis

### 2.1 Epic / Story Impact

| Epic | Story hiện tại / mới | Ảnh hưởng |
|---|---|---|
| Epic 2: Connectors | Story 2.6 (mới) | Connectors không chỉ là data sources mà còn là memory ingestion sources. Cần khả năng lưu kết quả scrape/search vào long-term memory. |
| Epic 3: Knowledge Base | Story 3.8 (mới) | KB mở rộng thành long-term memory store: facts, decisions, observations, research history. |
| Epic 4: Chat & Agents | Story 4.5, 4.6 (mới) | Agent cần MCP tools để remember/recall/continue research; runtime cần memory retrieval. |
| Epic 6: Automations | Story 6.5 (mới) | Automation cần memory-aware: resume research, update facts, trigger từ memory changes. |
| Epic 8: Platform Operations | Story 8.x (mới, optional) | Có thể cần track token/credit cho memory operations. |

### 2.2 Artifact Impact

| Artifact | Thay đổi |
|---|---|
| `prd.md` | Cập nhật Vision (đã xong), Target User JTBD, Key User Journeys, Glossary, FR cho memory layer, Chat/Agents, Automations; thêm gaps mới về memory model và MCP memory tools. |
| `epics.md` | Thêm stories mới: 2.6, 3.8, 4.5, 4.6, 6.5; cập nhật mục tiêu epic 3/4/6 để reflect memory. |
| `ARCHITECTURE-SPINE.md` | Thêm AD-11 (Long-term memory layer), AD-12 (MCP memory tools); cập nhật capability map. |
| UI/UX specs | Không có artifact hiện tại; cần tạo flows cho memory browser, research timeline, memory correction. |

### 2.3 Technical Impact

- **Data model**: Cần bổ sung bảng `Memory`, `MemoryRelation`, `ResearchThread` (hoặc mở rộng `ChatThread`/`Document`).
- **MCP server**: Cần expose `nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact`.
- **Retrieval**: Mở rộng `app/retriever/` hoặc tạo `app/memory/` để hỗ trợ hybrid search trên memory.
- **Agent runtime**: Main agent cần biết khi nào gọi memory tools; `AgentActionLog` ghi memory mutations.
- **Automations**: `AutomationRun` cần reference `research_thread_id` / `memory_context_id`.
- **Migrations**: Cần Alembic migrations cho memory schema; không ảnh hưởng existing data.

---

## 3. Recommended Approach

**Chọn: Direct Adjustment (bổ sung stories và cập nhật artifacts).**

### Lý do
- Vision pivot không invalidates existing work; nó **mở rộng** scope theo hướng đã có building blocks sẵn.
- Không cần rollback vì code hiện tại vẫn hợp lệ.
- MVP vẫn achievable nếu memory features được đưa vào như post-MVP hoặc MVP bổ sung (tuỳ PM quyết định).

### Effort & Risk
| | Đánh giá |
|---|---|
| **Effort** | Medium — cần data model + MCP tools + agent integration + UI |
| **Risk** | Medium — nếu không thiết kế memory model rõ ràng, dễ trở thành “dump everything into vector DB” |
| **Timeline impact** | +1–2 sprints cho MVP-level memory layer; full vision cần 3–4 sprints |

---

## 4. Detailed Change Proposals

### Change 1 — PRD: Update Target User & JTBD

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Section:** 2.1 Jobs To Be Done

**OLD:**
```
- Nhà nghiên cứu / analyst cần thu thập ý kiến thực từ Reddit, YouTube, TikTok, Google Maps, Amazon…
- AI agent builder cần một surface typed để agent gọi thay vì tự xử lý web.
- Team làm việc cùng nghiên cứu cần workspace chia sẻ, chat real-time, deliverables, và phân quyền.
- Self-hoster muốn nền tảng mở, chạy trên infra riêng với nhiều LLM/embedding model.
```

**NEW:**
```
- Nhà nghiên cứu / analyst cần thu thập ý kiến thực từ Reddit, YouTube, TikTok, Google Maps, Amazon… mà không tự viết scraper, và lưu lại kết quả để research tiếp giữa các phiên.
- AI agent builder cần một surface typed để agent gọi thay vì tự xử lý web; đặc biệt cần persistent memory qua MCP để agent không mất context giữa các session.
- Team làm việc cùng nghiên cứu cần workspace chia sẻ, chat real-time, deliverables, phân quyền, và bộ nhớ dự án chung (project memory) thay vì mỗi người một chat riêng.
- Self-hoster muốn nền tảng mở, chạy trên infra riêng với nhiều LLM/embedding model, và giữ dữ liệu research nội bộ thay vì gửi qua cloud của AI vendor.
```

**Rationale:** Làm rõ lợi ích của long-term memory và MCP cho từng persona.

---

### Change 2 — PRD: Add Key User Journeys for Memory

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Section:** 2.3 Key User Journeys

**ADD after UJ-5:**

#### UJ-6. AI agent builder dùng Nowing như memory layer qua MCP
- Cài `nowing_mcp` vào Claude Code / Cursor / OpenCode.
- Agent gọi `nowing_remember` để lưu fact/decision sau mỗi session.
- Ở session sau, agent gọi `nowing_recall` để truy xuất context mà không cần đọc lại toàn bộ file.

#### UJ-7. Team tiếp tục research đã bắt đầu
- User mở workspace, thấy danh sách “research threads” đang mở.
- Chọn một thread, agent tự động recall các facts/quyết định/citations liên quan.
- Team tiếp tục hỏi, agent trả lời dựa trên memory + internal docs + live data.

**Rationale:** Thể hiện vision “long-term research memory” qua concrete journeys.

---

### Change 3 — PRD: Add Glossary Entries for Memory

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Section:** 3. Glossary

**ADD:**
```
- **Memory** — một fact, decision, observation, hoặc kết quả research được lưu trữ lâu dài trong workspace, có embedding, metadata, và relation đến documents/chats/connector runs.
- **Research Thread** — một dòng nghiên cứu kéo dài nhiều session/chat, có memory context riêng và có thể được continue/resume.
- **Memory Type** — phân loại memory: episodic (sự kiện/session), semantic (fact/knowledge), procedural (quy trình/preference), working (context hiện tại).
- **MCP Memory Tools** — các tool `nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact` expose qua MCP server.
```

**Rationale:** Cần từ vựng chuẩn để downstream artifacts (epics, architecture, code) đồng nhất.

---

### Change 4 — PRD: Add Memory Layer Functional Requirement

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Section:** New subsection under 4.3 Knowledge Base hoặc 4.x mới

**NEW subsection `4.3.x` hoặc `4.9`:**

### 4.x Long-Term Research Memory
**Description:** Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search, relation graph, và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → decay/expire.

#### FR-XX: Memory Storage & Retrieval
Người dùng/agent có thể lưu memory với `content`, `type`, `source` (document, chat, scraper run, manual), `tags`, `confidence`; truy xuất bằng semantic + keyword + relation.

**Consequences:**
- `Memory`, `MemoryRelation`, `ResearchThread` models.
- `app/memory/` hoặc mở rộng `app/retriever/`.
- Endpoint `/memory` và MCP tools `nowing_remember` / `nowing_recall`.

#### FR-XX: Research Continuity
Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó.

**Consequences:**
- `ResearchThread` liên kết với `ChatThread` và `Memory`.
- MCP tool `nowing_continue_research(thread_id)`.

#### FR-XX: Memory Correction
Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history và propagate correction đến relations.

**Consequences:**
- `MemoryVersion` hoặc `MemoryCorrection` model.
- MCP tool `nowing_update_fact`.

**Rationale:** Định nghĩa core functional requirements của memory layer.

---

### Change 5 — PRD: Update Chat & Agents FR to Reference Memory

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Section:** 4.4 Chat & Agents

**Update FR-15:**

#### FR-15: Multi-agent Runtime with Tools
Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); **tự động hoặc theo yêu cầu recall workspace memory để tránh mất context**; dùng `AgentFeatureFlags` để bật/tắt middleware.

**Consequences:**
- `app/agents/chat/multi_agent_chat/`
- `AgentActionLog`, `AgentPermissionRule`, `DocumentRevision`/`FolderRevision` cho audit/revert.
- **Thêm:** memory retrieval integration trong `main_agent` loop.

**Rationale:** Agent runtime phải biết cách dùng memory layer.

---

### Change 6 — PRD: Add Memory-Aware Automation

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Section:** 4.6 Automations

**Update FR-18 / Add new FR:**

#### FR-XX: Memory-Driven Automations
Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu.

**Consequences:**
- Automation trigger type `memory_change`.
- `AutomationRun` reference `research_thread_id`.
- Action `continue_research`.

**Rationale:** Automations là một output channel của memory layer.

---

### Change 7 — PRD: Add New Gaps

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Section:** 5/8/9

**NEW GAP:**
> `[GAP] FR-XX: Long-term memory model chưa tồn tại. Chỉ có `Document`/`Chunk` và `ChatThread`/`ChatMessage`; chưa có `Memory`, `MemoryRelation`, `ResearchThread`.
>
> `[GAP] FR-XX: MCP memory tools (`nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact`) chưa được đăng ký trong `nowing_mcp`.
>
> `[GAP] NFR-XX: Chưa có UI/UX cho memory browser, research timeline, memory correction.

**Rationale:** Ghi rõ những chỗ cần xây dựng để thực hiện vision.

---

### Change 8 — Epics.md: Update Epic 3 Objective

**Artifact:** `epics.md`  
**Section:** Epic 3 header

**OLD:**
> Mục tiêu: Quản lý tài liệu, tìm kiếm, citation, và xử lý các gap về retention, full-editor citation highlight; đánh dấu AI File Sorting removed.

**NEW:**
> Mục tiêu: Quản lý tài liệu, **long-term research memory**, tìm kiếm, citation, và xử lý các gap về retention, full-editor citation highlight; đánh dấu AI File Sorting removed.

**Rationale:** Epic 3 giờ là nơi memory layer sinh sống.

---

### Change 9 — Epics.md: Add Story 3.8 — Long-Term Memory Storage & Retrieval

**Artifact:** `epics.md`  
**Section:** After Story 3.7 or end of Epic 3

**NEW:**

### Story 3.8: Long-Term Research Memory

As a workspace member,
I want to save facts, decisions, and research findings as persistent memory,
So that agents and teammates can recall them in later sessions.

**Acceptance Criteria:**

**Given** user/agent có quyền `memory:create`
**When** POST `/workspaces/{id}/memory` với `content`, `type`, `source`, `tags`, `confidence`
**Then** `Memory` được tạo, chunked/embedded, liên kết với `source` nếu có
**And** memory xuất hiện trong search results khi query liên quan

**Given** user/agent có quyền `memory:read`
**When** GET `/workspaces/{id}/memory/search?query=...` hoặc gọi MCP `nowing_recall`
**Then** kết quả trả về ranked list of memories với metadata, confidence, và source citations

**Rationale:** Core story cho memory layer.

---

### Change 10 — Epics.md: Add Story 4.5 — Agent Memory Tools (MCP)

**Artifact:** `epics.md`  
**Section:** Epic 4, after Story 4.4

**NEW:**

### Story 4.5: Agent Memory Tools via MCP

As an AI agent builder,
I want Claude/Cursor/OpenCode to remember and recall workspace context through Nowing MCP tools,
So that agents don’t lose context between sessions.

**Acceptance Criteria:**

**Given** MCP server configured with `nowing_mcp`
**When** agent gọi `nowing_remember(content=..., type=...)`
**Then** memory được lưu vào active workspace

**When** agent gọi `nowing_recall(query=..., limit=...)`
**Then** server trả về relevant memories dưới dạng compact context

**When** agent gọi `nowing_update_fact(memory_id=..., corrected_content=...)`
**Then** memory được update, old version được giữ lại trong history

**Rationale:** Tận dụng MCP server để distribute memory đến mọi agent client.

---

### Change 11 — Epics.md: Add Story 4.6 — Research Continuity

**Artifact:** `epics.md`  
**Section:** Epic 4, after Story 4.5

**NEW:**

### Story 4.6: Research Continuity

As a research team member,
I want to continue a previous research thread with full context,
So that long-running research doesn’t restart from scratch.

**Acceptance Criteria:**

**Given** một `ResearchThread` đã có với `chat_thread_id` và `memory_ids`
**When** user/agent gọi `nowing_continue_research(thread_id=...)` hoặc mở thread trong UI
**Then** agent tự động retrieve relevant memories, previous citations, và last state
**And** user có thể hỏi tiếp như thể chưa từng đóng chat

**Rationale:** Thực hiện promise “tiếp tục research” trong vision.

---

### Change 12 — Epics.md: Add Story 6.5 — Memory-Driven Automations

**Artifact:** `epics.md`  
**Section:** Epic 6, after Story 6.4

**NEW:**

### Story 6.5: Memory-Driven Automations

As a workspace owner,
I want automations to trigger when new memory matches a condition or to continue a research thread on schedule,
So that research workflows run continuously without manual prompts.

**Acceptance Criteria:**

**Given** automation có trigger `memory_change` hoặc `research_thread_continue`
**When** một memory mới matching query/tags được tạo **OR** cron schedule đến hạn
**Then** `AutomationRun` khởi chạy với `research_thread_id` và `memory_context`
**And** action `continue_research` hoặc `agent_task` có thể write-back kết quả

**Rationale:** Nối Automations với memory layer.

---

### Change 13 — ARCHITECTURE-SPINE.md: Add AD-11 — Long-Term Memory Layer

**Artifact:** `ARCHITECTURE-SPINE.md`  
**Section:** Invariants & Rules

**NEW:**

### AD-11 — Long-term research memory là first-class persistence layer
- **Binds:** FR-XX (memory), Story 3.8, Story 4.5
- **Prevents:** memory bị lưu dưới dạng ad-hoc notes hoặc dump vào chat context
- **Rule:** `Memory` model lưu `content`, `embedding`, `type`, `source`, `confidence`, `workspace_id`, `created_by_id`. `MemoryRelation` lưu edges giữa memories/documents/chats/scraper runs. Retrieval dùng hybrid (vector + keyword + relation) trong `app/retriever/` hoặc `app/memory/`. Mọi memory mutation ghi `MemoryVersion`.

### AD-12 — MCP server expose memory tools
- **Binds:** FR-29, Story 4.5
- **Prevents:** MCP client phải tự quản lý memory hoặc inject full file context
- **Rule:** `nowing_mcp/mcp_server/features/memory.py` đăng ký `nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact`. Các tool gọi backend `MemoryService` qua `NowingClient`. Kết quả trả về dạng compact string để tiết kiệm context window của agent.

### AD-13 — Research Thread là continuation context
- **Binds:** Story 4.6, Story 6.5
- **Prevents:** mỗi chat là một island, mất lịch sử research
- **Rule:** `ResearchThread` liên kết 1-n `ChatThread` và nhiều `Memory`. Agent loop có thể load `ResearchThread` context trước khi trả lời. `AutomationRun` có thể reference `research_thread_id`.

**Rationale:** Đảm bảo architecture ủng hộ vision memory layer.

---

### Change 14 — ARCHITECTURE-SPINE.md: Update Capability Map

**Artifact:** `ARCHITECTURE-SPINE.md`  
**Section:** Capability → Architecture Map

**ADD rows:**

| Capability / Area | Lives in | Governed by |
|---|---|---|
| Long-term memory storage & retrieval | `nowing_backend/app/memory/` hoặc `app/retriever/`, `app/db.py` (Memory, MemoryRelation, ResearchThread) | AD-2, AD-11 |
| MCP memory tools | `nowing_mcp/mcp_server/features/memory.py` | AD-7, AD-12 |
| Research continuity | `nowing_backend/app/agents/chat/multi_agent_chat/` | AD-4, AD-13 |

**Rationale:** Capability map phải reflect memory layer.

---

## 5. Implementation Handoff

### Phạm vi thay đổi
- **PRD update** — Minor/Medium: text changes, thêm sections.
- **Epics update** — Medium: thêm stories mới, cập nhật epic objectives.
- **Architecture update** — Medium: thêm AD invariants, capability map.
- **Code implementation** — Moderate/Major: new data models, migrations, MCP tools, agent integration, UI.

### Handoff recipients

| Owner | Task | Acceptance |
|---|---|---|
| **PM / Architect** | Phê duyệt Sprint Change Proposal; quyết định MVP scope cho memory layer (tất cả stories hay chỉ Story 3.8 + 4.5). | Có danh sách stories được ưu tiên cho sprint tiếp theo. |
| **Backend / Architect** | Thiết kế `Memory`, `MemoryRelation`, `ResearchThread` schema; viết ADR nếu cần. | Schema review xong; migrations ready. |
| **Backend** | Implement `app/memory/` service + REST endpoints + MCP tools. | Unit/integration tests pass. |
| **Agent Developer** | Integrate memory retrieval vào `main_agent` loop; thêm `nowing_remember`/`nowing_recall` calls. | Agent demo tiếp tục research qua 2 session. |
| **Web / UX** | Thiết kế memory browser, research timeline, memory correction UI. | Mockups hoặc prototype. |
| **QA** | Đối chiếu PRD/epics/architecture với code; viết tests cho memory CRUD, retrieval, MCP tools. | Coverage cho happy path + edge cases. |

### Cách tiếp cận ưu tiên (ponytail)
1. **Đừng xây graph database mới** — dùng PostgreSQL + pgvector đã có.
2. **Dùng `Document`/`Chunk` pattern** nếu memory có thể model như small documents.
3. **MCP tools trước, UI sau** — giá trị cho agent builder nhanh hơn web UI.
4. **Một memory type trước** — bắt đầu với semantic facts, mở rộng episodic/procedural sau.

---

## 6. Change Navigation Checklist Status

| Section | Check-item | Status |
|---|---|---|
| 1.1 Triggering story | PRD Vision pivot | [x] Done |
| 1.2 Core problem | Strategic pivot from NotebookLM alternative to long-term research memory | [x] Done |
| 1.3 Evidence | Market research: Mem0 $24M, Cognee $7.5M, multiple MCP memory repos; Claude/ChatGPT/OpenCode memory complaints | [x] Done |
| 2.1 Current epic | PRD Vision affects all epics; current epics can be extended | [x] Done |
| 2.2 Epic-level changes | Modify Epic 3/4/6 objectives; add new stories 2.6, 3.8, 4.5, 4.6, 6.5 | [x] Done |
| 2.3 Future epics | All epics impacted by memory requirement | [x] Done |
| 2.4 Invalidates future epics? | No epics become obsolete; new stories added | [x] Done |
| 2.5 Priority / order | Epic 3 (memory storage) and Epic 4 (MCP tools) should be prioritized | [x] Done |
| 3.1 PRD conflicts | Vision change requires PRD section updates | [x] Done |
| 3.2 Architecture conflicts | Need memory models and MCP memory tools | [x] Done |
| 3.3 UI/UX conflicts | No UX artifact exists; need new flows | [x] Done |
| 3.4 Other artifacts | README/public docs may need re-alignment later | [x] Done |
| 4.1 Direct Adjustment | Viable — add new stories and update artifacts | [x] Viable |
| 4.2 Rollback | Not viable — no need to revert | [N/A] Not viable |
| 4.3 MVP Review | Viable — can scope memory to core stories for MVP | [x] Viable |
| 4.4 Selected path | Direct Adjustment + scoped MVP | [x] Done |
| 5.1 Issue summary | Documented above | [x] Done |
| 5.2 Epic/artifact impact | Documented above | [x] Done |

---

## 7. Approval

**Approved by:** Luisphan  
**Date:** 2026-07-22  
**Decision:** [x] Approved for implementation  [ ] Needs revision  [ ] Rejected  
**Notes:** Artifact updates (PRD, epics, architecture spine) applied immediately. Code implementation to follow per story priority.

---

*This proposal supersedes or extends previous `sprint-change-proposal-2026-07-22.md` (artifact reality correction). It focuses specifically on the Vision pivot to long-term research memory.*
